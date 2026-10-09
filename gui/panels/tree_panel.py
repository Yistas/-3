# -*- coding: utf-8 -*-
"""
Менеджер левой панели с деревом стран
"""
import logging
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QToolBar,
                               QFrame, QHBoxLayout, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction
from gui.widgets.country_tree import CountryTreeWidget
from gui.dialogs.add_country_dialog import AddCountryDialog


class TreePanelManager:
    """Управление левой панелью с деревом стран"""

    def __init__(self, main_window):
        self.main = main_window
        self.logger = logging.getLogger('CoinCollector.GUI.TreePanel')
        self.country_tree = None
        self.expanded_state = {}
        self._collection_item = None
        self.title_label = None
        self.toolbar = None
        self.search_frame = None
        self.search_input = None
        self.clear_search_btn = None
        self.hide_search_btn = None

    # ========== ТЕМОЗАВИСИМОСТЬ ==========

    def _theme(self):
        """Возвращает словарь текущей темы"""
        try:
            return self.main.theme_manager.current_theme
        except Exception:
            return {}

    def update_style(self):
        """Применяет стили текущей темы к элементам панели"""
        t = self._theme()
        accent = t.get('accent', t.get('highlight', '#6c63ff'))
        accent_text = t.get('highlight_text', '#ffffff')
        window_bg = t.get('window_bg', '#0f0f1a')
        surface_hover = t.get('surface_hover', '#1f2b47')
        text_color = t.get('text', '#e4e4ef')
        border = t.get('border', '#2a2a4a')
        input_bg = t.get('input_bg', '#16213e')

        if self.title_label is not None:
            self.title_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
                background-color: {accent};
                color: {accent_text};
                border-radius: 3px;
            """)

        if self.toolbar is not None:
            self.toolbar.setStyleSheet(f"""
                QToolBar {{
                    border: none;
                    background-color: {window_bg};
                    padding: 2px;
                    spacing: 2px;
                }}
                QToolButton {{
                    padding: 2px;
                    border-radius: 4px;
                }}
                QToolButton:hover {{
                    background-color: {surface_hover};
                }}
            """)

        if self.search_frame is not None:
            self.search_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_bg};
                    border: none;
                }}
            """)

        if self.search_input is not None:
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {text_color};
                    border: 1px solid {border};
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 12px;
                }}
                QLineEdit:focus {{
                    border-color: {accent};
                }}
            """)

        for btn in (self.clear_search_btn, self.hide_search_btn):
            if btn is not None:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {input_bg};
                        color: {text_color};
                        border: 1px solid {border};
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {surface_hover};
                        border-color: {accent};
                    }}
                """)

        if self.country_tree is not None:
            self.country_tree.update_style()

    # ========== СОЗДАНИЕ ПАНЕЛИ ==========

    def create_panel(self):
        """Создает левую панель с деревом стран"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)

        # Заголовок
        self.title_label = QLabel("🌍 Страны")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Панель инструментов
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Строка поиска (скрыта по умолчанию)
        self.search_frame = self._create_search_frame()
        layout.addWidget(self.search_frame)

        # Дерево стран
        self.country_tree = CountryTreeWidget(self.main)
        layout.addWidget(self.country_tree)

        # Применяем стили текущей темы
        self.update_style()
        return panel

    def _create_search_frame(self):
        """Создает строку поиска по дереву"""
        frame = QFrame()
        frame.setVisible(False)
        frame_layout = QHBoxLayout()
        frame_layout.setSpacing(5)
        frame_layout.setContentsMargins(0, 2, 0, 2)
        frame.setLayout(frame_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск страны...")
        self.search_input.setMinimumHeight(26)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        frame_layout.addWidget(self.search_input)

        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setFixedSize(26, 26)
        self.clear_search_btn.setToolTip("Очистить поиск")
        self.clear_search_btn.clicked.connect(self._clear_search)
        frame_layout.addWidget(self.clear_search_btn)

        self.hide_search_btn = QPushButton("⬆")
        self.hide_search_btn.setFixedSize(26, 26)
        self.hide_search_btn.setToolTip("Скрыть поиск")
        self.hide_search_btn.clicked.connect(self._hide_search)
        frame_layout.addWidget(self.hide_search_btn)
        return frame

    def _create_toolbar(self):
        """Создает панель инструментов для дерева"""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(20, 20))

        # Добавление страны
        add_country_action = QAction("➕", self.main)
        add_country_action.triggered.connect(self._add_country)
        add_country_action.setToolTip("Добавить страну")
        toolbar.addAction(add_country_action)

        # Добавление уровня
        add_level_action = QAction("📁", self.main)
        add_level_action.triggered.connect(self.main.add_custom_level)
        add_level_action.setToolTip("Добавить уровень")
        toolbar.addAction(add_level_action)

        # Удаление уровня
        delete_level_action = QAction("🗑️", self.main)
        delete_level_action.triggered.connect(self.main.delete_custom_level)
        delete_level_action.setToolTip("Удалить уровень")
        toolbar.addAction(delete_level_action)

        toolbar.addSeparator()

        # Развернуть все
        expand_action = QAction("🔽", self.main)
        expand_action.triggered.connect(self.main.expand_all_tree)
        expand_action.setToolTip("Развернуть все")
        toolbar.addAction(expand_action)

        # Свернуть все
        collapse_action = QAction("🔼", self.main)
        collapse_action.triggered.connect(self.main.collapse_all_tree)
        collapse_action.setToolTip("Свернуть все")
        toolbar.addAction(collapse_action)

        toolbar.addSeparator()

        # Поиск по дереву
        search_action = QAction("🔍", self.main)
        search_action.triggered.connect(self._show_search)
        search_action.setToolTip("Поиск страны")
        toolbar.addAction(search_action)
        return toolbar

    # ========== ПОИСК ПО ДЕРЕВУ ==========

    def _show_search(self):
        """Показывает строку поиска"""
        if self.search_frame is not None:
            self.search_frame.setVisible(True)
            if self.search_input is not None:
                self.search_input.setFocus()

    def _hide_search(self):
        """Скрывает строку поиска и сбрасывает фильтр"""
        if self.search_frame is not None:
            if self.search_input is not None:
                self.search_input.clear()
            self.search_frame.setVisible(False)
            self._apply_tree_filter("")

    def _clear_search(self):
        """Очищает строку поиска"""
        if self.search_input is not None:
            self.search_input.clear()

    def _on_search_text_changed(self, text):
        """Обработчик изменения текста в строке поиска"""
        self._apply_tree_filter(text)

    def _apply_tree_filter(self, text):
        """Фильтрует дерево: скрывает неподходящие элементы"""
        if self.country_tree is None:
            return
        text = (text or "").strip().lower()
        root = self.country_tree.invisibleRootItem()
        if not text:
            self._set_all_visible(root)
            return
        self._filter_tree_item(root, text)

    def _set_all_visible(self, parent_item):
        """Показывает все элементы дерева"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self._set_all_visible(child)

    def _filter_tree_item(self, item, text):
        """Возвращает True, если элемент или его дети подходят под фильтр"""
        match = text in item.text(0).lower()
        any_child_visible = False
        for i in range(item.childCount()):
            if self._filter_tree_item(item.child(i), text):
                any_child_visible = True
        visible = match or any_child_visible
        item.setHidden(not visible)
        if any_child_visible and not item.isExpanded():
            item.setExpanded(True)
        return visible

    # ========== ОСНОВНЫЕ МЕТОДЫ ==========

    def _add_country(self):
        """Добавляет новую страну"""
        dialog = AddCountryDialog(self.main.db_manager, self.main)
        if dialog.exec():
            country_data = dialog.get_country_data()
            if country_data['name']:
                self.main.create_new_country(country_data)

    def load_tree(self, preserve_expanded=False):
        """Загружает дерево стран"""
        # Сбрасываем кэш при перезагрузке
        self._collection_item = None
        if preserve_expanded:
            self.save_expanded_state()
        self.country_tree.load_country_tree(preserve_expanded)
        if preserve_expanded and hasattr(self, 'expanded_state'):
            QTimer.singleShot(100, self.restore_expanded_state)
        # Авто-выбор КОЛЛЕКЦИИ после загрузки
        QTimer.singleShot(500, self.select_collection_item)

    def save_expanded_state(self):
        """Сохраняет состояние развернутых узлов"""
        if hasattr(self, 'country_tree') and self.country_tree:
            self.country_tree.save_expanded_state()
            self.expanded_state = self.country_tree.expanded_state

    def restore_expanded_state(self):
        """Восстанавливает состояние развернутых узлов"""
        if hasattr(self, 'country_tree') and hasattr(self, 'expanded_state'):
            self.country_tree.expanded_state = self.expanded_state
            self.country_tree.restore_expanded_state()

    def get_tree(self):
        """Возвращает виджет дерева"""
        return self.country_tree

    def select_collection_item(self):
        """Выбирает элемент КОЛЛЕКЦИЯ в дереве стран"""
        try:
            # Пропускаем, если главное окно заблокировало авто-выбор
            if hasattr(self.main, '_skip_auto_select') and self.main._skip_auto_select:
                self.logger.info("Авто-выбор КОЛЛЕКЦИИ заблокирован флагом _skip_auto_select")
                return
            if not self.country_tree:
                return
            # Кэшируем ссылку на элемент КОЛЛЕКЦИЯ
            if not hasattr(self, '_collection_item') or self._collection_item is None:
                for i in range(self.country_tree.topLevelItemCount()):
                    item = self.country_tree.topLevelItem(i)
                    if "КОЛЛЕКЦИЯ" in item.text(0):
                        self._collection_item = item
                        break
            collection_item = getattr(self, '_collection_item', None)
            if collection_item:
                self.country_tree.expandItem(collection_item)
                self.country_tree.setCurrentItem(collection_item)
                self.country_tree.on_item_selected(collection_item, 0)
            else:
                self._select_all_countries_fallback()
        except Exception as e:
            self.logger.error(f"Ошибка при выборе КОЛЛЕКЦИИ: {e}")

    def _select_all_countries_fallback(self):
        """Запасной вариант - выбрать Все страны или загрузить все монеты напрямую"""
        try:
            self.logger.info("Запуск запасного варианта выбора")
            if not self.country_tree:
                return
            # Пробуем найти элемент "Все страны"
            collection_root = None
            for i in range(self.country_tree.topLevelItemCount()):
                item = self.country_tree.topLevelItem(i)
                if "КОЛЛЕКЦИЯ" in item.text(0):
                    collection_root = item
                    break
            if collection_root:
                # Ищем внутри КОЛЛЕКЦИИ элемент "Все страны"
                for j in range(collection_root.childCount()):
                    child = collection_root.child(j)
                    if "Все страны" in child.text(0):
                        self.logger.info("✅ Найден элемент Все страны")
                        self.country_tree.setCurrentItem(child)
                        self.country_tree.on_item_selected(child, 0)
                        return
            # Если не нашли, загружаем все монеты напрямую
            self.logger.info("Загрузка всех монет напрямую (без выбора в дереве)")
            from database.models import Country
            all_countries = self.main.db_manager.session.query(Country).all()
            all_country_ids = [c.id for c in all_countries]
            # Устанавливаем фильтр
            self.main.current_filter_country_id = None
            self.main.current_folder_country_ids = all_country_ids
            # Загружаем монеты
            self.main.load_coins()
            # Обновляем боковую панель
            if hasattr(self.main, 'detail_panel'):
                self.main.detail_panel.show_collection_stats()
            self.logger.info(f"✅ Загружено монет: {len(self.main.current_coins) if hasattr(self.main, 'current_coins') else 0}")
        except Exception as e:
            self.logger.error(f"❌ Ошибка в запасном варианте: {e}")
            import traceback
            traceback.print_exc()