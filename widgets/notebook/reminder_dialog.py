# ===== gui/widgets/notebook/reminder_dialog.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для создания и управления напоминаниями
"""

from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QDateTimeEdit, QComboBox, QLineEdit, QTextEdit, QFormLayout,
    QGroupBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor

from database.models import NotebookReminder


class ReminderDialog(QDialog):
    """Диалог управления напоминаниями"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        
        self.setWindowTitle("🔔 Напоминания")
        self.setMinimumSize(600, 450)
        
        self.init_ui()
        self.load_reminders()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("🔔 Управление напоминаниями")
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
        
        # Форма добавления напоминания
        add_group = QGroupBox("➕ Добавить напоминание")
        add_layout = QFormLayout()
        
        self.reminder_title = QLineEdit()
        self.reminder_title.setPlaceholderText("Заголовок")
        add_layout.addRow("Заголовок:", self.reminder_title)
        
        self.reminder_text = QTextEdit()
        self.reminder_text.setMaximumHeight(60)
        self.reminder_text.setPlaceholderText("Текст напоминания (необязательно)")
        add_layout.addRow("Текст:", self.reminder_text)
        
        datetime_layout = QHBoxLayout()
        self.reminder_datetime = QDateTimeEdit()
        self.reminder_datetime.setCalendarPopup(True)
        self.reminder_datetime.setMinimumDateTime(QDateTime.currentDateTime())
        self.reminder_datetime.setDateTime(QDateTime.currentDateTime().addHours(1))
        datetime_layout.addWidget(self.reminder_datetime)
        
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("Не повторять", "none")
        self.repeat_combo.addItem("Ежедневно", "daily")
        self.repeat_combo.addItem("Еженедельно", "weekly")
        self.repeat_combo.addItem("Ежемесячно", "monthly")
        datetime_layout.addWidget(self.repeat_combo)
        
        add_layout.addRow("Дата и время:", datetime_layout)
        
        add_btn = QPushButton("➕ Добавить напоминание")
        add_btn.clicked.connect(self.add_reminder)
        add_layout.addRow("", add_btn)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        # Список напоминаний
        layout.addWidget(QLabel("📋 Список напоминаний:"))
        
        self.reminder_table = QTableWidget()
        self.reminder_table.setColumnCount(6)
        self.reminder_table.setHorizontalHeaderLabels(
            ["ID", "Заголовок", "Текст", "Дата и время", "Повтор", ""]
        )
        self.reminder_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.reminder_table.setAlternatingRowColors(True)
        
        header = self.reminder_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.reminder_table)
        
        # Панель кнопок
        button_layout = QHBoxLayout()
        
        delete_btn = QPushButton("🗑️ Удалить выбранное")
        delete_btn.clicked.connect(self.delete_reminder)
        button_layout.addWidget(delete_btn)
        
        complete_btn = QPushButton("✅ Отметить выполненным")
        complete_btn.clicked.connect(self.complete_reminder)
        button_layout.addWidget(complete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_reminders(self):
        """Загружает напоминания в таблицу"""
        reminders = self.db_manager.session.query(NotebookReminder).filter(
            NotebookReminder.is_done == False
        ).order_by(NotebookReminder.remind_at).all()
        
        self.reminder_table.setRowCount(len(reminders))
        self.reminder_table.setSortingEnabled(False)
        
        for row, rem in enumerate(reminders):
            # ID
            id_item = QTableWidgetItem(str(rem.id))
            id_item.setData(Qt.UserRole, rem.id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self.reminder_table.setItem(row, 0, id_item)
            
            # Заголовок
            title_item = QTableWidgetItem(rem.title)
            self.reminder_table.setItem(row, 1, title_item)
            
            # Текст
            text_item = QTableWidgetItem(rem.text or "")
            self.reminder_table.setItem(row, 2, text_item)
            
            # Дата и время
            date_str = rem.remind_at.strftime("%d.%m.%Y %H:%M")
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)
            
            # Подсветка просроченных
            if rem.remind_at < datetime.now():
                date_item.setForeground(QColor(231, 76, 60))
            
            self.reminder_table.setItem(row, 3, date_item)
            
            # Повтор
            repeat_names = {
                'none': 'Нет', 'daily': 'Ежедневно',
                'weekly': 'Еженедельно', 'monthly': 'Ежемесячно'
            }
            repeat_item = QTableWidgetItem(repeat_names.get(rem.repeat_type, 'Нет'))
            repeat_item.setTextAlignment(Qt.AlignCenter)
            self.reminder_table.setItem(row, 4, repeat_item)
            
            # Кнопка отложить
            snooze_btn = QPushButton("⏰ Отложить")
            snooze_btn.setFixedSize(80, 24)
            snooze_btn.clicked.connect(lambda checked, r=rem: self.snooze_reminder(r))
            self.reminder_table.setCellWidget(row, 5, snooze_btn)
        
        self.reminder_table.setSortingEnabled(True)
        self.reminder_table.resizeColumnsToContents()
    
    def add_reminder(self):
        """Добавляет новое напоминание"""
        title = self.reminder_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Предупреждение", "Введите заголовок")
            return
        
        reminder = NotebookReminder(
            title=title,
            text=self.reminder_text.toPlainText().strip() or None,
            remind_at=self.reminder_datetime.dateTime().toPython(),
            repeat_type=self.repeat_combo.currentData()
        )
        
        self.db_manager.session.add(reminder)
        self.db_manager.session.commit()
        
        self.reminder_title.clear()
        self.reminder_text.clear()
        self.reminder_datetime.setDateTime(QDateTime.currentDateTime().addHours(1))
        
        self.load_reminders()
        QMessageBox.information(self, "Успех", "Напоминание добавлено")
    
    def delete_reminder(self):
        """Удаляет выбранное напоминание"""
        current_row = self.reminder_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите напоминание")
            return
        
        rem_id = self.reminder_table.item(current_row, 0).data(Qt.UserRole)
        reminder = self.db_manager.session.query(NotebookReminder).get(rem_id)
        
        if reminder:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Удалить напоминание '{reminder.title}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.db_manager.session.delete(reminder)
                self.db_manager.session.commit()
                self.load_reminders()
    
    def complete_reminder(self):
        """Отмечает напоминание выполненным"""
        current_row = self.reminder_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите напоминание")
            return
        
        rem_id = self.reminder_table.item(current_row, 0).data(Qt.UserRole)
        reminder = self.db_manager.session.query(NotebookReminder).get(rem_id)
        
        if reminder:
            reminder.is_done = True
            self.db_manager.session.commit()
            self.load_reminders()
            QMessageBox.information(self, "Успех", "Напоминание отмечено выполненным")
    
    def snooze_reminder(self, reminder):
        """Откладывает напоминание на 1 час"""
        reminder.remind_at += timedelta(hours=1)
        self.db_manager.session.commit()
        self.load_reminders()
        QMessageBox.information(self, "Успех", f"Напоминание отложено до {reminder.remind_at.strftime('%H:%M')}")