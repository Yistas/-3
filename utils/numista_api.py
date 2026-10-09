# -*- coding: utf-8 -*-

"""
API клиент для Numista v3
Документация: https://api.numista.com/api/v3
"""

import logging
import requests
import urllib.parse
from typing import Optional, Dict

# Отключаем предупреждения о небезопасных соединениях
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NumistaAPI:
    """Клиент для работы с Numista API v3"""
    
    BASE_URL = "https://api.numista.com/api/v3"
    
    def __init__(self, api_key: str):
        """
        Инициализация API клиента
        
        Args:
            api_key: Ваш API ключ (получить на numista.com в настройках)
        """
        self.api_key = api_key
        self.logger = logging.getLogger('CoinCollector.NumistaAPI')
        self.session = requests.Session()
        
        # Отключаем проверку SSL (для решения проблем с сертификатами)
        self.session.verify = False
        
        # Заголовки для запросов
        self.session.headers.update({
            'User-Agent': 'CoinCollector/1.0',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}'
        })
    
    def search_coins(self, query: str, page: int = 1, per_page: int = 10) -> Optional[Dict]:
        """
        Поиск монет по запросу
        
        Args:
            query: поисковый запрос (страна, номинал, год)
            page: номер страницы
            per_page: результатов на странице (макс 50)
        
        Returns:
            Dict с результатами поиска
        """
        try:
            params = {
                'q': query,
                'page': page,
                'per_page': min(per_page, 50),
                'lang': 'ru'
            }
            
            # Логируем запрос
            encoded_query = urllib.parse.quote(query)
            self.logger.debug(f"Запрос к API: {self.BASE_URL}/search?q={encoded_query}")
            
            response = self.session.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self.logger.error("Ошибка авторизации: неверный API ключ")
                return None
            elif response.status_code == 429:
                self.logger.warning("Слишком много запросов, подождите...")
                return None
            else:
                self.logger.error(f"Ошибка поиска: {response.status_code}")
                return None
                
        except requests.exceptions.SSLError as e:
            self.logger.error(f"SSL ошибка: {e}")
            self.logger.info("Попробуйте обновить сертификаты: pip install --upgrade certifi")
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Таймаут соединения с API Numista")
            return None
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Ошибка соединения: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при поиске: {e}")
            return None
    
    def get_coin_by_id(self, coin_id: str) -> Optional[Dict]:
        """
        Получает детальную информацию о монете по ID
        
        Args:
            coin_id: ID монеты в Numista (например, 'pieces/russie-10-roubles-2023')
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/coins/{coin_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Ошибка получения деталей: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            return None
    
    def search_by_country_year(self, country: str, year: int, denomination: str = "") -> Optional[Dict]:
        """Поиск монеты по стране, году и номиналу"""
        query = f"{country} {year}"
        if denomination:
            query += f" {denomination}"
        return self.search_coins(query)
    
    def search_by_catalog_number(self, catalog_number: str) -> Optional[Dict]:
        """Поиск монеты по каталожному номеру"""
        return self.search_coins(catalog_number)
    
    def build_coin_url(self, coin_id: str) -> str:
        """Строит URL для просмотра монеты на сайте"""
        # Убираем префикс 'pieces/' если есть
        if coin_id.startswith('pieces/'):
            coin_id = coin_id[7:]
        return f"https://ru.numista.com/catalogue/pieces{coin_id}.html"
    
    def search_and_get_url(self, country: str, year: int, denomination: str = "") -> Optional[str]:
        """
        Ищет монету и возвращает URL для открытия в браузере
        """
        result = self.search_by_country_year(country, year, denomination)
        
        if result and result.get('data'):
            first_result = result['data'][0]
            coin_id = first_result.get('id')
            if coin_id:
                return self.build_coin_url(coin_id)
        
        return None
    
    def search_by_coin_data(self, coin) -> Optional[str]:
        """
        Ищет монету по данным из БД и возвращает URL
        """
        # Формируем поисковый запрос
        query_parts = []
        
        if coin.country:
            query_parts.append(coin.country.name)
        
        if coin.year:
            query_parts.append(str(coin.year))
        
        if coin.denomination_value:
            query_parts.append(coin.denomination_value)
        
        if coin.currency:
            query_parts.append(coin.currency)
        
        query = " ".join(query_parts)
        
        self.logger.info(f"Поиск в Numista: {query}")
        
        result = self.search_coins(query)
        
        if result and result.get('data'):
            # Сортируем результаты по релевантности
            best_match = None
            best_score = 0
            
            for item in result['data']:
                score = 0
                if coin.year and item.get('year'):
                    if str(coin.year) in str(item['year']):
                        score += 10
                
                if coin.denomination_value and item.get('denomination'):
                    if coin.denomination_value in str(item['denomination']):
                        score += 5
                
                if coin.country and item.get('country'):
                    if coin.country.name.lower() in item['country'].lower():
                        score += 3
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if best_match:
                coin_id = best_match.get('id')
                if coin_id:
                    url = self.build_coin_url(coin_id)
                    self.logger.info(f"Найдена монета: {url}")
                    return url
        
        # Если не нашли, пробуем поискать только по стране и году
        if coin.country and coin.year:
            query2 = f"{coin.country.name} {coin.year}"
            self.logger.info(f"Повторный поиск: {query2}")
            result = self.search_coins(query2)
            if result and result.get('data'):
                first_result = result['data'][0]
                coin_id = first_result.get('id')
                if coin_id:
                    return self.build_coin_url(coin_id)
        
        self.logger.warning(f"Монета не найдена: {query}")
        return None
    
    def get_coin_by_catalog(self, catalog_number: str, country: str = None) -> Optional[str]:
        """
        Ищет монету по каталожному номеру (KM#, Y#, etc.)
        """
        result = self.search_coins(catalog_number)
        
        if result and result.get('data'):
            for item in result['data']:
                if country and item.get('country'):
                    if country.lower() not in item['country'].lower():
                        continue
                
                coin_id = item.get('id')
                if coin_id:
                    return self.build_coin_url(coin_id)
        
        return None
    
    def test_connection(self) -> bool:
        """Проверяет соединение с API"""
        try:
            result = self.search_coins("рубль", per_page=1)
            if result is not None:
                self.logger.info("✅ Соединение с Numista API установлено")
                return True
            else:
                self.logger.error("❌ Не удалось подключиться к Numista API")
                return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка подключения: {e}")
            return False