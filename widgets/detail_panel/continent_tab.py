# ===== gui/widgets/detail_panel/continent_tab.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Вкладка со статистикой по континентам и стоимости коллекции
"""

from pathlib import Path
import logging
import os
import re
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
                               QGridLayout, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor, QFont
from utils.paths import paths
from database.models import Country, Coin, Continent, Metal, MetalPriceHistory

class NumericTableWidgetItem(QTableWidgetItem):
    """Элемент таблицы с числовой сортировкой"""
    
    def __init__(self, value, text=None):
        super().__init__()
        self.setData(Qt.UserRole, value)
        if text is not None:
            self.setText(text)
    
    def __lt__(self, other):
        """Переопределяем сравнение для сортировки"""
        if isinstance(other, NumericTableWidgetItem):
            return self.data(Qt.UserRole) < other.data(Qt.UserRole)
        return super().__lt__(other)


class ContinentTab(QWidget):
    """Вкладка со статистикой по континентам и стоимости коллекции"""
    
    # Сигнал для обновления данных
    data_updated = Signal()
    
    # Цвета для континентов
    CONTINENT_COLORS = {
        "Европа": "#4a6fa5",
        "Азия": "#e67e22",
        "Америка": "#27ae60",
        "Африка": "#f1c40f",
        "Океания": "#9b59b6",
        "Не указан": "#95a5a6"
    }
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.ContinentTab')
        
        self.current_continent = None
        self.current_mode = None
        
        # Для сортировки металлов
        self.gold_total = 0
        self.silver_total = 0
        self.other_total = 0
        self.gold_coins = 0
        self.silver_coins = 0
        self.other_coins = 0
        self.gold_weight = 0.0
        self.silver_weight = 0.0
        self.other_weight = 0.0
        self.current_sort_type = 'value'
        self.current_sort_order = False
        self.last_sort_type = 'value'
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # Название раздела
        self.section_name_label = QLabel()
        self.section_name_label.setMaximumHeight(30)
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #4a6fa5;
            padding: 5px;
            background-color: #f0f7ff;
            border: 1px solid #4a6fa5;
            border-radius: 3px;
        """)
        self.section_name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.section_name_label)
        
        # Карта (только для конкретного континента)
        self.map_group = QGroupBox("🗺️ Карта континента")
        self.map_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
                padding-top: 5px;
            }
        """)
        map_layout = QVBoxLayout()
        map_layout.setSpacing(5)
        map_layout.setContentsMargins(5, 5, 5, 5)
        
        self.continent_map_label = QLabel()
        self.continent_map_label.setAlignment(Qt.AlignCenter)
        self.continent_map_label.setMinimumHeight(200)
        self.continent_map_label.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 3px;
        """)
        map_layout.addWidget(self.continent_map_label)
        
        self.map_group.setLayout(map_layout)
        layout.addWidget(self.map_group)
        
        # Группа для стоимости коллекции
        self.value_group = QGroupBox("💰 Стоимость коллекции")
        self.value_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
                padding-top: 5px;
            }
        """)
        value_layout = QVBoxLayout()
        value_layout.setSpacing(5)
        
        # Дата последнего обновления цен
        self.last_date_label = QLabel()
        self.last_date_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        self.last_date_label.setAlignment(Qt.AlignCenter)
        value_layout.addWidget(self.last_date_label)
        
        # Таблица стоимости
        self.value_table = QTableWidget()
        self.value_table.setColumnCount(3)
        self.value_table.setHorizontalHeaderLabels(["Металл", "Кол", "₽₽₽"])
        self.value_table.setAlternatingRowColors(True)
        self.value_table.setSortingEnabled(False)
        
        header = self.value_table.horizontalHeader()
        # Фиксируем ширину колонок
        self.value_table.setColumnWidth(0, 100)   # Металл
        self.value_table.setColumnWidth(1, 50)    # Кол
        self.value_table.setColumnWidth(2, 100)   # ₽₽₽
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        
        value_layout.addWidget(self.value_table)
        
        # Общая стоимость
        total_layout = QHBoxLayout()
        total_layout.addWidget(QLabel("💰 Общая стоимость:"))
        self.total_value_label = QLabel("—")
        self.total_value_label.setStyleSheet("font-weight: bold; color: #28a745; font-size: 14px;")
        total_layout.addWidget(self.total_value_label)
        total_layout.addStretch()
        
        value_layout.addLayout(total_layout)
        
        self.value_group.setLayout(value_layout)
        layout.addWidget(self.value_group)
        
        # Основная статистика
        self.main_stats_group = QGroupBox("📊 Основная статистика")
        self.main_stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
                padding-top: 5px;
            }
        """)
        main_stats_layout = QGridLayout()
        main_stats_layout.setVerticalSpacing(5)
        main_stats_layout.setHorizontalSpacing(10)
        
        # Строка 0
        main_stats_layout.addWidget(QLabel("🏛️ Стран в разделе:"), 0, 0)
        self.stats_total_countries = QLabel("—")
        self.stats_total_countries.setStyleSheet("font-weight: bold;")
        main_stats_layout.addWidget(self.stats_total_countries, 0, 1)
        
        main_stats_layout.addWidget(QLabel("💰 Всего монет:"), 0, 2)
        self.stats_total_coins = QLabel("—")
        self.stats_total_coins.setStyleSheet("font-weight: bold;")
        main_stats_layout.addWidget(self.stats_total_coins, 0, 3)
        
        # Строка 1
        main_stats_layout.addWidget(QLabel("✅ В коллекции:"), 1, 0)
        self.stats_in_collection = QLabel("—")
        main_stats_layout.addWidget(self.stats_in_collection, 1, 1)
        
        main_stats_layout.addWidget(QLabel("⭐ Желаемые:"), 1, 2)
        self.stats_want = QLabel("—")
        main_stats_layout.addWidget(self.stats_want, 1, 3)
        
        # Строка 2
        main_stats_layout.addWidget(QLabel("💵 Проданные:"), 2, 0)
        self.stats_sold = QLabel("—")
        main_stats_layout.addWidget(self.stats_sold, 2, 1)
        
        main_stats_layout.addWidget(QLabel("💔 Утерянные:"), 2, 2)
        self.stats_lost = QLabel("—")
        main_stats_layout.addWidget(self.stats_lost, 2, 3)
        
        # Строка 3
        main_stats_layout.addWidget(QLabel("💰 Общая стоимость покупки:"), 3, 0)
        self.stats_total_value = QLabel("—")
        self.stats_total_value.setStyleSheet("font-weight: bold; color: #28a745;")
        main_stats_layout.addWidget(self.stats_total_value, 3, 1, 1, 3)
        
        self.main_stats_group.setLayout(main_stats_layout)
        layout.addWidget(self.main_stats_group)
        
        # Статистика по континентам
        self.continent_stats_group = QGroupBox("🌍 Распределение по континентам")
        self.continent_stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
                padding-top: 5px;
            }
        """)
        continent_stats_layout = QVBoxLayout()
        continent_stats_layout.setSpacing(3)
        continent_stats_layout.setContentsMargins(5, 5, 5, 5)

        self.continent_stats_table = QTableWidget()
        self.continent_stats_table.setColumnCount(4)
        self.continent_stats_table.setHorizontalHeaderLabels(["Континент", "Стоимость (₽)", "%", "Вес (г)"])
        self.continent_stats_table.setAlternatingRowColors(True)
        self.continent_stats_table.setSortingEnabled(True)
        
        header = self.continent_stats_table.horizontalHeader()
        self.continent_stats_table.setColumnWidth(0, 90)
        self.continent_stats_table.setColumnWidth(1, 100)
        self.continent_stats_table.setColumnWidth(2, 60)
        self.continent_stats_table.setColumnWidth(3, 80)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)

        continent_stats_layout.addWidget(self.continent_stats_table)
        self.continent_stats_group.setLayout(continent_stats_layout)
        layout.addWidget(self.continent_stats_group)
        
        # Таблица стран (для конкретного континента)
        self.table_group = QGroupBox("📋 Страны в разделе")
        self.table_group.hide()
        table_layout = QVBoxLayout()
        
        self.countries_table = QTableWidget()
        self.countries_table.setColumnCount(4)
        self.countries_table.setHorizontalHeaderLabels(["Страна", "Континент", "Статус", "Монет"])
        self.countries_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.countries_table.setAlternatingRowColors(True)
        self.countries_table.setSortingEnabled(True)
        
        header = self.countries_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        table_layout.addWidget(self.countries_table)
        self.table_group.setLayout(table_layout)
        layout.addWidget(self.table_group)
        
        # По умолчанию показываем стоимость коллекции
        self.hide_all_except_value()
    
    def hide_all_except_value(self):
        """Скрывает все группы кроме стоимости коллекции"""
        self.map_group.hide()
        self.main_stats_group.hide()
        self.continent_stats_group.hide()
        self.table_group.hide()
        self.value_group.show()
    
    def show_continent_ui(self):
        """Показывает UI для континента"""
        self.map_group.show()
        self.main_stats_group.show()
        self.continent_stats_group.hide()
        self.table_group.show()
        self.value_group.hide()
    
    def show_general_stats_ui(self):
        """Показывает UI для общей статистики"""
        self.map_group.hide()
        self.main_stats_group.show()
        self.continent_stats_group.show()
        self.table_group.hide()
        self.value_group.hide()
        
        self.update_continent_stats_headers(mode='count')
    
    def show_collection_value_ui(self):
        """Показывает UI для стоимости коллекции"""
        self.map_group.hide()
        self.main_stats_group.show()
        self.continent_stats_group.show()
        self.table_group.hide()
        self.value_group.show()
        
        self.update_continent_stats_headers(mode='value')
        
        header = self.value_table.horizontalHeader()
        self.value_table.setColumnWidth(0, 80)
        self.value_table.setColumnWidth(1, 55)
        self.value_table.setColumnWidth(2, 80)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
    
    # ========== ОСНОВНЫЕ МЕТОДЫ ОТОБРАЖЕНИЯ ==========
    
    def show_collection_value(self, country_ids=None, continent_name=None):
        """Отображает стоимость коллекции - ВСЕГДА всю коллекцию"""
        self.current_mode = 'collection_value'
        self.current_continent = None
        
        self.logger.info("show_collection_value вызван - вся коллекция")
        
        self.section_name_label.setText("💰 Стоимость коллекции")
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #28a745;
            padding: 5px;
            background-color: #f0fff0;
            border: 1px solid #28a745;
            border-radius: 3px;
        """)
        
        self.show_collection_value_ui()
        self.load_collection_value()
        
        # Обновляем статистику для всех стран
        all_countries = self.db_manager.get_all_countries()
        all_ids = [c.id for c in all_countries]
        self.update_stats_for_filtered_coins(country_ids=all_ids)
    
    def show_collection_stats(self):
        """Отображает статистику по всей коллекции (количество монет)"""
        self.current_mode = 'collection_stats'
        self.current_continent = None
        
        self.logger.info("show_collection_stats вызван - статистика по всей коллекции")
        
        self.section_name_label.setText("📚 Вся коллекция")
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #4a6fa5;
            padding: 5px;
            background-color: #f0f7ff;
            border: 1px solid #4a6fa5;
            border-radius: 3px;
        """)
        
        self.show_general_stats_ui()
        self.load_collection_statistics()
        
        # Обновляем статистику для всех стран
        all_countries = self.db_manager.get_all_countries()
        all_ids = [c.id for c in all_countries]
        self.update_stats_for_filtered_coins(country_ids=all_ids)
    
    def show_continent_stats(self, continent_name):
        """Отображает статистику по континенту"""
        clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
        self.current_mode = 'continent'
        self.current_continent = clean_name
        
        color = self.CONTINENT_COLORS.get(clean_name, "#4a6fa5")
        
        self.section_name_label.setText(clean_name)
        self.section_name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 16px;
            color: {color};
            padding: 5px;
            background-color: #f0f7ff;
            border: 1px solid {color};
            border-radius: 3px;
        """)
        
        self.show_continent_ui()
        self.load_continent_map(clean_name)
        self.load_continent_statistics(clean_name)
        
        # Обновляем статистику для стран континента
        countries = self.db_manager.session.query(Country).filter_by(
            continent=clean_name, is_extinct=False
        ).all()
        country_ids = [c.id for c in countries]
        self.update_stats_for_filtered_coins(country_ids=country_ids)
    
    def show_all_countries_stats(self):
        """Отображает статистику по всем существующим странам"""
        self.current_mode = 'all_countries'
        self.current_continent = None
        
        self.section_name_label.setText("🌍 Все страны")
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #4a6fa5;
            padding: 5px;
            background-color: #f0f7ff;
            border: 1px solid #4a6fa5;
            border-radius: 3px;
        """)
        
        self.show_general_stats_ui()
        self.load_all_countries_statistics()
        
        countries = self.db_manager.session.query(Country).filter_by(is_extinct=False).all()
        country_ids = [c.id for c in countries]
        self.update_stats_for_filtered_coins(country_ids=country_ids)
    
    def show_extinct_countries_stats(self):
        """Отображает статистику по исчезнувшим странам"""
        self.current_mode = 'extinct_countries'
        self.current_continent = None
        
        self.section_name_label.setText("💀 Исчезнувшие страны")
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #dc3545;
            padding: 5px;
            background-color: #fff5f5;
            border: 1px solid #dc3545;
            border-radius: 3px;
        """)
        
        self.show_general_stats_ui()
        self.load_extinct_countries_statistics()
        
        extinct_countries = self.db_manager.session.query(Country).filter_by(is_extinct=True).all()
        extinct_ids = [c.id for c in extinct_countries]
        self.update_stats_for_filtered_coins(country_ids=extinct_ids)
    
    def show_extinct_continent_stats(self, continent_name):
        """Отображает статистику по исчезнувшим странам континента"""
        clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
        self.current_mode = 'extinct_continent'
        self.current_continent = clean_name
        
        self.section_name_label.setText(f"💀 {clean_name} (исчезнувшие)")
        self.section_name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 16px;
            color: #dc3545;
            padding: 5px;
            background-color: #fff5f5;
            border: 1px solid #dc3545;
            border-radius: 3px;
        """)
        
        self.show_continent_ui()
        self.load_continent_map(clean_name)
        self.load_extinct_continent_statistics(clean_name)
        
        extinct_countries = self.db_manager.session.query(Country).filter_by(
            continent=clean_name, is_extinct=True
        ).all()
        extinct_ids = [c.id for c in extinct_countries]
        self.update_stats_for_filtered_coins(country_ids=extinct_ids)
    
    def show_folder_stats(self, folder_name, country_ids):
        """Отображает статистику по пользовательской папке"""
        self.current_mode = 'folder'
        self.current_continent = None
        
        self.section_name_label.setText(f"📁 {folder_name}")
        self.section_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #6c757d;
            padding: 5px;
            background-color: #f8f9fa;
            border: 1px solid #6c757d;
            border-radius: 3px;
        """)
        
        self.show_general_stats_ui()
        self.load_folder_statistics(folder_name, country_ids)
        self.update_stats_for_filtered_coins(country_ids=country_ids)
    
    # ========== ЗАГРУЗКА ДАННЫХ ==========
    
    def load_continent_map(self, continent_name):
        """Загружает карту континента"""
        continent_maps_dir = paths.get_data_dir() / "continent_maps"
        clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
        
        continent = self.db_manager.session.query(Continent).filter_by(name=clean_name).first()
        
        if continent:
            map_path = continent_maps_dir / f"continent_{continent.id}.png"
            if map_path.exists():
                try:
                    pixmap = QPixmap(str(map_path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(400, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.continent_map_label.setPixmap(scaled)
                        return
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке карты: {e}")
        
        self.continent_map_label.setText("🗺️")
        self.continent_map_label.setStyleSheet("font-size: 48px; color: #999;")
    
    def load_continent_statistics(self, continent_name):
        """Загружает статистику по континенту"""
        try:
            clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
            countries = self.db_manager.session.query(Country).filter_by(continent=clean_name).all()
            
            stats = self._calculate_statistics(countries)
            self._update_statistics_display(stats)
            self._fill_countries_table(countries)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке статистики континента: {e}")
    
    def load_all_countries_statistics(self):
        """Загружает статистику по всем странам"""
        try:
            all_countries = self.db_manager.session.query(Country).filter_by(is_extinct=False).all()
            stats = self._calculate_statistics(all_countries)
            self._update_statistics_display(stats)
            self._fill_continent_stats_with_count(all_countries, stats['total_coins'])
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке общей статистики: {e}")
    
    def load_extinct_countries_statistics(self):
        """Загружает статистику по исчезнувшим странам"""
        try:
            extinct_countries = self.db_manager.session.query(Country).filter_by(is_extinct=True).all()
            stats = self._calculate_statistics(extinct_countries)
            self._update_statistics_display(stats)
            self._fill_continent_stats_with_count(extinct_countries, stats['total_coins'])
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке статистики исчезнувших стран: {e}")
    
    def load_extinct_continent_statistics(self, continent_name):
        """Загружает статистику по исчезнувшим странам континента"""
        try:
            clean_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', continent_name)
            extinct_countries = self.db_manager.session.query(Country).filter_by(
                continent=clean_name, is_extinct=True
            ).all()
            
            stats = self._calculate_statistics(extinct_countries)
            self._update_statistics_display(stats)
            self._fill_extinct_countries_table(extinct_countries)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке статистики исчезнувших стран континента: {e}")
    
    def load_folder_statistics(self, folder_name, country_ids):
        """Загружает статистику для пользовательской папки"""
        try:
            countries = self.db_manager.session.query(Country).filter(
                Country.id.in_(country_ids)
            ).all()
            
            if not countries:
                self.stats_total_countries.setText("0")
                self.stats_total_coins.setText("0")
                self.stats_in_collection.setText("0")
                self.stats_want.setText("0")
                self.stats_sold.setText("0")
                self.stats_lost.setText("0")
                self.stats_total_value.setText("0 ₽")
                self.continent_stats_table.setRowCount(0)
                return
            
            stats = self._calculate_statistics(countries)
            self._update_statistics_display(stats)
            self._fill_continent_stats_with_count(countries, stats['total_coins'])
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке статистики для папки {folder_name}: {e}")
    
    def load_collection_value(self):
        """Загружает данные о стоимости коллекции с агрегатами и сортируемой таблицей"""
        try:
            from utils.metal_aggregator import MetalAggregator
            
            last_price_date = self.db_manager.session.query(
                MetalPriceHistory.date
            ).order_by(MetalPriceHistory.date.desc()).first()
            
            if not last_price_date:
                self.last_date_label.setText("❌ Нет данных о ценах")
                self.value_table.setRowCount(0)
                self.total_value_label.setText("—")
                return
            
            last_date = last_price_date[0]
            today = datetime.now().date()
            
            date_str = last_date.strftime("%d.%m.%Y")
            if last_date == today:
                date_str += " (сегодня)"
            elif last_date == today - timedelta(days=1):
                date_str += " (вчера)"
            
            self.last_date_label.setText(f"📅 Цены на {date_str}")
            
            # ИСПОЛЬЗУЕМ АГРЕГАТОР БЕЗ ФИЛЬТРА ПО СТАТУСУ
            self.logger.info("📊 Загрузка агрегированных весов металлов...")
            aggregated_weights = MetalAggregator.get_aggregated_weights(self.db_manager, status=None)
            
            if not aggregated_weights:
                self.last_date_label.setText("❌ Нет данных о монетах")
                self.value_table.setRowCount(0)
                self.total_value_label.setText("—")
                return
            
            self.logger.info(f"📊 Загружено агрегированных данных: {len(aggregated_weights)} металлов")
            
            value_data = []
            gold_total = 0
            silver_total = 0
            other_total = 0
            gold_coins = 0
            silver_coins = 0
            other_coins = 0
            gold_weight = 0.0
            silver_weight = 0.0
            other_weight = 0.0
            total_value = 0
            
            # Получаем цены для всех металлов за последнюю дату
            for metal_id, metal_data in aggregated_weights.items():
                metal = self.db_manager.session.query(Metal).get(metal_id)
                if not metal:
                    continue
                
                price_entry = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=metal_id,
                    date=last_date
                ).first()
                
                if not price_entry:
                    self.logger.warning(f"⚠️ Нет цены для {metal.name} на {last_date}")
                    continue
                
                metal_purity = metal.get_purity_decimal()
                metal_weight = metal_data['weight']
                metal_value = metal_weight * price_entry.close_price
                
                metal_name_lower = metal.name.lower()
                if 'золото' in metal_name_lower:
                    gold_total += metal_value
                    gold_coins += metal_data.get('coin_count', 0)
                    gold_weight += metal_weight
                elif 'серебро' in metal_name_lower:
                    silver_total += metal_value
                    silver_coins += metal_data.get('coin_count', 0)
                    silver_weight += metal_weight
                else:
                    other_total += metal_value
                    other_coins += metal_data.get('coin_count', 0)
                    other_weight += metal_weight
                
                value_data.append({
                    'name': metal.get_display_text(),
                    'coin_count': metal_data.get('coin_count', 0),
                    'value': metal_value,
                    'weight': metal_weight,
                })
                total_value += metal_value
            
            self.logger.info("=" * 50)
            self.logger.info(f"📊 ИТОГОВЫЕ ЗНАЧЕНИЯ:")
            self.logger.info(f"  Золото: {gold_coins} монет, {gold_weight:.2f}г, {gold_total:.2f}₽")
            self.logger.info(f"  Серебро: {silver_coins} монет, {silver_weight:.2f}г, {silver_total:.2f}₽")
            self.logger.info(f"  Другие: {other_coins} монет, {other_weight:.2f}г, {other_total:.2f}₽")
            self.logger.info("=" * 50)
            
            # Сохраняем данные для агрегатов
            self.gold_total = gold_total
            self.silver_total = silver_total
            self.other_total = other_total
            self.gold_coins = gold_coins
            self.silver_coins = silver_coins
            self.other_coins = other_coins
            self.gold_weight = gold_weight
            self.silver_weight = silver_weight
            self.other_weight = other_weight
            
            # Сохраняем данные для таблицы
            self.current_metal_data = value_data
            self.current_total_value = total_value
            
            # Обновляем агрегаты в основной статистике
            self._update_metal_aggregates(gold_total, silver_total, other_total, 
                                         gold_coins, silver_coins, other_coins,
                                         gold_weight, silver_weight, other_weight)
            
            # Заполняем таблицу
            self._update_value_table(value_data)
            
            # Включаем сортировку после заполнения
            self.value_table.setSortingEnabled(True)
            
            # Настраиваем заголовки для сортировки
            header = self.value_table.horizontalHeader()
            header.setSortIndicatorShown(True)
            header.setSortIndicator(2, Qt.DescendingOrder)
            
            self.total_value_label.setText(f"{total_value:,.2f} ₽")
            
            # Убрали вызов load_continent_value_statistics, так как он не нужен
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке стоимости коллекции: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.last_date_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def load_collection_statistics(self):
        """Загружает статистику по всей коллекции (количество монет)"""
        try:
            all_countries = self.db_manager.get_all_countries()
            stats = self._calculate_statistics(all_countries)
            self._update_statistics_display(stats)
            self._fill_continent_stats_with_count(all_countries, stats['total_coins'])
            self.logger.info(f"Статистика загружена: {stats['total_coins']} монет")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке статистики коллекции: {e}")
    
    def update_stats_for_filtered_coins(self, country_ids=None, continent_name=None):
        """Обновляет статистику (вес и стоимость) для отфильтрованных монет (БЕЗ фильтра по статусу)"""
        try:
            last_price_date = self.db_manager.session.query(
                MetalPriceHistory.date
            ).order_by(MetalPriceHistory.date.desc()).first()
            
            if not last_price_date:
                self.logger.warning("Нет данных о ценах металлов")
                return
            
            target_date = last_price_date[0]
            
            # БЕЗ фильтра по статусу
            query = self.db_manager.session.query(Coin).filter(
                Coin.weight.isnot(None),
                Coin.weight > 0,
                Coin.metal_id.isnot(None),
                Coin.purchase_date.isnot(None),
                Coin.purchase_date <= target_date
            )
            
            if country_ids is not None:
                query = query.filter(Coin.country_id.in_(country_ids))
            elif continent_name is not None:
                countries = self.db_manager.session.query(Country).filter_by(continent=continent_name).all()
                country_ids_list = [c.id for c in countries]
                query = query.filter(Coin.country_id.in_(country_ids_list))
            
            coins = query.all()
            
            self.logger.info(f"Найдено монет для статистики: {len(coins)}")
            
            if not coins:
                self._update_metal_aggregates(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
                return
            
            gold_value = 0.0
            silver_value = 0.0
            other_value = 0.0
            gold_weight = 0.0
            silver_weight = 0.0
            other_weight = 0.0
            gold_coins = 0
            silver_coins = 0
            other_coins = 0
            
            for coin in coins:
                metal = self.db_manager.session.query(Metal).get(coin.metal_id)
                if not metal:
                    continue
                
                price_entry = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=metal.id,
                    date=target_date
                ).first()
                
                if not price_entry:
                    continue
                
                metal_purity = metal.get_purity_decimal()
                metal_weight = coin.weight * metal_purity
                coin_value = metal_weight * price_entry.close_price
                
                metal_name_lower = metal.name.lower()
                if 'золото' in metal_name_lower:
                    gold_value += coin_value
                    gold_weight += metal_weight
                    gold_coins += 1
                elif 'серебро' in metal_name_lower:
                    silver_value += coin_value
                    silver_weight += metal_weight
                    silver_coins += 1
                else:
                    other_value += coin_value
                    other_weight += metal_weight
                    other_coins += 1
            
            self._update_metal_aggregates(
                gold_value, silver_value, other_value,
                gold_coins, silver_coins, other_coins,
                gold_weight, silver_weight, other_weight
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении статистики: {e}")
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def _update_metal_aggregates(self, gold_total, silver_total, other_total, 
                                 gold_coins, silver_coins, other_coins,
                                 gold_weight=0.0, silver_weight=0.0, other_weight=0.0):
        """Обновляет отображение агрегатных сумм по металлам"""
        # Сохраняем данные
        self.gold_total = gold_total
        self.silver_total = silver_total
        self.other_total = other_total
        self.gold_coins = gold_coins
        self.silver_coins = silver_coins
        self.other_coins = other_coins
        self.gold_weight = gold_weight
        self.silver_weight = silver_weight
        self.other_weight = other_weight
        
        self.logger.info(f"📊 _update_metal_aggregates: Золото вес={gold_weight:.2f}г, "
                        f"Серебро вес={silver_weight:.2f}г, Другие вес={other_weight:.2f}г")
        
        # Получаем текущий layout
        layout = self.main_stats_group.layout()
        
        # Если layout не QGridLayout, создаем новый
        if not isinstance(layout, QGridLayout):
            if layout:
                QWidget().setLayout(layout)
            
            layout = QGridLayout()
            layout.setVerticalSpacing(5)
            layout.setHorizontalSpacing(8)
            self.main_stats_group.setLayout(layout)
        else:
            # Очищаем layout
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
        
        # Собираем данные в список для сортировки
        metals_data = []
        
        if gold_coins > 0 or gold_weight > 0:
            metals_data.append({
                'name': '💰 Золото',
                'color': '#FFD700',
                'coins': gold_coins,
                'value': gold_total,
                'weight': gold_weight,
                'type': 'gold'
            })
        
        if silver_coins > 0 or silver_weight > 0:
            metals_data.append({
                'name': '🔘 Серебро',
                'color': '#C0C0C0',
                'coins': silver_coins,
                'value': silver_total,
                'weight': silver_weight,
                'type': 'silver'
            })
        
        if other_coins > 0 or other_weight > 0:
            metals_data.append({
                'name': '⚙️ Другие',
                'color': '#6c757d',
                'coins': other_coins,
                'value': other_total,
                'weight': other_weight,
                'type': 'other'
            })
        
        # Сортировка по стоимости
        metals_data.sort(key=lambda x: x['value'], reverse=True)
        
        row = 0
        
        # Заголовки
        name_header = QLabel("Металл")
        name_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #4a6fa5;")
        name_header.setMinimumWidth(140)
        name_header.setFixedWidth(140)
        name_header.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        name_header.setWordWrap(False)
        name_header.setCursor(Qt.PointingHandCursor)
        name_header.setToolTip("Нажмите для сортировки по названию")
        name_header.mousePressEvent = lambda e: self._sort_metals_by('name')
        
        coins_header = QLabel("Кол-во")
        coins_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #4a6fa5;")
        coins_header.setAlignment(Qt.AlignRight)
        coins_header.setCursor(Qt.PointingHandCursor)
        coins_header.setToolTip("Нажмите для сортировки по количеству")
        coins_header.mousePressEvent = lambda e: self._sort_metals_by('coins')
        coins_header.setMinimumWidth(50)
        
        value_header = QLabel("Стоимость (₽)")
        value_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #4a6fa5;")
        value_header.setAlignment(Qt.AlignRight)
        value_header.setCursor(Qt.PointingHandCursor)
        value_header.setToolTip("Нажмите для сортировки по стоимости")
        value_header.mousePressEvent = lambda e: self._sort_metals_by('value')
        value_header.setMinimumWidth(100)
        
        weight_header = QLabel("Вес (г)")
        weight_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #4a6fa5;")
        weight_header.setAlignment(Qt.AlignRight)
        weight_header.setCursor(Qt.PointingHandCursor)
        weight_header.setToolTip("Нажмите для сортировки по весу")
        weight_header.mousePressEvent = lambda e: self._sort_metals_by('weight')
        weight_header.setMinimumWidth(70)
        
        layout.addWidget(name_header, row, 0, Qt.AlignLeft)
        layout.addWidget(coins_header, row, 1, Qt.AlignRight)
        layout.addWidget(value_header, row, 2, Qt.AlignRight)
        layout.addWidget(weight_header, row, 3, Qt.AlignRight)
        row += 1
        
        # Данные
        for data in metals_data:
            name_label = QLabel(data['name'])
            name_label.setStyleSheet(f"font-weight: bold; color: {data['color']}; font-size: 11px;")
            name_label.setWordWrap(False)
            name_label.setMinimumWidth(140)
            name_label.setFixedWidth(140)
            name_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(name_label, row, 0)
            
            coins_label = QLabel(f"{data['coins']}")
            coins_label.setStyleSheet("color: #666; font-size: 10px;")
            coins_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(coins_label, row, 1)
            
            value_text = f"{data['value']:,.0f}".replace(',', ' ')
            value_label = QLabel(value_text)
            value_label.setStyleSheet("font-weight: bold; color: #28a745; font-size: 11px;")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(value_label, row, 2)
            
            weight_text = f"{data['weight']:,.2f}".replace(',', ' ')
            weight_label = QLabel(weight_text)
            weight_label.setStyleSheet("color: #9b59b6; font-size: 10px;")
            weight_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            weight_label.setMinimumWidth(70)  # Добавлено
            layout.addWidget(weight_label, row, 3)
            
            row += 1
        
        # Разделитель
        if row > 1:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            layout.addWidget(separator, row, 0, 1, 4)
            row += 1
        
        # Общая стоимость
        total_value = gold_total + silver_total + other_total
        total_label = QLabel("💰 Итого:")
        total_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(total_label, row, 0, 1, 2)
        
        total_value_text = f"{total_value:,.0f}".replace(',', ' ')
        total_value_label = QLabel(f"{total_value_text} ₽")
        total_value_label.setStyleSheet("font-weight: bold; color: #28a745; font-size: 13px;")
        total_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(total_value_label, row, 2)
        
        # Общий вес
        total_weight = gold_weight + silver_weight + other_weight
        total_weight_text = f"{total_weight:,.2f}".replace(',', ' ')
        total_weight_label = QLabel(f"{total_weight_text} г")
        total_weight_label.setStyleSheet("font-weight: bold; color: #9b59b6; font-size: 12px;")
        total_weight_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(total_weight_label, row, 3)
        
        # Настройка ширины колонок
        layout.setColumnMinimumWidth(0, 140)
        layout.setColumnMinimumWidth(1, 45)
        layout.setColumnMinimumWidth(2, 110)
        layout.setColumnMinimumWidth(3, 80)
        
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 0)
        
        # Принудительно обновляем группу
        self.main_stats_group.updateGeometry()
        self.main_stats_group.update()

    def _update_value_table(self, value_data):
        """Обновляет таблицу стоимости металлов"""
        if not value_data:
            self.value_table.setRowCount(0)
            return
        
        self.value_table.setSortingEnabled(False)
        self.value_table.setRowCount(len(value_data))
        
        for row, data in enumerate(value_data):
            name_item = QTableWidgetItem(data['name'])
            name_item.setForeground(QColor(self._get_metal_color(data['name'])))
            self.value_table.setItem(row, 0, name_item)
            
            count_item = NumericTableWidgetItem(data['coin_count'], str(data['coin_count']))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.value_table.setItem(row, 1, count_item)
            
            value_item = NumericTableWidgetItem(data['value'], f"{data['value']:,.2f}")
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_item.setForeground(QColor("#28a745"))
            self.value_table.setItem(row, 2, value_item)
        
        self.value_table.setSortingEnabled(True)
        self.value_table.sortItems(2, Qt.DescendingOrder)
    
    def _get_metal_color(self, metal_name):
        metal_name_lower = metal_name.lower()
        if 'золото' in metal_name_lower:
            return '#FFD700'
        elif 'серебро' in metal_name_lower:
            return '#C0C0C0'
        else:
            return '#4a6fa5'
    
    def _calculate_statistics(self, countries):
        """Рассчитывает статистику для списка стран (только количество)"""
        stats = {
            'total_countries': len(countries),
            'total_coins': 0,
            'in_collection': 0,
            'want': 0,
            'sold': 0,
            'lost': 0,
            'total_value': 0,
            'countries_data': []
        }
        
        for country in countries:
            try:
                coins = self.db_manager.session.query(Coin).filter_by(country_id=country.id).all()
                
                country_coins = len(coins)
                country_in_collection = sum(1 for c in coins if c.status == 'in_collection')
                country_want = sum(1 for c in coins if c.status == 'want')
                country_sold = sum(1 for c in coins if c.status == 'sold')
                country_lost = sum(1 for c in coins if c.status == 'lost')
                country_value = sum(c.purchase_price or 0 for c in coins if c.status == 'in_collection')
                
                stats['total_coins'] += country_coins
                stats['in_collection'] += country_in_collection
                stats['want'] += country_want
                stats['sold'] += country_sold
                stats['lost'] += country_lost
                stats['total_value'] += country_value
                
                stats['countries_data'].append({
                    'name': country.name,
                    'coins': country_coins,
                    'in_collection': country_in_collection
                })
                
            except Exception as e:
                self.logger.error(f"Ошибка при расчете статистики для страны {country.name}: {e}")
        
        return stats
    
    def _update_statistics_display(self, stats):
        """Обновляет отображение основной статистики"""
        try:
            if hasattr(self, 'stats_total_countries') and self.stats_total_countries is not None:
                self.stats_total_countries.setText(str(stats['total_countries']))
            if hasattr(self, 'stats_total_coins') and self.stats_total_coins is not None:
                self.stats_total_coins.setText(str(stats['total_coins']))
            if hasattr(self, 'stats_in_collection') and self.stats_in_collection is not None:
                self.stats_in_collection.setText(str(stats['in_collection']))
            if hasattr(self, 'stats_want') and self.stats_want is not None:
                self.stats_want.setText(str(stats['want']))
            if hasattr(self, 'stats_sold') and self.stats_sold is not None:
                self.stats_sold.setText(str(stats['sold']))
            if hasattr(self, 'stats_lost') and self.stats_lost is not None:
                self.stats_lost.setText(str(stats['lost']))
            if hasattr(self, 'stats_total_value') and self.stats_total_value is not None:
                self.stats_total_value.setText(f"{stats['total_value']:.2f} ₽")
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении статистики: {e}")
    
    def _fill_continent_stats_with_value(self, countries, target_date):
        """Заполняет таблицу распределения по континентам (стоимость)"""
        if not self.continent_stats_table or self.continent_stats_table.isHidden():
            return
        
        try:
            all_coins = self.db_manager.session.query(Coin).filter(
                Coin.weight.isnot(None),
                Coin.weight > 0,
                Coin.metal_id.isnot(None),
                Coin.purchase_date.isnot(None),
                Coin.purchase_date <= target_date
            ).all()
            
            coins_by_country = {}
            for coin in all_coins:
                if coin.country_id not in coins_by_country:
                    coins_by_country[coin.country_id] = []
                coins_by_country[coin.country_id].append(coin)
            
            continent_data = {}
            total_value = 0
            total_weight = 0
            
            for country in countries:
                continent = country.continent or "Не указан"
                coins = coins_by_country.get(country.id, [])
                
                if not coins:
                    continue
                
                if continent not in continent_data:
                    continent_data[continent] = {
                        'value': 0,
                        'weight': 0,
                        'color': self.CONTINENT_COLORS.get(continent, "#95a5a6")
                    }
                
                country_value = 0
                country_weight = 0
                
                for coin in coins:
                    metal = self.db_manager.session.query(Metal).get(coin.metal_id)
                    if not metal:
                        continue
                    
                    price_entry = self.db_manager.session.query(MetalPriceHistory).filter_by(
                        metal_id=metal.id,
                        date=target_date
                    ).first()
                    
                    if not price_entry:
                        continue
                    
                    metal_purity = metal.get_purity_decimal()
                    metal_weight = coin.weight * metal_purity
                    coin_value = metal_weight * price_entry.close_price
                    
                    country_value += coin_value
                    country_weight += metal_weight
                
                continent_data[continent]['value'] += country_value
                continent_data[continent]['weight'] += country_weight
                total_value += country_value
                total_weight += country_weight
            
            sorted_continents = sorted(continent_data.items(), key=lambda x: x[1]['value'], reverse=True)
            
            self.continent_stats_table.setRowCount(len(sorted_continents))
            self.continent_stats_table.setSortingEnabled(False)
            
            for row, (continent, data) in enumerate(sorted_continents):
                continent_item = QTableWidgetItem(continent)
                continent_item.setForeground(QColor(data['color']))
                continent_item.setFont(QFont("", -1, QFont.Bold))
                self.continent_stats_table.setItem(row, 0, continent_item)
                
                value_text = f"{data['value']:,.0f} ₽" if data['value'] > 0 else "0 ₽"
                value_item = QTableWidgetItem(value_text)
                value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if data['value'] > 0:
                    value_item.setForeground(QColor("#28a745"))
                self.continent_stats_table.setItem(row, 1, value_item)
                
                if total_value > 0:
                    percent = (data['value'] / total_value) * 100
                    percent_text = f"{percent:.1f}%"
                else:
                    percent_text = "0%"
                percent_item = QTableWidgetItem(percent_text)
                percent_item.setTextAlignment(Qt.AlignCenter)
                if data['value'] > 0:
                    percent_item.setForeground(QColor("#4a6fa5"))
                self.continent_stats_table.setItem(row, 2, percent_item)
                
                weight_text = f"{data['weight']:,.2f} г".replace(',', ' ')
                weight_item = QTableWidgetItem(weight_text)
                weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if data['weight'] > 0:
                    weight_item.setForeground(QColor("#9b59b6"))
                self.continent_stats_table.setItem(row, 3, weight_item)
            
            self.continent_stats_table.setSortingEnabled(True)
            
        except Exception as e:
            self.logger.error(f"Ошибка при заполнении статистики по континентам: {e}")
    
    def _fill_continent_stats_with_count(self, countries, total_coins):
        """Заполняет таблицу распределения по континентам (количество)"""
        if not self.continent_stats_table or self.continent_stats_table.isHidden():
            return
        
        try:
            continents_data = {}
            
            for country in countries:
                continent = country.continent or "Не указан"
                
                if continent not in continents_data:
                    continents_data[continent] = {
                        'coins': 0,
                        'color': self.CONTINENT_COLORS.get(continent, "#95a5a6")
                    }
                
                coins_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                continents_data[continent]['coins'] += coins_count
            
            sorted_continents = sorted(continents_data.items(), key=lambda x: x[1]['coins'], reverse=True)
            
            self.continent_stats_table.setRowCount(len(sorted_continents))
            self.continent_stats_table.setSortingEnabled(False)
            
            for row, (continent, data) in enumerate(sorted_continents):
                continent_item = QTableWidgetItem(continent)
                continent_item.setForeground(QColor(data['color']))
                continent_item.setFont(QFont("", -1, QFont.Bold))
                self.continent_stats_table.setItem(row, 0, continent_item)
                
                coins_item = QTableWidgetItem(str(data['coins']))
                coins_item.setTextAlignment(Qt.AlignCenter)
                if data['coins'] > 0:
                    coins_item.setForeground(QColor("#28a745"))
                self.continent_stats_table.setItem(row, 1, coins_item)
                
                if total_coins > 0:
                    percent = (data['coins'] / total_coins) * 100
                    percent_text = f"{percent:.1f}%"
                else:
                    percent_text = "0%"
                percent_item = QTableWidgetItem(percent_text)
                percent_item.setTextAlignment(Qt.AlignCenter)
                if data['coins'] > 0:
                    percent_item.setForeground(QColor("#4a6fa5"))
                self.continent_stats_table.setItem(row, 2, percent_item)
                
                weight_item = QTableWidgetItem("—")
                weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.continent_stats_table.setItem(row, 3, weight_item)
            
            self.continent_stats_table.setSortingEnabled(True)
            
        except Exception as e:
            self.logger.error(f"Ошибка при заполнении статистики по континентам: {e}")
    
    def _fill_countries_table(self, countries):
        """Заполняет таблицу стран для континента"""
        try:
            if not hasattr(self, 'countries_table') or self.countries_table is None:
                return
            
            countries_data = []
            total_coins_in_continent = 0
            
            for country in countries:
                try:
                    coins_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                    total_coins_in_continent += coins_count
                except Exception as e:
                    self.logger.error(f"Ошибка при подсчете монет для страны {country.name}: {e}")
            
            for country in countries:
                try:
                    coins_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                    
                    if total_coins_in_continent > 0:
                        percent = (coins_count / total_coins_in_continent) * 100
                    else:
                        percent = 0
                    
                    countries_data.append({
                        'name': country.name,
                        'coins': coins_count,
                        'percent': percent,
                        'is_extinct': country.is_extinct
                    })
                except Exception as e:
                    self.logger.error(f"Ошибка при получении данных для страны {country.name}: {e}")
                    countries_data.append({
                        'name': country.name,
                        'coins': 0,
                        'percent': 0,
                        'is_extinct': country.is_extinct
                    })
            
            countries_data.sort(key=lambda x: x['coins'], reverse=True)
            
            self.countries_table.setColumnCount(3)
            self.countries_table.setHorizontalHeaderLabels(["Страна", "Монет", "%"])
            self.countries_table.setRowCount(len(countries_data))
            self.countries_table.setSortingEnabled(False)
            
            for row, data in enumerate(countries_data):
                name_text = data['name']
                if data['is_extinct']:
                    name_text = f"💀 {name_text}"
                
                name_item = QTableWidgetItem(name_text)
                if data['is_extinct']:
                    name_item.setForeground(Qt.gray)
                self.countries_table.setItem(row, 0, name_item)
                
                coins_item = QTableWidgetItem(str(data['coins']))
                coins_item.setTextAlignment(Qt.AlignCenter)
                if data['coins'] > 0:
                    coins_item.setForeground(QColor("#28a745"))
                self.countries_table.setItem(row, 1, coins_item)
                
                percent_item = QTableWidgetItem(f"{data['percent']:.1f}%")
                percent_item.setTextAlignment(Qt.AlignCenter)
                if data['percent'] > 0:
                    percent_item.setForeground(QColor("#4a6fa5"))
                self.countries_table.setItem(row, 2, percent_item)
            
            self.countries_table.setSortingEnabled(True)
            
            header = self.countries_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            
        except Exception as e:
            self.logger.error(f"Ошибка при заполнении таблицы стран: {e}")
    
    def _fill_extinct_countries_table(self, countries):
        """Заполняет таблицу исчезнувших стран для континента"""
        try:
            countries_data = []
            total_coins_in_continent = 0
            
            for country in countries:
                try:
                    coins_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                    total_coins_in_continent += coins_count
                except Exception as e:
                    self.logger.error(f"Ошибка при подсчете монет для страны {country.name}: {e}")
            
            for country in countries:
                try:
                    coins_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                    
                    if total_coins_in_continent > 0:
                        percent = (coins_count / total_coins_in_continent) * 100
                    else:
                        percent = 0
                    
                    countries_data.append({
                        'name': country.name,
                        'coins': coins_count,
                        'percent': percent
                    })
                except Exception as e:
                    self.logger.error(f"Ошибка при получении данных для страны {country.name}: {e}")
                    countries_data.append({
                        'name': country.name,
                        'coins': 0,
                        'percent': 0
                    })
            
            countries_data.sort(key=lambda x: x['coins'], reverse=True)
            
            self.countries_table.setColumnCount(3)
            self.countries_table.setHorizontalHeaderLabels(["Страна", "Монет", "%"])
            self.countries_table.setRowCount(len(countries_data))
            self.countries_table.setSortingEnabled(False)
            
            for row, data in enumerate(countries_data):
                name_item = QTableWidgetItem(f"💀 {data['name']}")
                name_item.setForeground(Qt.gray)
                self.countries_table.setItem(row, 0, name_item)
                
                coins_item = QTableWidgetItem(str(data['coins']))
                coins_item.setTextAlignment(Qt.AlignCenter)
                if data['coins'] > 0:
                    coins_item.setForeground(QColor("#28a745"))
                self.countries_table.setItem(row, 1, coins_item)
                
                percent_item = QTableWidgetItem(f"{data['percent']:.1f}%")
                percent_item.setTextAlignment(Qt.AlignCenter)
                if data['percent'] > 0:
                    percent_item.setForeground(QColor("#4a6fa5"))
                self.countries_table.setItem(row, 2, percent_item)
            
            self.countries_table.setSortingEnabled(True)
            
            header = self.countries_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            
        except Exception as e:
            self.logger.error(f"Ошибка при заполнении таблицы исчезнувших стран: {e}")
    
    def update_continent_stats_headers(self, mode='value'):
        """Обновляет заголовки таблицы распределения по континентам"""
        if not self.continent_stats_table or self.continent_stats_table.isHidden():
            return
        
        try:
            if mode == 'value':
                headers = ["Континент", "Стоимость (₽)", "%", "Вес (г)"]
                widths = [90, 100, 60, 80]
            else:
                headers = ["Континент", "Количество", "%", "Вес (г)"]
                widths = [90, 80, 60, 80]
            
            self.continent_stats_table.setHorizontalHeaderLabels(headers)
            
            header = self.continent_stats_table.horizontalHeader()
            for i, width in enumerate(widths):
                self.continent_stats_table.setColumnWidth(i, width)
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                
        except RuntimeError:
            pass