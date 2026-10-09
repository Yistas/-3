# ===== gui/widgets/exchange_tab/purchases_table.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Кастомная таблица закупок с правильной обработкой клавиш (как в Excel)
"""

from PySide6.QtWidgets import QTableView, QLineEdit, QAbstractItemView, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent


class PurchasesTableView(QTableView):
    """Кастомная таблица закупок с обработкой клавиш как в Excel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pending_edit = False
        self._parent_tab = parent  # <-- ДОБАВЛЯЕМ ССЫЛКУ НА РОДИТЕЛЯ
        
        # Улучшенное выделение ячеек
        self.setStyleSheet("""
            QTableView {
                selection-background-color: #4a6fa5;
                selection-color: white;
                gridline-color: #d0d0d0;
                alternate-background-color: #fafafa;
            }
            QTableView::item:selected {
                background-color: #4a6fa5;
                color: white;
            }
            QTableView::item:selected:!active {
                background-color: #a0b8d4;
            }
            QTableView::item:hover {
                background-color: #e8f0fe;
            }
            QTableView::item:focus {
                background-color: #3a5a80;
                color: white;
                border: 1px solid #ff9800;
            }
        """)
        
        self.setSelectionBehavior(QTableView.SelectItems)
        self.setSelectionMode(QTableView.ExtendedSelection)
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.viewport().update()
    
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.viewport().update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатия клавиш"""
        # ===== ПРОБЕЛ - ПЕРЕКЛЮЧЕНИЕ AG НА КОЛОНКЕ AG =====
        if event.key() == Qt.Key_Space:
            current = self.currentIndex()
            if current.isValid():
                parent = self._parent_tab
                if parent is not None and hasattr(parent, '_ag_column_index'):
                    ag_col = parent._ag_column_index()
                    if ag_col >= 0 and current.column() == ag_col:
                        row = current.row()
                        model = self.model()
                        if model is not None and hasattr(model, 'mapToSource'):
                            row = model.mapToSource(current).row()
                        purchases = getattr(parent, '_filtered_purchases', [])
                        if 0 <= row < len(purchases) and purchases[row] is not None:
                            purchase = purchases[row]
                            parent._set_purchase_ag(
                                purchase,
                                not bool(getattr(purchase, 'ag', False)))
                            event.accept()
                            return
        # ===== CTRL+Z / CTRL+Y / CTRL+C / CTRL+V / CTRL+A =====
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                # Отмена
                parent = self._parent_tab
                if hasattr(parent, '_undo_last_change'):
                    parent._undo_last_change()
                event.accept()
                return
            elif event.key() == Qt.Key_Y:
                # Повтор
                parent = self._parent_tab
                if hasattr(parent, '_redo_last_change'):
                    parent._redo_last_change()
                event.accept()
                return
            elif event.key() == Qt.Key_C:
                # Копирование
                parent = self._parent_tab
                if hasattr(parent, '_copy_selected_cells'):
                    parent._copy_selected_cells()
                else:
                    self._default_copy()
                event.accept()
                return
            elif event.key() == Qt.Key_V:
                parent = self._parent_tab
                if hasattr(parent, '_paste_to_selected_cells'):
                    clipboard = QApplication.clipboard()
                    text = clipboard.text()
                    # Если в буфере одна строка без табуляции - вставляем одно значение
                    if text and "\n" not in text and "\t" not in text:
                        if hasattr(parent, '_paste_single_value_to_selected'):
                            parent._paste_single_value_to_selected(text)
                        else:
                            parent._paste_to_selected_cells()
                    else:
                        parent._paste_to_selected_cells()
                else:
                    self._default_paste()
                event.accept()
                return
            elif event.key() == Qt.Key_A:
                # Выделить всё
                self.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key_X:
                # Вырезать
                parent = self._parent_tab
                if hasattr(parent, '_cut_selected_cells'):
                    parent._cut_selected_cells()
                else:
                    self._default_cut()
                event.accept()
                return
        # ===== F2 - редактирование =====
        if event.key() == Qt.Key_F2:
            current = self.currentIndex()
            if current.isValid() and self.state() != QAbstractItemView.EditingState:
                self.edit(current)
                event.accept()
                return
        # ===== DELETE - очистить ячейки =====
        if event.key() == Qt.Key_Delete:
            parent = self._parent_tab
            if hasattr(parent, '_clear_selected_cells'):
                parent._clear_selected_cells()
            else:
                self._default_clear()
            event.accept()
            return
        # ===== НАЧАЛО ВВОДА ТЕКСТА (как в Excel) =====
        text = event.text()
        current = self.currentIndex()
        # Если нажата обычная печатная клавиша (буква, цифра, символ)
        if text and text.isprintable() and not event.modifiers() & Qt.ControlModifier:
            if current.isValid():
                # Если уже в режиме редактирования - передаём дальше
                if self.state() == QAbstractItemView.EditingState:
                    super().keyPressEvent(event)
                    return
                # Начинаем редактирование
                self.edit(current)
                # Отложенная установка текста (ждём создания редактора)
                def set_text():
                    editor = self.findChild(QLineEdit)
                    if editor:
                        editor.setText(text)
                        editor.setCursorPosition(1)
                        editor.setFocus()
                        self._pending_edit = False
                self._pending_edit = True
                QTimer.singleShot(10, set_text)
                event.accept()
                return
        # ===== НАВИГАЦИЯ (без редактирования) =====
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                           Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Home, Qt.Key_End,
                           Qt.Key_PageUp, Qt.Key_PageDown):
            super().keyPressEvent(event)
            return
        # Enter - перемещение вниз (как в Excel)
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.state() != QAbstractItemView.EditingState:
                current = self.currentIndex()
                if current.isValid():
                    new_row = current.row() + 1
                    if new_row < self.model().rowCount():
                        new_index = self.model().index(new_row, current.column())
                        self.setCurrentIndex(new_index)
                event.accept()
                return
        # Escape - отмена редактирования
        if event.key() == Qt.Key_Escape:
            if self.state() == QAbstractItemView.EditingState:
                self.setFocus()
                event.accept()
                return
        # Остальные клавиши
        super().keyPressEvent(event)

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (ЗАПАСНЫЕ ВАРИАНТЫ) =====
    
    def _default_copy(self):
        """Стандартное копирование (запасной вариант)"""
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        # Сортируем по строкам и колонкам
        rows = {}
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value
        
        # Формируем текст для буфера обмена
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
    
    def _default_paste(self):
        """Стандартная вставка (запасной вариант)"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        rows_data = [line.split("\t") for line in text.strip().split("\n")]
        if not rows_data:
            return
        
        current = self.currentIndex()
        if not current.isValid():
            return
        
        start_row = current.row()
        start_col = current.column()
        model = self.model()
        
        # Используем parent_tab для сохранения
        parent_tab = self._parent_tab
        if parent_tab:
            parent_tab._dirty_ids.clear()
        
        for r, row_data in enumerate(rows_data):
            target_row = start_row + r
            if target_row >= model.rowCount():
                if parent_tab and hasattr(parent_tab, '_insert_empty_row'):
                    parent_tab._insert_empty_row(target_row)
                else:
                    model.insertRow(model.rowCount())
            
            for c, cell_data in enumerate(row_data):
                target_col = start_col + c
                if target_col >= model.columnCount():
                    model.insertColumn(model.columnCount())
                
                index = model.index(target_row, target_col)
                if index.isValid():
                    if parent_tab:
                        # Получаем purchase
                        if target_row < len(parent_tab._filtered_purchases):
                            purchase = parent_tab._filtered_purchases[target_row]
                            if purchase:
                                col = target_col
                                column_key = parent_tab.COLUMN_KEYS[col] if col < len(parent_tab.COLUMN_KEYS) else None
                                if column_key:
                                    parent_tab._on_cell_edited(purchase, column_key, cell_data)
                    else:
                        model.setData(index, cell_data, Qt.EditRole)
        
        # Сохраняем всё в БД
        if parent_tab:
            try:
                parent_tab.db_manager.session.commit()
                parent_tab._dirty_ids.clear()
                if hasattr(parent_tab, 'save_status_label'):
                    parent_tab.save_status_label.setText("💾 Изменения сохранены")
                    parent_tab.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                    QTimer.singleShot(2000, lambda: parent_tab.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            except Exception as e:
                parent_tab.db_manager.session.rollback()
                parent_tab.logger.error(f"Ошибка сохранения: {e}")
    
    def _default_cut(self):
        """Стандартное вырезание (запасной вариант)"""
        self._default_copy()
        self._default_clear()
    
    def _default_clear(self):
        """Стандартная очистка ячеек (запасной вариант)"""
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        model = self.model()
        for idx in selected_indexes:
            if idx.isValid():
                model.setData(idx, "", Qt.EditRole)