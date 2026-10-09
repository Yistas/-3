# ===== gui/widgets/statistics_tab.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Вкладка со статистикой и аналитикой коллекции с интерактивными графиками Plotly
"""

import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QComboBox, QGroupBox, QFrame,
                               QMessageBox, QApplication, QSizePolicy,
                               QRadioButton, QButtonGroup)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QFont

# Импорт для WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

# import plotly.graph_objects as go
# import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from database.models import Coin, Country, Metal, MetalPriceHistory, MarketPriceHistory
from .plotly_loader import PlotlyLoader


class StatisticsTab(QWidget):
    """Вкладка со статистикой коллекции с интерактивными графиками Plotly"""
    
    # Цвета для графиков
    COLORS = ['#4a6fa5', '#e67e22', '#27ae60', '#f1c40f', '#9b59b6', 
              '#e74c3c', '#3498db', '#1abc9c', '#f39c12', '#d35400']
    
    # Доступные параметры для оси X
    AXIS_X_OPTIONS = {
        'century': 'Век',
        'decade': 'Десятилетие',
        'year': 'Год',
        'country': 'Страна',
        'continent': 'Континент',
        'metal': 'Металл',
        'mint': 'Монетный двор',
        'condition': 'Сохранность',
        'rarity': 'Редкость',
        'shape': 'Форма',
        'storage_location': 'Альбом',
        'issue_type': 'Тип выпуска',
        'avrev': 'АВ/РЕВ',
        'purchase_where': 'Где куплена',
        'purchase_country': 'Страна покупки',
        'acquisition_type': 'Тип приобретения',
        'purchase_date': 'Дата покупки (накопительный)',
        'status': 'Статус',
    }
    
    # Доступные параметры для оси Y
    AXIS_Y_OPTIONS = {
        'count': 'Количество монет',
        'weight': 'Вес (г)',
        'pure_weight': 'Чистый вес металла (г)',
        'metal_value': 'Стоимость металла (₽)',
        'market_price': 'Рыночная цена (₽)',
        'purchase_price': 'Цена покупки (₽)',
    }
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.StatisticsTab')
        
        self.current_html_file = None
        self._temp_html_files = []
        self.current_data = None
        self.current_fig = None
        
        # Параметры сортировки
        self.sort_by = 'x'  # 'x' или 'y'
        self.sort_order = 'asc'  # 'asc' или 'desc'
        
        # Параметры отображения
        self.limit = None  # None - все, 10 - топ-10, 20 - топ-20
        
        self.init_ui()
        self.load_data()

    def _get_theme(self):
        """Возвращает словарь текущей темы (поднимаясь к главному окну)"""
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                return tm.current_theme
            w = w.parent()
        return {}

    def _is_dark(self):
        """Возвращает True, если текущая тема тёмная"""
        return self._get_theme().get('type', 'dark') == 'dark'
    
    def init_ui(self):
        """Инициализация интерфейса (тёмная тема)"""
        t = self._get_theme()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)

        # Заголовок — тёмный, приглушённый
        title_label = QLabel("📊 Статистика коллекции")
        title_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            background-color: {t.get('surface', '#16213e')};
            color: {t.get('accent', '#6c63ff')};
            border: 1px solid {t.get('border', '#2a2a4a')};
            border-radius: 6px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Панель выбора осей и сортировки
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)

        # График
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(500)
            self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.web_view.page().setBackgroundColor(Qt.transparent)
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            layout.addWidget(self.web_view)
            layout.setStretchFactor(self.web_view, 1)
        else:
            warning_label = QLabel(
                "⚠️ PySide6-WebEngine не установлен.\n"
                "Графики Plotly не будут отображаться.\n"
                "Установите: pip install PySide6-WebEngine"
            )
            warning_label.setAlignment(Qt.AlignCenter)
            warning_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(warning_label)

        # Статус бар — тёмный
        self.status_bar = QFrame()
        self.status_bar.setFrameShape(QFrame.StyledPanel)
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('base', '#1a1a2e')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 4px;
            }}
        """)
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(5, 2, 5, 2)
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet(f"color: {t.get('tab_text', '#8888aa')};")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {t.get('tab_text', '#8888aa')};")
        status_layout.addWidget(self.stats_label)
        self.status_bar.setLayout(status_layout)
        layout.addWidget(self.status_bar)
 
    def _create_control_panel(self):
        """Создает панель управления с выбором осей, сортировки и лимита (тёмная тема)"""
        t = self._get_theme()
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('base', '#1a1a2e')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 6px;
                padding: 5px;
            }}
            QLabel {{
                color: {t.get('text', '#e4e4ef')};
            }}
        """)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(8, 5, 8, 5)

        # ПЕРВАЯ СТРОКА: Оси X и Y
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("Ось X:"))
        self.x_combo = QComboBox()
        self.x_combo.setMinimumWidth(180)
        for key, name in self.AXIS_X_OPTIONS.items():
            self.x_combo.addItem(name, key)
        self.x_combo.setCurrentIndex(0)
        self.x_combo.currentIndexChanged.connect(self.on_axis_changed)
        x_layout.addWidget(self.x_combo)
        row1.addLayout(x_layout)

        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Ось Y:"))
        self.y_combo = QComboBox()
        self.y_combo.setMinimumWidth(160)
        for key, name in self.AXIS_Y_OPTIONS.items():
            self.y_combo.addItem(name, key)
        self.y_combo.setCurrentIndex(0)
        self.y_combo.currentIndexChanged.connect(self.on_axis_changed)
        y_layout.addWidget(self.y_combo)
        row1.addLayout(y_layout)

        # Чекбоксы фильтрации металлов
        metal_layout = QHBoxLayout()
        metal_layout.setSpacing(15)
        metal_label = QLabel("Металл:")
        metal_label.setStyleSheet(f"font-weight: bold; color: {t.get('accent', '#6c63ff')};")
        metal_layout.addWidget(metal_label)

        self.metal_filter_group = QButtonGroup(self)
        self.metal_filter_group.setExclusive(True)
        self.metal_all_radio = QRadioButton("Все")
        self.metal_all_radio.setChecked(True)
        self.metal_all_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_all_radio)
        metal_layout.addWidget(self.metal_all_radio)

        self.metal_precious_radio = QRadioButton("🥇🥈 Драг. металлы")
        self.metal_precious_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_precious_radio)
        metal_layout.addWidget(self.metal_precious_radio)

        self.metal_non_precious_radio = QRadioButton("⚙️ Не драг.")
        self.metal_non_precious_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_non_precious_radio)
        metal_layout.addWidget(self.metal_non_precious_radio)

        row1.addLayout(metal_layout)
        row1.addStretch()
        main_layout.addLayout(row1)

        # ВТОРАЯ СТРОКА: Сортировка и лимит
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Сортировка:"))
        self.sort_axis_group = QButtonGroup(self)
        self.sort_x_radio = QRadioButton("По оси X")
        self.sort_x_radio.setChecked(True)
        self.sort_axis_group.addButton(self.sort_x_radio)
        sort_layout.addWidget(self.sort_x_radio)

        self.sort_y_radio = QRadioButton("По оси Y")
        self.sort_axis_group.addButton(self.sort_y_radio)
        sort_layout.addWidget(self.sort_y_radio)
        sort_layout.addWidget(QLabel("  "))

        self.sort_order_group = QButtonGroup(self)
        self.sort_asc_btn = QPushButton("▲")
        self.sort_asc_btn.setFixedSize(30, 26)
        self.sort_asc_btn.setCheckable(True)
        self.sort_asc_btn.setChecked(True)
        self.sort_asc_btn.setToolTip("По возрастанию")
        self.sort_asc_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #2c4a75;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.sort_asc_btn.clicked.connect(self.on_sort_changed)
        self.sort_order_group.addButton(self.sort_asc_btn)
        sort_layout.addWidget(self.sort_asc_btn)

        self.sort_desc_btn = QPushButton("▼")
        self.sort_desc_btn.setFixedSize(30, 26)
        self.sort_desc_btn.setCheckable(True)
        self.sort_desc_btn.setToolTip("По убыванию")
        self.sort_desc_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #5a6268;
            }
            QPushButton:hover {
                background-color: #7a8288;
            }
        """)
        self.sort_desc_btn.clicked.connect(self.on_sort_changed)
        self.sort_order_group.addButton(self.sort_desc_btn)
        sort_layout.addWidget(self.sort_desc_btn)
        row2.addLayout(sort_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(2)
        row2.addWidget(separator)

        # Лимит
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Показать:"))
        self.all_btn = QPushButton("Все")
        self.all_btn.setFixedSize(40, 28)
        self.all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.all_btn.clicked.connect(lambda: self.set_limit(None))
        limit_layout.addWidget(self.all_btn)

        self.top10_btn = QPushButton("Топ 10")
        self.top10_btn.setFixedSize(60, 28)
        self.top10_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.top10_btn.clicked.connect(lambda: self.set_limit(10))
        limit_layout.addWidget(self.top10_btn)

        self.top20_btn = QPushButton("Топ 20")
        self.top20_btn.setFixedSize(60, 28)
        self.top20_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.top20_btn.clicked.connect(lambda: self.set_limit(20))
        limit_layout.addWidget(self.top20_btn)
        row2.addLayout(limit_layout)
        row2.addStretch()

        # Кнопка обновления
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn.setMinimumHeight(30)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        row2.addWidget(self.refresh_btn)
        main_layout.addLayout(row2)
        panel.setLayout(main_layout)
        return panel

    def set_limit(self, limit):
        """Устанавливает лимит отображаемых категорий"""
        self.limit = limit
        
        # Обновляем стиль кнопок
        self.all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """ if limit is None else """
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        self.top10_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """ if limit == 10 else """
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        self.top20_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """ if limit == 20 else """
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        self.load_data()
    
    def on_axis_changed(self):
        """Обработчик изменения оси"""
        self.load_data()
    
    def on_sort_changed(self):
        """Обработчик изменения параметров сортировки"""
        self.sort_by = 'x' if self.sort_x_radio.isChecked() else 'y'
        self.sort_order = 'asc' if self.sort_asc_btn.isChecked() else 'desc'
        self.load_data()
    
    def save_chart(self):
        """Сохраняет текущий график в файл"""
        if not hasattr(self, '_current_fig') or self._current_fig is None:
            QMessageBox.warning(self, "Предупреждение", "Нет графика для сохранения")
            return
        
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить график",
            f"statistics_chart.html",
            "HTML files (*.html);;PNG files (*.png)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.png'):
                    self._current_fig.write_image(file_path, width=1200, height=800, scale=2)
                else:
                    PlotlyLoader.write_fig(self._current_fig, file_path)
                
                QMessageBox.information(self, "Успех", f"График сохранён:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить график:\n{e}")
    
    def load_data(self):
        """Загружает данные и строит график в зависимости от выбранных осей"""
        try:
            # Проверяем, что WebView существует и инициализирован
            if not hasattr(self, 'web_view') or self.web_view is None:
                self.logger.error("WebView не инициализирован")
                self.status_label.setText("❌ WebView не инициализирован")
                return
            
            self.status_label.setText("⏳ Загрузка данных...")
            QApplication.processEvents()
            
            x_key = self.x_combo.currentData()
            y_key = self.y_combo.currentData()
            x_name = self.x_combo.currentText()
            y_name = self.y_combo.currentText()
            
            self.logger.info(f"Построение графика: X={x_key}, Y={y_key}")
            
            # Получаем все монеты с учетом фильтра по металлам
            all_coins = self.db_manager.session.query(Coin)
            
            # Применяем фильтр по металлам
            if self.metal_precious_radio.isChecked():
                metal_ids = []
                metals = self.db_manager.session.query(Metal).all()
                for metal in metals:
                    name_lower = metal.name.lower()
                    if any(kw in name_lower for kw in ['золото', 'gold', 'серебро', 'silver', 'платина', 'platinum', 'палладий', 'palladium']):
                        metal_ids.append(metal.id)
                if metal_ids:
                    all_coins = all_coins.filter(Coin.metal_id.in_(metal_ids))
                else:
                    all_coins = all_coins.filter(False)
            elif self.metal_non_precious_radio.isChecked():
                metal_ids = []
                metals = self.db_manager.session.query(Metal).all()
                for metal in metals:
                    name_lower = metal.name.lower()
                    if not any(kw in name_lower for kw in ['золото', 'gold', 'серебро', 'silver', 'платина', 'platinum', 'палладий', 'palladium']):
                        metal_ids.append(metal.id)
                if metal_ids:
                    all_coins = all_coins.filter(Coin.metal_id.in_(metal_ids))
                else:
                    all_coins = all_coins.filter(False)
            
            all_coins = all_coins.all()
            
            if not all_coins:
                self.show_empty_chart("Нет данных в коллекции")
                self.status_label.setText("📭 Нет данных")
                return
            
            # Получаем последние цены металлов для расчета стоимости
            last_price_date = self.db_manager.session.query(
                MetalPriceHistory.date
            ).order_by(MetalPriceHistory.date.desc()).first()
            
            metal_prices = {}
            if last_price_date:
                target_date = last_price_date[0]
                metals = self.db_manager.session.query(Metal).all()
                for metal in metals:
                    price_entry = self.db_manager.session.query(MetalPriceHistory).filter_by(
                        metal_id=metal.id, date=target_date
                    ).first()
                    if price_entry:
                        metal_prices[metal.id] = price_entry.close_price
            
            # Группируем данные по оси X
            grouped_data = defaultdict(lambda: {
                'count': 0,
                'weight': 0.0,
                'pure_weight': 0.0,
                'metal_value': 0.0,
                'market_price': 0.0,
                'purchase_price': 0.0
            })
            
            for coin in all_coins:
                x_value = self._get_x_value(coin, x_key)
                if not x_value:
                    x_value = "Не указано"
                
                grouped_data[x_value]['count'] += 1
                
                if coin.weight:
                    grouped_data[x_value]['weight'] += coin.weight
                    
                    if coin.metal_id and coin.metal_id in metal_prices:
                        metal = self.db_manager.session.query(Metal).get(coin.metal_id)
                        if metal:
                            purity = metal.get_purity_decimal()
                            pure_weight = coin.weight * purity
                            grouped_data[x_value]['pure_weight'] += pure_weight
                            grouped_data[x_value]['metal_value'] += pure_weight * metal_prices[coin.metal_id]
                
                if coin.market_price:
                    grouped_data[x_value]['market_price'] += coin.market_price
                
                if coin.purchase_price:
                    grouped_data[x_value]['purchase_price'] += coin.purchase_price
            
            # Специальная обработка для десятилетий
            if x_key == 'decade':
                min_year = None
                max_year = None
                for coin in all_coins:
                    if coin.year:
                        if min_year is None or coin.year < min_year:
                            min_year = coin.year
                        if max_year is None or coin.year > max_year:
                            max_year = coin.year
                
                if min_year and max_year:
                    min_decade = (min_year // 10) * 10
                    max_decade = (max_year // 10) * 10
                    
                    for decade in range(min_decade, max_decade + 1, 10):
                        decade_key = f"{decade}-е гг."
                        if decade_key not in grouped_data:
                            grouped_data[decade_key] = {
                                'count': 0,
                                'weight': 0.0,
                                'pure_weight': 0.0,
                                'metal_value': 0.0,
                                'market_price': 0.0,
                                'purchase_price': 0.0
                            }
            
            # Применяем округление
            for x_value in grouped_data:
                grouped_data[x_value]['weight'] = round(grouped_data[x_value]['weight'], 2)
                grouped_data[x_value]['pure_weight'] = round(grouped_data[x_value]['pure_weight'], 2)
                grouped_data[x_value]['metal_value'] = round(grouped_data[x_value]['metal_value'], 2)
                grouped_data[x_value]['market_price'] = round(grouped_data[x_value]['market_price'], 2)
                grouped_data[x_value]['purchase_price'] = round(grouped_data[x_value]['purchase_price'], 2)
            
            # Накопительный график по дате покупки
            if x_key == 'purchase_date':
                sorted_items = sorted(grouped_data.items(), key=lambda x: x[0] if x[0] else datetime.min)
                
                cumulative = 0
                values_list = []
                labels_list = []
                for date, data in sorted_items:
                    cumulative += data[y_key]
                    values_list.append(cumulative)
                    labels_list.append(date.strftime("%Y-%m-%d") if date else "Не указана")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=labels_list,
                    y=values_list,
                    mode='lines+markers',
                    name=f'{y_name} (накоплено)',
                    line=dict(color='#4a6fa5', width=2.5),
                    marker=dict(size=4, color='#4a6fa5'),
                    fill='tozeroy',
                    fillcolor='rgba(74, 111, 165, 0.2)'
                ))
                
                if y_key in ['metal_value', 'market_price', 'purchase_price']:
                    y_title = f"{y_name} (₽)"
                elif y_key in ['weight', 'pure_weight']:
                    y_title = f"{y_name} (г)"
                else:
                    y_title = y_name
                
                fig.update_layout(
                    title=dict(
                        text=f'{y_name} по дате покупки (накопительный график)',
                        x=0.5,
                        font=dict(size=16)
                    ),
                    xaxis=dict(
                        title='Дата покупки',
                        tickangle=45,
                        gridcolor='lightgray',
                        gridwidth=0.5
                    ),
                    yaxis=dict(
                        title=y_title,
                        gridcolor='lightgray',
                        gridwidth=0.5
                    ),
                    template='plotly_white',
                    height=500,
                    margin=dict(l=60, r=60, t=80, b=100),
                    hovermode='x unified'
                )
                
                self._show_fig(fig)
                self._current_fig = fig
                self.status_label.setText("✅ Накопительный график построен")
                
                total_value = values_list[-1] if values_list else 0
                if y_key == 'count':
                    self.stats_label.setText(f"📊 Всего: {total_value:,.0f} монет")
                elif y_key in ['metal_value', 'market_price', 'purchase_price']:
                    self.stats_label.setText(f"💰 Всего: {total_value:,.2f} ₽")
                else:
                    self.stats_label.setText(f"⚖️ Всего: {total_value:,.2f} г")
                return
            
            # Сортируем данные
            sorted_items = list(grouped_data.items())
            
            if self.sort_by == 'x':
                if self.sort_order == 'asc':
                    sorted_items.sort(key=lambda x: str(x[0]))
                else:
                    sorted_items.sort(key=lambda x: str(x[0]), reverse=True)
            else:
                if self.sort_order == 'asc':
                    sorted_items.sort(key=lambda x: x[1][y_key])
                else:
                    sorted_items.sort(key=lambda x: x[1][y_key], reverse=True)
            
            if self.limit is not None and len(sorted_items) > self.limit:
                sorted_items = sorted_items[:self.limit]
            
            labels = [item[0] for item in sorted_items]
            values = [item[1][y_key] for item in sorted_items]
            values = [round(v, 2) if isinstance(v, float) else v for v in values]
            
            total_value = sum(values)
            if y_key in ['weight', 'pure_weight', 'metal_value', 'market_price', 'purchase_price']:
                total_value = round(total_value, 2)
            
            # Строим график
            fig = go.Figure()
            
            if x_key == 'year':
                # Для годов - линейный график
                fig.add_trace(go.Scatter(
                    x=labels,
                    y=values,
                    mode='lines+markers',
                    name=y_name,
                    line=dict(color='#4a6fa5', width=2.5),
                    marker=dict(size=6, color='#4a6fa5'),
                    fill='tozeroy',
                    fillcolor='rgba(74, 111, 165, 0.2)',
                    text=[f"{v:,.2f}" if isinstance(v, float) and v % 1 != 0 else f"{v:,.0f}" for v in values],
                    textposition='top center'
                ))
                
                # === ПУНКТИРНЫЕ ЛИНИИ ДЛЯ РАЗДЕЛЕНИЯ ВЕКОВ (ГОДЫ) ===
                if labels:
                    try:
                        numeric_labels = []
                        for l in labels:
                            try:
                                numeric_labels.append(int(l))
                            except (ValueError, TypeError):
                                pass
                        
                        if numeric_labels:
                            min_year = min(numeric_labels)
                            max_year = max(numeric_labels)
                            
                            min_century = ((min_year - 1) // 100) + 1
                            max_century = ((max_year - 1) // 100) + 1
                            
                            roman_centuries = {
                                15: 'XV', 16: 'XVI', 17: 'XVII', 18: 'XVIII',
                                19: 'XIX', 20: 'XX', 21: 'XXI', 22: 'XXII', 23: 'XXIII'
                            }
                            
                            for century in range(min_century, max_century + 1):
                                century_start = (century - 1) * 100 + 1
                                
                                fig.add_vline(
                                    x=century_start,
                                    line_dash="dash",
                                    line_color="gray",
                                    line_width=1,
                                    opacity=0.5
                                )
                                
                                century_label = roman_centuries.get(century, str(century))
                                
                                fig.add_annotation(
                                    x=century_start,
                                    y=1.02,
                                    xref='x',
                                    yref='paper',
                                    text=f"<b>{century_label} в.</b>",
                                    showarrow=False,
                                    font=dict(size=11, color='gray'),
                                    xanchor='left',
                                    xshift=8
                                )
                                
                                if century % 2 == 0:
                                    fig.add_vrect(
                                        x0=(century - 1) * 100 + 1,
                                        x1=century * 100,
                                        fillcolor="gray",
                                        opacity=0.03,
                                        line_width=0
                                    )
                            
                    except Exception as e:
                        self.logger.error(f"Ошибка при добавлении линий веков: {e}")
                
            elif x_key == 'decade':
                # Для десятилетий - столбчатая диаграмма
                bar_colors = []
                color_index = 0
                for val in values:
                    if val > 0:
                        bar_colors.append(self.COLORS[color_index % len(self.COLORS)])
                        color_index += 1
                    else:
                        bar_colors.append('#e0e0e0')
                
                fig.add_trace(go.Bar(
                    x=labels,
                    y=values,
                    marker_color=bar_colors,
                    text=[f"{v:,.2f}" if isinstance(v, float) and v % 1 != 0 else f"{v:,.0f}" if v > 0 else "" for v in values],
                    textposition='outside' if max(values) > 0 else 'none',
                    name=y_name
                ))
                
                # === ПУНКТИРНЫЕ ЛИНИИ И ПОДПИСИ ДЛЯ РАЗДЕЛЕНИЯ ВЕКОВ (ДЕСЯТИЛЕТИЯ) ===
                roman_centuries = {
                    15: 'XV', 16: 'XVI', 17: 'XVII', 18: 'XVIII',
                    19: 'XIX', 20: 'XX', 21: 'XXI', 22: 'XXII', 23: 'XXIII'
                }
                
                # Находим границы веков и первые десятилетия каждого века
                century_info = []
                
                for i, label in enumerate(labels):
                    try:
                        decade_start = int(label.split('-')[0])
                        if decade_start % 100 == 0:
                            century_num = (decade_start // 100) + 1
                            century_info.append((i, decade_start, century_num))
                    except:
                        pass
                
                # Добавляем линии на границах веков
                for mark_idx, decade_start, century_num in century_info:
                    fig.add_vline(
                        x=mark_idx - 0.5,
                        line_dash="dash",
                        line_color="black",
                        line_width=1.5,
                        opacity=0.7
                    )
                
                # Добавляем подписи веков НАД серединой века (третье десятилетие)
                for mark_idx, decade_start, century_num in century_info:
                    century_label = roman_centuries.get(century_num, str(century_num))
                    
                    # Смещаем на третье десятилетие (индекс + 2)
                    annotation_idx = mark_idx + 2
                    
                    if annotation_idx < len(labels):
                        try:
                            check_decade = int(labels[annotation_idx].split('-')[0])
                            check_century = (check_decade // 100) + 1
                            if check_century == century_num:
                                fig.add_annotation(
                                    x=annotation_idx,
                                    y=1.02,
                                    xref='x',
                                    yref='paper',
                                    text=f"<b>{century_label} в.</b>",
                                    showarrow=False,
                                    font=dict(size=11, color='gray'),
                                    xanchor='center'
                                )
                            else:
                                fig.add_annotation(
                                    x=mark_idx,
                                    y=1.02,
                                    xref='x',
                                    yref='paper',
                                    text=f"<b>{century_label} в.</b>",
                                    showarrow=False,
                                    font=dict(size=11, color='gray'),
                                    xanchor='center'
                                )
                        except:
                            fig.add_annotation(
                                x=mark_idx,
                                y=1.02,
                                xref='x',
                                yref='paper',
                                text=f"<b>{century_label} в.</b>",
                                showarrow=False,
                                font=dict(size=11, color='gray'),
                                xanchor='center'
                            )
                    else:
                        fig.add_annotation(
                            x=mark_idx,
                            y=1.02,
                            xref='x',
                            yref='paper',
                            text=f"<b>{century_label} в.</b>",
                            showarrow=False,
                            font=dict(size=11, color='gray'),
                            xanchor='center'
                        )
                
                # Добавляем финальную границу века, если нужно
                if labels and century_info:
                    try:
                        last_label = labels[-1]
                        last_decade_start = int(last_label.split('-')[0])
                        last_decade_end = last_decade_start + 9
                        last_century_num = (last_decade_start // 100) + 1
                        last_century_end = last_century_num * 100
                        
                        if last_decade_end >= last_century_end:
                            next_century_start = last_century_end
                            next_century_num = last_century_num + 1
                            next_century_label = roman_centuries.get(next_century_num, str(next_century_num))
                            
                            for i, label in enumerate(labels):
                                try:
                                    dec_start = int(label.split('-')[0])
                                    if dec_start >= next_century_start:
                                        fig.add_vline(
                                            x=i - 0.5,
                                            line_dash="dash",
                                            line_color="black",
                                            line_width=1.5,
                                            opacity=0.7
                                        )
                                        
                                        annotation_idx = i + 2
                                        if annotation_idx < len(labels):
                                            try:
                                                check_decade = int(labels[annotation_idx].split('-')[0])
                                                check_century = (check_decade // 100) + 1
                                                if check_century == next_century_num:
                                                    fig.add_annotation(
                                                        x=annotation_idx,
                                                        y=1.02,
                                                        xref='x',
                                                        yref='paper',
                                                        text=f"<b>{next_century_label} в.</b>",
                                                        showarrow=False,
                                                        font=dict(size=11, color='gray'),
                                                        xanchor='center'
                                                    )
                                                else:
                                                    fig.add_annotation(
                                                        x=i,
                                                        y=1.02,
                                                        xref='x',
                                                        yref='paper',
                                                        text=f"<b>{next_century_label} в.</b>",
                                                        showarrow=False,
                                                        font=dict(size=11, color='gray'),
                                                        xanchor='center'
                                                    )
                                            except:
                                                fig.add_annotation(
                                                    x=i,
                                                    y=1.02,
                                                    xref='x',
                                                    yref='paper',
                                                    text=f"<b>{next_century_label} в.</b>",
                                                    showarrow=False,
                                                    font=dict(size=11, color='gray'),
                                                    xanchor='center'
                                                )
                                        else:
                                            fig.add_annotation(
                                                x=i,
                                                y=1.02,
                                                xref='x',
                                                yref='paper',
                                                text=f"<b>{next_century_label} в.</b>",
                                                showarrow=False,
                                                font=dict(size=11, color='gray'),
                                                xanchor='center'
                                            )
                                        break
                                except:
                                    pass
                    except:
                        pass
                
            else:
                # Для остальных - столбчатая диаграмма
                fig.add_trace(go.Bar(
                    x=labels,
                    y=values,
                    marker_color=self.COLORS[:len(labels)],
                    text=[f"{v:,.2f}" if isinstance(v, float) and v % 1 != 0 else f"{v:,.0f}" for v in values],
                    textposition='outside' if max(values) > 0 else 'none',
                    name=y_name
                ))
            
            # Настройка оформления
            if y_key in ['metal_value', 'market_price', 'purchase_price']:
                y_title = f"{y_name} (₽)"
            elif y_key in ['weight', 'pure_weight']:
                y_title = f"{y_name} (г)"
            else:
                y_title = y_name
            
            limit_text = ""
            if self.limit == 10:
                limit_text = " (Топ 10)"
            elif self.limit == 20:
                limit_text = " (Топ 20)"
            
            fig.update_layout(
                title=dict(
                    text=f'{y_name} по {x_name.lower()}{limit_text}',
                    x=0.5,
                    font=dict(size=16)
                ),
                xaxis=dict(
                    title=x_name,
                    tickangle=45 if len(labels) > 8 else 0,
                    gridcolor='lightgray',
                    gridwidth=0.5
                ),
                yaxis=dict(
                    title=y_title,
                    gridcolor='lightgray',
                    gridwidth=0.5
                ),
                template='plotly_white',
                height=500,
                margin=dict(l=60, r=60, t=80, b=100),
                hovermode='x unified'
            )
            
            self.status_label.setText("✅ График построен")
            if y_key == 'count':
                self.stats_label.setText(f"📊 Всего: {total_value:,.0f} монет | Категорий: {len(labels)}")
            elif y_key in ['metal_value', 'market_price', 'purchase_price']:
                self.stats_label.setText(f"💰 Всего: {total_value:,.2f} ₽ | Категорий: {len(labels)}")
            else:
                self.stats_label.setText(f"⚖️ Всего: {total_value:,.2f} г | Категорий: {len(labels)}")
            
            self._show_fig(fig)
            self._current_fig = fig
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.show_empty_chart(f"Ошибка загрузки данных:\n{str(e)}")

    def _get_x_value(self, coin, x_key):
        """Возвращает значение для оси X в зависимости от ключа"""
        if x_key == 'century':
            if coin.year:
                century = ((coin.year - 1) // 100) + 1
                if century < 0:
                    return "до н.э."
                return f"{century} в."
            return None
        elif x_key == 'decade':
            if coin.year:
                decade = (coin.year // 10) * 10
                return f"{decade}-е гг."
            return None
        elif x_key == 'year':
            return coin.year
        elif x_key == 'country':
            return coin.country.name if coin.country else None
        elif x_key == 'continent':
            return coin.country.continent if coin.country and coin.country.continent else None
        elif x_key == 'metal':
            if coin.metal_obj:
                return coin.metal_obj.get_display_text()
            return coin.metal
        elif x_key == 'mint':
            if coin.mint_obj:
                return coin.mint_obj.get_display_text()
            return coin.mint
        elif x_key == 'condition':
            if hasattr(coin, 'condition_id') and coin.condition_id and coin.condition_ref:
                return coin.condition_ref.name
            return coin.condition
        elif x_key == 'rarity':
            if hasattr(coin, 'rarity_id') and coin.rarity_id and coin.rarity_ref:
                return coin.rarity_ref.name
            return getattr(coin, 'rarity', None)
        elif x_key == 'shape':
            if hasattr(coin, 'shape_id') and coin.shape_id and coin.shape_ref:
                return coin.shape_ref.name
            return getattr(coin, 'shape', None)
        elif x_key == 'storage_location':
            if hasattr(coin, 'storage_location_id') and coin.storage_location_id and coin.storage_location_ref:
                return coin.storage_location_ref.name
            return getattr(coin, 'storage_location', None)
        elif x_key == 'issue_type':
            if hasattr(coin, 'issue_type_id') and coin.issue_type_id and coin.issue_type_ref:
                return coin.issue_type_ref.name
            return getattr(coin, 'issue_type', None)
        elif x_key == 'avrev':
            if hasattr(coin, 'avrev_id') and coin.avrev_id and coin.avrev_ref:
                return coin.avrev_ref.name
            return getattr(coin, 'avrev', None)
        elif x_key == 'purchase_where':
            return getattr(coin, 'purchase_where', None)
        elif x_key == 'purchase_country':
            if hasattr(coin, 'purchase_country_obj') and coin.purchase_country_obj:
                return coin.purchase_country_obj.name
            return None
        elif x_key == 'acquisition_type':
            if hasattr(coin, 'acquisition_type_id') and coin.acquisition_type_id and coin.acquisition_type_ref:
                return coin.acquisition_type_ref.name
            return getattr(coin, 'acquisition_type', None)
        elif x_key == 'purchase_date':
            if coin.purchase_date:
                return coin.purchase_date
            return None
        elif x_key == 'status':
            if hasattr(coin, 'status_id') and coin.status_id and coin.status_ref:
                return coin.status_ref.name
            status_map = {
                'in_collection': 'В коллекции',
                'want': 'Хочу',
                'sold': 'Продано',
                'lost': 'Утеряна',
                'for_sale': 'На продажу'
            }
            return status_map.get(coin.status, coin.status)
        return None
    
    def _show_fig(self, fig):
        """Отображает график в WebView (с поддержкой тёмной темы)"""
        # Применяем тёмную тему к графику
        if self._is_dark():
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='#1a1a2e',
                plot_bgcolor='#16213e',
                font=dict(color='#e4e4ef'),
            )
            fig.update_xaxes(gridcolor='#2a2a4a', linecolor='#3a3a5a')
            fig.update_yaxes(gridcolor='#2a2a4a', linecolor='#3a3a5a')

        for file in self._temp_html_files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass
        self._temp_html_files.clear()

        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass

        bg_css_color = '#1a1a2e' if self._is_dark() else '#ffffff'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            PlotlyLoader.write_fig(fig, f.name)
            self.current_html_file = f.name
            self._temp_html_files.append(f.name)

        with open(self.current_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        css_to_add = f"""
<style>
html, body {{ margin: 0; padding: 0; overflow: hidden !important; height: 100%; width: 100%; background-color: {bg_css_color}; }}
.plotly-graph-div {{ height: 100%; width: 100%; position: absolute; top: 0; left: 0; }}
.main-svg {{ height: 100% !important; width: 100% !important; }}
</style>
"""
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', css_to_add + '</head>')
        else:
            html_content = css_to_add + html_content

        with open(self.current_html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.web_view.setUrl(QUrl.fromLocalFile(self.current_html_file))

    def show_empty_chart(self, message="Нет данных для отображения"):
        """Показывает пустой график с сообщением"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color="#666")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            template='plotly_white',
            height=500
        )
        self._show_fig(fig)
    
    def closeEvent(self, event):
        """Обработчик закрытия - удаляем временные файлы"""
        for file in self._temp_html_files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass
        self._temp_html_files.clear()
        
        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass
        
        super().closeEvent(event)
        
    def on_metal_filter_changed(self):
        """Обработчик изменения фильтра по металлам"""
        self.load_data()