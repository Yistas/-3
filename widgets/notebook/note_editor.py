# ===== gui/widgets/notebook/note_editor.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Редактор заметок и задач
"""

import json
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QColorDialog, QMessageBox,
    QDateTimeEdit, QCheckBox, QListWidget, QListWidgetItem,
    QInputDialog, QFrame, QScrollArea, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QColor

from database.models import NotebookNote, NotebookCategory, NotebookTask


class TaskItem(QWidget):
    """Виджет задачи с чекбоксом"""
    
    task_deleted = Signal(object)
    task_toggled = Signal(object, bool)
    
    def __init__(self, text, is_checked=False, parent=None):
        super().__init__(parent)
        self.text = text
        self.is_checked = is_checked
        self.init_ui()
    
# ===== gui/widgets/notebook/note_editor.py =====
# МЕТОД: NoteEditor.init_ui (ПОЛНОСТЬЮ)

    def init_ui(self):
        """Инициализация интерфейса"""
        from PySide6.QtWidgets import QSizePolicy, QFrame
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # Верхняя панель
        top_panel = self._create_top_panel()
        top_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_panel.setFixedHeight(80)
        layout.addWidget(top_panel)
        
        # Заголовок
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Заголовок...")
        self.title_edit.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        self.title_edit.setMinimumHeight(35)
        layout.addWidget(self.title_edit)
        
        # Содержимое (для заметок) - С ПОДДЕРЖКОЙ HTML
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText(
            "Текст заметки...\n\n"
            "Поддерживается форматирование:\n"
            "• Таблицы\n"
            "• Жирный/курсив (Ctrl+B, Ctrl+I)\n"
            "• Списки\n"
            "• Вставка изображений (Ctrl+V)"
        )
        # Включаем Rich Text (HTML) режим
        self.content_edit.setAcceptRichText(True)
        self.content_edit.setMinimumHeight(200)
        layout.addWidget(self.content_edit)
        
        # Список задач (для task/checklist)
        self.tasks_widget = QWidget()
        self.tasks_layout = QVBoxLayout()
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(2)
        self.tasks_widget.setLayout(self.tasks_layout)
        layout.addWidget(self.tasks_widget)
        self.tasks_widget.hide()
        
        # Кнопка добавления задачи
        self.add_task_btn = QPushButton("➕ Добавить задачу")
        self.add_task_btn.clicked.connect(self.add_task)
        self.add_task_btn.setFixedHeight(30)
        self.add_task_btn.hide()
        layout.addWidget(self.add_task_btn)
        
        # Нижняя панель
        bottom_panel = self._create_bottom_panel()
        bottom_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_panel.setFixedHeight(45)
        layout.addWidget(bottom_panel)
        
        # Статус
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        self.status_label.setFixedHeight(20)
        layout.addWidget(self.status_label)

    def _on_checkbox_changed(self, state):
        self.is_checked = (state == Qt.Checked)
        if self.is_checked:
            self.label.setStyleSheet("text-decoration: line-through; color: #999;")
        else:
            self.label.setStyleSheet("")
        self.task_toggled.emit(self, self.is_checked)
    
    def _on_delete(self):
        self.task_deleted.emit(self)
    
    def get_text(self):
        return self.text


class NoteEditor(QWidget):
    """Редактор заметок и задач"""
    
    note_saved = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_note = None
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        # Верхняя панель
        top_panel = self._create_top_panel()
        layout.addWidget(top_panel)
        
        # Заголовок
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Заголовок...")
        self.title_edit.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.title_edit)
        
        # Содержимое (для заметок)
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Текст заметки...")
        layout.addWidget(self.content_edit)
        
        # Список задач (для task/checklist)
        self.tasks_widget = QWidget()
        self.tasks_layout = QVBoxLayout()
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_widget.setLayout(self.tasks_layout)
        layout.addWidget(self.tasks_widget)
        
        self.tasks_widget.hide()
        
        # Кнопка добавления задачи
        self.add_task_btn = QPushButton("➕ Добавить задачу")
        self.add_task_btn.clicked.connect(self.add_task)
        self.add_task_btn.hide()
        layout.addWidget(self.add_task_btn)
        
        # Нижняя панель
        bottom_panel = self._create_bottom_panel()
        layout.addWidget(bottom_panel)
        
        # Статус
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.status_label)
    
# ===== gui/widgets/notebook/note_editor.py =====
# МЕТОД: NoteEditor._create_top_panel (ПОЛНОСТЬЮ)

    def _create_top_panel(self):
        """Создаёт верхнюю панель с настройками"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 5px;
                padding: 2px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)
        panel.setLayout(layout)
        
        # Тип заметки
        layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("📝 Заметка", "note")
        self.type_combo.addItem("☑ Список задач", "task")
        self.type_combo.addItem("📋 Чек-лист", "checklist")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.type_combo.setFixedHeight(28)
        self.type_combo.setMinimumWidth(120)
        layout.addWidget(self.type_combo)
        
        layout.addSpacing(15)
        
        # Категория
        layout.addWidget(QLabel("Категория:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("— Без категории —", None)
        self.category_combo.setFixedHeight(28)
        self.category_combo.setMinimumWidth(150)
        layout.addWidget(self.category_combo)
        
        # Кнопка выбора цвета
        self.color_btn = QPushButton("🎨 Цвет")
        self.color_btn.clicked.connect(self.choose_color)
        self.color_btn.setFixedSize(80, 28)
        layout.addWidget(self.color_btn)
        
        layout.addStretch()
        
        # Кнопка напоминания
        self.reminder_btn = QPushButton("🔔 Напомнить")
        self.reminder_btn.clicked.connect(self.set_reminder)
        self.reminder_btn.setFixedSize(100, 28)
        layout.addWidget(self.reminder_btn)
        
        return panel

# ===== gui/widgets/notebook/note_editor.py =====
# МЕТОД: NoteEditor._create_bottom_panel (ПОЛНОСТЬЮ)

    def _create_bottom_panel(self):
        """Создаёт нижнюю панель с кнопками"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-top: 1px solid #ddd;
                border-radius: 0 0 5px 5px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)
        panel.setLayout(layout)
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_note)
        self.save_btn.setFixedHeight(32)
        self.save_btn.setMinimumWidth(100)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
        
        self.pin_btn = QPushButton("📍 Закрепить")
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setFixedHeight(32)
        self.pin_btn.setMinimumWidth(100)
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #333;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        layout.addWidget(self.pin_btn)
        
        self.archive_btn = QPushButton("📦 В архив")
        self.archive_btn.clicked.connect(self.toggle_archive)
        self.archive_btn.setFixedHeight(32)
        self.archive_btn.setMinimumWidth(100)
        self.archive_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        layout.addWidget(self.archive_btn)
        
        return panel
    
    def load_categories(self):
        """Загружает категории в комбобокс"""
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        self.category_combo.blockSignals(True)
        current_id = self.category_combo.currentData()
        
        self.category_combo.clear()
        self.category_combo.addItem("— Без категории —", None)
        
        for cat in categories:
            self.category_combo.addItem(f"{cat.icon} {cat.name}", cat.id)
        
        if current_id:
            idx = self.category_combo.findData(current_id)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        
        self.category_combo.blockSignals(False)
    
    def on_type_changed(self):
        """Обработчик изменения типа заметки"""
        note_type = self.type_combo.currentData()
        
        if note_type in ['task', 'checklist']:
            self.content_edit.hide()
            self.tasks_widget.show()
            self.add_task_btn.show()
        else:
            self.content_edit.show()
            self.tasks_widget.hide()
            self.add_task_btn.hide()
    
    def add_task(self):
        """Добавляет новую задачу"""
        text, ok = QInputDialog.getText(self, "Новая задача", "Введите текст задачи:")
        if ok and text.strip():
            task_widget = TaskItem(text.strip(), False, self)
            task_widget.task_deleted.connect(self.on_task_deleted)
            task_widget.task_toggled.connect(self.on_task_toggled)
            self.tasks_layout.addWidget(task_widget)
    
    def on_task_deleted(self, task_widget):
        """Удаляет задачу из списка"""
        self.tasks_layout.removeWidget(task_widget)
        task_widget.deleteLater()
    
    def on_task_toggled(self, task_widget, is_checked):
        """Обработчик изменения состояния задачи"""
        # Можно добавить логику при изменении состояния
        pass
    
    def choose_color(self):
        """Выбор цвета для заметки"""
        current_color = self.current_note.color if self.current_note else None
        initial = QColor(current_color) if current_color else QColor("#ffffff")
        color = QColorDialog.getColor(initial, self, "Выберите цвет")
        if color.isValid():
            self.color_btn.setStyleSheet(f"background-color: {color.name()};")
            self.color_btn.setText("")
            self.color_btn.setToolTip(color.name())
            if self.current_note:
                self.current_note.color = color.name()
    
    def set_reminder(self):
        """Установка напоминания"""
        if not self.current_note:
            QMessageBox.warning(self, "Предупреждение", "Сначала сохраните заметку")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Напоминание")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Дата и время:"))
        datetime_edit = QDateTimeEdit()
        datetime_edit.setCalendarPopup(True)
        datetime_edit.setMinimumDateTime(QDateTime.currentDateTime())
        if self.current_note.remind_at:
            datetime_edit.setDateTime(QDateTime(self.current_note.remind_at))
        else:
            datetime_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        layout.addWidget(datetime_edit)
        
        layout.addWidget(QLabel("Повтор:"))
        repeat_combo = QComboBox()
        repeat_combo.addItem("Нет", "none")
        repeat_combo.addItem("Ежедневно", "daily")
        repeat_combo.addItem("Еженедельно", "weekly")
        repeat_combo.addItem("Ежемесячно", "monthly")
        layout.addWidget(repeat_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            self.current_note.remind_at = datetime_edit.dateTime().toPython()
            self.current_note.remind_sent = False
            self.db_manager.session.commit()
            QMessageBox.information(self, "Успех", "Напоминание установлено")
    
# ===== gui/widgets/notebook/note_editor.py =====
# В МЕТОДЕ load_note, ЗАМЕНИТЬ загрузку контента

    def load_note(self, note):
        """Загружает заметку в редактор"""
        self.current_note = note
        
        self.load_categories()
        
        # Заголовок
        self.title_edit.setText(note.title or "")
        
        # Тип
        idx = self.type_combo.findData(note.note_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        
        # Категория
        if note.category_id:
            idx = self.category_combo.findData(note.category_id)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        
        # Цвет
        if note.color:
            self.color_btn.setStyleSheet(f"background-color: {note.color};")
            self.color_btn.setText("")
            self.color_btn.setToolTip(note.color)
        else:
            self.color_btn.setStyleSheet("")
            self.color_btn.setText("🎨 Цвет")
        
        # Контент или задачи - ИСПРАВЛЕНО: сохраняем HTML
        if note.note_type in ['task', 'checklist']:
            self.on_type_changed()
            # Очищаем существующие задачи
            while self.tasks_layout.count():
                child = self.tasks_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            # Загружаем задачи
            for task in note.tasks:
                task_widget = TaskItem(task.text, task.is_checked, self)
                task_widget.task_deleted.connect(self.on_task_deleted)
                task_widget.task_toggled.connect(self.on_task_toggled)
                self.tasks_layout.addWidget(task_widget)
        else:
            # Загружаем HTML-контент
            content = note.content or ""
            # Проверяем, не является ли контент обычным текстом (без HTML тегов)
            if content and not ('<' in content and '>' in content):
                # Обычный текст - преобразуем в HTML с сохранением переносов
                content = content.replace('\n', '<br>')
            self.content_edit.setHtml(content)
        
        self.status_label.setText(f"Обновлено: {note.updated_at.strftime('%d.%m.%Y %H:%M')}")

# ===== gui/widgets/notebook/note_editor.py =====
# В МЕТОДЕ save_note, ЗАМЕНИТЬ сохранение контента

    def save_note(self):
        """Сохраняет заметку"""
        if not self.current_note:
            return
        
        self.current_note.title = self.title_edit.text().strip() or "Без названия"
        self.current_note.note_type = self.type_combo.currentData()
        self.current_note.category_id = self.category_combo.currentData()
        self.current_note.updated_at = datetime.now()
        
        # Сохраняем контент или задачи
        if self.current_note.note_type in ['task', 'checklist']:
            # Сначала удаляем старые задачи
            for task in self.current_note.tasks[:]:
                self.db_manager.session.delete(task)
            
            # Добавляем новые задачи
            for i in range(self.tasks_layout.count()):
                widget = self.tasks_layout.itemAt(i).widget()
                if widget and isinstance(widget, TaskItem):
                    task = NotebookTask(
                        note_id=self.current_note.id,
                        text=widget.get_text(),
                        is_checked=widget.is_checked,
                        sort_order=i
                    )
                    self.db_manager.session.add(task)
            
            self.current_note.content = None
        else:
            # Сохраняем HTML-контент (с форматированием)
            html_content = self.content_edit.toHtml()
            # Удаляем лишний обёрточный HTML, если он есть
            # QTextEdit.toHtml() возвращает полный HTML документ, нам нужен только body
            if '<body>' in html_content and '</body>' in html_content:
                import re
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL)
                if body_match:
                    html_content = body_match.group(1).strip()
            self.current_note.content = html_content
        
        self.db_manager.session.commit()
        
        self.status_label.setText(f"Сохранено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        self.note_saved.emit()

    def toggle_pin(self):
        """Закрепить/открепить заметку"""
        if not self.current_note:
            return
        self.current_note.is_pinned = not self.current_note.is_pinned
        self.db_manager.session.commit()
        self.note_saved.emit()
        
        if self.current_note.is_pinned:
            QMessageBox.information(self, "Успех", "Заметка закреплена")
        else:
            QMessageBox.information(self, "Успех", "Заметка откреплена")
    
    def toggle_archive(self):
        """Архивировать/восстановить заметку"""
        if not self.current_note:
            return
        self.current_note.is_archived = not self.current_note.is_archived
        if self.current_note.is_archived:
            self.current_note.is_pinned = False
        self.db_manager.session.commit()
        self.note_saved.emit()
        
        if self.current_note.is_archived:
            QMessageBox.information(self, "Успех", "Заметка перемещена в архив")
        else:
            QMessageBox.information(self, "Успех", "Заметка восстановлена из архива")
    
    def clear(self):
        """Очищает форму редактора"""
        self.current_note = None
        self.title_edit.clear()
        self.content_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.color_btn.setStyleSheet("")
        self.color_btn.setText("🎨 Цвет")
        self.status_label.clear()
        
        # Очищаем задачи
        while self.tasks_layout.count():
            child = self.tasks_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.content_edit.show()
        self.tasks_widget.hide()
        self.add_task_btn.hide()