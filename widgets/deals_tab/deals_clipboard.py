# -*- coding: utf-8 -*-

"""
Копирование/вставка для вкладки "Сделки"
"""

import logging
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QInputDialog

from database.models import Deal


class DealsClipboardMixin:
    """Примесь с методами копирования/вставки"""

    def _copy_selected_cells(self):
        """Копирует выделенные ячейки в буфер обмена"""
        self.logger.debug("_copy_selected_cells: копирование ячеек")
        selected_indexes = self.table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        rows = {}
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value

        lines = []
        for row in sorted(rows.keys()):
            cols = rows[row]
            max_col = max(cols.keys()) if cols else 0
            line = []
            for col in range(max_col + 1):
                line.append(cols.get(col, ""))
            lines.append("\t".join(line))

        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

        self.status_label.setText(f"📋 Скопировано {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _paste_to_selected_cells(self):
        """Вставляет данные из буфера обмена в выделенные ячейки"""
        self.logger.debug("_paste_to_selected_cells: вставка в ячейки")
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        rows_data = [line.split("\t") for line in text.strip().split("\n")]
        if not rows_data:
            return

        selected_indexes = self.table.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = self.table.currentIndex()
            if current.isValid():
                selected_indexes = [current]

        if not selected_indexes:
            return

        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0

        if source_rows == 0 or source_cols == 0:
            return

        self.table.setUpdatesEnabled(False)
        self.model.blockSignals(True)

        try:
            for i, target_idx in enumerate(selected_indexes):
                source_row = i % source_rows
                source_col = (i // source_rows) % source_cols
                value = rows_data[source_row][source_col] if source_col < len(rows_data[source_row]) else ""

                row = target_idx.row()
                col = target_idx.column()
                source_row_idx = self._get_source_row(row)

                if source_row_idx < len(self._filtered_deals):
                    deal = self._filtered_deals[source_row_idx]
                    if deal:
                        field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                        if field_name and field_name != 'id':
                            old_value = getattr(deal, field_name, None)
                            if str(old_value) != value:
                                self._on_deal_edited(deal, field_name, value)

            self.model.dataChanged.emit(
                self.model.index(0, 0),
                self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
                [Qt.DisplayRole]
            )

            self.status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.logger.error(f"Ошибка вставки: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
        finally:
            self.model.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def _copy_row(self, rows):
        """Копирует строки в буфер"""
        if not rows:
            return
        if isinstance(rows, int):
            rows = [rows]

        self.logger.debug(f"_copy_row: копирование {len(rows)} строк")

        self._copied_row_data = []
        for row in rows:
            source_row = self._get_source_row(row)
            if source_row < len(self._filtered_deals):
                deal = self._filtered_deals[source_row]
                if deal:
                    data = {}
                    for key in self.COLUMN_KEYS:
                        if key and key != 'id':
                            value = getattr(deal, key, None)
                            data[key] = value
                    self._copied_row_data.append(data)

        count = len(self._copied_row_data)
        self.status_label.setText(f"📝 Скопировано {count} строк")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _insert_empty_row(self, row):
        """Вставляет пустую строку"""
        self.logger.debug(f"_insert_empty_row: вставка пустой строки на позицию {row}")
        try:
            new_deal = Deal()
            for key in self.CHECKBOX_COLUMNS.values():
                setattr(new_deal, key, "❌")
            self.db_manager.session.add(new_deal)
            self.db_manager.session.flush()
            self.db_manager.session.commit()

            frozen = {'id': new_deal.id}
            for key in self.COLUMN_KEYS:
                if key != 'id':
                    frozen[key] = getattr(new_deal, key, None)

            self._frozen_deals.append(frozen)
            self._all_deals.append(new_deal)
            self._apply_filters()

            self.status_label.setText(f"✅ Добавлена строка")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строки: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _insert_n_rows(self, row, n):
        """Вставляет N пустых строк"""
        if n is None:
            n, ok = QInputDialog.getInt(self, "Вставить строки", "Количество строк:", 5, 1, 100, 1)
            if not ok:
                return

        self.logger.debug(f"_insert_n_rows: вставка {n} строк")

        try:
            for _ in range(n):
                new_deal = Deal()
                for key in self.CHECKBOX_COLUMNS.values():
                    setattr(new_deal, key, "❌")
                self.db_manager.session.add(new_deal)
                self.db_manager.session.flush()

                frozen = {'id': new_deal.id}
                for key in self.COLUMN_KEYS:
                    if key != 'id':
                        frozen[key] = getattr(new_deal, key, None)

                self._frozen_deals.append(frozen)
                self._all_deals.append(new_deal)

            self.db_manager.session.commit()
            self._apply_filters()

            self.status_label.setText(f"✅ Добавлено {n} строк")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строк: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _undo_last_change(self):
        """Отменяет последнее изменение (Ctrl+Z)"""
        self.logger.debug("_undo_last_change: отмена последнего изменения")
        if not self._last_changes:
            self.status_label.setText("ℹ️ Нет действий для отмены")
            return

        try:
            changes = self._last_changes.pop()
            self._redo_stack.append(changes)

            for change in changes:
                for deal in self._filtered_deals:
                    if deal.id == change['deal_id']:
                        setattr(deal, change['field'], change['old_value'])
                        deal.updated_at = datetime.now()
                        self._on_deal_edited(deal, change['field'], change['old_value'])
                        break

            self.model.set_data(self._filtered_deals)
            self.status_label.setText("↩️ Изменение отменено")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка отмены: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")