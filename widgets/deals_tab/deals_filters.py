# -*- coding: utf-8 -*-

"""
Фильтрация для вкладки "Сделки"
"""

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QCheckBox
from PySide6.QtGui import QAction

from database.config_db import get_config_db


class DealsFiltersMixin:
    """Примесь с методами фильтрации"""

    def _update_filter_label(self):
        """Обновляет метку активных фильтров"""
        if not self._column_filters:
            self.filter_label.setVisible(False)
            return

        self.filter_label.setVisible(True)
        parts = []
        for col, val in sorted(self._column_filters.items()):
            col_name = self.HEADERS[col] if col < len(self.HEADERS) else str(col)
            if isinstance(val, set):
                parts.append(f"{col_name}: {len(val)} знач.")
        self.filter_label.setText("🔍 Фильтры: " + " | ".join(parts) + "  [нажмите для сброса]")

    def _clear_all_filters(self):
        """Сбрасывает все фильтры"""
        self.logger.debug("_clear_all_filters: сброс всех фильтров")
        self._column_filters.clear()
        self.filter_label.setVisible(False)
        self._save_column_filters_to_json()
        self._apply_filters()

    def _filter_by_value(self, col, value):
        """Фильтрует: показать ТОЛЬКО это значение"""
        self.logger.debug(f"_filter_by_value: колонка {col}, значение '{value}'")
        self._column_filters[col] = {value}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()

    def _filter_exclude_value(self, col, value):
        """Фильтрует: показать ВСЁ КРОМЕ этого значения"""
        self.logger.debug(f"_filter_exclude_value: колонка {col}, исключить '{value}'")
        all_values = set()
        for deal in self._all_deals:
            key = self.COLUMN_KEYS[col]
            if key == 'id':
                continue
            val = self._get_deal_value(deal, col)
            if val and str(val).strip():
                all_values.add(str(val).strip())

        filtered = all_values - {value}
        if filtered:
            self._column_filters[col] = filtered
        else:
            self._column_filters.pop(col, None)

        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()

    def _apply_filters(self):
        """Применяет все фильтры"""
        self.logger.debug("_apply_filters: применение фильтров")
        self._apply_filters_to_frozen()
        self.load_nicknames_combo()
        self.update_statistics()

    def _save_column_filters_to_json(self):
        """Сохраняет фильтры в ConfigDB"""
        self.logger.debug("_save_column_filters_to_json: сохранение фильтров")
        try:
            config_db = get_config_db()
            filters_to_save = {}
            for k, v in self._column_filters.items():
                if isinstance(v, set):
                    filters_to_save[str(k)] = list(v)
                else:
                    filters_to_save[str(k)] = v
            config_db.set('deals_tab_filters', filters_to_save, 'filters')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения фильтров: {e}")

    def _load_column_filters_from_json(self):
        """Загружает фильтры из ConfigDB"""
        self.logger.debug("_load_column_filters_from_json: загрузка фильтров")
        try:
            config_db = get_config_db()
            saved = config_db.get('deals_tab_filters')
            if saved:
                for k, v in saved.items():
                    self._column_filters[int(k)] = set(v) if isinstance(v, list) else v
                self._update_filter_label()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки фильтров: {e}")

    def _show_header_filter_menu(self, position):
        """Показывает меню фильтрации для заголовка"""
        self.logger.debug("_show_header_filter_menu: показ меню фильтрации заголовка")

        header = self.table.horizontalHeader()
        logical_index = header.logicalIndexAt(position)

        if logical_index < 0 or logical_index >= len(self.HEADERS):
            self.logger.debug("  Индекс вне диапазона")
            return

        column_name = self.HEADERS[logical_index]
        self.logger.debug(f"  Фильтр для колонки: {column_name}")

        all_values = set()
        for deal in self._all_deals:
            key = self.COLUMN_KEYS[logical_index]
            if key == 'id':
                continue
            val = self._get_deal_value(deal, logical_index)
            if val and str(val).strip():
                all_values.add(str(val).strip())

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Фильтр: {column_name}")
        dialog.setMinimumWidth(350)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        title_label = QLabel(f"📌 Фильтр по '{column_name}'")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        checkboxes = []
        for value in sorted(all_values):
            cb = QCheckBox(value)
            cb.setChecked(logical_index in self._column_filters and value in self._column_filters[logical_index])
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, value))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ Применить")
        cancel_btn = QPushButton("❌ Отмена")

        def apply():
            selected = {v for cb, v in checkboxes if cb.isChecked()}
            if selected:
                self._column_filters[logical_index] = selected
            else:
                self._column_filters.pop(logical_index, None)
            self._update_filter_label()
            self._save_column_filters_to_json()
            self._apply_filters()
            dialog.accept()

        ok_btn.clicked.connect(apply)
        cancel_btn.clicked.connect(dialog.reject)

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.exec()
        self.logger.debug("  Диалог фильтрации закрыт")