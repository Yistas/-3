# -*- coding: utf-8 -*-

"""
Кастомный диалог прогресса с подробной информацией
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QApplication,
                               QTextEdit, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class ProgressDialog(QDialog):
    """Кастомный диалог прогресса с логом операций"""
    
    def __init__(self, title="Выполняется операция", message="Пожалуйста, подождите...", parent=None):
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Убираем кнопку "?" из заголовка
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # Устанавливаем стиль
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border: 1px solid #4a6fa5;
                border-radius: 8px;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
            }
            QProgressBar {
                border: 1px solid #4a6fa5;
                border-radius: 3px;
                text-align: center;
                background-color: #3c3c3c;
                color: #ffffff;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4a6fa5;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #4a6fa5;
                border-radius: 3px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        self.setLayout(layout)
        
        # Заголовок с иконкой
        title_layout = QHBoxLayout()
        
        self.icon_label = QLabel("🔄")
        self.icon_label.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(self.icon_label)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        # Статус
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #4a6fa5; font-size: 12px;")
        title_layout.addWidget(self.status_label)
        
        layout.addLayout(title_layout)
        
        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #4a6fa5;")
        layout.addWidget(sep)
        
        # Сообщение
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(self.message_label)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Лог операций
        log_label = QLabel("📋 Детали операции:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setMinimumHeight(100)
        layout.addWidget(self.log_text)
        
        # Кнопка отмены
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.setVisible(False)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self._canceled = False
        self._auto_close_timer = None
        self._step_counter = 0
    
    def set_message(self, message):
        """Обновляет основное сообщение"""
        self.message_label.setText(message)
        QApplication.processEvents()
    
    def set_status(self, status):
        """Обновляет статус (например, "Загрузка...")"""
        self.status_label.setText(status)
        QApplication.processEvents()
    
    def add_log(self, text, level="info"):
        """Добавляет запись в лог"""
        self._step_counter += 1
        prefix = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "progress": "🔄"
        }.get(level, "📌")
        
        timestamp = QApplication.instance().applicationName()
        log_line = f"{prefix} {text}"
        self.log_text.append(log_line)
        
        # Прокручиваем вниз
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        QApplication.processEvents()
    
    def set_value(self, value):
        """Устанавливает значение прогресса"""
        self.progress_bar.setValue(value)
        QApplication.processEvents()
    
    def set_range(self, minimum, maximum):
        """Устанавливает диапазон прогресса"""
        self.progress_bar.setRange(minimum, maximum)
    
    def set_cancel_enabled(self, enabled=True):
        """Включает/отключает кнопку отмены"""
        self.cancel_btn.setVisible(enabled)
    
    def cancel(self):
        """Отменяет операцию"""
        self._canceled = True
        self.set_message("⏹️ Отмена операции...")
        self.add_log("Операция отменена пользователем", "warning")
        self.cancel_btn.setEnabled(False)
        self.icon_label.setText("⏹️")
    
    def was_canceled(self):
        """Возвращает True, если операция была отменена"""
        return self._canceled
    
    def auto_close(self, delay_ms=1000):
        """Автоматически закрывает диалог через указанную задержку"""
        self._auto_close_timer = QTimer()
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.accept)
        self._auto_close_timer.start(delay_ms)
    
    def closeEvent(self, event):
        """Обработчик закрытия"""
        if self._auto_close_timer:
            self._auto_close_timer.stop()
        event.accept()