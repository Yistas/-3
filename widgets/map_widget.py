# -*- coding: utf-8 -*-

"""
Виджет для отображения статистической карты мира с возможностью переключения
между режимами "По странам" и "По континентам" и фильтром по векам
"""

import os
import logging
import tempfile
import webbrowser
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Импорт WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                               QLabel, QPushButton, QFrame, QMessageBox,
                               QRadioButton, QButtonGroup, QCheckBox)

import folium

# Путь к GeoJSON файлу с границами стран
COUNTRIES_GEOJSON = Path(__file__).parent.parent / "data" / "world-countries.json"


class MapWidget(QWidget):
    """Виджет для отображения статистической карты"""
    
    # Константы для режимов отображения
    MODE_COUNTRIES = 0  # По странам
    MODE_CONTINENTS = 1  # По континентам
    
    # Цвета для континентов
    CONTINENT_COLORS = {
        "Европа": "#4a6fa5",      # Синий
        "Азия": "#e67e22",         # Оранжевый
        "Америка": "#27ae60",      # Зелёный
        "Африка": "#f1c40f",       # Жёлтый
        "Океания": "#9b59b6",      # Фиолетовый
        "Другие": "#95a5a6"        # Серый
    }
    
    # Века для фильтрации
    CENTURIES = [21, 20, 19, 18, 17, 16, 15]
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.MapWidget')
        self.db_manager = db_manager
        self.last_map_file = None
        self.display_mode = self.MODE_COUNTRIES  # По умолчанию - по странам
        self.selected_centuries = set()  # Пустое множество = все века
        
        # Проверяем наличие GeoJSON файла
        self.geojson_path = COUNTRIES_GEOJSON
        if not self.geojson_path.exists():
            self.logger.warning(f"GeoJSON файл не найден: {self.geojson_path}")
            # Создаём папку data, если её нет
            self.geojson_path.parent.mkdir(exist_ok=True)
            
            # Пытаемся скачать файл
            self.download_geojson()
        
        self.init_ui()
        QTimer.singleShot(100, self.update_map)
    
    def download_geojson(self):
        """Скачивает GeoJSON файл с границами стран"""
        try:
            import requests
            url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(self.geojson_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info("GeoJSON файл успешно скачан")
            else:
                self.logger.error("Не удалось скачать GeoJSON файл")
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании GeoJSON: {e}")
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("🗺️ Статистическая карта мира")
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 14px; 
            padding: 5px; 
            background-color: #4a6fa5; 
            color: white; 
            border-radius: 3px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель управления
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_panel.setStyleSheet("QFrame { background-color: #f5f5f5; border-radius: 3px; padding: 5px; }")
        
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_panel.setLayout(control_layout)
        
        # Первая строка - область и кнопка обновления
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Область:"))
        
        self.area_combo = QComboBox()
        self.area_combo.addItems(["Весь мир", "Европа", "Азия", "Америка", "Африка", "Океания"])
        self.area_combo.currentTextChanged.connect(self.on_area_changed)
        top_row.addWidget(self.area_combo)
        
        top_row.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.update_map)
        top_row.addWidget(self.refresh_btn)
        
        control_layout.addLayout(top_row)
        
        # Вторая строка - переключатель режимов
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Режим:"))
        
        self.mode_group = QButtonGroup(self)
        
        self.country_mode_radio = QRadioButton("🗺️ По странам")
        self.country_mode_radio.setChecked(True)
        self.country_mode_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.country_mode_radio, self.MODE_COUNTRIES)
        mode_row.addWidget(self.country_mode_radio)
        
        self.continent_mode_radio = QRadioButton("🌍 По континентам")
        self.continent_mode_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.continent_mode_radio, self.MODE_CONTINENTS)
        mode_row.addWidget(self.continent_mode_radio)
        
        mode_row.addStretch()
        
        control_layout.addLayout(mode_row)
        
        # Третья строка - фильтр по векам
        century_row = QHBoxLayout()
        century_row.addWidget(QLabel("Века:"))
        
        # Кнопка "Все века"
        self.all_centuries_check = QCheckBox("Все")
        self.all_centuries_check.setChecked(True)
        self.all_centuries_check.toggled.connect(self.on_all_centuries_toggled)
        century_row.addWidget(self.all_centuries_check)
        
        # Чекбоксы для каждого века
        self.century_checks = {}
        for century in self.CENTURIES:
            check = QCheckBox(f"{century} в.")
            check.setChecked(False)
            check.toggled.connect(self.on_century_toggled)
            self.century_checks[century] = check
            century_row.addWidget(check)
        
        century_row.addStretch()
        
        control_layout.addLayout(century_row)
        
        layout.addWidget(control_panel)
        
        # Информационная строка
        self.info_label = QLabel("Загрузка данных...")
        self.info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.info_label)
        
        # Если WebEngine доступен, используем его
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(500)
            
            # Включаем JavaScript
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            
            layout.addWidget(self.web_view)
        else:
            # Если нет WebEngine, показываем кнопку для открытия в браузере
            self.browser_btn = QPushButton("🌍 Открыть карту в браузере")
            self.browser_btn.clicked.connect(self.open_map_in_browser)
            self.browser_btn.setMinimumHeight(40)
            layout.addWidget(self.browser_btn)
    
    def on_area_changed(self, area_name):
        """Обработчик изменения области"""
        self.update_map()
    
    def on_mode_changed(self):
        """Обработчик изменения режима отображения"""
        if self.country_mode_radio.isChecked():
            self.display_mode = self.MODE_COUNTRIES
            self.logger.info("Переключено в режим: По странам")
        else:
            self.display_mode = self.MODE_CONTINENTS
            self.logger.info("Переключено в режим: По континентам")
        self.update_map()
    
    def on_all_centuries_toggled(self, checked):
        """Обработчик переключения чекбокса 'Все века'"""
        if checked:
            # Если выбран "Все", снимаем все остальные чекбоксы
            for check in self.century_checks.values():
                check.setChecked(False)
            self.selected_centuries = set()
        self.update_map()
    
    def on_century_toggled(self):
        """Обработчик переключения чекбокса века"""
        # Собираем выбранные века
        self.selected_centuries = set()
        for century, check in self.century_checks.items():
            if check.isChecked():
                self.selected_centuries.add(century)
        
        # Если есть выбранные века, снимаем чекбокс "Все"
        if self.selected_centuries:
            self.all_centuries_check.setChecked(False)
        else:
            # Если ничего не выбрано, автоматически включаем "Все"
            self.all_centuries_check.setChecked(True)
        
        self.update_map()
    
    def get_century_filter_description(self):
        """Возвращает текстовое описание фильтра по векам"""
        if not self.selected_centuries:
            return "все века"
        
        centuries_list = sorted(list(self.selected_centuries), reverse=True)
        if len(centuries_list) == 1:
            return f"{centuries_list[0]} век"
        else:
            return f"{', '.join(str(c) for c in centuries_list[:-1])} и {centuries_list[-1]} века"
    
    def get_coin_count_for_country(self, country_id):
        """Получает количество монет для страны с учётом фильтра по векам"""
        from database.models import Coin
        from sqlalchemy import or_
        
        query = self.db_manager.session.query(Coin).filter_by(country_id=country_id)
        
        # Применяем фильтр по векам, если выбраны конкретные века
        if self.selected_centuries:
            # Определяем диапазон лет для каждого века
            century_conditions = []
            for century in self.selected_centuries:
                start_year = (century - 1) * 100 + 1
                end_year = century * 100
                century_conditions.append((Coin.year >= start_year) & (Coin.year <= end_year))
            
            # Объединяем условия через OR
            query = query.filter(or_(*century_conditions))
        
        return query.count()
    
    def get_continent_for_country(self, country):
        """Определяет континент для страны (с учётом преемственности)"""
        # Сначала пробуем получить континент из страны
        if country.continent and country.continent in self.CONTINENT_COLORS:
            return country.continent
        
        # Если у страны нет континента, пробуем определить по имени
        name_to_continent = {
            # Европа
            "Россия": "Европа", "Великобритания": "Европа", "Германия": "Европа",
            "Франция": "Европа", "Италия": "Европа", "Испания": "Европа",
            "Швеция": "Европа", "Норвегия": "Европа", "Финляндия": "Европа",
            "Дания": "Европа", "Польша": "Европа", "Чехия": "Европа",
            "Венгрия": "Европа", "Австрия": "Европа", "Швейцария": "Европа",
            "Нидерланды": "Европа", "Бельгия": "Европа", "Португалия": "Европа",
            "Греция": "Европа", "Ирландия": "Европа", "Англия": "Европа",
            "СССР": "Европа", "Российская Империя": "Европа",
            
            # Азия
            "Китай": "Азия", "Япония": "Азия", "Индия": "Азия",
            "Турция": "Азия", "Таиланд": "Азия", "Вьетнам": "Азия",
            "Индонезия": "Азия", "Малайзия": "Азия", "Филиппины": "Азия",
            "Лаос": "Азия", "Камбоджа": "Азия", "Мьянма": "Азия",
            "Шри-Ланка": "Азия", "Непал": "Азия", "Бутан": "Азия",
            "Бангладеш": "Азия", "Пакистан": "Азия", "Афганистан": "Азия",
            "Иран": "Азия", "Ирак": "Азия", "Сирия": "Азия",
            "Ливан": "Азия", "Иордания": "Азия", "Израиль": "Азия",
            "Саудовская Аравия": "Азия", "ОАЭ": "Азия", "Катар": "Азия",
            "Кувейт": "Азия", "Бахрейн": "Азия", "Оман": "Азия",
            "Йемен": "Азия", "Киргизия": "Азия", "Таджикистан": "Азия",
            "Туркмения": "Азия", "Узбекистан": "Азия", "Казахстан": "Азия",
            "Монголия": "Азия", "Северная Корея": "Азия", "Южная Корея": "Азия",
            "Тайвань": "Азия", "Сингапур": "Азия", "Бруней": "Азия",
            
            # Америка
            "США": "Америка", "Канада": "Америка", "Мексика": "Америка",
            "Бразилия": "Америка", "Аргентина": "Америка", "Куба": "Америка",
            "Колумбия": "Америка", "Венесуэла": "Америка", "Перу": "Америка",
            "Чили": "Америка", "Эквадор": "Америка", "Боливия": "Америка",
            "Парагвай": "Америка", "Уругвай": "Америка", "Гайана": "Америка",
            "Суринам": "Америка", "Французская Гвиана": "Америка",
            
            # Африка
            "ЮАР": "Африка", "Египет": "Африка", "Нигерия": "Африка",
            "Марокко": "Африка", "Алжир": "Африка", "Тунис": "Африка",
            "Ливия": "Африка", "Судан": "Африка", "Эфиопия": "Африка",
            "Кения": "Африка", "Танзания": "Африка", "Уганда": "Африка",
            "Гана": "Африка", "Кот-д'Ивуар": "Африка", "Камерун": "Африка",
            "Ангола": "Африка", "Мозамбик": "Африка", "Мадагаскар": "Африка",
            
            # Океания
            "Австралия": "Океания", "Новая Зеландия": "Океания",
            "Папуа - Новая Гвинея": "Океания", "Фиджи": "Океания",
            "Соломоновы Острова": "Океания", "Вануату": "Океания",
            "Самоа": "Океания", "Тонга": "Океания", "Кирибати": "Океания",
            "Микронезия": "Океания", "Маршалловы Острова": "Океания",
            "Палау": "Океания", "Науру": "Океания", "Тувалу": "Океания",
        }
        
        return name_to_continent.get(country.name, "Другие")
    
    def get_country_data_by_countries(self):
        """Собирает данные по странам с учётом фильтра по векам и множественных преемников"""
        from database.models import Coin
        
        countries = self.db_manager.get_all_countries()
        
        # Словарь для данных: ID страны -> количество монет
        raw_country_data = {}
        total_coins = 0
        
        # Собираем монеты по оригинальным странам с учётом фильтра
        for country in countries:
            coin_count = self.get_coin_count_for_country(country.id)
            if coin_count > 0:
                raw_country_data[country.id] = coin_count
                total_coins += coin_count
        
        # Группируем по странам-преемникам для карты (теперь может быть несколько)
        map_country_data = defaultdict(float)
        country_objects = {c.id: c for c in countries}
        
        for country_id, coin_count in raw_country_data.items():
            effective_ids = self.db_manager.get_all_effective_countries_for_map(country_id)
            
            if effective_ids:
                # Распределяем монеты равномерно между всеми преемниками
                coins_per_successor = coin_count / len(effective_ids)
                
                for eff_id in effective_ids:
                    map_country_data[eff_id] += coins_per_successor
            else:
                # Если нет преемников, оставляем как есть
                map_country_data[country_id] += coin_count
        
        # Преобразуем ID обратно в объекты Country
        result_data = {}
        for country_id, coin_count in map_country_data.items():
            country = country_objects.get(country_id)
            if country:
                result_data[country] = coin_count
        
        return result_data, total_coins
    
    def get_country_data_by_continents(self):
        """Собирает данные по континентам с учётом фильтра по векам и множественных преемников"""
        countries = self.db_manager.get_all_countries()
        
        # Словарь для данных: континент -> количество монет
        continent_data = {continent: 0.0 for continent in self.CONTINENT_COLORS.keys()}
        total_coins = 0
        
        # Собираем монеты по странам с учётом фильтра
        country_coin_counts = {}
        for country in countries:
            coin_count = self.get_coin_count_for_country(country.id)
            if coin_count > 0:
                country_coin_counts[country.id] = coin_count
                total_coins += coin_count
        
        # Группируем по континентам (с учётом преемственности)
        country_objects = {c.id: c for c in countries}
        
        for country_id, coin_count in country_coin_counts.items():
            effective_ids = self.db_manager.get_all_effective_countries_for_map(country_id)
            
            if effective_ids:
                # Распределяем монеты между всеми преемниками
                coins_per_successor = coin_count / len(effective_ids)
                
                for eff_id in effective_ids:
                    effective_country = country_objects.get(eff_id)
                    if effective_country:
                        continent = self.get_continent_for_country(effective_country)
                        if continent in continent_data:
                            continent_data[continent] += coins_per_successor
                        else:
                            continent_data["Другие"] += coins_per_successor
            else:
                # Если нет преемников, используем оригинальную страну
                original_country = country_objects.get(country_id)
                if original_country:
                    continent = self.get_continent_for_country(original_country)
                    if continent in continent_data:
                        continent_data[continent] += coin_count
                    else:
                        continent_data["Другие"] += coin_count
        
        # Фильтруем только континенты с монетами
        result_data = {k: v for k, v in continent_data.items() if v > 0}
        
        return result_data, total_coins
    
    def get_country_data(self):
        """Собирает статистику в зависимости от выбранного режима"""
        if self.display_mode == self.MODE_COUNTRIES:
            return self.get_country_data_by_countries()
        else:
            return self.get_country_data_by_continents()
    
    def get_country_code(self, country):
        """Получает код страны для карты"""
        # Сначала пробуем iso2 (двухбуквенный код)
        if country.iso2 and len(country.iso2) == 2:
            # Конвертируем двухбуквенный код в трёхбуквенный для карты
            iso2_to_iso3 = {
                "RU": "RUS", "US": "USA", "GB": "GBR", "DE": "DEU", "FR": "FRA",
                "IT": "ITA", "ES": "ESP", "CN": "CHN", "JP": "JPN", "CA": "CAN",
                "AU": "AUS", "IN": "IND", "BR": "BRA", "MX": "MEX", "AR": "ARG",
                "ZA": "ZAF", "EG": "EGY", "TR": "TUR", "SE": "SWE", "NO": "NOR",
                "FI": "FIN", "DK": "DNK", "PL": "POL", "CZ": "CZE", "HU": "HUN",
                "AT": "AUT", "CH": "CHE", "NL": "NLD", "BE": "BEL", "PT": "PRT",
                "GR": "GRC", "IE": "IRL", "NZ": "NZL", "IL": "ISR", "SA": "SAU",
                "AE": "ARE", "TH": "THA", "VN": "VNM", "MY": "MYS", "ID": "IDN",
                "PH": "PHL", "PK": "PAK", "BD": "BGD", "NG": "NGA", "KE": "KEN",
                "UA": "UKR", "BY": "BLR", "KZ": "KAZ", "GE": "GEO", "AM": "ARM",
                "AZ": "AZE", "MD": "MDA", "LV": "LVA", "LT": "LTU", "EE": "EST",
                "RO": "ROU", "BG": "BGR", "RS": "SRB", "HR": "HRV", "SI": "SVN",
                "SK": "SVK", "BA": "BIH", "MK": "MKD", "AL": "ALB", "ME": "MNE",
                "CY": "CYP", "MT": "MLT", "IS": "ISL", "LU": "LUX", "LI": "LIE",
                "MC": "MCO", "AD": "AND", "SM": "SMR", "VA": "VAT", "CU": "CUB",
                "DO": "DOM", "PR": "PRI", "JM": "JAM", "HT": "HTI", "BS": "BHS",
                "BB": "BRB", "TT": "TTO", "GY": "GUY", "SR": "SUR", "CO": "COL",
                "VE": "VEN", "EC": "ECU", "PE": "PER", "BO": "BOL", "CL": "CHL",
                "PY": "PRY", "UY": "URY", "CR": "CRI", "NI": "NIC", "HN": "HND",
                "SV": "SLV", "GT": "GTM", "BZ": "BLZ", "PA": "PAN", "AW": "ABW",
                "CW": "CUW", "SX": "SXM", "MF": "MAF", "SU": "SUN",  # СССР
                "LA": "LAO",  # Лаос
                "KH": "KHM",  # Камбоджа
                "MM": "MMR",  # Мьянма
                "LK": "LKA",  # Шри-Ланка
                "NP": "NPL",  # Непал
                "BT": "BTN",  # Бутан
                "AF": "AFG",  # Афганистан
                "IR": "IRN",  # Иран
                "IQ": "IRQ",  # Ирак
                "SY": "SYR",  # Сирия
                "LB": "LBN",  # Ливан
                "JO": "JOR",  # Иордания
                "PS": "PSE",  # Палестина
                "KW": "KWT",  # Кувейт
                "QA": "QAT",  # Катар
                "BH": "BHR",  # Бахрейн
                "OM": "OMN",  # Оман
                "YE": "YEM",  # Йемен
                "KG": "KGZ",  # Киргизия
                "TJ": "TJK",  # Таджикистан
                "TM": "TKM",  # Туркмения
                "UZ": "UZB",  # Узбекистан
                "MN": "MNG",  # Монголия
                "KP": "PRK",  # Северная Корея
                "KR": "KOR",  # Южная Корея
                "TW": "TWN",  # Тайвань
                "SG": "SGP",  # Сингапур
                "BN": "BRN",  # Бруней
                "TL": "TLS",  # Восточный Тимор
            }
            return iso2_to_iso3.get(country.iso2)
        
        # Пробуем iso3 (трёхбуквенный код)
        if country.iso3 and len(country.iso3) == 3:
            return country.iso3
        
        # Если нет кодов, используем словарь по названиям
        name_to_code = {
            "Россия": "RUS", "США": "USA", "Великобритания": "GBR",
            "Германия": "DEU", "Франция": "FRA", "Италия": "ITA",
            "Испания": "ESP", "Китай": "CHN", "Япония": "JPN",
            "Канада": "CAN", "Австралия": "AUS", "Индия": "IND",
            "Бразилия": "BRA", "Мексика": "MEX", "Аргентина": "ARG",
            "ЮАР": "ZAF", "Египет": "EGY", "Турция": "TUR",
            "Швеция": "SWE", "Норвегия": "NOR", "Финляндия": "FIN",
            "Дания": "DNK", "Польша": "POL", "Чехия": "CZE",
            "Венгрия": "HUN", "Австрия": "AUT", "Швейцария": "CHE",
            "Нидерланды": "NLD", "Бельгия": "BEL", "Португалия": "PRT",
            "Греция": "GRC", "Ирландия": "IRL", "Новая Зеландия": "NZL",
            "СССР": "RUS", "Российская Империя": "RUS", "Англия": "GBR",
            "Нидерландские Антильские острова": "ANT",
            "Израиль": "ISR", "Саудовская Аравия": "SAU", "ОАЭ": "ARE",
            "Таиланд": "THA", "Вьетнам": "VNM", "Малайзия": "MYS",
            "Индонезия": "IDN", "Филиппины": "PHL", "Пакистан": "PAK",
            "Бангладеш": "BGD", "Нигерия": "NGA", "Кения": "KEN",
            "Украина": "UKR", "Беларусь": "BLR", "Казахстан": "KAZ",
            "Грузия": "GEO", "Армения": "ARM", "Азербайджан": "AZE",
            "Молдова": "MDA", "Латвия": "LVA", "Литва": "LTU",
            "Эстония": "EST", "Румыния": "ROU", "Болгария": "BGR",
            "Сербия": "SRB", "Хорватия": "HRV", "Словения": "SVN",
            "Словакия": "SVK", "Босния и Герцеговина": "BIH",
            "Македония": "MKD", "Албания": "ALB", "Черногория": "MNE",
            "Кипр": "CYP", "Мальта": "MLT", "Исландия": "ISL",
            "Люксембург": "LUX", "Лихтенштейн": "LIE", "Монако": "MCO",
            "Андорра": "AND", "Сан-Марино": "SMR", "Ватикан": "VAT",
            "Куба": "CUB", "Доминикана": "DOM", "Пуэрто-Рико": "PRI",
            "Ямайка": "JAM", "Гаити": "HTI", "Багамы": "BHS",
            "Барбадос": "BRB", "Тринидад и Тобаго": "TTO", "Гайана": "GUY",
            "Суринам": "SUR", "Колумбия": "COL", "Венесуэла": "VEN",
            "Эквадор": "ECU", "Перу": "PER", "Боливия": "BOL",
            "Чили": "CHL", "Парагвай": "PRY", "Уругвай": "URY",
            "Коста-Рика": "CRI", "Никарагуа": "NIC", "Гондурас": "HND",
            "Сальвадор": "SLV", "Гватемала": "GTM", "Белиз": "BLZ",
            "Панама": "PAN", "Аруба": "ABW", "Кюрасао": "CUW",
            "Синт-Мартен": "SXM", "Сен-Мартен": "MAF",
            # Добавленные страны
            "Лаос": "LAO",
            "Камбоджа": "KHM",
            "Мьянма": "MMR",
            "Шри-Ланка": "LKA",
            "Непал": "NPL",
            "Бутан": "BTN",
            "Афганистан": "AFG",
            "Иран": "IRN",
            "Ирак": "IRQ",
            "Сирия": "SYR",
            "Ливан": "LBN",
            "Иордания": "JOR",
            "Палестина": "PSE",
            "Кувейт": "KWT",
            "Катар": "QAT",
            "Бахрейн": "BHR",
            "Оман": "OMN",
            "Йемен": "YEM",
            "Киргизия": "KGZ",
            "Таджикистан": "TJK",
            "Туркмения": "TKM",
            "Узбекистан": "UZB",
            "Монголия": "MNG",
            "Северная Корея": "PRK",
            "Южная Корея": "KOR",
            "Тайвань": "TWN",
            "Сингапур": "SGP",
            "Бруней": "BRN",
            "Восточный Тимор": "TLS",
        }
        return name_to_code.get(country.name)
    
    def create_map(self):
        """Создаёт карту с данными"""
        area = self.area_combo.currentText()
        
        if area == "Весь мир":
            m = folium.Map(location=[20, 0], zoom_start=2, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        elif area == "Европа":
            m = folium.Map(location=[50, 10], zoom_start=4, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        elif area == "Азия":
            m = folium.Map(location=[30, 100], zoom_start=3, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        elif area == "Америка":
            m = folium.Map(location=[20, -80], zoom_start=3, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        elif area == "Африка":
            m = folium.Map(location=[0, 20], zoom_start=3, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        elif area == "Океания":
            m = folium.Map(location=[-20, 140], zoom_start=3, 
                          tiles='CartoDB positron', 
                          control_scale=True)
        
        return m
    
    def add_country_data_to_map(self, m, country_data, total_coins):
        """Добавляет данные по странам на карту с заливкой от белого до зелёного"""
        if self.geojson_path.exists():
            try:
                choropleth_data = {}
                countries_with_codes = 0
                countries_without_codes = []
                
                # Находим максимальное количество монет для нормализации
                max_coins = max(country_data.values()) if country_data else 1
                
                for country, count in country_data.items():
                    code = self.get_country_code(country)
                    if code:
                        choropleth_data[code] = count
                        countries_with_codes += 1
                    else:
                        countries_without_codes.append(country.name)
                
                if countries_without_codes:
                    self.logger.warning(f"Страны без кодов: {', '.join(countries_without_codes[:5])}")
                
                if choropleth_data:
                    # Создаем кастомную цветовую шкалу от белого до темно-зеленого
                    # Используем колорбар YlGn (желто-зеленый) но настроим его
                    
                    # Добавляем хороплет с зеленой цветовой схемой
                    folium.Choropleth(
                        geo_data=str(self.geojson_path),
                        name='choropleth',
                        data=choropleth_data,
                        key_on='feature.id',
                        fill_color='YlGn',  # Желто-зеленая схема (от светлого к темному)
                        fill_opacity=0.7,
                        line_opacity=0.2,
                        legend_name='Количество монет',
                        smooth_factor=1.0,
                        highlight=True,
                        nan_fill_color='white',  # Страны без данных - белые
                        nan_fill_opacity=0.3
                    ).add_to(m)
                    
                    # Добавляем границы стран
                    style_function = lambda x: {
                        'fillColor': '#ffffff',
                        'color': '#000000',
                        'fillOpacity': 0.0,
                        'weight': 0.5
                    }
                    
                    folium.GeoJson(
                        str(self.geojson_path),
                        style_function=style_function,
                        name='countries',
                        tooltip=folium.GeoJsonTooltip(
                            fields=['name'],
                            aliases=['Страна:'],
                            localize=True,
                            sticky=False,
                            labels=True
                        )
                    ).add_to(m)
                    
                    filter_text = self.get_century_filter_description()
                    mode_text = "По странам"
                    
                    # Показываем информацию о распределении
                    distribution_info = ""
                    if len(choropleth_data) > countries_with_codes:
                        distribution_info = f" | Распределено между {len(choropleth_data)} странами"
                    
                    self.info_label.setText(
                        f"✅ {mode_text} | {filter_text} | Монет: {total_coins:.1f} | "
                        f"Макс: {max_coins:.1f} | Стран с кодами: {countries_with_codes}{distribution_info} | Область: {self.area_combo.currentText()}"
                    )
                    
                else:
                    # Если нет кодов, показываем маркеры
                    self.logger.warning("Нет кодов стран для хороплета, используем маркеры")
                    self.add_markers_to_map(m, country_data)
                    
            except Exception as e:
                self.logger.error(f"Ошибка при создании хороплета: {e}")
                self.add_markers_to_map(m, country_data)
        else:
            self.add_markers_to_map(m, country_data)
        
        return m

    def add_continent_data_to_map(self, m, continent_data, total_coins):
        """Добавляет данные по континентам на карту"""
        if self.geojson_path.exists():
            try:
                countries = self.db_manager.get_all_countries()
                country_objects = {c.id: c for c in countries}
                
                country_to_continent = {}
                for country in countries:
                    continent = self.get_continent_for_country(country)
                    country_to_continent[country.name] = continent
                
                # Соответствие английских названий стран в GeoJSON русским названиям
                geo_country_names = {
                    "United States of America": "США",
                    "United Kingdom": "Великобритания",
                    "Russian Federation": "Россия",
                    "China": "Китай",
                    "Japan": "Япония",
                    "Germany": "Германия",
                    "France": "Франция",
                    "Italy": "Италия",
                    "Spain": "Испания",
                    "Canada": "Канада",
                    "Australia": "Австралия",
                    "India": "Индия",
                    "Brazil": "Бразилия",
                    "Mexico": "Мексика",
                    "Argentina": "Аргентина",
                    "South Africa": "ЮАР",
                    "Egypt": "Египет",
                    "Turkey": "Турция",
                    "Sweden": "Швеция",
                    "Norway": "Норвегия",
                    "Finland": "Финляндия",
                    "Denmark": "Дания",
                    "Poland": "Польша",
                    "Czech Republic": "Чехия",
                    "Hungary": "Венгрия",
                    "Austria": "Австрия",
                    "Switzerland": "Швейцария",
                    "Netherlands": "Нидерланды",
                    "Belgium": "Бельгия",
                    "Portugal": "Португалия",
                    "Greece": "Греция",
                    "Ireland": "Ирландия",
                    "New Zealand": "Новая Зеландия",
                    "Laos": "Лаос",
                    "Cambodia": "Камбоджа",
                    "Vietnam": "Вьетнам",
                    "Myanmar": "Мьянма",
                    "Sri Lanka": "Шри-Ланка",
                    "Nepal": "Непал",
                    "Bhutan": "Бутан",
                    "Bangladesh": "Бангладеш",
                    "Pakistan": "Пакистан",
                    "Afghanistan": "Афганистан",
                    "Iran": "Иран",
                    "Iraq": "Ирак",
                    "Syria": "Сирия",
                    "Lebanon": "Ливан",
                    "Jordan": "Иордания",
                    "Israel": "Израиль",
                    "Saudi Arabia": "Саудовская Аравия",
                    "United Arab Emirates": "ОАЭ",
                    "Qatar": "Катар",
                    "Kuwait": "Кувейт",
                    "Bahrain": "Бахрейн",
                    "Oman": "Оман",
                    "Yemen": "Йемен",
                    "Kyrgyzstan": "Киргизия",
                    "Tajikistan": "Таджикистан",
                    "Turkmenistan": "Туркмения",
                    "Uzbekistan": "Узбекистан",
                    "Kazakhstan": "Казахстан",
                    "Mongolia": "Монголия",
                    "North Korea": "Северная Корея",
                    "South Korea": "Южная Корея",
                    "Taiwan": "Тайвань",
                    "Singapore": "Сингапур",
                    "Brunei": "Бруней",
                    "East Timor": "Восточный Тимор",
                }
                
                def style_function(feature):
                    geo_name = feature['properties'].get('name', '')
                    country_name = geo_country_names.get(geo_name, geo_name)
                    continent = country_to_continent.get(country_name, "Другие")
                    color = self.CONTINENT_COLORS.get(continent, "#95a5a6")
                    
                    continent_count = continent_data.get(continent, 0)
                    if continent_count > 0:
                        opacity = 0.3 + min(continent_count / total_coins, 0.5)
                    else:
                        opacity = 0.1
                    
                    return {
                        'fillColor': color,
                        'color': '#000000',
                        'weight': 0.5,
                        'fillOpacity': opacity,
                    }
                
                # Добавляем GeoJson с заливкой по континентам
                folium.GeoJson(
                    str(self.geojson_path),
                    name='continents',
                    style_function=style_function,
                    tooltip=folium.GeoJsonTooltip(
                        fields=['name'],
                        aliases=['Страна:'],
                        localize=True,
                        sticky=False,
                        labels=True,
                    )
                ).add_to(m)
                
                # Получаем данные по странам для списка
                country_data, _ = self.get_country_data_by_countries()
                
                # Добавляем маркеры с информацией по континентам
                for continent, count in continent_data.items():
                    continent_center = {
                        "Европа": [50, 10],
                        "Азия": [40, 100],
                        "Америка": [20, -80],
                        "Африка": [0, 20],
                        "Океания": [-20, 140],
                        "Другие": [0, 0]
                    }.get(continent, [0, 0])
                    
                    color = self.CONTINENT_COLORS.get(continent, "#95a5a6")
                    
                    countries_list = []
                    for country, cnt in country_data.items():
                        if self.get_continent_for_country(country) == continent:
                            countries_list.append(f"{country.name}: {cnt:.1f}")
                    
                    countries_text = "<br>".join(countries_list[:8])
                    if len(countries_list) > 8:
                        countries_text += f"<br>... и ещё {len(countries_list) - 8}"
                    
                    popup_html = f"""
                    <div style="font-family: Arial; min-width: 250px; max-width: 300px; max-height: 400px; overflow-y: auto; padding: 8px;">
                        <h3 style="margin: 0 0 5px 0; color: {color}; font-size: 18px; text-align: center;">{continent}</h3>
                        <hr style="margin: 5px 0; border: 1px solid {color};">
                        <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 3px; font-weight: bold;">💰 Всего монет:</td>
                                <td style="padding: 3px; text-align: right; font-weight: bold; color: {color};">{count:.1f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 3px; font-weight: bold;">🗺️ Стран:</td>
                                <td style="padding: 3px; text-align: right;">{len(countries_list)}</td>
                            </tr>
                        </table>
                        <hr style="margin: 5px 0;">
                        <p style="font-weight: bold; margin: 3px 0; font-size: 13px;">📋 Страны:</p>
                        <div style="background-color: #f5f5f5; padding: 5px; border-radius: 3px; font-size: 12px; max-height: 200px; overflow-y: auto;">
                            {countries_text if countries_text else "Нет монет"}
                        </div>
                    </div>
                    """
                    
                    folium.Marker(
                        continent_center,
                        popup=folium.Popup(popup_html, max_width=350, max_height=450),
                        icon=folium.DivIcon(
                            html=f"""
                            <div style="
                                background-color: {color};
                                color: white;
                                font-weight: bold;
                                padding: 6px 12px;
                                border-radius: 20px;
                                border: 2px solid white;
                                box-shadow: 0 0 10px rgba(0,0,0,0.4);
                                opacity: 0.95;
                                font-size: 14px;
                                text-align: center;
                                min-width: 120px;
                                cursor: pointer;
                            ">
                                {continent}<br>
                                <span style="font-size: 12px;">{count:.1f} монет</span>
                            </div>
                            """
                        ),
                        tooltip=f"{continent}: {count:.1f} монет"
                    ).add_to(m)
                
                filter_text = self.get_century_filter_description()
                mode_text = "По континентам"
                self.info_label.setText(
                    f"✅ {mode_text} | {filter_text} | Монет: {total_coins:.1f} | Континентов: {len(continent_data)} | "
                    f"Область: {self.area_combo.currentText()}"
                )
                
            except Exception as e:
                self.logger.error(f"Ошибка при создании карты континентов: {e}")
                self.add_markers_to_map(m, {})
        else:
            self.add_markers_to_map(m, {})
        
        return m
    
    def add_markers_to_map(self, m, country_data):
        """Добавляет маркеры на карту (запасной вариант)"""
        country_coords = {
            "Россия": [55.75, 37.62], "США": [37.09, -95.71],
            "Великобритания": [51.51, -0.13], "Германия": [52.52, 13.40],
            "Франция": [48.86, 2.35], "Италия": [41.90, 12.50],
            "Испания": [40.42, -3.70], "Китай": [39.91, 116.40],
            "Япония": [35.68, 139.76], "Канада": [45.42, -75.70],
            "Австралия": [-35.28, 149.13], "Индия": [28.61, 77.23],
            "Бразилия": [-15.79, -47.88], "Мексика": [19.43, -99.13],
            "Аргентина": [-34.60, -58.38], "ЮАР": [-25.75, 28.19],
            "Египет": [30.04, 31.24], "Турция": [39.92, 32.85],
            "Швеция": [59.33, 18.07], "Норвегия": [59.91, 10.75],
            "Финляндия": [60.17, 24.94], "Дания": [55.68, 12.57],
            "Польша": [52.23, 21.01], "Чехия": [50.08, 14.42],
            "Венгрия": [47.50, 19.04], "Австрия": [48.21, 16.37],
            "Швейцария": [46.95, 7.45], "Нидерланды": [52.37, 4.90],
            "Бельгия": [50.85, 4.35], "Португалия": [38.72, -9.14],
            "Греция": [37.98, 23.73], "Ирландия": [53.35, -6.26],
            "Новая Зеландия": [-41.29, 174.78], "Англия": [51.51, -0.13],
            "Нидерландские Антильские острова": [12.2, -68.9],
            "Лаос": [18.0, 105.0], "Камбоджа": [12.5, 105.0],
            "Вьетнам": [16.0, 108.0], "Таиланд": [15.0, 100.0],
            "Мьянма": [22.0, 98.0], "Малайзия": [4.0, 102.0],
            "Индонезия": [-5.0, 120.0], "Филиппины": [13.0, 122.0],
        }
        
        for country, count in country_data.items():
            if country.name in country_coords:
                lat, lon = country_coords[country.name]
                
                popup_html = f"""
                <div style="font-family: Arial; min-width: 200px;">
                    <h4 style="margin: 5px 0; color: #4a6fa5;">{country.name}</h4>
                    <hr style="margin: 5px 0;">
                    <p><b>Монет в коллекции:</b> {count:.1f}</p>
                </div>
                """
                
                folium.CircleMarker(
                    [lat, lon],
                    radius=10 + min(count, 20),
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{country.name}: {count:.1f} монет",
                    color='#4a6fa5',
                    fill=True,
                    fillColor='#4a6fa5',
                    fillOpacity=0.7
                ).add_to(m)
    
    def update_map(self):
        """Обновляет карту"""
        try:
            self.info_label.setText("🔄 Создание карты...")
            
            country_data, total_coins = self.get_country_data()
            
            if not country_data:
                mode_text = "По странам" if self.display_mode == self.MODE_COUNTRIES else "По континентам"
                filter_text = self.get_century_filter_description()
                self.show_html_message("📭 Нет данных", 
                                      f"Нет монет за {filter_text}\n\nРежим: {mode_text}")
                self.info_label.setText(f"📭 Нет данных за {filter_text}")
                return
            
            m = self.create_map()
            
            if self.display_mode == self.MODE_COUNTRIES:
                m = self.add_country_data_to_map(m, country_data, total_coins)
            else:
                m = self.add_continent_data_to_map(m, country_data, total_coins)
            
            folium.LayerControl().add_to(m)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                m.save(f.name)
                self.last_map_file = f.name
            
            # Добавляем CSS для скрытия логотипов
            with open(self.last_map_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            hide_css = """
            <style>
                .leaflet-control-attribution,
                .leaflet-control-attribution a,
                a[href*="leafletjs.com"],
                a[href*="openstreetmap.org"] {
                    display: none !important;
                }
            </style>
            """
            
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', hide_css + '</head>')
            else:
                html_content = hide_css + html_content
            
            with open(self.last_map_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
                self.web_view.setUrl(QUrl.fromLocalFile(self.last_map_file))
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании карты: {e}", exc_info=True)
            self.show_html_message("❌ Ошибка", str(e))
            self.info_label.setText(f"❌ Ошибка: {str(e)[:50]}...")
    
    def show_html_message(self, title, message):
        """Показывает HTML сообщение"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                }}
                .message {{
                    text-align: center;
                    padding: 30px;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 400px;
                }}
                h2 {{ color: #4a6fa5; margin-bottom: 15px; }}
                p {{ color: #666; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="message">
                <h2>{title}</h2>
                <p>{message}</p>
            </div>
        </body>
        </html>
        """
        
        if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
            self.web_view.setHtml(html)
    
    def open_map_in_browser(self):
        """Открывает карту в браузере"""
        if self.last_map_file and os.path.exists(self.last_map_file):
            webbrowser.open('file://' + self.last_map_file)
    
    def closeEvent(self, event):
        """Обработчик закрытия"""
        if self.last_map_file and os.path.exists(self.last_map_file):
            try:
                os.unlink(self.last_map_file)
            except:
                pass
        super().closeEvent(event)