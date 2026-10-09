# utils/moex_api.py

import requests
import logging
import os
import time
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from typing import Optional

# Отключаем предупреждения о небезопасных соединениях
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('CoinCollector.MOEX')

class MOEXAPIClient:
    """Клиент для получения исторических данных с Московской биржи"""
    
    # Только основной URL, альтернативный требует авторизации
    BASE_URL = "https://iss.moex.com/iss/history/engines/currency/markets/selt/securities.xml"
    
    # Добавляем заголовки для имитации браузера
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/xml, text/xml, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
    }
    
    @staticmethod
    def is_weekend(date: datetime) -> bool:
        """Проверяет, является ли дата выходным (суббота или воскресенье)"""
        return date.weekday() >= 5  # 5=Saturday, 6=Sunday
    
    @staticmethod
    def fetch_price_for_date(ticker: str, target_date: datetime, start: int = 0, max_pages: int = 5) -> Optional[float]:
        """
        Запрашивает цену закрытия для указанного тикера на конкретную дату.
        Проверка SSL отключена для работы в корпоративных сетях.
        """
        # Проверяем, не выходной ли день
        if MOEXAPIClient.is_weekend(target_date):
            logger.debug(f"{target_date.strftime('%Y-%m-%d')} - выходной день, пропускаем")
            return None
        
        date_str = target_date.strftime("%Y-%m-%d")
        
        # Настройки прокси (раскомментируйте и укажите свои значения если нужно)
        proxies = None
        # proxies = {
        #     'http': 'http://proxy-server:port',
        #     'https': 'http://proxy-server:port'
        # }
        
        # Переменные окружения для прокси (если установлены)
        if not proxies:
            http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            if http_proxy or https_proxy:
                proxies = {}
                if http_proxy:
                    proxies['http'] = http_proxy
                if https_proxy:
                    proxies['https'] = https_proxy
                    logger.info(f"Используется прокси: {https_proxy}")
        
        # Создаем сессию для повторного использования
        session = requests.Session()
        session.headers.update(MOEXAPIClient.HEADERS)
        session.verify = False  # Отключаем проверку SSL
        
        if proxies:
            session.proxies.update(proxies)
        
        for page in range(max_pages):
            current_start = start + page * 100
            
            params = {
                'date': date_str,
                'iss.meta': 'off',
                'iss.only': 'history',
                'history.columns': 'SECID,CLOSE,BOARDID',
                'start': current_start
            }
            
            timeout = 20 if page >= 4 else 15  # Увеличиваем таймауты
            
            try:
                logger.debug(f"Запрос к MOEX для {ticker} на {date_str} со start={current_start} (страница {page+1})")
                
                response = session.get(
                    MOEXAPIClient.BASE_URL, 
                    params=params, 
                    timeout=timeout
                )
                
                # Проверяем статус ответа
                if response.status_code != 200:
                    logger.error(f"HTTP ошибка {response.status_code} на странице {page+1}")
                    if response.status_code == 401 or response.status_code == 403:
                        logger.error("Требуется авторизация. Возможно, IP заблокирован или требуется VPN.")
                        # Пробуем с другими заголовками
                        session.headers.update({
                            'User-Agent': 'Mozilla/5.0 (compatible; YandexBot/3.0)',
                            'Accept': '*/*'
                        })
                        continue
                    time.sleep(2)  # Пауза перед повтором
                    continue
                
                # Парсим XML
                try:
                    root = ET.fromstring(response.content)
                except ET.ParseError as e:
                    logger.error(f"Ошибка парсинга XML на странице {page+1}: {e}")
                    logger.debug(f"Получен ответ: {response.text[:200]}")
                    continue
                
                # Ищем данные
                rows = root.findall(".//row")
                
                if not rows:
                    logger.debug(f"Нет данных на странице {page+1} (start={current_start})")
                    continue
                
                logger.debug(f"На странице {page+1} найдено {len(rows)} записей")
                
                # Ищем нужный тикер
                for row in rows:
                    attrs = row.attrib
                    secid = attrs.get('SECID')
                    boardid = attrs.get('BOARDID')
                    close = attrs.get('CLOSE')
                    
                    # Проверяем соответствие тикеру и BOARDID
                    if secid == ticker and boardid in ['CNGD', 'CETS'] and close:
                        try:
                            price = float(close)
                            if price > 0:
                                logger.info(f"✅ Найдена цена для {ticker} на {date_str}: {price} (страница {page+1})")
                                return price
                        except (ValueError, TypeError):
                            continue
                
            except requests.exceptions.SSLError as e:
                logger.error(f"SSL ошибка на странице {page+1}: {e}")
                # Пробуем еще раз без проверки SSL (уже отключено, но на всякий случай)
                time.sleep(1)
                continue
                
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут на странице {page+1} (start={current_start})")
                time.sleep(2)
                continue
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ошибка соединения на странице {page+1}: {e}")
                time.sleep(3)
                continue
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка сети на странице {page+1}: {e}")
                time.sleep(2)
                continue
                
            except Exception as e:
                logger.error(f"Неожиданная ошибка на странице {page+1}: {e}")
                continue
            
            # Небольшая задержка между страницами
            time.sleep(0.7)
        
        logger.warning(f"❌ Тикер {ticker} не найден на {date_str} после проверки {max_pages} страниц")
        return None
    
    @staticmethod
    def get_last_business_day() -> datetime:
        """Возвращает дату последнего рабочего дня"""
        today = datetime.now()
        last_day = today - timedelta(days=1)
        
        # Пропускаем выходные
        while MOEXAPIClient.is_weekend(last_day):
            last_day -= timedelta(days=1)
        
        return last_day

# Функция для тестирования соединения
def test_connection():
    """Тестирует соединение с MOEX"""
    session = requests.Session()
    session.verify = False
    
    try:
        logger.info("Тестирование соединения с MOEX...")
        response = session.get("https://iss.moex.com", timeout=10)
        logger.info(f"✅ Основной сайт MOEX: {response.status_code}")
        
        # Тест API
        params = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'iss.meta': 'off',
            'iss.only': 'history',
            'history.columns': 'SECID,CLOSE,BOARDID',
            'start': 0
        }
        response = session.get(MOEXAPIClient.BASE_URL, params=params, timeout=10)
        logger.info(f"✅ API MOEX: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ Соединение с MOEX работает")
            return True
        else:
            logger.error(f"❌ Ошибка API: {response.status_code}")
            return False
            
    except requests.exceptions.SSLError as e:
        logger.error(f"❌ SSL ошибка: {e}")
        return False
    except requests.exceptions.Timeout:
        logger.error("❌ Таймаут соединения")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Ошибка соединения: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка: {e}")
        return False

if __name__ == "__main__":
    # При запуске скрипта напрямую тестируем соединение
    test_connection()