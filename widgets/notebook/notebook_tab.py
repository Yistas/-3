# ===== gui/widgets/notebook/notebook_tab.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Вкладка "Заметки" - полноценный органайзер
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QComboBox, QLineEdit, QLabel, QMenu, QApplication
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QColor

from database.models import NotebookNote, NotebookCategory, NotebookTask

from .note_editor import NoteEditor
from .category_manager import CategoryManagerDialog


class NotebookTab(QWidget):
    """Вкладка "Заметки" - органайзер"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.NotebookTab')
        
        self.current_note_id = None
        self.current_filter = 'active'  # 'active', 'archived', 'trash'
        self.current_category_id = None
        
        self.init_ui()
        self.load_categories()
        self.load_notes()
        
        # Таймер для проверки напоминаний (каждую минуту)
        # self.reminder_timer = QTimer()
        # self.reminder_timer.timeout.connect(self.check_reminders)
        # self.reminder_timer.start(60000)  # 60 секунд
    
# ===== gui/widgets/notebook/notebook_tab.py =====
# МЕТОД: NotebookTab.init_ui (ПОЛНОСТЬЮ ЗАМЕНИТЬ)

    def init_ui(self):
        """Инициализация интерфейса"""
        from PySide6.QtWidgets import QSizePolicy
        
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Панель инструментов (НЕ РАСТЯГИВАЕТСЯ)
        toolbar = self._create_toolbar()
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setFixedHeight(40)  # Фиксированная высота
        layout.addWidget(toolbar)
        
        # Фильтры (НЕ РАСТЯГИВАЮТСЯ)
        filter_bar = self._create_filter_bar()
        filter_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_bar.setFixedHeight(35)  # Фиксированная высота
        layout.addWidget(filter_bar)
        
        # Основной сплиттер (растягивается)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Левая панель - список заметок
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - редактор
        self.note_editor = NoteEditor(self.db_manager, self)
        self.note_editor.note_saved.connect(self.on_note_saved)
        splitter.addWidget(self.note_editor)
        
        splitter.setSizes([350, 550])
        layout.addWidget(splitter)

# ===== gui/widgets/notebook/notebook_tab.py =====
# МЕТОД: NotebookTab._create_toolbar (исправить)

    def _create_toolbar(self):
        """Создаёт панель инструментов"""
        from PySide6.QtWidgets import QSizePolicy
        
        toolbar = QWidget()
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)
        toolbar.setLayout(layout)
        
        # Кнопки
        self.new_note_btn = QPushButton("📝 Новая заметка")
        self.new_note_btn.clicked.connect(lambda: self.new_note('note'))
        self.new_note_btn.setFixedHeight(28)
        layout.addWidget(self.new_note_btn)
        
        self.new_task_btn = QPushButton("☑ Новый список")
        self.new_task_btn.clicked.connect(lambda: self.new_note('task'))
        self.new_task_btn.setFixedHeight(28)
        layout.addWidget(self.new_task_btn)
        
        self.new_checklist_btn = QPushButton("📋 Новый чек-лист")
        self.new_checklist_btn.clicked.connect(lambda: self.new_note('checklist'))
        self.new_checklist_btn.setFixedHeight(28)
        layout.addWidget(self.new_checklist_btn)
        
        layout.addStretch()
        
        # Кнопка категорий
        self.cat_btn = QPushButton("📁 Управление категориями")
        self.cat_btn.clicked.connect(self.manage_categories)
        self.cat_btn.setFixedHeight(28)
        layout.addWidget(self.cat_btn)
        
        return toolbar

# ===== gui/widgets/notebook/notebook_tab.py =====
# МЕТОД: NotebookTab._create_filter_bar (исправить)

    def _create_filter_bar(self):
        """Создаёт панель фильтров"""
        from PySide6.QtWidgets import QSizePolicy
        
        filter_widget = QWidget()
        filter_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_widget.setStyleSheet("""
            QWidget {
                background-color: #fafafa;
                border-bottom: 1px solid #ddd;
                padding: 2px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        filter_widget.setLayout(layout)
        
        layout.addWidget(QLabel("Фильтр:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("📌 Все заметки", "active")
        self.filter_combo.addItem("📎 Архив", "archived")
        self.filter_combo.addItem("🗑️ Корзина", "trash")
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        self.filter_combo.setFixedHeight(26)
        layout.addWidget(self.filter_combo)
        
        layout.addWidget(QLabel("Категория:"))
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("📁 Все категории", None)
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)
        self.category_combo.setFixedHeight(26)
        layout.addWidget(self.category_combo)
        
        layout.addWidget(QLabel("Поиск:"))
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по заметкам...")
        self.search_edit.setFixedHeight(26)
        self.search_edit.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_edit)
        
        layout.addStretch()
        
        return filter_widget

    def _create_left_panel(self):
        """Создаёт левую панель со списком заметок"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        
        self.note_list = QListWidget()
        self.note_list.itemClicked.connect(self.on_note_selected)
        self.note_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self.show_note_context_menu)
        layout.addWidget(self.note_list)
        
        return panel
    
    def load_categories(self):
        """Загружает категории в комбобокс"""
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        self.category_combo.blockSignals(True)
        # Сохраняем текущий выбранный ID
        current_data = self.category_combo.currentData()
        
        self.category_combo.clear()
        self.category_combo.addItem("📁 Все категории", None)
        
        for cat in categories:
            self.category_combo.addItem(f"{cat.icon} {cat.name}", cat.id)
        
        # Восстанавливаем выбор
        if current_data:
            idx = self.category_combo.findData(current_data)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        
        self.category_combo.blockSignals(False)
    
    def load_notes(self):
        """Загружает заметки в список"""
        query = self.db_manager.session.query(NotebookNote)
        
        # Фильтр по состоянию
        if self.current_filter == 'active':
            query = query.filter(NotebookNote.is_archived == False, NotebookNote.is_trashed == False)
        elif self.current_filter == 'archived':
            query = query.filter(NotebookNote.is_archived == True)
        elif self.current_filter == 'trash':
            query = query.filter(NotebookNote.is_trashed == True)
        
        # Фильтр по категории
        if self.current_category_id:
            query = query.filter(NotebookNote.category_id == self.current_category_id)
        
        # Поиск
        search_text = self.search_edit.text().strip().lower()
        if search_text:
            query = query.filter(
                (NotebookNote.title.contains(search_text)) |
                (NotebookNote.content.contains(search_text))
            )
        
        # Сортировка: сначала закреплённые, потом по дате обновления
        notes = query.order_by(
            NotebookNote.is_pinned.desc(),
            NotebookNote.updated_at.desc()
        ).all()
        
        self.note_list.clear()
        
        for note in notes:
            # Иконка в зависимости от типа
            if note.note_type == 'task':
                icon = "☑"
            elif note.note_type == 'checklist':
                icon = "📋"
            else:
                icon = "📝"
            
            # Если закреплена - добавляем 📌
            title = note.title
            if note.is_pinned:
                title = f"📌 {title}"
            
            # Подсчитываем невыполненные задачи
            pending_count = 0
            if note.tasks:
                pending_count = sum(1 for t in note.tasks if not t.is_checked)
                if pending_count > 0:
                    title = f"{title} ({pending_count})"
            
            item = QListWidgetItem(f"{icon} {title}")
            item.setData(Qt.UserRole, note.id)
            
            # Цвет для закреплённых
            if note.is_pinned:
                item.setBackground(QColor(255, 248, 225))
            
            self.note_list.addItem(item)
    
    def on_filter_changed(self):
        """Обработчик изменения фильтра"""
        self.current_filter = self.filter_combo.currentData()
        self.load_notes()
    
    def on_category_changed(self):
        """Обработчик изменения категории"""
        self.current_category_id = self.category_combo.currentData()
        self.load_notes()
    
    def on_search_changed(self):
        """Обработчик поиска"""
        self.load_notes()
    
# ===== gui/widgets/notebook/notebook_tab.py =====
# В МЕТОДЕ on_note_selected, уже должно работать, так как load_note использует setHtml

    def on_note_selected(self, item):
        """Выбор заметки из списка"""
        note_id = item.data(Qt.UserRole)
        note = self.db_manager.session.query(NotebookNote).get(note_id)
        
        if note:
            self.current_note_id = note.id
            self.note_editor.load_note(note)  # Здесь используется setHtml
    
    def on_note_saved(self):
        """Обновляет список после сохранения"""
        self.load_notes()
    
    def new_note(self, note_type):
        """Создаёт новую заметку"""
        from datetime import datetime
        
        # Диалог для ввода заголовка
        title, ok = QInputDialog.getText(self, "Новая заметка", "Введите заголовок:")
        if not ok or not title.strip():
            return
        
        note = NotebookNote(
            title=title.strip(),
            note_type=note_type,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db_manager.session.add(note)
        self.db_manager.session.commit()
        
        self.load_notes()
        
        # Выбираем новую заметку
        for i in range(self.note_list.count()):
            if self.note_list.item(i).data(Qt.UserRole) == note.id:
                self.note_list.setCurrentRow(i)
                self.on_note_selected(self.note_list.item(i))
                break
    
    def show_note_context_menu(self, position: QPoint):
        """Контекстное меню для заметки в списке"""
        item = self.note_list.itemAt(position)
        if not item:
            return
        
        note_id = item.data(Qt.UserRole)
        note = self.db_manager.session.query(NotebookNote).get(note_id)
        if not note:
            return
        
        menu = QMenu(self)
        
        # Закрепить/открепить
        if note.is_pinned:
            pin_action = QAction("📌 Открепить", self)
            pin_action.triggered.connect(lambda: self.toggle_pin(note))
        else:
            pin_action = QAction("📍 Закрепить", self)
            pin_action.triggered.connect(lambda: self.toggle_pin(note))
        menu.addAction(pin_action)
        
        menu.addSeparator()
        
        # Архивировать/восстановить
        if note.is_archived:
            unarchive_action = QAction("📂 Восстановить из архива", self)
            unarchive_action.triggered.connect(lambda: self.toggle_archive(note))
            menu.addAction(unarchive_action)
        else:
            archive_action = QAction("📦 В архив", self)
            archive_action.triggered.connect(lambda: self.toggle_archive(note))
            menu.addAction(archive_action)
        
        # В корзину
        if not note.is_trashed:
            trash_action = QAction("🗑️ В корзину", self)
            trash_action.triggered.connect(lambda: self.move_to_trash(note))
            menu.addAction(trash_action)
        else:
            restore_action = QAction("🔄 Восстановить из корзины", self)
            restore_action.triggered.connect(lambda: self.restore_from_trash(note))
            menu.addAction(restore_action)
            
            menu.addSeparator()
            
            delete_action = QAction("💀 Удалить навсегда", self)
            delete_action.triggered.connect(lambda: self.delete_permanently(note))
            menu.addAction(delete_action)
        
        menu.exec(self.note_list.mapToGlobal(position))
    
    def toggle_pin(self, note):
        """Закрепить/открепить заметку"""
        note.is_pinned = not note.is_pinned
        note.updated_at = datetime.now()
        self.db_manager.session.commit()
        self.load_notes()
    
    def toggle_archive(self, note):
        """Архивировать/восстановить заметку"""
        note.is_archived = not note.is_archived
        if note.is_archived:
            note.is_pinned = False
        note.updated_at = datetime.now()
        self.db_manager.session.commit()
        self.load_notes()
    
    def move_to_trash(self, note):
        """Переместить в корзину"""
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Переместить '{note.title}' в корзину?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            note.is_trashed = True
            note.is_archived = False
            note.is_pinned = False
            note.deleted_at = datetime.now()
            note.updated_at = datetime.now()
            self.db_manager.session.commit()
            self.load_notes()
            
            if self.current_note_id == note.id:
                self.note_editor.clear()
                self.current_note_id = None
    
    def restore_from_trash(self, note):
        """Восстановить из корзины"""
        note.is_trashed = False
        note.deleted_at = None
        note.updated_at = datetime.now()
        self.db_manager.session.commit()
        self.load_notes()
    
    def delete_permanently(self, note):
        """Удалить заметку навсегда"""
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить '{note.title}' навсегда?\nЭто действие нельзя отменить!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db_manager.session.delete(note)
            self.db_manager.session.commit()
            self.load_notes()
            
            if self.current_note_id == note.id:
                self.note_editor.clear()
                self.current_note_id = None
    
    def manage_categories(self):
        """Управление категориями"""
        dialog = CategoryManagerDialog(self.db_manager, self)
        if dialog.exec():
            self.load_categories()
            self.load_notes()
    
# ===== gui/widgets/notebook/notebook_tab.py =====
# МЕТОД: NotebookTab.check_reminders (ПОЛНОСТЬЮ ЗАМЕНИТЬ)

    def check_reminders(self):
        """Проверяет напоминания и показывает уведомления"""
        from database.models import NotebookReminder
        from datetime import datetime, timedelta
        
        try:
            # Проверяем состояние сессии и при необходимости создаём новую
            try:
                # Пробуем выполнить простой запрос
                self.db_manager.session.execute("SELECT 1")
            except Exception:
                # Если сессия в некорректном состоянии, создаём новую
                self.db_manager.session.rollback()
                self.db_manager.session.close()
                self.db_manager.session = self.db_manager.Session()
            
            now = datetime.now()
            
            # Получаем напоминания
            reminders = self.db_manager.session.query(NotebookReminder).filter(
                NotebookReminder.remind_at <= now,
                NotebookReminder.is_done == False
            ).all()
            
            for reminder in reminders:
                QMessageBox.information(
                    self,
                    "🔔 Напоминание",
                    f"<b>{reminder.title}</b><br><br>{reminder.text or ''}"
                )
                
                if reminder.repeat_type == 'none':
                    reminder.is_done = True
                elif reminder.repeat_type == 'daily':
                    reminder.remind_at += timedelta(days=1)
                elif reminder.repeat_type == 'weekly':
                    reminder.remind_at += timedelta(days=7)
                elif reminder.repeat_type == 'monthly':
                    reminder.remind_at += timedelta(days=30)
            
            if reminders:
                self.db_manager.session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка при проверке напоминаний: {e}")
            try:
                self.db_manager.session.rollback()
            except:
                pass