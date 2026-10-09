# -*- coding: utf-8 -*-

"""
Фильтрация и контекстные меню для таблицы закупок
С использованием ConfigDB
"""

import json
from pathlib import Path
from PySide6.QtWidgets import QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QLineEdit, QCheckBox, QMessageBox
from PySide6.QtCore import Qt, QPoint

from database.config_db import get_config_db


class PurchasesFiltersMixin:
    """Примесь с методами фильтрации закупок"""
    
    def _apply_filters(self):
        """Применяет фильтры и сортировку"""
        # Используем self._all_data вместо self._all_purchases
        if not self._all_data:
            self.model.set_data([])
            if hasattr(self, 'purchase_count_label'):
                self.purchase_count_label.setText("Записей: 0")
            return
        
        filtered = list(self._all_data)
        
        # Фильтр по стране
        country_id = self.country_filter.currentData()
        if country_id:
            filtered = [p for p in filtered if getattr(p, 'import_country_id', None) == country_id]
        
        # Фильтры по колонкам
        if self._column_filters:
            filtered = self._apply_column_filters_to_list(filtered)
        
        self._filtered_purchases = filtered
        
        # Обновляем модель
        if hasattr(self.model, '_data'):
            self.model.beginResetModel()
            self.model._data = filtered
            self.model.endResetModel()
        else:
            self.model.set_data(filtered)
        
        if hasattr(self, 'purchase_count_label'):
            self.purchase_count_label.setText(f"Записей: {len(filtered)}")
        
        self.load_country_filter()

    def _apply_column_filters_to_list(self, purchases):
        """Применяет фильтры по колонкам к списку закупок"""
        filtered = []
        for purchase in purchases:
            match = True
            for li, filter_val in self._column_filters.items():
                actual_val = self._get_column_value(purchase, li)
                if isinstance(filter_val, set):
                    if not actual_val.strip():
                        if "__EMPTY__" not in filter_val:
                            match = False
                            break
                    elif actual_val not in filter_val:
                        match = False
                        break
            if match:
                filtered.append(purchase)
        return filtered
    
    def _show_header_filter_menu(self, position: QPoint):
        """Показывает меню фильтрации для заголовка (тёмная тема)"""
        header = self.purchases_table.horizontalHeader()
        logical_index = header.logicalIndexAt(position)
        if logical_index < 0 or logical_index >= len(self.model.HEADERS):
            return
        column_name = self.model.HEADERS[logical_index]
        all_values = set()
        visible_values = set()
        has_empty_all = False
        has_empty_visible = False
        for purchase in self._all_purchases:
            try:
                country_id = self.country_filter.currentData()
                if country_id and purchase.import_country_id != country_id:
                    continue
                val = self._get_column_value(purchase, logical_index)
                if val and val.strip():
                    all_values.add(val.strip())
                else:
                    has_empty_all = True
            except Exception:
                continue
        for purchase in self._filtered_purchases:
            try:
                val = self._get_column_value(purchase, logical_index)
                if val and val.strip():
                    visible_values.add(val.strip())
                else:
                    has_empty_visible = True
            except Exception:
                continue
        inactive_values = all_values - visible_values

        def natural_sort_key(val):
            try:
                return (0, float(val.replace(',', '.')))
            except:
                return (1, val.lower())

        sorted_visible = sorted(visible_values, key=natural_sort_key)
        sorted_inactive = sorted(inactive_values, key=natural_sort_key)
        current_filter = self._column_filters.get(logical_index, set())
        if isinstance(current_filter, set):
            current_filter_set = current_filter
        elif current_filter == "__EMPTY__":
            current_filter_set = {"__EMPTY__"}
        else:
            current_filter_set = set()
        all_selected = (not current_filter_set)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Фильтр: {column_name}")
        dialog.setMinimumWidth(350)
        dialog.setMaximumHeight(550)
        dialog.setModal(True)
        # ТЁМНАЯ ТЕМА диалога фильтра — значения читаемы
        dialog.setStyleSheet("""
            QDialog { background-color: #1a1a2e; }
            QWidget { background-color: #1a1a2e; }
            QLabel { color: #e4e4ef; background: transparent; }
            QCheckBox { color: #e4e4ef; background: transparent; spacing: 6px; }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1px solid #3d3d5c;
                border-radius: 3px;
                background-color: #16213e;
            }
            QCheckBox::indicator:checked {
                background-color: #6c63ff;
                border-color: #6c63ff;
            }
            QScrollArea {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
            }
            QLineEdit {
                background-color: #16213e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 3px 8px;
            }
            QPushButton {
                background-color: #262640;
                color: #e4e4ef;
                border: 1px solid #3d3d5c;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #6c63ff; color: #ffffff; }
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title_label = QLabel(f"📌 Фильтр по '{column_name}'")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px; color: #7c74ff;")
        layout.addWidget(title_label)
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔍 Поиск значений...")
        search_input.setClearButtonEnabled(True)
        search_input.setMinimumHeight(30)
        layout.addWidget(search_input)
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("☑ Выбрать все")
        select_all_btn.setMinimumHeight(28)
        clear_all_btn = QPushButton("☐ Сбросить все")
        clear_all_btn.setMinimumHeight(28)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(clear_all_btn)
        layout.addLayout(btn_layout)
        stats_label = QLabel(f"✅ Активных: {len(sorted_visible)} | ⬜ Неактивных: {len(sorted_inactive)}")
        stats_label.setStyleSheet("color: #8888aa; font-size: 11px;")
        layout.addWidget(stats_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(1)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        checkboxes = []
        value_to_cb = {}
        if has_empty_visible or has_empty_all:
            cb = QCheckBox("📭 Пустые значения")
            cb.setChecked(all_selected or "__EMPTY__" in current_filter_set)
            cb.setStyleSheet("QCheckBox { padding: 2px 0; color: #e4e4ef; font-weight: bold; background: transparent; }")
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, "__EMPTY__"))
            value_to_cb["__EMPTY__"] = cb
        if sorted_visible or sorted_inactive:
            separator = QLabel("")
            separator.setStyleSheet("border-top: 1px solid #2a2a4a; margin: 5px 0;")
            scroll_layout.addWidget(separator)
        if sorted_visible:
            active_label = QLabel("✅ Активные значения:")
            active_label.setStyleSheet("font-weight: bold; color: #28a745; font-size: 11px; padding: 5px 0 2px 0;")
            scroll_layout.addWidget(active_label)
            for value in sorted_visible:
                cb = QCheckBox(value)
                cb.setChecked(all_selected or value in current_filter_set)
                cb.setStyleSheet("QCheckBox { padding: 2px 0; color: #e4e4ef; background: transparent; }")
                scroll_layout.addWidget(cb)
                checkboxes.append((cb, value))
                value_to_cb[value] = cb
        if sorted_inactive:
            separator = QLabel("")
            separator.setStyleSheet("border-top: 1px solid #2a2a4a; margin: 5px 0;")
            scroll_layout.addWidget(separator)
            inactive_label = QLabel("⬜ Неактивные значения (отфильтрованы другими колонками):")
            inactive_label.setStyleSheet("font-weight: bold; color: #8888aa; font-size: 11px; padding: 5px 0 2px 0;")
            scroll_layout.addWidget(inactive_label)
            for value in sorted_inactive:
                cb = QCheckBox(value)
                cb.setChecked(all_selected or value in current_filter_set)
                cb.setStyleSheet("QCheckBox { padding: 2px 0; color: #8888aa; background: transparent; }")
                scroll_layout.addWidget(cb)
                checkboxes.append((cb, value))
                value_to_cb[value] = cb
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        def filter_checkboxes(text):
            search_text = text.lower().strip()
            for value, cb in value_to_cb.items():
                if value == "__EMPTY__":
                    display = "пустые значения"
                else:
                    display = value.lower()
                cb.setVisible(not search_text or search_text in display)

        search_input.textChanged.connect(filter_checkboxes)

        def toggle_visible(checked):
            for cb, val in checkboxes:
                if cb.isVisible():
                    cb.setChecked(checked)

        select_all_btn.clicked.connect(lambda: toggle_visible(True))
        clear_all_btn.clicked.connect(lambda: toggle_visible(False))
        dialog_btns = QHBoxLayout()
        dialog_btns.addStretch()
        ok_btn = QPushButton("✅ Применить")
        ok_btn.setMinimumHeight(32)
        ok_btn.setMinimumWidth(100)
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setMinimumWidth(100)

        def apply():
            selected = {v for cb, v in checkboxes if cb.isChecked()}
            total_vis = sum(1 for cb, v in checkboxes if cb.isVisible())
            if len(selected) == total_vis or len(selected) == 0:
                if logical_index in self._column_filters:
                    del self._column_filters[logical_index]
            else:
                self._column_filters[logical_index] = selected
            self._update_filter_label()
            self._save_column_filters_to_json()
            self._apply_filters()
            dialog.accept()

        ok_btn.clicked.connect(apply)
        cancel_btn.clicked.connect(dialog.reject)
        dialog_btns.addWidget(ok_btn)
        dialog_btns.addWidget(cancel_btn)
        layout.addLayout(dialog_btns)
        dialog.exec()

    def _update_filter_label(self):
        """Обновляет метку активных фильтров"""
        # Очищаем существующие виджеты
        if hasattr(self, '_filter_checkboxes_layout'):
            while self._filter_checkboxes_layout.count():
                child = self._filter_checkboxes_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            self._filter_checkboxes_layout = QHBoxLayout()
            self._filter_checkboxes_layout.setContentsMargins(0, 0, 0, 0)
            self._filter_checkboxes_layout.setSpacing(2)
            if hasattr(self, 'filter_label'):
                self.filter_label.setLayout(self._filter_checkboxes_layout)
        
        if not self._column_filters:
            if hasattr(self, 'filter_label'):
                self.filter_label.setVisible(False)
            return
        
        if hasattr(self, 'filter_label'):
            self.filter_label.setVisible(True)
        
        # Добавляем текст "Фильтры:"
        label = QLabel("🔍 Фильтры: ")
        label.setStyleSheet("color: #dc3545; font-size: 11px;")
        self._filter_checkboxes_layout.addWidget(label)
        
        # Добавляем чекбокс для каждого фильтра
        for col, val in sorted(self._column_filters.items()):
            col_name = self.model.HEADERS[col] if col < len(self.model.HEADERS) else str(col)
            
            if isinstance(val, set):
                if len(val) == 1:
                    display = list(val)[0]
                    display = display if len(display) <= 15 else display[:12] + "..."
                else:
                    display = f"{len(val)} знач."
            else:
                display = "пусто" if val == "__EMPTY__" else str(val)
                display = display if len(display) <= 15 else display[:12] + "..."
            
            cb = QCheckBox(f"{col_name}: {display}")
            cb.setChecked(True)
            cb.setStyleSheet("""
                QCheckBox {
                    color: #dc3545;
                    font-size: 10px;
                    padding: 0px 2px;
                    spacing: 3px;
                }
                QCheckBox::indicator {
                    width: 12px;
                    height: 12px;
                }
                QCheckBox:hover {
                    color: #a71d2a;
                    font-weight: bold;
                }
            """)
            cb.setToolTip(f"Снять фильтр по колонке «{col_name}»")
            cb.setProperty("filter_column_index", col)
            cb.toggled.connect(self._on_filter_checkbox_toggled)
            
            self._filter_checkboxes_layout.addWidget(cb)
        
        # Кнопка сброса всех фильтров
        clear_all = QPushButton("✕ все")
        clear_all.setFixedSize(35, 18)
        clear_all.setStyleSheet("""
            QPushButton {
                color: #fff;
                background-color: #dc3545;
                border: none;
                border-radius: 3px;
                font-size: 9px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #a71d2a;
            }
        """)
        clear_all.setToolTip("Сбросить все фильтры")
        clear_all.clicked.connect(self._clear_all_filters)
        self._filter_checkboxes_layout.addWidget(clear_all)
        
        self._filter_checkboxes_layout.addStretch()
    
    def _on_filter_checkbox_toggled(self, checked):
        """Обработчик отключения/включения отдельного фильтра"""
        cb = self.sender()
        if not cb:
            return
        
        logical_index = cb.property("filter_column_index")
        if logical_index is None:
            return
        
        if not checked:
            if logical_index in self._column_filters:
                if not hasattr(self, '_disabled_filters'):
                    self._disabled_filters = {}
                self._disabled_filters[logical_index] = self._column_filters[logical_index]
                del self._column_filters[logical_index]
            self._save_column_filters_to_json()
            self._apply_filters()
        else:
            if hasattr(self, '_disabled_filters') and logical_index in self._disabled_filters:
                self._column_filters[logical_index] = self._disabled_filters.pop(logical_index)
                self._save_column_filters_to_json()
                self._apply_filters()
    
    def _clear_all_filters(self):
        """Сбрасывает все фильтры"""
        self._column_filters.clear()
        self._disabled_filters.clear()
        if hasattr(self, 'filter_label'):
            self.filter_label.setVisible(False)
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _save_column_filters_to_json(self):
        """Сохраняет фильтры колонок в ConfigDB"""
        try:
            config_db = get_config_db()
            filters_to_save = {}
            for k, v in self._column_filters.items():
                if isinstance(v, set):
                    filters_to_save[str(k)] = list(v)
                else:
                    filters_to_save[str(k)] = v
            config_db.set('exchange_tab_filters', filters_to_save, 'filters')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения фильтров: {e}")
    
    def _load_column_filters_from_json(self):
        """Загружает фильтры колонок из ConfigDB"""
        try:
            config_db = get_config_db()
            saved = config_db.get('exchange_tab_filters')
            
            if saved:
                for k, v in saved.items():
                    self._column_filters[int(k)] = set(v) if isinstance(v, list) else v
                self._update_filter_label()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки фильтров: {e}")
    
    def _filter_by_value(self, col, value):
        """Фильтрует: показать ТОЛЬКО это значение"""
        self._column_filters[col] = {value}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _filter_exclude_value(self, col, value):
        """Фильтрует: показать ВСЁ КРОМЕ этого значения"""
        all_values = set()
        for purchase in self._all_purchases:
            country_id = self.country_filter.currentData()
            if country_id and purchase.import_country_id != country_id:
                continue
            val = self._get_column_value(purchase, col)
            if val and val.strip():
                all_values.add(val.strip())
        
        filtered = all_values - {value}
        
        if filtered:
            self._column_filters[col] = filtered
        else:
            if col in self._column_filters:
                del self._column_filters[col]
        
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _clear_column_filter(self, col):
        """Сбрасывает фильтр для конкретной колонки"""
        if col in self._column_filters:
            del self._column_filters[col]
        if col in getattr(self, '_disabled_filters', {}):
            del self._disabled_filters[col]
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()