# -*- coding: utf-8 -*-

"""
Виджет для отображения исторических цен на металлы в виде таблицы
"""

import logging
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QLabel, QMessageBox, QDateEdit,
                               QProgressDialog, QFrame)
from PySide6.QtCore import Qt, QDate, QThread, Signal, Slot
from PySide6.QtGui import QColor

from database.models import Metal, MetalPriceHistory
from utils.moex_api import MOEXAPIClient


class PriceLoaderThread(QThread):
    """Поток для загрузки данных с MOEX"""
    
    finished = Signal(dict)  # dict with date keys and price values
    error = Signal(str)
    progress = Signal(int, int)  # current, total
    
    def __init__(self, db_manager, metal_id, ticker, start_date, end_date):
        super().__init__()
        self.db_manager = db_manager
        self.metal_id = metal_id
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        
    def run(self):
        try:
            result = {}
            current_date = self.start_date
            total_days = (self.end_date - self.start_date).days + 1
            day_count = 0
            
            while current_date <= self.end_date:
                # Проверяем, есть ли уже данные в БД
                existing = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=self.metal_id,
                    date=current_date.date()
                ).first()
                
                if existing:
                    result[current_date.date().isoformat()] = existing.close_price
                else:
                    # Загружаем с MOEX, перебирая страницы
                    price = MOEXAPIClient.fetch_price_for_date(
                        self.ticker, 
                        current_date,
                        start=0,
                        max_pages=5
                    )
                    
                    if price is not None:
                        # Сохраняем в БД
                        history_entry = MetalPriceHistory(
                            metal_id=self.metal_id,
                            date=current_date.date(),
                            close_price=price
                        )
                        self.db_manager.session.add(history_entry)
                        self.db_manager.session.commit()
                        result[current_date.date().isoformat()] = price
                
                current_date += timedelta(days=1)
                day_count += 1
                self.progress.emit(day_count, total_days)
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class MetalPricesTable(QWidget):
    """Виджет для отображения цен на металлы в таблице"""
    
    # Тикеры для золота и серебра
    METAL_TICKERS = {
        'Золото': 'GLDRUB_TOM',
        'Серебро': 'SLVRUB_TOM'
    }
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.MetalPricesTable')
        
        self.current_data = {}  # {date: price}
        self.loading_thread = None
        self.progress = None
        
        self.init_ui()
        self.load_metals()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("💰 Исторические цены на драгоценные металлы (данные с MOEX)")
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
        
        # Панель управления
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_panel.setStyleSheet("QFrame { background-color: #f5f5f5; border-radius: 3px; padding: 5px; }")
        
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)
        
        # Выбор металла
        control_layout.addWidget(QLabel("Металл:"))
        self.metal_combo = QComboBox()
        self.metal_combo.setMinimumWidth(150)
        self.metal_combo.currentIndexChanged.connect(self.on_metal_changed)
        control_layout.addWidget(self.metal_combo)
        
        # Период
        control_layout.addWidget(QLabel("С:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setMaximumWidth(120)
        control_layout.addWidget(self.start_date_edit)
        
        control_layout.addWidget(QLabel("По:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setMaximumWidth(120)
        control_layout.addWidget(self.end_date_edit)
        
        # Кнопка загрузки
        self.load_btn = QPushButton("📥 Загрузить данные")
        self.load_btn.clicked.connect(self.load_data)
        self.load_btn.setMinimumHeight(30)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        control_layout.addWidget(self.load_btn)
        
        # Кнопка обновления из БД
        self.refresh_btn = QPushButton("🔄 Обновить из БД")
        self.refresh_btn.clicked.connect(self.refresh_from_db)
        self.refresh_btn.setMinimumHeight(30)
        control_layout.addWidget(self.refresh_btn)
        
        control_layout.addStretch()
        control_panel.setLayout(control_layout)
        layout.addWidget(control_panel)
        
        # Таблица для отображения данных
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Дата", "Цена закрытия (₽/г)", "Изменение", "Источник"])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Настройка колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        # Статус бар
        self.status_bar = QFrame()
        self.status_bar.setFrameShape(QFrame.StyledPanel)
        self.status_bar.setMaximumHeight(30)
        self.status_bar.setStyleSheet("QFrame { background-color: #f0f0f0; }")
        
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
    
    def load_metals(self):
        """Загружает только золото и серебро в комбобокс"""
        self.metal_combo.clear()
        self.metal_combo.addItem("— Выберите металл —", None)
        
        # Получаем только металлы с нужными тикерами
        metals = self.db_manager.session.query(Metal).filter(
            Metal.ticker_moex.in_(['GLDRUB_TOM', 'SLVRUB_TOM'])
        ).order_by(Metal.name).all()
        
        # Если металлы не найдены в БД, создаем их
        if not metals:
            self._create_default_metals()
            metals = self.db_manager.session.query(Metal).filter(
                Metal.ticker_moex.in_(['GLDRUB_TOM', 'SLVRUB_TOM'])
            ).order_by(Metal.name).all()
        
        for metal in metals:
            display_text = metal.get_display_text()
            if metal.ticker_moex:
                display_text += f" [{metal.ticker_moex}]"
            self.metal_combo.addItem(display_text, metal.id)
    
    def _create_default_metals(self):
        """Создает записи для золота и серебра, если их нет"""
        try:
            # Проверяем, есть ли уже золото
            gold = self.db_manager.session.query(Metal).filter_by(name="Золото").first()
            if not gold:
                gold = Metal(
                    name="Золото",
                    purity="999",
                    description="Золото 999 пробы",
                    ticker_moex="GLDRUB_TOM"
                )
                self.db_manager.session.add(gold)
            
            # Проверяем, есть ли уже серебро
            silver = self.db_manager.session.query(Metal).filter_by(name="Серебро").first()
            if not silver:
                silver = Metal(
                    name="Серебро",
                    purity="999",
                    description="Серебро 999 пробы",
                    ticker_moex="SLVRUB_TOM"
                )
                self.db_manager.session.add(silver)
            
            self.db_manager.session.commit()
            self.logger.info("Созданы записи для золота и серебра")
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании металлов: {e}")
    
    def on_metal_changed(self, index):
        """Обработчик выбора металла"""
        metal_id = self.metal_combo.currentData()
        if metal_id:
            self.refresh_from_db()
    
    def refresh_from_db(self):
        """Обновляет данные из базы данных"""
        metal_id = self.metal_combo.currentData()
        if not metal_id:
            return
        
        # Получаем данные из БД
        prices = self.db_manager.session.query(MetalPriceHistory).filter_by(
            metal_id=metal_id
        ).order_by(MetalPriceHistory.date.desc()).all()
        
        if not prices:
            self.status_label.setText("Нет данных в базе. Загрузите с MOEX.")
            self.table.setRowCount(0)
            self.stats_label.setText("")
            return
        
        # Заполняем таблицу
        self._fill_table(prices)
        
        # Обновляем статус
        metal = self.db_manager.session.query(Metal).get(metal_id)
        last_date = prices[0].date if prices else "—"
        self.status_label.setText(f"Данные из БД для {metal.get_display_text()}")
        self.stats_label.setText(f"Всего записей: {len(prices)} | Последнее обновление: {last_date}")
    
    def load_data(self):
        """Загружает данные с MOEX"""
        metal_id = self.metal_combo.currentData()
        if not metal_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите металл")
            return
        
        metal = self.db_manager.session.query(Metal).get(metal_id)
        if not metal.ticker_moex:
            QMessageBox.warning(self, "Предупреждение", 
                               f"Для металла '{metal.name}' не указан биржевой тикер.")
            return
        
        # Получаем даты
        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()
        
        if start_qdate > end_qdate:
            QMessageBox.warning(self, "Предупреждение", "Начальная дата не может быть позже конечной")
            return
        
        start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day())
        end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day())
        
        # Показываем прогресс
        self.progress = QProgressDialog("Загрузка исторических цен...", "Отмена", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setAutoClose(True)
        self.progress.setAutoReset(True)
        self.progress.show()
        
        # Отключаем кнопки
        self.load_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.metal_combo.setEnabled(False)
        
        # Запускаем поток загрузки
        self.loading_thread = PriceLoaderThread(
            self.db_manager, metal_id, metal.ticker_moex, start_date, end_date
        )
        self.loading_thread.finished.connect(self.on_data_loaded)
        self.loading_thread.error.connect(self.on_load_error)
        self.loading_thread.progress.connect(self.on_load_progress)
        self.loading_thread.finished.connect(self.on_thread_finished)
        self.loading_thread.error.connect(self.on_thread_finished)
        self.loading_thread.start()
    
    @Slot(int, int)
    def on_load_progress(self, current, total):
        """Обновляет прогресс загрузки"""
        if self.progress is not None:
            try:
                percent = int((current / total) * 100)
                self.progress.setValue(percent)
                self.progress.setLabelText(f"Загрузка... {current}/{total} дней")
            except (RuntimeError, AttributeError):
                self.progress = None
                self.logger.debug(f"Прогресс-диалог недоступен: {current}/{total}")
    
    @Slot(dict)
    def on_data_loaded(self, price_data):
        """Обработчик успешной загрузки данных"""
        if not price_data:
            self.status_label.setText("Нет данных за выбранный период")
            return
        
        # Получаем все данные из БД для этого металла
        metal_id = self.metal_combo.currentData()
        prices = self.db_manager.session.query(MetalPriceHistory).filter_by(
            metal_id=metal_id
        ).order_by(MetalPriceHistory.date.desc()).all()
        
        # Заполняем таблицу
        self._fill_table(prices)
        
        # Обновляем статус
        metal = self.db_manager.session.query(Metal).get(metal_id)
        dates = list(price_data.keys())
        
        total_in_db = len(prices)
        new_records = len(price_data)
        
        self.status_label.setText(f"✅ Загружено {new_records} новых записей для {metal.get_display_text()}")
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            self.stats_label.setText(f"Всего в БД: {total_in_db} | Период: {min_date} - {max_date}")
    
    @Slot(str)
    def on_load_error(self, error_msg):
        """Обработчик ошибки загрузки"""
        QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить данные:\n{error_msg}")
        self.status_label.setText("❌ Ошибка загрузки")
        
        # Даже при ошибке показываем то, что уже есть в БД
        metal_id = self.metal_combo.currentData()
        if metal_id:
            prices = self.db_manager.session.query(MetalPriceHistory).filter_by(
                metal_id=metal_id
            ).order_by(MetalPriceHistory.date.desc()).all()
            
            if prices:
                self._fill_table(prices)
                self.stats_label.setText(f"Показаны данные из БД: {len(prices)} записей")
    
    @Slot()
    def on_thread_finished(self):
        """Обработчик завершения потока"""
        self.load_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.metal_combo.setEnabled(True)
        
        if self.progress is not None:
            try:
                self.progress.close()
            except:
                pass
            self.progress = None
        
        self.loading_thread = None
    
    def _fill_table(self, prices):
        """Заполняет таблицу данными"""
        self.table.setRowCount(len(prices))
        self.table.setSortingEnabled(False)
        
        last_price = None
        for row, price_entry in enumerate(prices):
            # Дата
            date_item = QTableWidgetItem(price_entry.date.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, date_item)
            
            # Цена
            price_item = QTableWidgetItem(f"{price_entry.close_price:.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, price_item)
            
            # Изменение
            if last_price is not None:
                change = price_entry.close_price - last_price
                change_percent = (change / last_price) * 100
                
                change_text = f"{change:+.2f} ({change_percent:+.2f}%)"
                change_item = QTableWidgetItem(change_text)
                change_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                if change > 0:
                    change_item.setForeground(QColor(40, 167, 69))
                elif change < 0:
                    change_item.setForeground(QColor(220, 53, 69))
                else:
                    change_item.setForeground(QColor(108, 117, 125))
            else:
                change_item = QTableWidgetItem("—")
                change_item.setTextAlignment(Qt.AlignCenter)
            
            self.table.setItem(row, 2, change_item)
            
            # Источник
            source_item = QTableWidgetItem("MOEX")
            source_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, source_item)
            
            last_price = price_entry.close_price
        
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()