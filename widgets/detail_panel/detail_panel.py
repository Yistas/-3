# -*- coding: utf-8 -*-

"""
Панель с детальной информацией - объединяет все вкладки
"""

import logging
import re
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt, QTimer

from .country_tab import CountryTab
from .coin_tab import CoinTab
from .continent_tab import ContinentTab
from .dashboard_tab import DashboardTab
from database.models import Country


class EditableDetailPanel(QWidget):
    """Панель с детальной информацией о выбранной монете или стране"""
    
    # Константы для вкладок
    TAB_DASHBOARD = 0
    TAB_COUNTRY = 1
    TAB_STATISTICS = 2
    TAB_COIN = 3
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.parent_window = parent
        self.logger = logging.getLogger('CoinCollector.GUI.DetailPanel')
        
        self.current_coin = None
        self.current_country = None
        self.current_continent = None
        self.current_mode = None
        self.last_selection = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        
        # Флаг для предотвращения рекурсии - ДОБАВИТЬ ЭТУ СТРОКУ
        self._updating = False
        
        self.setMinimumWidth(305)
        self.setMaximumWidth(700)
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Создаем вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Индекс 0: ДАШБОРД
        self.dashboard_tab = DashboardTab(self.db_manager, self)
        self.tab_widget.addTab(self.dashboard_tab, "📊 Дашборд")
        
        # Индекс 1: СТРАНА
        self.country_tab = CountryTab(self.db_manager, self)
        self.tab_widget.addTab(self.country_tab, "🌍 Страна")
        
        # Индекс 2: СТАТИСТИКА
        self.continent_tab = ContinentTab(self.db_manager, self)
        self.tab_widget.addTab(self.continent_tab, "🗺️ Статистика")
        
        # Индекс 3: МОНЕТА
        self.coin_tab = CoinTab(self.db_manager, self)
        self.tab_widget.addTab(self.coin_tab, "🪙 Монета")
        
        layout.addWidget(self.tab_widget)
    
    def on_tab_changed(self, index):
        """Обработчик смены вкладки"""
        # Проверяем, есть ли атрибут _updating (для обратной совместимости)
        if hasattr(self, '_updating') and self._updating:
            return
        
        if hasattr(self, '_updating'):
            self._updating = True
        
        try:
            if index == self.TAB_STATISTICS:
                # При переключении на вкладку статистики
                if self.current_mode == 'collection_stats':
                    self.continent_tab.show_collection_stats()
                elif self.current_mode == 'collection_value':
                    self.continent_tab.show_collection_value()
                elif self.current_mode == 'folder' and self.current_folder_name:
                    self.continent_tab.show_folder_stats(self.current_folder_name, self.current_folder_country_ids)
                elif self.current_continent:
                    if self.current_mode == 'extinct_continent':
                        self.continent_tab.show_extinct_continent_stats(self.current_continent)
                    else:
                        self.continent_tab.show_continent_stats(self.current_continent)
                elif self.current_mode == 'all_countries':
                    self.continent_tab.show_all_countries_stats()
                elif self.current_mode == 'extinct_countries':
                    self.continent_tab.show_extinct_countries_stats()
                else:
                    self.continent_tab.show_collection_stats()
            
            elif index == self.TAB_COUNTRY and self.current_country:
                self.country_tab.show_country_info(self.current_country)
            
            elif index == self.TAB_COIN and self.current_coin:
                self.coin_tab.show_coin_info(self.current_coin)
            
            elif index == self.TAB_DASHBOARD:
                if hasattr(self, 'dashboard_tab'):
                    self.dashboard_tab.refresh()
        finally:
            if hasattr(self, '_updating'):
                self._updating = False
    
    # ========== МЕТОДЫ ПЕРЕКЛЮЧЕНИЯ ВКЛАДОК ==========
    
    def show_dashboard(self):
        """Показывает дашборд (при выборе КОЛЛЕКЦИЯ)"""
        self.logger.info("show_dashboard вызван")
        self.tab_widget.setCurrentIndex(self.TAB_DASHBOARD)
        if hasattr(self, 'dashboard_tab'):
            self.dashboard_tab.refresh()
    
    def show_statistics(self):
        """Показывает вкладку статистики"""
        self.logger.info("show_statistics вызван")
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
    
    def show_country_info_by_id(self, country_id):
        """Показывает информацию о стране по ID"""
        self.logger.info(f"show_country_info_by_id вызван для {country_id}")
        country = self.db_manager.session.query(Country).get(country_id)
        if country:
            self.show_country_info(country)
        else:
            self.logger.warning(f"Страна с ID {country_id} не найдена")
    
    def show_coin_info(self, coin):
        """Отображает информацию о монете"""
        # Убираем проверку _updating — она блокирует показ
        self._updating = False
        
        self.logger.info(f"=== show_coin_info ===")
        self.logger.info(f"  coin: {coin.id if coin else None}")
        
        self.current_coin = coin
        self.current_country = None
        self.current_continent = None
        self.current_mode = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'coin'
        
        if coin is None:
            self.logger.warning("  coin is None")
            # Очищаем отображение
            if hasattr(self, 'coin_tab'):
                self.coin_tab.clear_view()
            return
        
        # Переключаемся на вкладку монеты
        self.logger.info(f"  Переключение на вкладку {self.TAB_COIN}")
        self.tab_widget.setCurrentIndex(self.TAB_COIN)
        
        # Обновляем отображение
        self.logger.info(f"  Вызов coin_tab.show_coin_info")
        self.coin_tab.show_coin_info(coin)
        
        self.logger.info(f"=== show_coin_info завершен ===")

    def show_country_info(self, country):
        """Отображает информацию о стране"""
        if self._updating:
            self.logger.info("show_country_info: already updating, skip")
            return
        
        self._updating = True
        try:
            self.logger.info(f"=== show_country_info ===")
            self.logger.info(f"  country: {country.name if country else None}")
            self.logger.info(f"  TAB_COUNTRY = {self.TAB_COUNTRY}")
            
            self.current_country = country
            self.current_coin = None
            self.current_continent = None
            self.current_mode = None
            self.current_folder_name = None
            self.current_folder_country_ids = None
            self.last_selection = 'country'
            
            if country is None:
                self.logger.warning("  country is None")
                return
            
            # Переключаемся на вкладку страны
            self.logger.info(f"  Переключение на вкладку {self.TAB_COUNTRY}")
            self.tab_widget.setCurrentIndex(self.TAB_COUNTRY)
            
            # Обновляем отображение
            self.logger.info(f"  Вызов country_tab.show_country_info")
            self.country_tab.show_country_info(country)
            
            self.logger.info(f"=== show_country_info завершен ===")
        finally:
            self._updating = False
    
    def show_continent_stats(self, continent_name):
        """Отображает статистику по континенту"""
        import re
        clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
        
        self.current_continent = clean_name
        self.current_country = None
        self.current_coin = None
        self.current_mode = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'continent'
        
        self.logger.info(f"show_continent_stats вызван для '{continent_name}'")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_continent_stats(clean_name)
    
    def show_extinct_continent_stats(self, continent_name):
        """Отображает статистику по исчезнувшим странам конкретного континента"""
        clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
        
        self.current_continent = clean_name
        self.current_mode = 'extinct_continent'
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'extinct_continent'
        
        self.logger.info(f"show_extinct_continent_stats вызван для {continent_name}")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_extinct_continent_stats(clean_name)
    
    def show_all_countries_stats(self):
        """Отображает статистику по всем странам"""
        self.current_mode = 'all_countries'
        self.current_continent = None
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'all_countries'
        
        self.logger.info("show_all_countries_stats вызван")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_all_countries_stats()
    
    def show_extinct_countries_stats(self):
        """Отображает статистику по исчезнувшим странам"""
        self.current_mode = 'extinct_countries'
        self.current_continent = None
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'extinct_countries'
        
        self.logger.info("show_extinct_countries_stats вызван")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_extinct_countries_stats()
    
    def show_folder_stats(self, folder_name, country_ids):
        """Отображает статистику по пользовательской папке"""
        self.current_mode = 'folder'
        self.current_continent = None
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = folder_name
        self.current_folder_country_ids = country_ids
        self.last_selection = 'folder'
        
        self.logger.info(f"show_folder_stats вызван для {folder_name} с {len(country_ids)} странами")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_folder_stats(folder_name, country_ids)
    
    def show_collection_value(self, country_ids=None, continent_name=None):
        """Отображает стоимость коллекции - всегда показываем всю коллекцию"""
        self.current_mode = 'collection_value'
        self.current_continent = None
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'collection_value'
        
        self.logger.info("show_collection_value вызван - вся коллекция")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_collection_value()
    
    def show_collection_stats(self):
        """Отображает статистику по всей коллекции"""
        self.current_mode = 'collection_stats'
        self.current_continent = None
        self.current_country = None
        self.current_coin = None
        self.current_folder_name = None
        self.current_folder_country_ids = None
        self.last_selection = 'collection_stats'
        
        self.logger.info("show_collection_stats вызван - статистика по всей коллекции")
        
        self.tab_widget.setCurrentIndex(self.TAB_STATISTICS)
        self.continent_tab.show_collection_stats()
    
    def refresh_country_combos(self):
        """Обновляет комбобоксы со странами"""
        if hasattr(self.coin_tab, 'load_countries_to_combo'):
            self.coin_tab.load_countries_to_combo()
            self.coin_tab.load_countries_to_purchase_combo()
    
    def update_continent_stats(self, continent_values, last_date):
        """Обновляет статистику по континентам на боковой панели"""
        if hasattr(self, 'continent_tab'):
            self.continent_tab.update_continent_stats(continent_values, last_date)
    
    def reset_edit_mode(self):
        """Сбрасывает режим редактирования на вкладке монеты"""
        if hasattr(self, 'coin_tab'):
            if self.coin_tab.edit_mode:
                self.coin_tab.switch_to_view_mode()
                
    def update_style(self):
        """Переприменяет стили текущей темы ко всем вкладкам панели"""
        for tab in (getattr(self, 'dashboard_tab', None),
                    getattr(self, 'country_tab', None),
                    getattr(self, 'continent_tab', None),
                    getattr(self, 'coin_tab', None)):
            if tab is not None and hasattr(tab, 'update_style'):
                tab.update_style()