# -*- coding: utf-8 -*-

"""
Виджет для отображения стоимости коллекции на основе исторических цен металлов
с интерфейсом для загрузки цен
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QMessageBox, QDateEdit, QGroupBox,
                               QProgressDialog, QFrame, QRadioButton,
                               QButtonGroup, QApplication, QGridLayout,
                               QSizePolicy)
from PySide6.QtCore import Qt, QDate, QUrl, QThread, Signal, Slot
from PySide6.QtGui import QColor

# Импорт для WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

import plotly.graph_objects as go

from database.models import Metal, MetalPriceHistory, Coin, Country
from utils.moex_api import MOEXAPIClient


class PriceLoaderThread(QThread):
    """Поток для загрузки цен с MOEX"""
    
    progress = Signal(int, int, str)
    finished = Signal(str, int)
    error = Signal(str, str)
    
    def __init__(self, db_manager, metal_name, ticker, start_date, end_date):
        super().__init__()
        self.db_manager = db_manager
        self.metal_name = metal_name
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self._is_running = True
        self.logger = logging.getLogger('CoinCollector.PriceLoader')
    
    def run(self):
        try:
            try:
                self.db_manager.session.rollback()
            except:
                pass
            
            metals = self.db_manager.session.query(Metal).filter_by(ticker_moex=self.ticker).all()
            if not metals:
                self.error.emit(self.metal_name, f"Металлы с тикером {self.ticker} не найдены")
                return
            
            metal_ids = [m.id for m in metals]
            
            current_date = self.start_date
            total_days = (self.end_date - self.start_date).days + 1
            day_count = 0
            loaded_count = 0
            
            while current_date <= self.end_date and self._is_running:
                from utils.moex_api import MOEXAPIClient
                if MOEXAPIClient.is_weekend(current_date):
                    current_date += timedelta(days=1)
                    day_count += 1
                    self.progress.emit(day_count, total_days, self.metal_name)
                    continue
                
                try:
                    self.db_manager.session.rollback()
                except:
                    pass
                
                existing = self.db_manager.session.query(MetalPriceHistory).filter(
                    MetalPriceHistory.metal_id.in_(metal_ids),
                    MetalPriceHistory.date == current_date.date()
                ).first()
                
                if not existing:
                    price = MOEXAPIClient.fetch_price_for_date(
                        self.ticker, current_date, start=0, max_pages=5
                    )
                    
                    if price is not None:
                        for metal_id in metal_ids:
                            exists = self.db_manager.session.query(MetalPriceHistory).filter_by(
                                metal_id=metal_id, date=current_date.date()
                            ).first()
                            if not exists:
                                history_entry = MetalPriceHistory(
                                    metal_id=metal_id, date=current_date.date(), close_price=price
                                )
                                self.db_manager.session.add(history_entry)
                        
                        try:
                            self.db_manager.session.commit()
                            loaded_count += 1
                        except Exception as e:
                            self.logger.error(f"Ошибка коммита: {e}")
                            self.db_manager.session.rollback()
                else:
                    price = existing.close_price
                    need_commit = False
                    for metal_id in metal_ids:
                        has_price = self.db_manager.session.query(MetalPriceHistory).filter_by(
                            metal_id=metal_id, date=current_date.date()
                        ).first()
                        if not has_price and price is not None:
                            history_entry = MetalPriceHistory(
                                metal_id=metal_id, date=current_date.date(), close_price=price
                            )
                            self.db_manager.session.add(history_entry)
                            need_commit = True
                    
                    if need_commit:
                        try:
                            self.db_manager.session.commit()
                            loaded_count += 1
                        except Exception as e:
                            self.logger.error(f"Ошибка коммита: {e}")
                            self.db_manager.session.rollback()
                
                current_date += timedelta(days=1)
                day_count += 1
                self.progress.emit(day_count, total_days, self.metal_name)
            
            self.finished.emit(self.metal_name, loaded_count)
            
        except Exception as e:
            try:
                self.db_manager.session.rollback()
            except:
                pass
            self.error.emit(self.metal_name, str(e))
    
    def stop(self):
        self._is_running = False


class CollectionValueChart(QWidget):
    """Виджет для отображения стоимости коллекции с интерфейсом загрузки цен"""
    value_updated = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.CollectionValueChart')
        
        self.current_data = {}
        self.all_dates = []
        self.continent_data = {}
        self.current_html_file = None
        self.loader_threads = []
        
        self.setup_ui()
        self.update_metal_prices()
    
    def setup_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        title = QLabel("📈 Стоимость коллекции на основе исторических цен металлов")
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
        
        # Панель загрузки цен
        load_group = QGroupBox("📥 Загрузка цен с MOEX")
        load_group.setFixedHeight(90)
        
        load_layout = QGridLayout()
        load_layout.setSpacing(5)
        load_layout.setContentsMargins(10, 10, 10, 10)
        
        load_layout.addWidget(QLabel("Период:"), 0, 0)
        
        self.load_start_date = QDateEdit()
        self.load_start_date.setDate(QDate.currentDate().addDays(-15))
        self.load_start_date.setCalendarPopup(True)
        self.load_start_date.setMaximumWidth(120)
        load_layout.addWidget(self.load_start_date, 0, 1)
        
        load_layout.addWidget(QLabel("—"), 0, 2)
        
        self.load_end_date = QDateEdit()
        self.load_end_date.setDate(QDate.currentDate())
        self.load_end_date.setCalendarPopup(True)
        self.load_end_date.setMaximumWidth(120)
        load_layout.addWidget(self.load_end_date, 0, 3)
        
        self.load_gold_btn = QPushButton("📥 Загрузить золото")
        self.load_gold_btn.clicked.connect(lambda: self.load_prices('Золото'))
        self.load_gold_btn.setFixedHeight(30)
        load_layout.addWidget(self.load_gold_btn, 0, 4)
        
        self.load_silver_btn = QPushButton("📥 Загрузить серебро")
        self.load_silver_btn.clicked.connect(lambda: self.load_prices('Серебро'))
        self.load_silver_btn.setFixedHeight(30)
        load_layout.addWidget(self.load_silver_btn, 0, 5)
        
        self.load_all_btn = QPushButton("📥 Загрузить всё")
        self.load_all_btn.clicked.connect(self.load_all_prices)
        self.load_all_btn.setFixedHeight(30)
        load_layout.addWidget(self.load_all_btn, 0, 6)
        
        self.fix_prices_btn = QPushButton("🔧 Исправить цены")
        self.fix_prices_btn.clicked.connect(self.fix_existing_prices)
        self.fix_prices_btn.setFixedHeight(30)
        load_layout.addWidget(self.fix_prices_btn, 0, 7)
        
        self.load_status = QLabel("Статус: готов")
        self.load_status.setStyleSheet("color: #666; padding: 2px;")
        load_layout.addWidget(self.load_status, 1, 0, 1, 8)
        
        load_group.setLayout(load_layout)
        layout.addWidget(load_group)
        
        # Панель расчета
        calc_group = QGroupBox("📊 Расчет стоимости")
        calc_layout = QHBoxLayout()
        calc_layout.setSpacing(10)
        calc_layout.setContentsMargins(10, 10, 10, 10)
        
        left_widget = QWidget()
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_widget.setLayout(left_layout)
        
        left_layout.addWidget(QLabel("Период:"))
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate(2010, 1, 1))
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
        self.calc_btn.clicked.connect(self.calculate_value_optimized)
        self.calc_btn.setFixedHeight(30)
        left_layout.addWidget(self.calc_btn)
        
        calc_layout.addWidget(left_widget)
        calc_layout.addStretch()
        
        # Правая часть - текущие цены
        self.prices_widget = QWidget()
        prices_layout = QHBoxLayout()
        prices_layout.setContentsMargins(0, 0, 0, 0)
        prices_layout.setSpacing(15)
        self.prices_widget.setLayout(prices_layout)
        
        date_widget = QWidget()
        date_layout = QVBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(2)
        date_widget.setLayout(date_layout)
        
        date_title = QLabel("📅 Актуально на:")
        date_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #666;")
        date_layout.addWidget(date_title)
        
        self.current_date_label = QLabel("—")
        self.current_date_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #4a6fa5;")
        date_layout.addWidget(self.current_date_label)
        prices_layout.addWidget(date_widget)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(2)
        prices_layout.addWidget(separator)
        
        gold_widget = QWidget()
        gold_layout = QVBoxLayout()
        gold_layout.setContentsMargins(0, 0, 0, 0)
        gold_layout.setSpacing(2)
        gold_widget.setLayout(gold_layout)
        
        gold_title = QLabel("🥇 Золото")
        gold_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #FFD700;")
        gold_layout.addWidget(gold_title)
        
        self.gold_price_label = QLabel("— ₽/г")
        self.gold_price_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        gold_layout.addWidget(self.gold_price_label)
        
        self.gold_delta_label = QLabel("—")
        self.gold_delta_label.setStyleSheet("font-size: 10px;")
        gold_layout.addWidget(self.gold_delta_label)
        prices_layout.addWidget(gold_widget)
        
        silver_widget = QWidget()
        silver_layout = QVBoxLayout()
        silver_layout.setContentsMargins(0, 0, 0, 0)
        silver_layout.setSpacing(2)
        silver_widget.setLayout(silver_layout)
        
        silver_title = QLabel("🥈 Серебро")
        silver_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #C0C0C0;")
        silver_layout.addWidget(silver_title)
        
        self.silver_price_label = QLabel("— ₽/г")
        self.silver_price_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        silver_layout.addWidget(self.silver_price_label)
        
        self.silver_delta_label = QLabel("—")
        self.silver_delta_label.setStyleSheet("font-size: 10px;")
        silver_layout.addWidget(self.silver_delta_label)
        prices_layout.addWidget(silver_widget)
        
        calc_layout.addWidget(self.prices_widget)
        calc_group.setLayout(calc_layout)
        layout.addWidget(calc_group)
        
        # Панель отображения
        display_group = QGroupBox("📈 Отображение")
        display_group.setFixedHeight(80)
        
        display_layout = QVBoxLayout()
        display_layout.setSpacing(5)
        display_layout.setContentsMargins(10, 5, 10, 5)
        
        # Первая строка - тип металла
        metal_row = QHBoxLayout()
        metal_row.addWidget(QLabel("Металл:"))
        
        self.metal_group = QButtonGroup(self)
        
        self.sum_radio = QRadioButton("💰 Сумма (золото + серебро)")
        self.metal_group.addButton(self.sum_radio)
        metal_row.addWidget(self.sum_radio)
        
        self.gold_radio = QRadioButton("🥇 Золото")
        self.metal_group.addButton(self.gold_radio)
        metal_row.addWidget(self.gold_radio)
        
        self.silver_radio = QRadioButton("🥈 Серебро")
        self.silver_radio.setChecked(True)  # <-- УСТАНАВЛИВАЕМ СЕРЕБРО ПО УМОЛЧАНИЮ
        self.metal_group.addButton(self.silver_radio)
        metal_row.addWidget(self.silver_radio)
        
        metal_row.addStretch()
        display_layout.addLayout(metal_row)
        
        # Вторая строка - тип группировки
        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("Группировка:"))
        
        self.group_group = QButtonGroup(self)
        
        self.total_radio = QRadioButton("📊 Общая стоимость")
        self.group_group.addButton(self.total_radio)
        group_row.addWidget(self.total_radio)
        
        self.continent_radio = QRadioButton("🌍 По континентам")
        self.continent_radio.setChecked(True)  # <-- УСТАНАВЛИВАЕМ КОНТИНЕНТЫ ПО УМОЛЧАНИЮ
        self.group_group.addButton(self.continent_radio)
        group_row.addWidget(self.continent_radio)
        
        group_row.addStretch()
        display_layout.addLayout(group_row)
        
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
        self.sum_radio.toggled.connect(self.update_chart)
        self.gold_radio.toggled.connect(self.update_chart)
        self.silver_radio.toggled.connect(self.update_chart)
        self.total_radio.toggled.connect(self.update_chart)
        self.continent_radio.toggled.connect(self.update_chart)

    def fix_existing_prices(self):
        """Проверяет и исправляет существующие цены"""
        reply = QMessageBox.question(
            self, "Исправление цен",
            "Будут проверены все металлы и добавлены недостающие цены.\n"
            "Цены для металлов с одинаковыми биржевыми тикерами будут синхронизированы.\n\n"
            "Продолжить?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            self.db_manager.session.rollback()
        except:
            pass
        
        progress = QProgressDialog("Исправление цен...", "Отмена", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.show()
        
        try:
            metals = self.db_manager.session.query(Metal).filter(Metal.ticker_moex.isnot(None)).all()
            
            metals_by_ticker = defaultdict(list)
            for metal in metals:
                if metal.ticker_moex not in metals_by_ticker:
                    metals_by_ticker[metal.ticker_moex] = []
                metals_by_ticker[metal.ticker_moex].append(metal)
            
            fixed_count = 0
            total_tickers = len(metals_by_ticker)
            current_ticker = 0
            
            for ticker, metal_list in metals_by_ticker.items():
                if len(metal_list) <= 1:
                    current_ticker += 1
                    progress.setValue(int((current_ticker / total_tickers) * 100))
                    continue
                
                metal_ids = [m.id for m in metal_list]
                metal_names = [m.name for m in metal_list]
                progress.setLabelText(f"Обработка {', '.join(metal_names)}...")
                
                dates_with_prices = self.db_manager.session.query(
                    MetalPriceHistory.date
                ).filter(
                    MetalPriceHistory.metal_id.in_(metal_ids)
                ).distinct().order_by(MetalPriceHistory.date).all()
                
                for date in dates_with_prices:
                    price_entry = self.db_manager.session.query(MetalPriceHistory).filter(
                        MetalPriceHistory.metal_id.in_(metal_ids),
                        MetalPriceHistory.date == date[0]
                    ).first()
                    
                    if price_entry:
                        price = price_entry.close_price
                        for metal_id in metal_ids:
                            existing = self.db_manager.session.query(MetalPriceHistory).filter_by(
                                metal_id=metal_id, date=date[0]
                            ).first()
                            
                            if not existing:
                                history_entry = MetalPriceHistory(
                                    metal_id=metal_id, date=date[0], close_price=price
                                )
                                self.db_manager.session.add(history_entry)
                                fixed_count += 1
                
                try:
                    self.db_manager.session.commit()
                except Exception as e:
                    self.logger.error(f"Ошибка коммита: {e}")
                    self.db_manager.session.rollback()
                
                current_ticker += 1
                progress.setValue(int((current_ticker / total_tickers) * 100))
            
            progress.close()
            
            if fixed_count > 0:
                QMessageBox.information(self, "Успех", f"Добавлено {fixed_count} недостающих цен")
            else:
                QMessageBox.information(self, "Информация", "Все цены уже синхронизированы")
            
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при исправлении цен:\n{e}")
            self.logger.error(f"Ошибка в fix_existing_prices: {e}", exc_info=True)
            try:
                self.db_manager.session.rollback()
            except:
                pass
        
        self.update_metal_prices()
    
    def load_prices(self, metal_name):
        """Загружает цены для указанного металла"""
        start_qdate = self.load_start_date.date()
        end_qdate = self.load_end_date.date()
        
        if start_qdate > end_qdate:
            QMessageBox.warning(self, "Предупреждение", "Начальная дата не может быть позже конечной")
            return
        
        start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day())
        end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day())
        
        metal = self.db_manager.session.query(Metal).filter_by(name=metal_name).first()
        if not metal or not metal.ticker_moex:
            QMessageBox.warning(self, "Предупреждение", f"Для металла '{metal_name}' не указан биржевой тикер")
            return
        
        try:
            self.db_manager.session.rollback()
        except:
            pass
        
        self.load_gold_btn.setEnabled(False)
        self.load_silver_btn.setEnabled(False)
        self.load_all_btn.setEnabled(False)
        self.fix_prices_btn.setEnabled(False)
        self.calc_btn.setEnabled(False)
        
        self.load_status.setText(f"⏳ Загрузка {metal_name}...")
        
        thread = PriceLoaderThread(self.db_manager, metal_name, metal.ticker_moex, start_date, end_date)
        thread.progress.connect(self.on_load_progress)
        thread.finished.connect(self.on_load_finished)
        thread.error.connect(self.on_load_error)
        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.error.connect(lambda: self.cleanup_thread(thread))
        
        self.loader_threads.append(thread)
        thread.start()
    
    def load_all_prices(self):
        """Загружает цены для всех металлов"""
        gold = self.db_manager.session.query(Metal).filter_by(name='Золото').first()
        if gold and gold.ticker_moex:
            self.load_prices('Золото')
        
        silver = self.db_manager.session.query(Metal).filter_by(name='Серебро').first()
        if silver and silver.ticker_moex:
            self.load_prices('Серебро')
    
    @Slot(int, int, str)
    def on_load_progress(self, current, total, metal_name):
        percent = int((current / total) * 100)
        self.load_status.setText(f"⏳ Загрузка {metal_name}: {current}/{total} дней ({percent}%)")
    
    @Slot(str, int)
    def on_load_finished(self, metal_name, loaded_count):
        self.load_status.setText(f"✅ Загружено {loaded_count} новых цен для {metal_name}")
        self.update_metal_prices()
        
        self.load_gold_btn.setEnabled(True)
        self.load_silver_btn.setEnabled(True)
        self.load_all_btn.setEnabled(True)
        self.fix_prices_btn.setEnabled(True)
        self.calc_btn.setEnabled(True)
        
        self.update_metal_prices()
        QMessageBox.information(self, "Успех", f"Загрузка {metal_name} завершена!")
        
        if hasattr(self, 'current_data') and self.current_data:
            self.update_chart()
    
    @Slot(str, str)
    def on_load_error(self, metal_name, error_msg):
        self.load_status.setText(f"❌ Ошибка загрузки {metal_name}")
        self.load_gold_btn.setEnabled(True)
        self.load_silver_btn.setEnabled(True)
        self.load_all_btn.setEnabled(True)
        self.fix_prices_btn.setEnabled(True)
        self.calc_btn.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить {metal_name}:\n{error_msg}")
    
    def cleanup_thread(self, thread):
        if thread in self.loader_threads:
            self.loader_threads.remove(thread)


    def calculate_value_optimized(self):
        """
        ОПТИМИЗИРОВАННЫЙ расчет стоимости коллекции.
        Использует MetalAggregator для агрегации весов через SQL GROUP BY.
        """
        from datetime import datetime
        from utils.metal_aggregator import MetalAggregator
        
        # ПРИНУДИТЕЛЬНО СБРАСЫВАЕМ ФИЛЬТРЫ - считаем всю коллекцию
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'current_filter_country_id'):
                main_window.current_filter_country_id = None
            if main_window and hasattr(main_window, 'current_folder_country_ids'):
                main_window.current_folder_country_ids = None
            self.logger.info("📊 Расчет стоимости для ВСЕЙ коллекции (фильтры сброшены)")
        except Exception as e:
            self.logger.warning(f"Не удалось сбросить фильтры: {e}")
        
        try:
            self.db_manager.session.rollback()
        except:
            pass
        
        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()
        
        if start_qdate > end_qdate:
            QMessageBox.warning(self, "Предупреждение", "Начальная дата не может быть позже конечной")
            return
        
        start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day())
        end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day())
        
        from gui.widgets.progress_dialog import ProgressDialog
        
        progress = ProgressDialog(
            title="Расчет стоимости коллекции",
            message=f"Период: {start_qdate.toString('dd.MM.yyyy')} - {end_qdate.toString('dd.MM.yyyy')}",
            parent=self
        )
        progress.set_cancel_enabled(False)
        progress.show()
        
        progress.add_log(f"Начало расчета за период {start_qdate.toString('dd.MM.yyyy')} - {end_qdate.toString('dd.MM.yyyy')}", "info")
        progress.set_status("Загрузка данных...")
        QApplication.processEvents()
        
        self.calc_btn.setEnabled(False)
        
        try:
            # 1. Получаем все металлы с тикерами
            progress.add_log("Получение списка металлов...", "progress")
            metals = self.db_manager.session.query(Metal).filter(
                Metal.ticker_moex.isnot(None)
            ).all()
            
            if not metals:
                progress.add_log("Металлы с тикерами не найдены", "error")
                progress.close()
                QMessageBox.warning(self, "Предупреждение", "Металлы с тикерами не найдены в справочнике")
                return
            
            progress.add_log(f"Найдено металлов: {len(metals)}", "success")
            
            # 2. Группируем металлы по ticker_moex
            metals_by_ticker = defaultdict(list)
            for metal in metals:
                metals_by_ticker[metal.ticker_moex].append(metal)
            
            progress.add_log(f"Уникальных тикеров: {len(metals_by_ticker)}", "info")
            
            # 3. Получаем агрегированные веса через MetalAggregator (без фильтра по статусу)
            progress.add_log("Агрегация весов металлов (SQL GROUP BY)...", "progress")
            aggregated_weights = MetalAggregator.get_aggregated_weights(self.db_manager, status=None)
            
            if not aggregated_weights:
                progress.add_log("Нет данных для расчета", "error")
                progress.close()
                QMessageBox.warning(self, "Предупреждение", "Нет монет с указанным весом для расчета")
                return
            
            progress.add_log(f"Найдено уникальных металлов: {len(aggregated_weights)}", "success")
            
            # 4. Генерируем все даты в периоде
            all_period_dates = []
            current = start_date
            while current <= end_date:
                all_period_dates.append(current.date())
                current += timedelta(days=1)
            
            # 5. Для каждого металла получаем словарь цен
            metal_prices = {}
            
            for ticker, metal_list in metals_by_ticker.items():
                metal_ids = [m.id for m in metal_list]
                
                # Получаем все цены для этого тикера
                prices = self.db_manager.session.query(MetalPriceHistory).filter(
                    MetalPriceHistory.metal_id.in_(metal_ids),
                    MetalPriceHistory.date >= start_date.date(),
                    MetalPriceHistory.date <= end_date.date()
                ).order_by(MetalPriceHistory.date).all()
                
                if not prices:
                    continue
                
                # Создаем словарь цена -> дата
                price_dict = {p.date: p.close_price for p in prices}
                
                # Для каждого металла в тикере заполняем цены для всех дат
                for metal in metal_list:
                    metal_prices[metal.id] = {}
                    
                    # Проходим по всем датам периода
                    for date in all_period_dates:
                        if date in price_dict:
                            metal_prices[metal.id][date] = price_dict[date]
                        else:
                            # Ищем ближайшую цену (вперед или назад)
                            nearest_price = None
                            days_offset = 1
                            max_offset = 30
                            
                            while days_offset <= max_offset:
                                future_date = date + timedelta(days=days_offset)
                                if future_date in price_dict:
                                    nearest_price = price_dict[future_date]
                                    break
                                
                                past_date = date - timedelta(days=days_offset)
                                if past_date in price_dict:
                                    nearest_price = price_dict[past_date]
                                    break
                                
                                days_offset += 1
                            
                            if nearest_price is not None:
                                metal_prices[metal.id][date] = nearest_price
                            else:
                                if prices:
                                    metal_prices[metal.id][date] = prices[-1].close_price
                                else:
                                    metal_prices[metal.id][date] = 0
            
            # 6. Рассчитываем стоимость на основе агрегированных весов
            result = {}
            continent_values = {}
            continent_weights = {}
            all_dates_set = set()
            
            # Для агрегации по металлам (золото, серебро, другие)
            gold_total_weight = 0.0
            silver_total_weight = 0.0
            other_total_weight = 0.0
            gold_total_value = 0.0
            silver_total_value = 0.0
            other_total_value = 0.0
            gold_coins_count = 0
            silver_coins_count = 0
            other_coins_count = 0
            
            for metal_id, metal_data in aggregated_weights.items():
                metal = self.db_manager.session.query(Metal).get(metal_id)
                if not metal or metal.id not in metal_prices:
                    continue
                
                metal_name = metal.get_display_text()
                metal_values = {}
                metal_weights = {}
                
                # Для каждого металла нужно получить распределение по континентам
                # Для этого получаем все монеты этого металла и группируем по континентам
                coins = self.db_manager.session.query(Coin).filter(
                    Coin.metal_id == metal_id,
                    Coin.weight.isnot(None),
                    Coin.weight > 0,
                    Coin.country_id.isnot(None)
                ).all()
                
                # Группируем монеты по континентам
                continent_weights_agg = defaultdict(float)
                continent_coin_counts = defaultdict(int)
                
                for coin in coins:
                    if coin.country and coin.country.continent:
                        continent = coin.country.continent
                    else:
                        continent = "Не указан"
                    
                    # Рассчитываем чистый вес с учетом пробы
                    metal_purity = metal.get_purity_decimal()
                    metal_weight = coin.weight * metal_purity
                    continent_weights_agg[continent] += metal_weight
                    continent_coin_counts[continent] += 1
                
                # Проходим по всем датам периода
                for date in all_period_dates:
                    price = metal_prices[metal.id].get(date, 0)
                    if price == 0:
                        continue
                    
                    # Рассчитываем стоимость на основе агрегированного веса
                    total_weight = metal_data['weight']
                    total_value = total_weight * price
                    date_str = date.isoformat()
                    metal_values[date_str] = total_value
                    metal_weights[date_str] = total_weight
                    all_dates_set.add(date_str)
                    
                    # Сохраняем стоимость по континентам с указанием металла
                    if date_str not in continent_values:
                        continent_values[date_str] = {}
                        continent_weights[date_str] = {}
                    
                    # Распределяем стоимость по континентам пропорционально весу
                    for continent, weight in continent_weights_agg.items():
                        if total_weight > 0:
                            continent_value = (weight / total_weight) * total_value
                            key = f"{metal_name} ({continent})"
                            continent_values[date_str][key] = continent_values[date_str].get(key, 0) + continent_value
                            continent_weights[date_str][key] = continent_weights[date_str].get(key, 0) + weight
                
                if metal_values:
                    result[metal_name] = metal_values
                    progress.add_log(f"  {metal.name}: рассчитано {len(metal_values)} дат, распределено по {len(continent_weights_agg)} континентам", "success")
                    
                    # Обновляем агрегаты
                    metal_name_lower = metal.name.lower()
                    if 'золото' in metal_name_lower:
                        gold_total_weight += metal_data['weight']
                        gold_total_value += list(metal_values.values())[-1] if metal_values else 0
                        gold_coins_count += metal_data.get('coin_count', 0)
                    elif 'серебро' in metal_name_lower:
                        silver_total_weight += metal_data['weight']
                        silver_total_value += list(metal_values.values())[-1] if metal_values else 0
                        silver_coins_count += metal_data.get('coin_count', 0)
                    else:
                        other_total_weight += metal_data['weight']
                        other_total_value += list(metal_values.values())[-1] if metal_values else 0
                        other_coins_count += metal_data.get('coin_count', 0)
            
            # Сохраняем агрегированные данные
            self.gold_total_value = gold_total_value
            self.silver_total_value = silver_total_value
            self.other_total_value = other_total_value
            self.gold_total_weight = gold_total_weight
            self.silver_total_weight = silver_total_weight
            self.other_total_weight = other_total_weight
            self.gold_coins_count = gold_coins_count
            self.silver_coins_count = silver_coins_count
            self.other_coins_count = other_coins_count
            
            progress.add_log("=" * 50, "info")
            progress.add_log(f"📊 ИТОГОВЫЕ ЗНАЧЕНИЯ:", "info")
            progress.add_log(f"  Золото: {gold_coins_count} монет, {gold_total_weight:.2f}г, {gold_total_value:.2f}₽", "info")
            progress.add_log(f"  Серебро: {silver_coins_count} монет, {silver_total_weight:.2f}г, {silver_total_value:.2f}₽", "info")
            progress.add_log(f"  Другие: {other_coins_count} монет, {other_total_weight:.2f}г, {other_total_value:.2f}₽", "info")
            progress.add_log("=" * 50, "info")
            
            if not result or not all_dates_set:
                progress.add_log("Нет данных для отображения", "error")
                progress.close()
                QMessageBox.warning(self, "Предупреждение", "Нет данных для отображения")
                return
            
            self.current_data = result
            self.all_dates = sorted(list(all_dates_set))
            self.continent_data = continent_values
            self.continent_weights = continent_weights
            
            progress.add_log("Обновление графика...", "progress")
            self.value_updated.emit()
            self.update_chart()
            self.update_status()
            
            progress.add_log("✅ Расчет успешно завершен!", "success")
            progress.set_message("✅ Расчет завершен!")
            progress.set_value(100)
            progress.auto_close(1500)
            
        except Exception as e:
            progress.add_log(f"Ошибка: {str(e)}", "error")
            progress.close()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при расчете:\n{e}")
            self.logger.error(f"Ошибка расчета: {e}", exc_info=True)
            try:
                self.db_manager.session.rollback()
            except:
                pass
        
        finally:
            self.calc_btn.setEnabled(True)
        self.update_metal_prices()

    def update_chart(self):
        """Обновляет график в зависимости от выбранных опций"""
        if not WEBENGINE_AVAILABLE:
            return
        
        if not hasattr(self, 'current_data') or not self.current_data:
            self.show_empty_chart()
            return
        
        # Если выбран режим "По континентам"
        if self.continent_radio.isChecked():
            self._update_continent_chart()
            return
        
        # Сортируем даты
        sorted_dates = sorted(self.all_dates)
        if not sorted_dates:
            self.show_empty_chart()
            return
        
        # Преобразуем даты в объекты datetime
        dates = [datetime.fromisoformat(d) for d in sorted_dates]
        
        # Собираем данные по дням
        gold_values = []
        silver_values = []
        sum_values = []
        
        for date_str in sorted_dates:
            gold_val = 0
            silver_val = 0
            for metal_key, metal_values in self.current_data.items():
                metal_lower = metal_key.lower()
                if 'золото' in metal_lower or 'gold' in metal_lower:
                    gold_val += metal_values.get(date_str, 0)
                elif 'серебро' in metal_lower or 'silver' in metal_lower:
                    silver_val += metal_values.get(date_str, 0)
            gold_values.append(gold_val)
            silver_values.append(silver_val)
            sum_values.append(gold_val + silver_val)
        
        fig = go.Figure()
        
        # Определяем что показывать
        if self.sum_radio.isChecked():
            # Сумма + золото + серебро отдельными линиями
            fig.add_trace(go.Scatter(
                x=dates,
                y=gold_values,
                mode='lines',
                name='🥇 Золото',
                line=dict(color='#FFD700', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=dates,
                y=silver_values,
                mode='lines',
                name='🥈 Серебро',
                line=dict(color='#C0C0C0', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=dates,
                y=sum_values,
                mode='lines',
                name='💰 Сумма (золото + серебро)',
                line=dict(color='#4a6fa5', width=3)
            ))
            
        elif self.gold_radio.isChecked():
            # Только золото
            fig.add_trace(go.Scatter(
                x=dates,
                y=gold_values,
                mode='lines',
                name='Золото',
                line=dict(color='#FFD700', width=3)
            ))
            
        elif self.silver_radio.isChecked():
            # Только серебро
            fig.add_trace(go.Scatter(
                x=dates,
                y=silver_values,
                mode='lines',
                name='Серебро',
                line=dict(color='#C0C0C0', width=3)
            ))
        
        if len(fig.data) == 0:
            self.show_empty_chart()
            return
        
        # Последнее значение
        if self.sum_radio.isChecked() and sum_values:
            last_sum = sum_values[-1]
            last_gold = gold_values[-1] if gold_values else 0
            last_silver = silver_values[-1] if silver_values else 0
            last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
            title_text = f'💰 Стоимость коллекции<br><sup>Золото: {last_gold:,.0f} ₽ | Серебро: {last_silver:,.0f} ₽ | Всего: {last_sum:,.0f} ₽ на {last_date}</sup>'
            
        elif self.gold_radio.isChecked() and gold_values:
            last_value = gold_values[-1]
            last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
            title_text = f'🥇 Стоимость золота в коллекции<br><sup>Всего: {last_value:,.0f} ₽ на {last_date}</sup>'
            
        elif self.silver_radio.isChecked() and silver_values:
            last_value = silver_values[-1]
            last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
            title_text = f'🥈 Стоимость серебра в коллекции<br><sup>Всего: {last_value:,.0f} ₽ на {last_date}</sup>'
        else:
            last_value = 0
            last_date = ''
            title_text = '📊 Стоимость коллекции'
        
        fig.update_layout(
            title=dict(text=title_text, x=0.5, font=dict(size=14)),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)

    def _update_continent_chart(self):
        """Показывает график стоимости по континентам для выбранного металла"""
        if not hasattr(self, 'continent_data') or not self.continent_data:
            self.show_empty_chart()
            return
        
        # Сортируем даты
        all_dates = sorted(self.all_dates)
        if not all_dates:
            self.show_empty_chart()
            return
        
        # Определяем, какой металл показывать
        if self.gold_radio.isChecked():
            metal_filter = 'золото'
            title_prefix = '🥇 Стоимость золота по континентам'
            line_color = '#FFD700'
        elif self.silver_radio.isChecked():
            metal_filter = 'серебро'
            title_prefix = '🥈 Стоимость серебра по континентам'
            line_color = '#C0C0C0'
        else:
            metal_filter = None
            title_prefix = '💰 Стоимость коллекции по континентам (золото + серебро)'
            line_color = '#4a6fa5'
        
        # Собираем данные по континентам с учетом фильтра по металлу
        continents_data = {}
        # Собираем общую сумму для выбранного металла (чёрная линия)
        total_by_metal = []
        
        for date_str in all_dates:
            metals_data = self.continent_data.get(date_str, {})
            date_total = 0
            
            for key, value in metals_data.items():
                # Парсим ключ "Металл (Континент)"
                if ' (' in key:
                    metal, continent = key.split(' (')
                    continent = continent.rstrip(')')
                else:
                    # Если ключ не в формате "Металл (Континент)", пропускаем
                    continue
                
                # Фильтруем по металлу
                if metal_filter:
                    metal_lower = metal.lower()
                    if metal_filter not in metal_lower:
                        continue
                
                # Суммируем общую стоимость для выбранного металла
                date_total += value
                
                if continent not in continents_data:
                    continents_data[continent] = {}
                continents_data[continent][date_str] = continents_data[continent].get(date_str, 0) + value
            
            total_by_metal.append(date_total)
        
        if not continents_data:
            self.show_empty_chart()
            return
        
        # Преобразуем даты
        dates = [datetime.fromisoformat(d) for d in all_dates]
        
        continent_colors = {
            "Европа": "#4a6fa5",
            "Азия": "#e67e22",
            "Америка": "#27ae60",
            "Африка": "#f1c40f",
            "Океания": "#9b59b6",
            "Не указан": "#95a5a6"
        }
        
        fig = go.Figure()
        
        # Для каждого континента строим график
        for continent in sorted(continents_data.keys()):
            values = []
            for date_str in all_dates:
                val = continents_data[continent].get(date_str, 0)
                values.append(val)
            
            color = continent_colors.get(continent, "#4a6fa5")
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines',
                name=continent,
                line=dict(color=color, width=2)
            ))
        
        # Добавляем общую сумму по ВЫБРАННОМУ металлу (чёрная линия)
        fig.add_trace(go.Scatter(
            x=dates,
            y=total_by_metal,
            mode='lines',
            name='📊 Общая сумма',
            line=dict(color='black', width=3, dash='solid')
        ))
        
        if len(fig.data) == 0:
            self.show_empty_chart()
            return
        
        # Добавляем информацию о последнем значении в заголовок
        last_total = total_by_metal[-1] if total_by_metal else 0
        last_date = dates[-1].strftime('%d.%m.%Y') if dates else ''
        
        if self.gold_radio.isChecked():
            last_gold = sum(continents_data.get(continent, {}).get(all_dates[-1], 0) 
                           for continent in continents_data)
            title_text = f'{title_prefix}<br><sup>Золото: {last_gold:,.0f} ₽ | Всего по золоту: {last_total:,.0f} ₽ на {last_date}</sup>'
        elif self.silver_radio.isChecked():
            last_silver = sum(continents_data.get(continent, {}).get(all_dates[-1], 0) 
                             for continent in continents_data)
            title_text = f'{title_prefix}<br><sup>Серебро: {last_silver:,.0f} ₽ | Всего по серебру: {last_total:,.0f} ₽ на {last_date}</sup>'
        else:
            title_text = f'{title_prefix}<br><sup>Всего: {last_total:,.0f} ₽ на {last_date}</sup>'
        
        fig.update_layout(
            title=dict(text=title_text, x=0.5, font=dict(size=13)),
            xaxis=dict(title='Дата', tickformat='%d.%m.%Y', tickangle=45),
            yaxis=dict(title='Стоимость (руб)', tickformat=',.0f'),
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            template='plotly_white',
            height=450
        )
        
        self._show_fig(fig)

    def _show_fig(self, fig):
        """Отображает график в WebView с использованием локального Plotly"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            # Используем локальный PlotlyLoader вместо CDN
            from gui.widgets.plotly_loader import PlotlyLoader
            PlotlyLoader.write_fig(fig, f.name)
            self.current_html_file = f.name
        
        # Добавляем CSS для правильного отображения
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
        fig.add_annotation(text="Нет данных для отображения.<br>1. Загрузите цены с MOEX<br>2. Нажмите 'Рассчитать стоимость'",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), template='plotly_white', height=450)
        
        self._show_fig(fig)
    
    def update_status(self):
        """Обновляет статус"""
        try:
            gold_total = 0
            silver_total = 0
            
            for metal_key, metal_values in self.current_data.items():
                metal_key_lower = metal_key.lower()
                if 'золото' in metal_key_lower or 'gold' in metal_key_lower:
                    if metal_values:
                        gold_total += list(metal_values.values())[-1]
                elif 'серебро' in metal_key_lower or 'silver' in metal_key_lower:
                    if metal_values:
                        silver_total += list(metal_values.values())[-1]
            
            total_sum = gold_total + silver_total
            
            if total_sum > 0:
                self.status_label.setText("✅ Расчет завершен")
                self.stats_label.setText(f"💰 Золото: {gold_total:,.2f} ₽ | 🔘 Серебро: {silver_total:,.2f} ₽ | 📊 Всего: {total_sum:,.2f} ₽")
            else:
                self.status_label.setText("✅ Расчет завершен")
                self.stats_label.setText("Нет монет для отображения")
                
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении статуса: {e}")
    
    def update_metal_prices(self):
        """Обновляет отображение цен металлов"""
        try:
            try:
                self.db_manager.session.rollback()
            except:
                pass
            
            from datetime import timedelta
            
            last_price = self.db_manager.session.query(MetalPriceHistory).order_by(
                MetalPriceHistory.date.desc()
            ).first()
            
            if not last_price:
                self.current_date_label.setText("—")
                self.gold_price_label.setText("— ₽/г")
                self.silver_price_label.setText("— ₽/г")
                return
            
            current_date = last_price.date
            date_str = current_date.strftime("%d.%m.%Y")
            today = datetime.now().date()
            
            if current_date == today:
                date_str += " (сегодня)"
            elif current_date == today - timedelta(days=1):
                date_str += " (вчера)"
            else:
                weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
                date_str += f" ({weekdays[current_date.weekday()]})"
            
            self.current_date_label.setText(date_str)
            
            prev_price_entry = None
            for days in range(1, 8):
                prev_date = current_date - timedelta(days=days)
                prev = self.db_manager.session.query(MetalPriceHistory).filter_by(date=prev_date).first()
                if prev:
                    prev_price_entry = prev
                    break
            
            gold_metals = self.db_manager.session.query(Metal).filter(Metal.ticker_moex == 'GLDRUB_TOM').all()
            silver_metals = self.db_manager.session.query(Metal).filter(Metal.ticker_moex == 'SLVRUB_TOM').all()
            
            gold_current = None
            gold_prev = None
            if gold_metals:
                first_gold = gold_metals[0]
                current = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=first_gold.id, date=current_date
                ).first()
                if current:
                    gold_current = current.close_price
                if prev_price_entry:
                    prev = self.db_manager.session.query(MetalPriceHistory).filter_by(
                        metal_id=first_gold.id, date=prev_price_entry.date
                    ).first()
                    if prev:
                        gold_prev = prev.close_price
            
            silver_current = None
            silver_prev = None
            if silver_metals:
                first_silver = silver_metals[0]
                current = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=first_silver.id, date=current_date
                ).first()
                if current:
                    silver_current = current.close_price
                if prev_price_entry:
                    prev = self.db_manager.session.query(MetalPriceHistory).filter_by(
                        metal_id=first_silver.id, date=prev_price_entry.date
                    ).first()
                    if prev:
                        silver_prev = prev.close_price
            
            if gold_current:
                self.gold_price_label.setText(f"{gold_current:.2f} ₽/г")
                if gold_prev:
                    delta = gold_current - gold_prev
                    delta_percent = (delta / gold_prev) * 100
                    delta_text = f"{delta:+.2f} ({delta_percent:+.1f}%)"
                    if delta > 0:
                        self.gold_delta_label.setText(f"▲ {delta_text}")
                        self.gold_delta_label.setStyleSheet("color: #28a745; font-weight: bold;")
                    elif delta < 0:
                        self.gold_delta_label.setText(f"▼ {delta_text}")
                        self.gold_delta_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                    else:
                        self.gold_delta_label.setText("0.00 (0.0%)")
                        self.gold_delta_label.setStyleSheet("color: #666;")
                else:
                    self.gold_delta_label.setText("нет данных")
            else:
                self.gold_price_label.setText("— ₽/г")
                self.gold_delta_label.setText("—")
            
            if silver_current:
                self.silver_price_label.setText(f"{silver_current:.2f} ₽/г")
                if silver_prev:
                    delta = silver_current - silver_prev
                    delta_percent = (delta / silver_prev) * 100
                    delta_text = f"{delta:+.2f} ({delta_percent:+.1f}%)"
                    if delta > 0:
                        self.silver_delta_label.setText(f"▲ {delta_text}")
                        self.silver_delta_label.setStyleSheet("color: #28a745; font-weight: bold;")
                    elif delta < 0:
                        self.silver_delta_label.setText(f"▼ {delta_text}")
                        self.silver_delta_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                    else:
                        self.silver_delta_label.setText("0.00 (0.0%)")
                        self.silver_delta_label.setStyleSheet("color: #666;")
                else:
                    self.silver_delta_label.setText("нет данных")
            else:
                self.silver_price_label.setText("— ₽/г")
                self.silver_delta_label.setText("—")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении цен металлов: {e}")
            try:
                self.db_manager.session.rollback()
            except:
                pass
    
    def closeEvent(self, event):
        for thread in self.loader_threads:
            thread.stop()
            thread.wait(1000)
        
        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass
        super().closeEvent(event)