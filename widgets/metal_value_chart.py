import logging
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QDateEdit, QComboBox, QLabel, QMessageBox,
                               QCheckBox, QProgressDialog)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QTimer
from PySide6.QtGui import QFont

# Импорты для графика (используем matplotlib, как в statistics_tab)
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from database.models import Metal, Coin, MetalPriceHistory
from utils.moex_api import MOEXAPIClient

# Поток для фоновой загрузки данных с биржи
class PriceLoaderThread(QThread):
    finished = Signal(dict)  # Сигнал с результатом {metal_id: {date: price}}
    error = Signal(str)
    
    def __init__(self, db_manager, metal_id, start_date, end_date):
        super().__init__()
        self.db_manager = db_manager
        self.metal_id = metal_id
        self.start_date = start_date
        self.end_date = end_date
        
    def run(self):
        try:
            metal = self.db_manager.session.query(Metal).get(self.metal_id)
            if not metal or not metal.ticker_moex:  # Добавьте поле ticker_moex в модель Metal
                self.error.emit(f"Для металла '{metal.name if metal else 'Неизвестный'}' не указан биржевой тикер.")
                return
            
            result = {}
            current_date = self.start_date
            while current_date <= self.end_date:
                # Проверяем, есть ли уже данные в БД
                existing = self.db_manager.session.query(MetalPriceHistory).filter_by(
                    metal_id=self.metal_id, date=current_date.date()
                ).first()
                
                if existing:
                    result[current_date.date()] = existing.close_price
                else:
                    # Загружаем с MOEX
                    price = MOEXAPIClient.fetch_price_for_date(metal.ticker_moex, current_date)
                    if price is not None:
                        # Сохраняем в БД
                        history_entry = MetalPriceHistory(
                            metal_id=self.metal_id,
                            date=current_date.date(),
                            close_price=price
                        )
                        self.db_manager.session.add(history_entry)
                        self.db_manager.session.commit()
                        result[current_date.date()] = price
                    else:
                        # Если данных нет (выходной), пропускаем, но можно сохранить как None
                        pass
                
                current_date += timedelta(days=1)
            
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MetalValueChartWidget(QWidget):
    """Виджет для отображения графика стоимости металлов в коллекции"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.MetalValueChart')
        
        self.current_data = {}  # {date: total_value}
        self.loading_thread = None
        
        self.init_ui()
        self.load_initial_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📈 График стоимости коллекции (на основе биржевых цен металлов)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Выбор металла
        control_panel.addWidget(QLabel("Металл:"))
        self.metal_combo = QComboBox()
        self.load_metals()
        control_panel.addWidget(self.metal_combo)
        
        # Период
        control_panel.addWidget(QLabel("С:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.setCalendarPopup(True)
        control_panel.addWidget(self.start_date_edit)
        
        control_panel.addWidget(QLabel("По:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        control_panel.addWidget(self.end_date_edit)
        
        # Кнопка обновления
        self.refresh_btn = QPushButton("🔄 Загрузить и обновить")
        self.refresh_btn.clicked.connect(self.load_data)
        control_panel.addWidget(self.refresh_btn)
        
        # Чекбокс для автозагрузки последнего дня
        self.auto_load_check = QCheckBox("Автозагрузка последнего рабочего дня")
        self.auto_load_check.setChecked(True)
        control_panel.addWidget(self.auto_load_check)
        
        control_panel.addStretch()
        layout.addLayout(control_panel)
        
        # График
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Статус
        self.status_label = QLabel("Готов к загрузке данных")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
    
    def load_metals(self):
        """Загружает список металлов в комбобокс"""
        self.metal_combo.clear()
        metals = self.db_manager.session.query(Metal).all()
        for metal in metals:
            # Здесь нужно добавить поле ticker_moex в модель Metal
            # Если его нет, пока просто добавляем название
            self.metal_combo.addItem(metal.name, metal.id)
    
    def load_initial_data(self):
        """Загружает данные при старте (последний месяц)"""
        if self.metal_combo.count() > 0:
            self.load_data()
    
    def load_data(self):
        """Загружает данные за выбранный период"""
        metal_id = self.metal_combo.currentData()
        if not metal_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите металл")
            return
        
        start_date = self.start_date_edit.date().toPython()
        end_date = self.end_date_edit.date().toPython()
        
        # Показываем прогресс
        progress = QProgressDialog("Загрузка исторических цен...", "Отмена", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        
        # Запускаем поток загрузки
        self.loading_thread = PriceLoaderThread(self.db_manager, metal_id, start_date, end_date)
        self.loading_thread.finished.connect(self.on_data_loaded)
        self.loading_thread.error.connect(self.on_load_error)
        self.loading_thread.finished.connect(progress.close)
        self.loading_thread.error.connect(progress.close)
        self.loading_thread.start()
    
    def on_data_loaded(self, price_data):
        """Обработчик завершения загрузки данных"""
        # price_data: {date: price_per_gram}
        if not price_data:
            self.status_label.setText("Нет данных за выбранный период")
            return
        
        # Получаем все монеты из выбранного металла
        metal_id = self.metal_combo.currentData()
        coins = self.db_manager.session.query(Coin).filter(
            Coin.metal_id == metal_id,
            Coin.status == 'in_collection'  # Только те, что в коллекции
        ).all()
        
        if not coins:
            self.status_label.setText("Нет монет из этого металла в коллекции")
            return
        
        # Рассчитываем общую стоимость на каждую дату
        daily_values = {}
        for date, price_per_gram in price_data.items():
            total_value = 0
            for coin in coins:
                if coin.weight and coin.fineness:
                    # Вес чистого металла = вес монеты * (проба/1000)
                    # Предполагаем, что fineness хранится как число (например, 925, 900)
                    try:
                        purity = float(coin.fineness) / 1000
                    except:
                        purity = 1.0  # Если проба не указана, считаем 1000-й
                    
                    metal_weight = coin.weight * purity
                    total_value += metal_weight * price_per_gram
            
            daily_values[date] = total_value
        
        self.current_data = daily_values
        self.plot_graph(daily_values)
        self.status_label.setText(f"Данные загружены. Всего дней: {len(daily_values)}")
    
    def on_load_error(self, error_msg):
        """Обработчик ошибок загрузки"""
        QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить данные:\n{error_msg}")
        self.status_label.setText("Ошибка загрузки")
    
    def plot_graph(self, data):
        """Строит график"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        dates = list(data.keys())
        values = list(data.values())
        
        ax.plot(dates, values, marker='o', linestyle='-', color='#4a6fa5', linewidth=2, markersize=4)
        ax.fill_between(dates, values, alpha=0.2, color='#4a6fa5')
        
        # Настройка осей
        ax.set_xlabel('Дата')
        ax.set_ylabel('Стоимость коллекции (руб)')
        ax.set_title(f'Стоимость коллекции на основе цен {self.metal_combo.currentText()}')
        ax.grid(True, linestyle='--', alpha=0.6)
        
        # Форматирование дат на оси X
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.figure.autofmt_xdate()
        
        self.canvas.draw()