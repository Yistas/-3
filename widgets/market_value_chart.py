# -*- coding: utf-8 -*-
"""
Виджет рыночной стоимости коллекции.
Расчёт выполняется в фоновом потоке (QThread) с агрегацией в памяти
(один запрос истории + один запрос монет со связями вместо N запросов).
Потоки управляются корректно: быстрый перебор фильтров не роняет программу.
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
from PySide6.QtCore import Qt, QDate, QUrl, QTimer, Signal, QThread
from PySide6.QtGui import QColor

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

import plotly.graph_objects as go
from sqlalchemy.orm import joinedload
from database.models import Coin, Country, MarketPriceHistory

PRECIOUS_KEYWORDS = ('золото', 'gold', 'серебро', 'silver',
                     'платина', 'platinum', 'палладий', 'palladium')


class MarketValueCalcThread(QThread):
    """Фоновый поток расчёта рыночной стоимости (не блокирует UI)"""
    progress = Signal(str)
    finished_ok = Signal(dict)
    error = Signal(str)

    def __init__(self, db_manager, start_date, end_date, metal_filter):
        super().__init__()
        self.db_manager = db_manager
        self.start_date = start_date
        self.end_date = end_date
        self.metal_filter = metal_filter
        self._stop = False

    def stop(self):
        """Мягкая остановка потока"""
        self._stop = True

    def run(self):
        # СВОЯ сессия на поток — не трогаем сессию главного потока
        session = self.db_manager.Session()
        try:
            self._run_inner(session)
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))
        finally:
            session.close()

    def _run_inner(self, session):
        self.progress.emit("⏳ Загрузка истории цен...")
        history = session.query(MarketPriceHistory).filter(
            MarketPriceHistory.price_date >= self.start_date,
            MarketPriceHistory.price_date <= self.end_date
        ).all()
        if self._stop:
            return
        if not history:
            self.finished_ok.emit({'empty': 'Нет данных за выбранный период'})
            return

        # ОДИН запрос на все монеты со связями (вместо N запросов get_coin)
        self.progress.emit("⏳ Загрузка справочника монет...")
        coins = session.query(Coin).options(
            joinedload(Coin.country),
            joinedload(Coin.metal_obj)
        ).all()
        coin_map = {c.id: c for c in coins}
        if self._stop:
            return

        # Фильтр по металлам
        if self.metal_filter in ('precious', 'non_precious'):
            def is_precious(rec):
                c = coin_map.get(rec.coin_id)
                if not c or not c.metal_obj:
                    return False
                n = (c.metal_obj.name or '').lower()
                return any(k in n for k in PRECIOUS_KEYWORDS)
            if self.metal_filter == 'precious':
                history = [r for r in history if is_precious(r)]
            else:
                history = [r for r in history if not is_precious(r)]
            if not history:
                self.finished_ok.emit(
                    {'empty': 'Нет данных за выбранный период с учётом фильтра'})
                return

        self.progress.emit("⏳ Агрегация по датам...")
        by_date = defaultdict(list)
        for rec in history:
            by_date[rec.price_date].append(rec)
        all_dates = sorted(by_date.keys())

        current_data = {}
        continent_data = {}
        country_data = {}
        metal_data = {}
        century_data = {}

        for dt in all_dates:
            if self._stop:
                return
            total = 0
            continents = defaultdict(float)
            countries = defaultdict(float)
            metals_data = defaultdict(float)
            centuries = defaultdict(float)
            for rec in by_date[dt]:
                price = rec.market_price
                total += price
                coin = coin_map.get(rec.coin_id)
                continent = "Не указан"
                if coin and coin.country:
                    continent = coin.country.continent or "Не указан"
                continents[continent] += price
                countries[rec.country_name or "Неизвестно"] += price
                metal_name = "Не указан"
                if coin and coin.metal_obj:
                    ln = coin.metal_obj.name.lower()
                    if "золото" in ln:
                        metal_name = "Золото"
                    elif "серебро" in ln:
                        metal_name = "Серебро"
                    elif "медь" in ln:
                        metal_name = "Медь"
                    elif "платина" in ln:
                        metal_name = "Платина"
                    else:
                        metal_name = "Другие"
                metals_data[metal_name] += price
                if rec.year:
                    centuries[f"{(rec.year - 1) // 100 + 1} в."] += price
                else:
                    centuries["Не указан"] += price
            current_data[dt] = total
            continent_data[dt] = dict(continents)
            country_data[dt] = dict(countries)
            metal_data[dt] = dict(metals_data)
            century_data[dt] = dict(centuries)

        filter_text = ""
        if self.metal_filter == 'precious':
            filter_text = " (драг. металлы)"
        elif self.metal_filter == 'non_precious':
            filter_text = " (недраг. металлы)"
        max_v = max(current_data.values()) if current_data else 0
        min_v = min(current_data.values()) if current_data else 0
        stats = (f"Всего дат: {len(all_dates)} | "
                 f"Цены: {min_v:,.0f} - {max_v:,.0f} ₽{filter_text}")
        self.finished_ok.emit({
            'current_data': current_data,
            'continent_data': continent_data,
            'country_data': country_data,
            'metal_data': metal_data,
            'century_data': century_data,
            'all_dates': all_dates,
            'stats': stats,
        })


class MarketValueChart(QWidget):
    """Виджет для отображения рыночной стоимости коллекции"""
    value_updated = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.MarketValueChart')
        self.current_data = {}
        self.all_dates = []
        self.continent_data = {}
        self.country_data = {}
        self.metal_data = {}
        self.century_data = {}
        self.current_html_file = None
        self._calc_thread = None
        self._filter_timer = None
        self.setup_ui()

    def setup_ui(self):
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

        display_group = QGroupBox("📈 Отображение")
        display_group.setFixedHeight(130)
        display_layout = QVBoxLayout()
        display_layout.setSpacing(5)
        display_layout.setContentsMargins(10, 5, 10, 5)
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

        self.total_radio.toggled.connect(self.update_chart)
        self.continent_radio.toggled.connect(self.update_chart)
        self.country_radio.toggled.connect(self.update_chart)
        self.metal_radio.toggled.connect(self.update_chart)
        self.century_radio.toggled.connect(self.update_chart)

    def add_log(self, message, level="info"):
        self.status_label.setText(message)
        self.logger.info(message)

    # ================= РАСЧЁТ (ФОНОВЫЙ ПОТОК) =================
    def calculate_value(self):
        """Запускает расчёт в фоновом потоке.
        Если предыдущий поток ещё работает — корректно останавливаем и ждём,
        поэтому быстрое переключение фильтров НЕ роняет программу."""
        try:
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            if start_qdate > end_qdate:
                QMessageBox.warning(self, "Предупреждение",
                                    "Начальная дата не может быть позже конечной")
                return
            start_date = start_qdate.toPython()
            end_date = end_qdate.toPython()
            min_date = datetime(2026, 4, 7).date()
            if start_date < min_date:
                start_date = min_date
                self.start_date_edit.setDate(QDate(2026, 4, 7))
                self.add_log("📅 Дата начала скорректирована на 07.04.2026", "info")

            if self.metal_precious_radio.isChecked():
                metal_filter = 'precious'
            elif self.metal_non_precious_radio.isChecked():
                metal_filter = 'non_precious'
            else:
                metal_filter = 'all'

            # === КОРРЕКТНЫЙ ЖИЗНЕННЫЙ ЦИКЛ ПОТОКА ===
            old = self._calc_thread
            if old is not None and old.isRunning():
                old.stop()
                old.wait(5000)  # ждём завершения старого потока

            self._calc_thread = MarketValueCalcThread(
                self.db_manager, start_date, end_date, metal_filter)
            self._calc_thread.progress.connect(self._on_calc_progress)
            self._calc_thread.finished_ok.connect(self._on_calc_finished)
            self._calc_thread.error.connect(self._on_calc_error)
            self.calc_btn.setEnabled(False)
            self.status_label.setText("⏳ Расчет рыночной стоимости...")
            self._calc_thread.start()
        except Exception as e:
            self.logger.error(f"Ошибка запуска расчета: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _on_calc_progress(self, message):
        self.status_label.setText(message)

    def _on_calc_finished(self, result):
        self.calc_btn.setEnabled(True)
        if 'empty' in result:
            self.status_label.setText(f"❌ {result['empty']}")
            QMessageBox.warning(self, "Предупреждение", result['empty'])
            return
        self.current_data = result['current_data']
        self.continent_data = result['continent_data']
        self.country_data = result['country_data']
        self.metal_data = result['metal_data']
        self.century_data = result['century_data']
        self.all_dates = result['all_dates']
        self.status_label.setText("✅ Расчет завершен")
        self.stats_label.setText(result['stats'])
        self.update_chart()
        self.value_updated.emit()

    def _on_calc_error(self, err):
        self.calc_btn.setEnabled(True)
        self.logger.error(f"Ошибка расчета: {err}")
        self.status_label.setText(f"❌ Ошибка: {str(err)[:50]}")
        QMessageBox.critical(self, "Ошибка", f"Не удалось рассчитать стоимость:\n{err}")

    def on_metal_filter_changed(self):
        """Debounce 250 мс: быстрые переключения фильтра не создают потоки"""
        if self._filter_timer is None:
            self._filter_timer = QTimer(self)
            self._filter_timer.setSingleShot(True)
            self._filter_timer.setInterval(250)
            self._filter_timer.timeout.connect(self.calculate_value)
        self._filter_timer.start()

    # ================= ГРАФИКИ =================
    def update_chart(self):
        if not WEBENGINE_AVAILABLE:
            return
        if not self.current_data:
            self.show_empty_chart()
            return
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
        values = [self.current_data.get(dt.date(), 0) for dt in dates]
        if not values:
            self.show_empty_chart()
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=values, mode='lines+markers',
            name='Рыночная стоимость',
            line=dict(color='#4a6fa5', width=2.5), marker=dict(size=6)))
        last_value = values[-1] if values else 0
        last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
        fig.update_layout(
            title=dict(text=f'📊 Изменение рыночной стоимости коллекции<br>'
                            f'<sup>Текущая стоимость: {last_value:,.0f} ₽ на {last_date}</sup>', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified', template='plotly_white', height=450)
        self._show_fig(fig)

    def _show_continent_chart(self, dates):
        all_continents = set()
        for date_data in self.continent_data.values():
            all_continents.update(date_data.keys())
        if not all_continents:
            self.show_empty_chart()
            return
        continent_colors = {
            "Европа": "#4a6fa5", "Азия": "#e67e22", "Америка": "#27ae60",
            "Африка": "#f1c40f", "Океания": "#9b59b6", "Не указан": "#95a5a6"}
        fig = go.Figure()
        for continent in sorted(all_continents):
            values = [self.continent_data.get(dt.date(), {}).get(continent, 0) for dt in dates]
            fig.add_trace(go.Scatter(
                x=dates, y=values, mode='lines+markers', name=continent,
                line=dict(color=continent_colors.get(continent, "#4a6fa5"), width=2),
                marker=dict(size=4)))
        fig.update_layout(
            title=dict(text='🌍 Распределение рыночной стоимости по континентам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white', height=450)
        self._show_fig(fig)

    def _show_country_chart(self, dates):
        if not self.all_dates:
            self.show_empty_chart()
            return
        last_country_data = self.country_data.get(self.all_dates[-1], {})
        if not last_country_data:
            self.show_empty_chart()
            return
        top_countries = sorted(last_country_data.items(), key=lambda x: x[1], reverse=True)[:10]
        colors = ['#4a6fa5', '#e67e22', '#27ae60', '#f1c40f', '#9b59b6',
                  '#e74c3c', '#3498db', '#1abc9c', '#f39c12', '#d35400']
        fig = go.Figure()
        for i, (country, _) in enumerate(top_countries):
            values = [self.country_data.get(dt.date(), {}).get(country, 0) for dt in dates]
            fig.add_trace(go.Scatter(
                x=dates, y=values, mode='lines+markers', name=country[:25],
                line=dict(color=colors[i % len(colors)], width=2), marker=dict(size=4)))
        fig.update_layout(
            title=dict(text='🏳️ Распределение рыночной стоимости по странам (топ-10)', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white', height=450)
        self._show_fig(fig)

    def _show_metal_chart(self, dates):
        all_metals = set()
        for date_data in self.metal_data.values():
            all_metals.update(date_data.keys())
        if not all_metals:
            self.show_empty_chart()
            return
        metal_colors = {"Золото": "#FFD700", "Серебро": "#C0C0C0", "Медь": "#B87333",
                        "Платина": "#E5E4E2", "Другие": "#4a6fa5", "Не указан": "#95a5a6"}
        fig = go.Figure()
        for metal in sorted(all_metals):
            values = [self.metal_data.get(dt.date(), {}).get(metal, 0) for dt in dates]
            fig.add_trace(go.Scatter(
                x=dates, y=values, mode='lines+markers', name=metal,
                line=dict(color=metal_colors.get(metal, "#4a6fa5"), width=2), marker=dict(size=4)))
        fig.update_layout(
            title=dict(text='⚙️ Распределение рыночной стоимости по металлам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white', height=450)
        self._show_fig(fig)

    def _show_century_chart(self, dates):
        all_centuries = set()
        for date_data in self.century_data.values():
            all_centuries.update(date_data.keys())
        if not all_centuries:
            self.show_empty_chart()
            return

        def century_sort_key(century):
            if century == "Не указан":
                return 999
            try:
                return int(century.replace(" в.", ""))
            except Exception:
                return 0

        colors = ['#4a6fa5', '#e67e22', '#27ae60', '#f1c40f', '#9b59b6',
                  '#e74c3c', '#3498db', '#1abc9c', '#f39c12', '#d35400']
        fig = go.Figure()
        for i, century in enumerate(sorted(all_centuries, key=century_sort_key)):
            values = [self.century_data.get(dt.date(), {}).get(century, 0) for dt in dates]
            fig.add_trace(go.Scatter(
                x=dates, y=values, mode='lines+markers', name=century,
                line=dict(color=colors[i % len(colors)], width=2), marker=dict(size=4)))
        fig.update_layout(
            title=dict(text='📅 Распределение рыночной стоимости по векам', x=0.5),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white', height=450)
        self._show_fig(fig)

    def _show_fig(self, fig):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            fig.write_html(f.name, include_plotlyjs='cdn', config={
                'displayModeBar': True, 'responsive': True,
                'scrollZoom': True, 'autosizable': True})
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
        fig = go.Figure()
        fig.add_annotation(
            text="Нет данных для отображения.\nЗагрузите рыночные цены через 'Сервисы → Загрузка рыночных цен'",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False),
                          template='plotly_white', height=450)
        self._show_fig(fig)

    def closeEvent(self, event):
        # Корректно останавливаем поток при закрытии вкладки
        if self._calc_thread is not None and self._calc_thread.isRunning():
            self._calc_thread.stop()
            self._calc_thread.wait(3000)
        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except Exception:
                pass
        super().closeEvent(event)