# -*- coding: utf-8 -*-

"""
Виджет для отображения рыночной стоимости коллекции на основе загруженных цен
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta, date
from collections import defaultdict
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QMessageBox, QDateEdit, QGroupBox,
                               QFrame, QRadioButton, QButtonGroup, QApplication,
                               QSizePolicy, QComboBox, QCheckBox)
from PySide6.QtCore import Qt, QDate, QUrl, QTimer, Signal
from PySide6.QtGui import QColor

# Импорт для WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

import plotly.graph_objects as go

from database.models import Coin, Country, MarketPriceHistory


class MarketValueChart(QWidget):
    """Виджет для отображения рыночной стоимости коллекции"""
    value_updated = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.MarketValueChart')
        
        self.current_data = {}  # {date: total_value}
        self.all_dates = []
        self.continent_data = {}  # {date: {continent: value}}
        self.country_data = {}    # {date: {country: value}}
        self.metal_data = {}      # {date: {metal: value}}
        self.century_data = {}    # {date: {century: value}}
        
        self.current_html_file = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        title = QLabel("📊 Рыночная стоимость коллекции (на основе загруженных цен)")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 5px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Панель расчета
        calc_group = QGroupBox("📊 Параметры")
        calc_layout = QHBoxLayout()
        calc_layout.setSpacing(10)
        calc_layout.setContentsMargins(10, 10, 10, 10)
        
        left_widget = QWidget()
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_widget.setLayout(left_layout)
        
        left_layout.addWidget(QLabel("Период:"))
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate(2026, 4, 7))
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setMaximumWidth(120)
        left_layout.addWidget(self.start_date_edit)
        
        left_layout.addWidget(QLabel("—"))
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setMaximumWidth(120)
        left_layout.addWidget(self.end_date_edit)
        
        self.calc_btn = QPushButton("📊 Рассчитать стоимость")
        self.calc_btn.clicked.connect(self.calculate_value)
        self.calc_btn.setFixedHeight(30)
        left_layout.addWidget(self.calc_btn)
        
        calc_layout.addWidget(left_widget)
        calc_layout.addStretch()
        
        calc_group.setLayout(calc_layout)
        layout.addWidget(calc_group)
        
        # Панель отображения
        display_group = QGroupBox("📈 Отображение")
        display_group.setFixedHeight(130)
        
        display_layout = QVBoxLayout()
        display_layout.setSpacing(5)
        display_layout.setContentsMargins(10, 5, 10, 5)
        
        # Первая строка - тип группировки
        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("Группировка:"))
        
        self.group_group = QButtonGroup(self)
        
        self.total_radio = QRadioButton("📊 Общая стоимость")
        self.total_radio.setChecked(True)
        self.group_group.addButton(self.total_radio)
        group_row.addWidget(self.total_radio)
        
        self.continent_radio = QRadioButton("🌍 По континентам")
        self.group_group.addButton(self.continent_radio)
        group_row.addWidget(self.continent_radio)
        
        self.country_radio = QRadioButton("🏳️ По странам (топ-10)")
        self.group_group.addButton(self.country_radio)
        group_row.addWidget(self.country_radio)
        
        self.metal_radio = QRadioButton("⚙️ По металлам")
        self.group_group.addButton(self.metal_radio)
        group_row.addWidget(self.metal_radio)
        
        self.century_radio = QRadioButton("📅 По векам")
        self.group_group.addButton(self.century_radio)
        group_row.addWidget(self.century_radio)
        
        group_row.addStretch()
        display_layout.addLayout(group_row)
        
        # Вторая строка - фильтр по металлам
        metal_row = QHBoxLayout()
        metal_row.setSpacing(15)
        
        metal_label = QLabel("Металл:")
        metal_label.setStyleSheet("font-weight: bold; color: #4a6fa5;")
        metal_row.addWidget(metal_label)
        
        self.metal_filter_group = QButtonGroup(self)
        self.metal_filter_group.setExclusive(True)
        
        self.metal_all_radio = QRadioButton("Все")
        self.metal_all_radio.setChecked(True)
        self.metal_all_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_all_radio)
        metal_row.addWidget(self.metal_all_radio)
        
        self.metal_precious_radio = QRadioButton("🥇🥈 Драг. металлы")
        self.metal_precious_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_precious_radio)
        metal_row.addWidget(self.metal_precious_radio)
        
        self.metal_non_precious_radio = QRadioButton("⚙️ Не драг.")
        self.metal_non_precious_radio.toggled.connect(self.on_metal_filter_changed)
        self.metal_filter_group.addButton(self.metal_non_precious_radio)
        metal_row.addWidget(self.metal_non_precious_radio)
        
        metal_row.addStretch()
        display_layout.addLayout(metal_row)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # График
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(450)
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
        
        # Статус бар
        self.status_bar = QFrame()
        self.status_bar.setFrameShape(QFrame.StyledPanel)
        self.status_bar.setFixedHeight(30)
        
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(5, 2, 5, 2)
        
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.stats_label)
        
        self.status_bar.setLayout(status_layout)
        layout.addWidget(self.status_bar)
        
        # Подключаем сигналы
        self.total_radio.toggled.connect(self.update_chart)
        self.continent_radio.toggled.connect(self.update_chart)
        self.country_radio.toggled.connect(self.update_chart)
        self.metal_radio.toggled.connect(self.update_chart)
        self.century_radio.toggled.connect(self.update_chart)

    def add_log(self, message, level="info"):
        """Добавляет запись в лог (для совместимости)"""
        self.status_label.setText(message)
        self.logger.info(message)
    
    def calculate_value(self):
        """Рассчитывает рыночную стоимость на основе истории цен"""
        try:
            from database.models import Metal
            
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            
            if start_qdate > end_qdate:
                QMessageBox.warning(self, "Предупреждение", "Начальная дата не может быть позже конечной")
                return
            
            start_date = start_qdate.toPython()
            end_date = end_qdate.toPython()
            
            min_date = datetime(2026, 4, 7).date()
            if start_date < min_date:
                start_date = min_date
                self.start_date_edit.setDate(QDate(2026, 4, 7))
                self.add_log(f"📅 Дата начала скорректирована на 07.04.2026", "info")
            
            self.status_label.setText("⏳ Расчет рыночной стоимости...")
            QApplication.processEvents()
            
            history = self.db_manager.get_market_price_history(
                start_date=start_date,
                end_date=end_date,
                limit=1000000
            )
            
            self.logger.info(f"Получено записей из истории: {len(history)}")
            
            if not history:
                self.status_label.setText("❌ Нет данных за выбранный период")
                QMessageBox.warning(self, "Предупреждение", "Нет данных о рыночных ценах")
                return
            
            # === ФИЛЬТРАЦИЯ ПО МЕТАЛЛАМ ===
            if self.metal_precious_radio.isChecked():
                # Только драгоценные металлы
                metal_ids = set()
                metals = self.db_manager.session.query(Metal).all()
                for metal in metals:
                    name_lower = metal.name.lower()
                    if any(kw in name_lower for kw in ['золото', 'gold', 'серебро', 'silver', 'платина', 'platinum', 'палладий', 'palladium']):
                        metal_ids.add(metal.id)
                
                if metal_ids:
                    filtered_history = []
                    for record in history:
                        coin = self.db_manager.get_coin(record.coin_id)
                        if coin and coin.metal_id in metal_ids:
                            filtered_history.append(record)
                    history = filtered_history
                else:
                    history = []
                    
            elif self.metal_non_precious_radio.isChecked():
                # Только недрагоценные металлы
                precious_ids = set()
                metals = self.db_manager.session.query(Metal).all()
                for metal in metals:
                    name_lower = metal.name.lower()
                    if any(kw in name_lower for kw in ['золото', 'gold', 'серебро', 'silver', 'платина', 'platinum', 'палладий', 'palladium']):
                        precious_ids.add(metal.id)
                
                if precious_ids:
                    filtered_history = []
                    for record in history:
                        coin = self.db_manager.get_coin(record.coin_id)
                        if coin and coin.metal_id and coin.metal_id not in precious_ids:
                            filtered_history.append(record)
                    history = filtered_history
            
            if not history:
                self.status_label.setText("❌ Нет данных за выбранный период с учётом фильтра")
                return
            
            # Группируем по датам
            by_date = defaultdict(list)
            for record in history:
                by_date[record.price_date].append(record)
            
            self.all_dates = sorted(by_date.keys())
            self.logger.info(f"Найдено дат: {len(self.all_dates)}")
            
            # Рассчитываем стоимость по датам
            self.current_data = {}
            self.continent_data = {}
            self.country_data = {}
            self.metal_data = {}
            self.century_data = {}
            
            for dt in self.all_dates:
                records = by_date[dt]
                total = 0
                continents = defaultdict(float)
                countries = defaultdict(float)
                metals_data = defaultdict(float)
                centuries = defaultdict(float)
                
                for record in records:
                    total += record.market_price
                    
                    # Континент
                    continent = "Не указан"
                    coin = self.db_manager.get_coin(record.coin_id)
                    if coin and coin.country:
                        continent = coin.country.continent or "Не указан"
                    continents[continent] += record.market_price
                    
                    # Страна
                    country_name = record.country_name or "Неизвестно"
                    countries[country_name] += record.market_price
                    
                    # Металл
                    metal_name = "Не указан"
                    if coin and coin.metal_obj:
                        metal_name = coin.metal_obj.name
                        if "золото" in metal_name.lower():
                            metal_name = "Золото"
                        elif "серебро" in metal_name.lower():
                            metal_name = "Серебро"
                        elif "медь" in metal_name.lower():
                            metal_name = "Медь"
                        elif "платина" in metal_name.lower():
                            metal_name = "Платина"
                        else:
                            metal_name = "Другие"
                    metals_data[metal_name] += record.market_price
                    
                    # Век
                    if record.year:
                        century_num = (record.year - 1) // 100 + 1
                        century = f"{century_num} в."
                        centuries[century] += record.market_price
                    else:
                        centuries["Не указан"] += record.market_price
                
                self.current_data[dt] = total
                self.continent_data[dt] = dict(continents)
                self.country_data[dt] = dict(countries)
                self.metal_data[dt] = dict(metals_data)
                self.century_data[dt] = dict(centuries)
            
            self.status_label.setText("✅ Расчет завершен")
            if self.current_data:
                max_value = max(self.current_data.values())
                min_value = min(self.current_data.values())
                
                # Определяем текст фильтра для статус-бара
                filter_text = ""
                if self.metal_precious_radio.isChecked():
                    filter_text = " (драг. металлы)"
                elif self.metal_non_precious_radio.isChecked():
                    filter_text = " (недраг. металлы)"
                
                self.stats_label.setText(f"Всего дат: {len(self.all_dates)} | Цены: {min_value:,.0f} - {max_value:,.0f} ₽{filter_text}")
            
            self.update_chart()
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось рассчитать стоимость:\n{e}")

    def update_chart(self):
        """Обновляет график в зависимости от выбранных опций"""
        if not WEBENGINE_AVAILABLE:
            return
        
        if not self.current_data:
            self.show_empty_chart()
            return
        
        # Сортируем даты
        dates = sorted(self.current_data.keys())
        datetime_dates = [datetime.combine(d, datetime.min.time()) for d in dates]
        
        if self.total_radio.isChecked():
            self._show_total_chart(datetime_dates)
        elif self.continent_radio.isChecked():
            self._show_continent_chart(datetime_dates)
        elif self.country_radio.isChecked():
            self._show_country_chart(datetime_dates)
        elif self.metal_radio.isChecked():
            self._show_metal_chart(datetime_dates)
        elif self.century_radio.isChecked():
            self._show_century_chart(datetime_dates)
    
    def _show_total_chart(self, dates):
        """Показывает график общей стоимости (изменение)"""
        values = []
        for dt in dates:
            date_key = dt.date()
            daily_value = self.current_data.get(date_key, 0)
            values.append(daily_value)
        
        if not values:
            self.show_empty_chart()
            return
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            mode='lines+markers',
            name='Рыночная стоимость',
            line=dict(color='#4a6fa5', width=2.5),
            marker=dict(size=6)
        ))
        
        last_value = values[-1] if values else 0
        last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
        
        fig.update_layout(
            title=dict(text=f'📊 Изменение рыночной стоимости коллекции<br><sup>Текущая стоимость: {last_value:,.0f} ₽ на {last_date}</sup>', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)
    
    def _show_continent_chart(self, dates):
        """Показывает график стоимости по континентам"""
        # Собираем все континенты
        all_continents = set()
        for date_data in self.continent_data.values():
            all_continents.update(date_data.keys())
        
        if not all_continents:
            self.show_empty_chart()
            return
        
        continent_colors = {
            "Европа": "#4a6fa5",
            "Азия": "#e67e22",
            "Америка": "#27ae60",
            "Африка": "#f1c40f",
            "Океания": "#9b59b6",
            "Не указан": "#95a5a6"
        }
        
        fig = go.Figure()
        
        for continent in sorted(all_continents):
            values = []
            for dt in dates:
                date_key = dt.date()
                val = self.continent_data.get(date_key, {}).get(continent, 0)
                values.append(val)
            
            color = continent_colors.get(continent, "#4a6fa5")
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name=continent,
                line=dict(color=color, width=2),
                marker=dict(size=4)
            ))
        
        fig.update_layout(
            title=dict(text='🌍 Распределение рыночной стоимости по континентам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)
    
    def _show_country_chart(self, dates):
        """Показывает график стоимости по странам (топ-10)"""
        # Собираем сумму по странам за последнюю дату
        if not self.all_dates:
            self.show_empty_chart()
            return
        
        last_date = self.all_dates[-1]
        last_country_data = self.country_data.get(last_date, {})
        
        if not last_country_data:
            self.show_empty_chart()
            return
        
        # Берем топ-10 по последней дате
        top_countries = sorted(last_country_data.items(), key=lambda x: x[1], reverse=True)[:10]
        top_country_names = [c[0] for c in top_countries]
        
        colors = ['#4a6fa5', '#e67e22', '#27ae60', '#f1c40f', '#9b59b6', 
                  '#e74c3c', '#3498db', '#1abc9c', '#f39c12', '#d35400']
        
        fig = go.Figure()
        
        for i, country in enumerate(top_country_names):
            values = []
            for dt in dates:
                date_key = dt.date()
                val = self.country_data.get(date_key, {}).get(country, 0)
                values.append(val)
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name=country[:25],
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=4)
            ))
        
        fig.update_layout(
            title=dict(text='🏳️ Распределение рыночной стоимости по странам (топ-10)', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)
    
    def _show_metal_chart(self, dates):
        """Показывает график стоимости по металлам"""
        # Собираем все металлы
        all_metals = set()
        for date_data in self.metal_data.values():
            all_metals.update(date_data.keys())
        
        if not all_metals:
            self.show_empty_chart()
            return
        
        metal_colors = {
            "Золото": "#FFD700",
            "Серебро": "#C0C0C0",
            "Медь": "#B87333",
            "Платина": "#E5E4E2",
            "Другие": "#4a6fa5",
            "Не указан": "#95a5a6"
        }
        
        fig = go.Figure()
        
        for metal in sorted(all_metals):
            values = []
            for dt in dates:
                date_key = dt.date()
                val = self.metal_data.get(date_key, {}).get(metal, 0)
                values.append(val)
            
            color = metal_colors.get(metal, "#4a6fa5")
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name=metal,
                line=dict(color=color, width=2),
                marker=dict(size=4)
            ))
        
        fig.update_layout(
            title=dict(text='⚙️ Распределение рыночной стоимости по металлам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)
    
    def _show_century_chart(self, dates):
        """Показывает график стоимости по векам"""
        # Собираем все века
        all_centuries = set()
        for date_data in self.century_data.values():
            all_centuries.update(date_data.keys())
        
        if not all_centuries:
            self.show_empty_chart()
            return
        
        # Сортируем века
        def century_sort_key(century):
            if century == "Не указан":
                return 999
            try:
                return int(century.replace(" в.", ""))
            except:
                return 0
        
        colors = ['#4a6fa5', '#e67e22', '#27ae60', '#f1c40f', '#9b59b6', 
                  '#e74c3c', '#3498db', '#1abc9c', '#f39c12', '#d35400']
        
        fig = go.Figure()
        
        for i, century in enumerate(sorted(all_centuries, key=century_sort_key)):
            values = []
            for dt in dates:
                date_key = dt.date()
                val = self.century_data.get(date_key, {}).get(century, 0)
                values.append(val)
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name=century,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=4)
            ))
        
        fig.update_layout(
            title=dict(text='📅 Распределение рыночной стоимости по векам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)
    
    def _show_fig(self, fig):
        """Отображает график в WebView"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            fig.write_html(f.name, include_plotlyjs='cdn', config={
                'displayModeBar': True, 'responsive': True, 'scrollZoom': True, 'autosizable': True
            })
            self.current_html_file = f.name
        
        with open(self.current_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        css_to_add = """
        <style>
            html, body { margin: 0; padding: 0; overflow: hidden !important; height: 100%; width: 100%; }
            .plotly-graph-div { height: 100%; width: 100%; position: absolute; top: 0; left: 0; }
            .main-svg { height: 100% !important; width: 100% !important; }
        </style>
        """
        
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', css_to_add + '</head>')
        else:
            html_content = css_to_add + html_content
        
        with open(self.current_html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.web_view.setUrl(QUrl.fromLocalFile(self.current_html_file))
    
    def show_empty_chart(self):
        """Показывает пустой график"""
        fig = go.Figure()
        fig.add_annotation(text="Нет данных для отображения.\nЗагрузите рыночные цены через 'Сервисы → Загрузка рыночных цен'",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), template='plotly_white', height=450)
        
        self._show_fig(fig)
    
    def closeEvent(self, event):
        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass
        super().closeEvent(event)
        
    def on_metal_filter_changed(self):
        """Обработчик изменения фильтра по металлам"""
        self.calculate_value()