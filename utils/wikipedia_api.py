#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для загрузки текстовых данных о странах из Wikipedia
"""

import re
import json
import logging
import requests
import urllib3
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Отключаем предупреждения о небезопасных соединениях
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logger = logging.getLogger('CoinCollector.WikipediaAPI')


class WikipediaAPI:
    """
    Класс для работы с Wikipedia API
    Загружает только текстовую информацию о странах
    """
    
    # API endpoints
    WIKIPEDIA_API_URL = "https://ru.wikipedia.org/w/api.php"
    WIKIPEDIA_BASE_URL = "https://ru.wikipedia.org/wiki/"
    
    def __init__(self, cache_dir: str = "cache/wikipedia"):
        """
        Инициализация API
        
        Args:
            cache_dir: Директория для кэширования результатов
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CoinCollector/1.0'
        })
        # Отключаем проверку SSL
        self.session.verify = False
        logger.info(f"WikipediaAPI инициализирован, кэш: {self.cache_dir}")
    
    def _get_cache_path(self, key: str) -> Path:
        """Возвращает путь к файлу кэша"""
        safe_key = re.sub(r'[^\w\-_]', '_', key)
        return self.cache_dir / f"{safe_key}.json"
    
    def _load_from_cache(self, key: str, max_age_hours: int = 168) -> Optional[Dict]:
        """Загружает данные из кэша, если они не устарели"""
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cached_time = datetime.fromisoformat(data['_cached_at'])
            age = datetime.now() - cached_time
            if age.total_seconds() > max_age_hours * 3600:
                logger.debug(f"Кэш для {key} устарел")
                return None
            
            return data['data']
        except Exception:
            return None
    
    def _save_to_cache(self, key: str, data: Dict):
        """Сохраняет данные в кэш"""
        cache_path = self._get_cache_path(key)
        try:
            cache_data = {
                '_cached_at': datetime.now().isoformat(),
                'data': data
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def search_country(self, country_name: str) -> Optional[str]:
        """Ищет страну в Wikipedia и возвращает название страницы"""
        logger.info(f"Поиск страны: {country_name}")
        
        cache_key = f"search_{country_name}"
        cached = self._load_from_cache(cache_key)
        if cached:
            return cached
        
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': country_name,
            'format': 'json',
            'utf8': 1,
            'srlimit': 3
        }
        
        try:
            # Используем verify=False для отключения проверки SSL
            response = self.session.get(self.WIKIPEDIA_API_URL, params=params, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()
            
            if 'query' in data and data['query']['search']:
                title = data['query']['search'][0]['title']
                self._save_to_cache(cache_key, title)
                return title
            return None
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL ошибка при поиске {country_name}: {e}")
            # Пробуем еще раз с отключенной проверкой (уже отключена)
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при поиске {country_name}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка соединения при поиске {country_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при поиске {country_name}: {e}")
            return None
    
    def get_country_info(self, country_name: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Получает текстовую информацию о стране из Wikipedia
        """
        logger.info(f"Получение информации о стране: {country_name}")
        
        if use_cache:
            cached = self._load_from_cache(f"info_{country_name}")
            if cached:
                logger.info(f"Данные загружены из кэша для {country_name}")
                return cached
        
        page_title = self.search_country(country_name)
        if not page_title:
            logger.warning(f"Страница не найдена для: {country_name}")
            return None
        
        try:
            # Получаем HTML страницы
            url = self.WIKIPEDIA_BASE_URL + page_title.replace(' ', '_')
            # Используем verify=False для отключения проверки SSL
            response = self.session.get(url, timeout=10, verify=False)
            response.raise_for_status()
            
            # Парсим HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем информацию
            info = self._parse_infobox(soup)
            
            if info:
                self._save_to_cache(f"info_{country_name}", info)
                logger.info(f"Найдены поля: {list(info.keys())}")
            
            return info
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL ошибка при получении информации о {country_name}: {e}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при получении информации о {country_name}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка соединения при получении информации о {country_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении информации: {e}")
            return None
    
    def _parse_infobox(self, soup: BeautifulSoup) -> Dict:
        """
        Парсит инфобокс из HTML страницы
        """
        info = {}
        
        # Ищем инфобокс
        infobox = soup.find('table', class_='infobox')
        if not infobox:
            logger.debug("Инфобокс не найден")
            return info
        
        # Проходим по всем строкам
        for row in infobox.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            
            if th and td:
                # Получаем текст метки
                label = th.get_text(strip=True).lower()
                
                # Получаем значение
                value = td.get_text(strip=True)
                
                # Очищаем значение от примечаний
                value = re.sub(r'\[\d+\]', '', value)
                value = ' '.join(value.split())
                
                # Столица
                if 'столица' in label:
                    info['capital'] = value
                    logger.debug(f"Найдена столица: {value}")
                
                # Язык
                elif any(word in label for word in ['официальный язык', 'государственный язык', 'языки']):
                    info['languages'] = value
                    logger.debug(f"Найден язык: {value}")
                
                # Форма правления
                elif any(word in label for word in ['форма правления', 'государственный строй']):
                    info['government'] = value
                    logger.debug(f"Найдена форма правления: {value}")
                
                # Территория
                elif 'территория' in label:
                    area = self._parse_number(value)
                    if area:
                        info['area'] = area
                        logger.debug(f"Найдена площадь: {area}")
                
                # Население
                elif 'население' in label:
                    population = self._parse_number(value)
                    if population:
                        info['population'] = population
                        logger.debug(f"Найдено население: {population}")
                
                # Валюта
                elif 'валюта' in label:
                    currency = self._parse_currency(value)
                    if currency:
                        info['currency'] = currency
                        logger.debug(f"Найдена валюта: {currency}")
                
                # Религия
                elif 'религия' in label:
                    info['religion'] = value
                    logger.debug(f"Найдена религия: {value}")
                
                # Код МОК
                elif any(word in label for word in ['код мок', 'ioc', 'код мока']):
                    info['ioc_code'] = value
                    logger.debug(f"Найден код МОК: {value}")
        
        return info
    
    def _parse_number(self, text: str) -> Optional[int]:
        """Парсит число из текста"""
        try:
            # Ищем число (цифры, пробелы, точки, запятые)
            match = re.search(r'([\d\s\.,]+)', text)
            if match:
                # Убираем пробелы и заменяем запятые на точки
                num_str = match.group(1).replace(' ', '').replace(',', '')
                # Берем только цифры до точки
                if '.' in num_str:
                    num_str = num_str.split('.')[0]
                return int(num_str)
        except:
            pass
        return None

    def fetch_country_info(country_name: str) -> Optional[Dict]:
        """Удобная функция для получения информации о стране"""
        api = WikipediaAPI()
        return api.get_country_info(country_name)
    
    def _parse_currency(self, text: str) -> Dict:
        """Парсит информацию о валюте"""
        currency = {'name': None, 'code': None}
        
        # Очищаем текст
        text = re.sub(r'\[\d+\]', '', text)
        text = ' '.join(text.split())
        
        # Ищем код валюты в скобках
        code_match = re.search(r'\(([A-Z]{3})\)', text)
        if code_match:
            currency['code'] = code_match.group(1)
            # Убираем код из названия
            text = text.replace(f"({currency['code']})", "").strip()
        
        # Название валюты
        if text:
            currency['name'] = text
        
        return currency
        
    def get_country_media(self, country_name: str, use_cache: bool = True) -> Dict:
        """Ищет на странице страны файлы флага, герба и карты.
        Возвращает словарь {'flag': url, 'coat': url, 'map': url}
        с прямыми ссылками (для SVG Wikipedia отдаёт PNG-превью)."""
        logger.info(f"Поиск медиа-файлов страны: {country_name}")
        cache_key = f"media_{country_name}"
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached:
                logger.info(f"Медиа для {country_name} взяты из кэша")
                return cached

        page_title = self.search_country(country_name)
        if not page_title:
            return {}

        from utils.map_settings import RUSSIAN_TO_ENGLISH
        eng = RUSSIAN_TO_ENGLISH.get(country_name, country_name).replace(' ', '_')
        eng_low = eng.lower()

        # Список файлов на странице страны
        params = {
            'action': 'query',
            'prop': 'images',
            'titles': page_title,
            'imlimit': 50,
            'format': 'json',
        }
        try:
            response = self.session.get(self.WIKIPEDIA_API_URL, params=params,
                                        timeout=15, verify=False)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов {country_name}: {e}")
            return {}

        image_titles = []
        for page in data.get('query', {}).get('pages', {}).values():
            for im in page.get('images', []):
                image_titles.append(im.get('title', ''))

        flag_title = coat_title = map_title = None
        for title in image_titles:
            name = title.split(':', 1)[1] if ':' in title else title
            low = name.lower().replace(' ', '_')
            # Флаг: Flag_of_Andorra.svg / Flag_of_the_United_States.svg
            if flag_title is None and 'flag' in low and eng_low in low \
                    and 'coat' not in low and 'emblem' not in low:
                flag_title = title
            # Герб: Coat_of_arms_of_... / Emblem_of_... / Seal_of_...
            elif coat_title is None and eng_low in low and \
                    ('coat' in low or 'emblem' in low or 'seal' in low):
                coat_title = title
            # Карта: Location_Andorra_Europe.png / Andorra_location_map.svg
            elif map_title is None and eng_low in low and \
                    ('location' in low or 'orthographic' in low):
                map_title = title

        chosen = {'flag': flag_title, 'coat': coat_title, 'map': map_title}
        titles = [t for t in chosen.values() if t]
        if not titles:
            logger.warning(f"Медиа-файлы не найдены для: {country_name}")
            return {}

        # Прямые ссылки (iiurlwidth даёт PNG-превью даже для SVG)
        params2 = {
            'action': 'query',
            'titles': '|'.join(titles),
            'prop': 'imageinfo',
            'iiprop': 'url',
            'iiurlwidth': 600,
            'format': 'json',
        }
        result = {}
        try:
            response = self.session.get(self.WIKIPEDIA_API_URL, params=params2,
                                        timeout=15, verify=False)
            response.raise_for_status()
            data2 = response.json()
            for page in data2.get('query', {}).get('pages', {}).values():
                title = page.get('title', '')
                info = (page.get('imageinfo') or [{}])[0]
                url = info.get('thumburl') or info.get('url')
                if not url:
                    continue
                if title == flag_title:
                    result['flag'] = url
                elif title == coat_title:
                    result['coat'] = url
                elif title == map_title:
                    result['map'] = url
        except Exception as e:
            logger.error(f"Ошибка получения ссылок на файлы {country_name}: {e}")

        if result:
            self._save_to_cache(cache_key, result)
        logger.info(f"Найдены медиа для {country_name}: {list(result.keys())}")
        return result

    def download_image_bytes(self, url: str) -> Optional[bytes]:
        """Скачивает изображение по прямой ссылке, возвращает байты или None"""
        try:
            response = self.session.get(url, timeout=20, verify=False)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения {url}: {e}")
            return None

