# ===== gui/widgets/yearly_table/excel_like_table.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Excel-подобная таблица с поддержкой границ, объединения ячеек, формул
"""

import logging
import re
import math
import pickle
import base64
from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem, QMenu, QMessageBox,
                               QInputDialog, QColorDialog, QFontDialog, QApplication, QStyledItemDelegate)
from PySide6.QtCore import Qt, Signal, QMimeData, QSettings, QTimer
from PySide6.QtGui import (QAction, QColor, QFont, QBrush, QKeySequence,
                           QPainter, QPen, QPixmap, QIcon)



class FormattingManager:
    """Менеджер для хранения форматирования ячеек отдельно от данных"""
    
    def __init__(self):
        self.formats = {}  # {(row, col): format_data}
        self._dirty = False
    
    def get_format(self, row, col):
        """Возвращает форматирование для ячейки"""
        return self.formats.get((row, col))
    
    def set_format(self, row, col, format_data):
        """Устанавливает форматирование для ячейки"""
        if format_data:
            self.formats[(row, col)] = format_data
        else:
            self.formats.pop((row, col), None)
        self._dirty = True
    
    def clear_format(self, row, col):
        """Очищает форматирование для ячейки"""
        self.formats.pop((row, col), None)
        self._dirty = True
    
    def clear_all(self):
        """Очищает всё форматирование"""
        self.formats.clear()
        self._dirty = True
    
    def get_all_formats(self):
        """Возвращает все форматы"""
        return self.formats.copy()
    
    def set_from_dict(self, formats_dict):
        """Восстанавливает форматирование из словаря"""
        self.formats = formats_dict.copy() if formats_dict else {}
    
    def is_dirty(self):
        return self._dirty
    
    def clear_dirty(self):
        self._dirty = False


class FormatBackgroundDelegate(QStyledItemDelegate):
    """Делегат, принудительно рисующий заливку ячейки даже при активном stylesheet"""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        brush = index.data(Qt.BackgroundRole)
        if brush and brush.color().isValid() and brush.color().alpha() > 0:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(brush)
            painter.drawRect(option.rect)
            # Текст поверх заливки
            text = index.data(Qt.DisplayRole)
            if text:
                fg = index.data(Qt.ForegroundRole)
                if fg and fg.color().isValid():
                    painter.setPen(fg.color())
                else:
                    painter.setPen(option.palette.color(QPalette.WindowText))
                painter.setFont(option.font)
                align = index.data(Qt.TextAlignmentRole)
                if not align:
                    align = Qt.AlignLeft | Qt.AlignVCenter
                painter.drawText(option.rect.adjusted(3, 0, -3, 0), align, str(text))
            painter.restore()

class ExcelLikeTable(QTableWidget):
    """Таблица с Excel-подобным поведением"""
    
    dataChanged = Signal()
    
    # Константы для стилей границ
    BORDER_NONE = 0
    BORDER_THIN = 1
    BORDER_MEDIUM = 2
    BORDER_THICK = 3
    BORDER_DOUBLE = 4
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.ExcelLikeTable')
        self.logger.setLevel(logging.WARNING)
        
        self.formulas = {}
        self.merged_cells = []
        
        # Менеджер форматирования
        self.format_manager = FormattingManager()
        
        # Система Undo/Redo
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 100
        self.is_undo_redo = False
        
        self.settings = QSettings('CoinCollector', 'ExcelLikeTable')
        self.sheet_name = None
        
        # Таймеры для debounce сохранения размеров
        self._save_timer = None
        self._pending_sheet_name = None
        self._last_saved_state = None
        
        # Оптимизация: ленивая загрузка форматов
        self._formats_loaded = False
        self._formats_changed = False
        self._format_save_timer = None
        
        self._setup_table()
    
    def _setup_table(self):
        """Настройка таблицы"""
        self.setAlternatingRowColors(False)  # заливка управляется форматированием
        self.setSortingEnabled(False)
        self.setSelectionBehavior(QTableWidget.SelectItems)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setDragEnabled(True)
        self.horizontalHeader().setDropIndicatorShown(True)
        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.verticalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.verticalHeader().setSectionsMovable(True)
        self.horizontalHeader().customContextMenuRequested.connect(self.show_header_menu)
        self.verticalHeader().customContextMenuRequested.connect(self.show_header_menu)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_cell_menu)
        self.setStyleSheet(self._get_dark_style())
        # Делегат рисует заливку поверх stylesheet — заливка видна в тёмной теме
        self.setItemDelegate(FormatBackgroundDelegate(self))
        
    def _is_dark_theme(self):
        """Возвращает True, если текущая тема тёмная"""
        try:
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if w.__class__.__name__ == 'MainWindow':
                    return w.theme_manager.current_theme.get('type', 'dark') == 'dark'
        except Exception:
            pass
        return True

    def _default_text_color(self):
        """Цвет текста по умолчанию: светлый на тёмном фоне, чёрный на светлом"""
        if self._is_dark_theme():
            return QColor(232, 232, 239)  # #e8e8ef
        return QColor(0, 0, 0)

    def _auto_text_color(self, item):
        """Подбирает читаемый цвет текста по фону ячейки и теме"""
        bg = item.background().color()
        if bg.isValid() and bg.alpha() > 0:
            lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
            if lum > 140:
                return QColor(0, 0, 0)      # светлый фон → чёрный текст
            return QColor('#e4e4ef')        # тёмный фон → светлый текст
        # Фон не задан — по теме
        return QColor('#e4e4ef') if self._is_dark_theme() else QColor(0, 0, 0)

    def _mark_formats_changed(self):
        """Отмечает, что форматирование изменилось"""
        self._formats_changed = True
        # Отложенное сохранение через 2 секунды
        if self._format_save_timer:
            self._format_save_timer.stop()
        self._format_save_timer = QTimer()
        self._format_save_timer.setSingleShot(True)
        self._format_save_timer.timeout.connect(self._save_formats_if_needed)
        self._format_save_timer.start(2000)
    
    def _save_formats_if_needed(self):
        """Сохраняет форматы только если они изменились"""
        if self._formats_changed and self.sheet_name:
            self.save_formats_to_settings()
            self._formats_changed = False
    
    # ========== СОХРАНЕНИЕ РАЗМЕРОВ С DEBOUNCE ==========
    
    def _schedule_save_dimensions(self, sheet_name):
        """Отложенное сохранение размеров (debounce)"""
        if not sheet_name:
            return
        
        self._pending_sheet_name = sheet_name
        
        if self._save_timer is not None:
            self._save_timer.stop()
        
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_dimensions)
        self._save_timer.start(1000)
    
    def _do_save_dimensions(self):
        """Реальное сохранение размеров"""
        if not self._pending_sheet_name:
            return
        
        current_state = self._get_dimensions_state()
        if current_state == self._last_saved_state:
            return
        
        self.save_table_dimensions(self._pending_sheet_name)
        self._last_saved_state = self._get_dimensions_state()
        self._pending_sheet_name = None
    
    def _get_dimensions_state(self):
        """Возвращает хеш текущих размеров для проверки изменений"""
        try:
            state = []
            for col in range(min(self.columnCount(), 50)):
                state.append(self.columnWidth(col))
            for row in range(min(self.rowCount(), 100)):
                state.append(self.rowHeight(row))
            return hash(tuple(state))
        except:
            return None
    
    def save_table_dimensions(self, sheet_name):
        """Сохраняет ширину колонок и высоту строк"""
        try:
            column_widths = []
            for col in range(self.columnCount()):
                width = self.columnWidth(col)
                column_widths.append(width if width > 0 else 0)
            self.settings.setValue(f'column_widths_{sheet_name}', column_widths)
            
            row_heights = []
            for row in range(min(self.rowCount(), 500)):
                height = self.rowHeight(row)
                row_heights.append(height if height > 0 else 0)
            self.settings.setValue(f'row_heights_{sheet_name}', row_heights)
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения размеров для {sheet_name}: {e}")

    def restore_table_dimensions(self, sheet_name):
        """Восстанавливает ширину колонок и высоту строк (оптимизировано)"""
        self.sheet_name = sheet_name
        try:
            column_widths = self.settings.value(f'column_widths_{sheet_name}')
            if column_widths:
                for col, width in enumerate(column_widths):
                    if width and col < self.columnCount():
                        try:
                            width_val = int(width) if isinstance(width, str) else width
                            if width_val > 0:
                                self.setColumnWidth(col, width_val)
                        except (ValueError, TypeError):
                            pass
            
            row_heights = self.settings.value(f'row_heights_{sheet_name}')
            if row_heights:
                for row, height in enumerate(row_heights[:100]):
                    if height and row < self.rowCount():
                        try:
                            height_val = int(height) if isinstance(height, str) else height
                            if height_val > 0:
                                self.setRowHeight(row, height_val)
                        except (ValueError, TypeError):
                            pass
                    
        except Exception as e:
            self.logger.error(f"Ошибка восстановления размеров для {sheet_name}: {e}")

    def save_column_widths(self, sheet_name):
        """Сохраняет только ширину колонок (для обратной совместимости)"""
        try:
            column_widths = []
            for col in range(self.columnCount()):
                width = self.columnWidth(col)
                column_widths.append(width if width > 0 else 0)
            self.settings.setValue(f'column_widths_{sheet_name}', column_widths)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения ширины: {e}")
    
    # ========== ФОРМАТЫ (ЛЕНИВАЯ ЗАГРУЗКА) ==========

# ===== gui/widgets/yearly_table/excel_like_table.py =====
# ЗАМЕНИТЬ СЕКЦИЮ item И _apply_format_on_demand

    def load_formats_from_settings(self):
        """Загружает форматы из настроек (ленивая загрузка)"""
        if self._formats_loaded or not self.sheet_name:
            return
        
        settings = QSettings('CoinCollector', 'ExcelLikeTable')
        formats_data = settings.value(f'formats_{self.sheet_name}')
        if formats_data:
            formats_dict = {}
            for key_str, value in formats_data.items():
                parts = key_str.split(',')
                if len(parts) == 2:
                    try:
                        row, col = int(parts[0]), int(parts[1])
                        formats_dict[(row, col)] = value
                    except ValueError:
                        pass
            self.format_manager.set_from_dict(formats_dict)
        
        self._formats_loaded = True
    
    def save_formats_to_settings(self):
        """Сохраняет форматы в настройки (только изменённые)"""
        if not self.sheet_name:
            return
        
        settings = QSettings('CoinCollector', 'ExcelLikeTable')
        formats_dict = self.format_manager.get_all_formats()
        
        save_dict = {}
        for (row, col), value in formats_dict.items():
            save_dict[f"{row},{col}"] = value
        
        settings.setValue(f'formats_{self.sheet_name}', save_dict)
    
    def _apply_format_on_demand(self, row, col):
        """Применяет формат к ячейке только при необходимости"""
        if not self._formats_loaded:
            self.load_formats_from_settings()
            self._formats_loaded = True
        
        # Прямой вызов super().item() чтобы избежать рекурсии
        item = super().item(row, col)
        if item and not getattr(item, '_formatted', False):
            self._apply_format_info(item, row, col)
            if item:
                item._formatted = True
    
    def item(self, row, col):
        """Переопределяем item для ленивого применения форматирования"""
        item = super().item(row, col)
        if item and not getattr(item, '_formatted', False):
            self._apply_format_info(item, row, col)
            if item:
                item._formatted = True
        return item

    # ========== UNDO/REDO ==========
    
    def _save_state(self):
        """Сохраняет текущее состояние таблицы для Undo"""
        if self.is_undo_redo:
            return
        
        state = self._capture_state()
        self.undo_stack.append(state)
        
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        
        self.redo_stack.clear()
    
    def _capture_state(self):
        """Захватывает текущее состояние таблицы"""
        state = {
            'rows': self.rowCount(),
            'cols': self.columnCount(),
            'data': {},
            'formats': self.format_manager.get_all_formats(),
            'formulas': self.formulas.copy(),
            'merged_cells': self.merged_cells.copy(),
            'horizontal_headers': [],
            'vertical_headers': [],
            'column_widths': [],
            'row_heights': []
        }
        
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    state['data'][(row, col)] = item.text()
                    formula = item.data(Qt.UserRole + 1)
                    if formula:
                        state['formulas'][(row, col)] = formula
        
        for col in range(self.columnCount()):
            header = self.horizontalHeaderItem(col)
            if header:
                header_text = header.text()
                if not header_text.isdigit() and not header_text.startswith('Колонка'):
                    state['horizontal_headers'].append((col, header_text))
        
        for row in range(self.rowCount()):
            header = self.verticalHeaderItem(row)
            if header:
                header_text = header.text()
                if not header_text.isdigit() and not header_text.startswith('Строка'):
                    state['vertical_headers'].append((row, header_text))
        
        for col in range(self.columnCount()):
            state['column_widths'].append(self.columnWidth(col))
        
        for row in range(min(self.rowCount(), 500)):
            state['row_heights'].append(self.rowHeight(row))
        
        return state

    def _restore_state(self, state):
        """Восстанавливает состояние таблицы"""
        if not state:
            return
        
        self.is_undo_redo = True
        
        current_row = self.currentRow()
        current_col = self.currentColumn()
        
        self.clear()
        self.setRowCount(state['rows'])
        self.setColumnCount(state['cols'])
        
        for col in range(self.columnCount()):
            self.setHorizontalHeaderItem(col, QTableWidgetItem(str(col + 1)))
        
        for row in range(self.rowCount()):
            self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
        
        for col, header_text in state.get('horizontal_headers', []):
            if col < self.columnCount():
                item = QTableWidgetItem(header_text)
                self.setHorizontalHeaderItem(col, item)
        
        for row, header_text in state.get('vertical_headers', []):
            if row < self.rowCount():
                item = QTableWidgetItem(header_text)
                self.setVerticalHeaderItem(row, item)
        
        for (row, col), text in state['data'].items():
            if row < self.rowCount() and col < self.columnCount():
                item = QTableWidgetItem(text)
                self.setItem(row, col, item)
                
                if (row, col) in state.get('formulas', {}):
                    formula = state['formulas'][(row, col)]
                    item.setData(Qt.UserRole + 1, formula)
                    item.setForeground(QBrush(QColor(0, 100, 0)))
        
        formats_dict = state.get('formats', {})
        self.format_manager.set_from_dict(formats_dict)
        self._formats_loaded = True
        
        for (row, col), format_data in formats_dict.items():
            if row < self.rowCount() and col < self.columnCount():
                item = self.item(row, col)
                if item:
                    self._apply_format_info(item, row, col)
                    if item:
                        item._formatted = True
        
        self.merged_cells = state.get('merged_cells', []).copy()
        for merge in self.merged_cells:
            self.setSpan(merge['top'], merge['left'], merge['rows'], merge['cols'])
        
        column_widths = state.get('column_widths', [])
        for col, width in enumerate(column_widths):
            if col < self.columnCount() and width > 0:
                self.setColumnWidth(col, width)
        
        row_heights = state.get('row_heights', [])
        for row, height in enumerate(row_heights):
            if row < self.rowCount() and height > 0:
                self.setRowHeight(row, height)
        
        if current_row < self.rowCount() and current_col < self.columnCount():
            self.setCurrentCell(current_row, current_col)
        
        self.viewport().update()
        self.dataChanged.emit()
        
        self.is_undo_redo = False

    def undo(self):
        if not self.undo_stack:
            QMessageBox.information(self, "Отмена", "Нет действий для отмены")
            return
        current_state = self._capture_state()
        self.redo_stack.append(current_state)
        state = self.undo_stack.pop()
        self._restore_state(state)
    
    def redo(self):
        if not self.redo_stack:
            QMessageBox.information(self, "Повтор", "Нет действий для повтора")
            return
        current_state = self._capture_state()
        self.undo_stack.append(current_state)
        state = self.redo_stack.pop()
        self._restore_state(state)
    
    # ========== КЛАВИАТУРА ==========
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo()
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            self.redo()
        elif event.matches(QKeySequence.Copy):
            self.copy_selection()
        elif event.matches(QKeySequence.Paste):
            self.paste_selection()
        elif event.matches(QKeySequence.Cut):
            self.cut_selection()
        elif event.key() == Qt.Key_Delete:
            self.clear_selection()
        elif event.key() == Qt.Key_Tab:
            current = self.currentIndex()
            if current.isValid():
                if current.column() < self.columnCount() - 1:
                    self.setCurrentCell(current.row(), current.column() + 1)
                else:
                    if current.row() < self.rowCount() - 1:
                        self.setCurrentCell(current.row() + 1, 0)
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current = self.currentIndex()
            if current.isValid() and current.row() < self.rowCount() - 1:
                self.setCurrentCell(current.row() + 1, current.column())
        else:
            super().keyPressEvent(event)
    
    # ========== КОПИРОВАНИЕ/ВСТАВКА ==========
    
    def copy_selection(self):
        """Копирует выделенные ячейки с форматированием"""
        selection = self.selectedRanges()
        if not selection:
            return
        
        sel = selection[0]
        rows_data = []
        
        for row in range(sel.topRow(), sel.bottomRow() + 1):
            row_data = []
            for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                item = self.item(row, col)
                if item:
                    cell_data = {
                        'text': item.text(),
                        'formula': item.data(Qt.UserRole + 1),
                        'format': self._extract_format_info(item)
                    }
                    row_data.append(cell_data)
                else:
                    row_data.append({'text': '', 'format': None})
            rows_data.append(row_data)
        
        import json
        import base64
        
        data_json = json.dumps(rows_data, ensure_ascii=False)
        encoded = base64.b64encode(data_json.encode('utf-8')).decode('ascii')
        
        mime_data = QMimeData()
        mime_data.setText(encoded)
        QApplication.clipboard().setMimeData(mime_data)
    
    def paste_selection(self):
        """Вставляет данные из буфера во все выделенные ячейки"""
        mime_data = QApplication.clipboard().mimeData()
        if not mime_data:
            return
        
        encoded = mime_data.text()
        if not encoded:
            return
        
        try:
            import json
            import base64
            
            data_json = base64.b64decode(encoded).decode('utf-8')
            source_data = json.loads(data_json)
            
            selected_ranges = self.selectedRanges()
            if not selected_ranges:
                current = self.currentIndex()
                if not current.isValid():
                    return
                self._paste_to_cell(current.row(), current.column(), source_data)
                return
            
            self._save_state()
            
            source_rows = len(source_data)
            source_cols = len(source_data[0]) if source_rows > 0 else 0
            
            for sel in selected_ranges:
                top = sel.topRow()
                left = sel.leftColumn()
                bottom = sel.bottomRow()
                right = sel.rightColumn()
                
                target_rows = bottom - top + 1
                target_cols = right - left + 1
                
                for row_offset in range(target_rows):
                    for col_offset in range(target_cols):
                        source_row = row_offset % source_rows
                        source_col = col_offset % source_cols
                        
                        target_row = top + row_offset
                        target_col = left + col_offset
                        
                        if source_row < len(source_data) and source_col < len(source_data[source_row]):
                            cell_data = source_data[source_row][source_col]
                        else:
                            continue
                        
                        if target_row >= self.rowCount():
                            self.insertRow(self.rowCount())
                        if target_col >= self.columnCount():
                            self.insertColumn(self.columnCount())
                        
                        item = self.item(target_row, target_col)
                        if not item:
                            item = QTableWidgetItem()
                            self.setItem(target_row, target_col, item)
                        
                        text = cell_data.get('text', '')
                        item.setText(text)
                        
                        formula = cell_data.get('formula')
                        if formula:
                            item.setData(Qt.UserRole + 1, formula)
                            result = self.evaluate_formula(formula, target_row, target_col)
                            if result is not None:
                                item.setText(str(result))
                            item.setForeground(QBrush(QColor(0, 100, 0)))
                        
                        format_info = cell_data.get('format')
                        if format_info:
                            self.format_manager.set_format(target_row, target_col, format_info)
                            self._apply_format_info(item, target_row, target_col)
                            self._mark_formats_changed()
            
            self.dataChanged.emit()
            
        except Exception as e:
            self.logger.error(f"Ошибка вставки: {e}")
            self._paste_simple_text_to_selection()

    def cut_selection(self):
        self._save_state()
        self.copy_selection()
        self.clear_selection()
    
    def clear_selection(self):
        self._save_state()
        for item in self.selectedItems():
            item.setText('')
        self.dataChanged.emit()
    
    # ========== МЕНЮ ==========
    
    def show_cell_menu(self, position):
        """Показывает контекстное меню для ячеек"""
        menu = QMenu()
        
        undo_action = QAction("↩ Отменить (Ctrl+Z)", self)
        undo_action.triggered.connect(self.undo)
        undo_action.setEnabled(len(self.undo_stack) > 0)
        menu.addAction(undo_action)
        
        redo_action = QAction("↪ Повторить (Ctrl+Y)", self)
        redo_action.triggered.connect(self.redo)
        redo_action.setEnabled(len(self.redo_stack) > 0)
        menu.addAction(redo_action)
        
        menu.addSeparator()
        
        # Подменю для выравнивания
        align_menu = menu.addMenu("🎯 Выравнивание")
        
        hor_align_menu = align_menu.addMenu("↔ По горизонтали")
        
        left_align = QAction("⬅ По левому краю", self)
        left_align.triggered.connect(lambda: self.set_alignment(Qt.AlignLeft, None))
        hor_align_menu.addAction(left_align)
        
        center_align = QAction("⬌ По центру", self)
        center_align.triggered.connect(lambda: self.set_alignment(Qt.AlignCenter, None))
        hor_align_menu.addAction(center_align)
        
        right_align = QAction("➡ По правому краю", self)
        right_align.triggered.connect(lambda: self.set_alignment(Qt.AlignRight, None))
        hor_align_menu.addAction(right_align)
        
        justify_align = QAction("📐 По ширине", self)
        justify_align.triggered.connect(lambda: self.set_alignment(Qt.AlignJustify, None))
        hor_align_menu.addAction(justify_align)
        
        align_menu.addSeparator()
        
        ver_align_menu = align_menu.addMenu("↕ По вертикали")
        
        top_align = QAction("⬆ По верхнему краю", self)
        top_align.triggered.connect(lambda: self.set_alignment(None, Qt.AlignTop))
        ver_align_menu.addAction(top_align)
        
        vcenter_align = QAction("⬌ По центру", self)
        vcenter_align.triggered.connect(lambda: self.set_alignment(None, Qt.AlignVCenter))
        ver_align_menu.addAction(vcenter_align)
        
        bottom_align = QAction("⬇ По нижнему краю", self)
        bottom_align.triggered.connect(lambda: self.set_alignment(None, Qt.AlignBottom))
        ver_align_menu.addAction(bottom_align)
        
        align_menu.addSeparator()
        
        combine_menu = align_menu.addMenu("🔄 Комбинированное")
        
        top_left = QAction("↖ По левому верхнему", self)
        top_left.triggered.connect(lambda: self.set_alignment(Qt.AlignLeft, Qt.AlignTop))
        combine_menu.addAction(top_left)
        
        top_center = QAction("⬆ По центру вверху", self)
        top_center.triggered.connect(lambda: self.set_alignment(Qt.AlignCenter, Qt.AlignTop))
        combine_menu.addAction(top_center)
        
        top_right = QAction("↗ По правому верхнему", self)
        top_right.triggered.connect(lambda: self.set_alignment(Qt.AlignRight, Qt.AlignTop))
        combine_menu.addAction(top_right)
        
        combine_menu.addSeparator()
        
        center_left = QAction("⬅ По левому центру", self)
        center_left.triggered.connect(lambda: self.set_alignment(Qt.AlignLeft, Qt.AlignVCenter))
        combine_menu.addAction(center_left)
        
        center_center = QAction("🎯 По центру", self)
        center_center.triggered.connect(lambda: self.set_alignment(Qt.AlignCenter, Qt.AlignVCenter))
        combine_menu.addAction(center_center)
        
        center_right = QAction("➡ По правому центру", self)
        center_right.triggered.connect(lambda: self.set_alignment(Qt.AlignRight, Qt.AlignVCenter))
        combine_menu.addAction(center_right)
        
        combine_menu.addSeparator()
        
        bottom_left = QAction("↙ По левому нижнему", self)
        bottom_left.triggered.connect(lambda: self.set_alignment(Qt.AlignLeft, Qt.AlignBottom))
        combine_menu.addAction(bottom_left)
        
        bottom_center = QAction("⬇ По центру внизу", self)
        bottom_center.triggered.connect(lambda: self.set_alignment(Qt.AlignCenter, Qt.AlignBottom))
        combine_menu.addAction(bottom_center)
        
        bottom_right = QAction("↘ По правому нижнему", self)
        bottom_right.triggered.connect(lambda: self.set_alignment(Qt.AlignRight, Qt.AlignBottom))
        combine_menu.addAction(bottom_right)
        
        menu.addSeparator()
        
        borders_menu = menu.addMenu("🔲 Границы")
        
        thin_border_action = QAction("─ Тонкая (1px)", self)
        thin_border_action.triggered.connect(lambda: self.set_border(self.BORDER_THIN))
        borders_menu.addAction(thin_border_action)
        
        medium_border_action = QAction("━ Средняя (2px)", self)
        medium_border_action.triggered.connect(lambda: self.set_border(self.BORDER_MEDIUM))
        borders_menu.addAction(medium_border_action)
        
        thick_border_action = QAction("┅ Толстая (3px)", self)
        thick_border_action.triggered.connect(lambda: self.set_border(self.BORDER_THICK))
        borders_menu.addAction(thick_border_action)
        
        double_border_action = QAction("═ Двойная", self)
        double_border_action.triggered.connect(lambda: self.set_border(self.BORDER_DOUBLE))
        borders_menu.addAction(double_border_action)
        
        borders_menu.addSeparator()
        
        no_border_action = QAction("✖ Убрать границы", self)
        no_border_action.triggered.connect(lambda: self.set_border(self.BORDER_NONE))
        borders_menu.addAction(no_border_action)
        
        borders_menu.addSeparator()
        
        individual_menu = borders_menu.addMenu("📐 Отдельные стороны")
        
        top_border_action = QAction("⬆ Верхняя", self)
        top_border_action.triggered.connect(lambda: self.set_individual_border('top', self.BORDER_THIN))
        individual_menu.addAction(top_border_action)
        
        bottom_border_action = QAction("⬇ Нижняя", self)
        bottom_border_action.triggered.connect(lambda: self.set_individual_border('bottom', self.BORDER_THIN))
        individual_menu.addAction(bottom_border_action)
        
        left_border_action = QAction("⬅ Левая", self)
        left_border_action.triggered.connect(lambda: self.set_individual_border('left', self.BORDER_THIN))
        individual_menu.addAction(left_border_action)
        
        right_border_action = QAction("➡ Правая", self)
        right_border_action.triggered.connect(lambda: self.set_individual_border('right', self.BORDER_THIN))
        individual_menu.addAction(right_border_action)
        
        individual_menu.addSeparator()
        
        clear_top_action = QAction("✖ Убрать верхнюю", self)
        clear_top_action.triggered.connect(lambda: self.set_individual_border('top', self.BORDER_NONE))
        individual_menu.addAction(clear_top_action)
        
        clear_bottom_action = QAction("✖ Убрать нижнюю", self)
        clear_bottom_action.triggered.connect(lambda: self.set_individual_border('bottom', self.BORDER_NONE))
        individual_menu.addAction(clear_bottom_action)
        
        clear_left_action = QAction("✖ Убрать левую", self)
        clear_left_action.triggered.connect(lambda: self.set_individual_border('left', self.BORDER_NONE))
        individual_menu.addAction(clear_left_action)
        
        clear_right_action = QAction("✖ Убрать правую", self)
        clear_right_action.triggered.connect(lambda: self.set_individual_border('right', self.BORDER_NONE))
        individual_menu.addAction(clear_right_action)
        
        menu.addSeparator()
        
        color_action = QAction("🎨 Цвет заливки", self)
        color_action.triggered.connect(self.set_cell_color)
        menu.addAction(color_action)
        
        font_menu = menu.addMenu("🔤 Шрифт")
        
        bold_action = QAction("🔲 Жирный (Ctrl+B)", self)
        bold_action.triggered.connect(self.toggle_bold)
        font_menu.addAction(bold_action)
        
        font_action = QAction("Выбрать шрифт...", self)
        font_action.triggered.connect(self.set_cell_font)
        font_menu.addAction(font_action)
        
        font_size_menu = font_menu.addMenu("📏 Размер шрифта")
        
        increase_font = QAction("⬆ Увеличить (Ctrl+Колесо)", self)
        increase_font.triggered.connect(lambda: self.change_font_size(1))
        font_size_menu.addAction(increase_font)
        
        decrease_font = QAction("⬇ Уменьшить (Ctrl+Колесо)", self)
        decrease_font.triggered.connect(lambda: self.change_font_size(-1))
        font_size_menu.addAction(decrease_font)
        
        font_size_menu.addSeparator()
        
        for size in [8, 9, 10, 11, 12, 14, 16, 18, 20]:
            size_action = QAction(str(size), self)
            size_action.triggered.connect(lambda s=size: self.set_font_size(s))
            font_size_menu.addAction(size_action)
        
        menu.addSeparator()
        
        merge_action = QAction("🔗 Объединить ячейки", self)
        merge_action.triggered.connect(self.merge_selected_cells)
        menu.addAction(merge_action)
        
        unmerge_action = QAction("🔓 Разъединить ячейки", self)
        unmerge_action.triggered.connect(self.unmerge_selected_cells)
        menu.addAction(unmerge_action)
        
        menu.addSeparator()
        
        formula_action = QAction("ƒ Вставить формулу", self)
        formula_action.triggered.connect(self.insert_formula_dialog)
        menu.addAction(formula_action)
        
        menu.addSeparator()
        
        insert_row_above = QAction("⬆️ Вставить строку выше", self)
        insert_row_above.triggered.connect(self.insert_row_above)
        menu.addAction(insert_row_above)
        
        insert_row_below = QAction("⬇️ Вставить строку ниже", self)
        insert_row_below.triggered.connect(self.insert_row_below)
        menu.addAction(insert_row_below)
        
        insert_col_left = QAction("⬅️ Вставить столбец слева", self)
        insert_col_left.triggered.connect(self.insert_column_left)
        menu.addAction(insert_col_left)
        
        insert_col_right = QAction("➡️ Вставить столбец справа", self)
        insert_col_right.triggered.connect(self.insert_column_right)
        menu.addAction(insert_col_right)
        
        menu.addSeparator()
        
        delete_row = QAction("🗑️ Удалить строку", self)
        delete_row.triggered.connect(self.delete_selected_rows)
        menu.addAction(delete_row)
        
        delete_col = QAction("🗑️ Удалить столбец", self)
        delete_col.triggered.connect(self.delete_selected_columns)
        menu.addAction(delete_col)
        
        menu.addSeparator()
        
        copy_action = QAction("📋 Копировать", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selection)
        menu.addAction(copy_action)
        
        paste_action = QAction("📌 Вставить", self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_selection)
        menu.addAction(paste_action)
        
        cut_action = QAction("✂️ Вырезать", self)
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.triggered.connect(self.cut_selection)
        menu.addAction(cut_action)
        
        clear_action = QAction("🧹 Очистить", self)
        clear_action.triggered.connect(self.clear_selection)
        menu.addAction(clear_action)
        
        menu.addSeparator()
        
        set_all_height_action = QAction("📏 Высота для всех строк", self)
        set_all_height_action.triggered.connect(self.set_all_rows_height_dialog)
        menu.addAction(set_all_height_action)
        
        menu.exec(self.viewport().mapToGlobal(position))

    def show_header_menu(self, position):
        menu = QMenu()
        if self.sender() == self.horizontalHeader():
            index = self.horizontalHeader().logicalIndexAt(position)
            if index >= 0:
                insert_action = QAction("➕ Вставить столбец", self)
                insert_action.triggered.connect(lambda: self._insert_column_at(index))
                menu.addAction(insert_action)
                
                delete_action = QAction("🗑️ Удалить столбец", self)
                delete_action.triggered.connect(lambda: self._delete_column_at(index))
                menu.addAction(delete_action)
                
                rename_action = QAction("✏️ Переименовать", self)
                rename_action.triggered.connect(lambda: self._rename_column_at(index))
                menu.addAction(rename_action)
        else:
            index = self.verticalHeader().logicalIndexAt(position)
            if index >= 0:
                insert_action = QAction("➕ Вставить строку", self)
                insert_action.triggered.connect(lambda: self._insert_row_at(index))
                menu.addAction(insert_action)
                
                delete_action = QAction("🗑️ Удалить строку", self)
                delete_action.triggered.connect(lambda: self._delete_row_at(index))
                menu.addAction(delete_action)
                
                rename_action = QAction("✏️ Переименовать", self)
                rename_action.triggered.connect(lambda: self._rename_row_at(index))
                menu.addAction(rename_action)
        menu.exec(self.mapToGlobal(position))
    
    def _insert_column_at(self, col):
        self._save_state()
        self.insertColumn(col)
        self.dataChanged.emit()
    
    def _delete_column_at(self, col):
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить столбец {col+1}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._save_state()
            self.removeColumn(col)
            self.dataChanged.emit()
    
    def _insert_row_at(self, row):
        self._save_state()
        self.insertRow(row)
        self.dataChanged.emit()
    
    def _delete_row_at(self, row):
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить строку {row+1}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._save_state()
            self.removeRow(row)
            self.dataChanged.emit()
    
    def _rename_column_at(self, col):
        self._save_state()
        current = self.horizontalHeaderItem(col)
        text, ok = QInputDialog.getText(self, "Переименовать", "Новое название:", text=current.text() if current else "")
        if ok and text:
            self.setHorizontalHeaderItem(col, QTableWidgetItem(text))
            self.dataChanged.emit()
    
    def _rename_row_at(self, row):
        self._save_state()
        current = self.verticalHeaderItem(row)
        text, ok = QInputDialog.getText(self, "Переименовать", "Новое название:", text=current.text() if current else "")
        if ok and text:
            self.setVerticalHeaderItem(row, QTableWidgetItem(text))
            self.dataChanged.emit()
    
    def set_cell_color(self):
        self._save_state()
        color = QColorDialog.getColor()
        if color.isValid():
            for item in self.selectedItems():
                row = item.row()
                col = item.column()
                format_info = self.format_manager.get_format(row, col) or {}
                format_info['background'] = (color.red(), color.green(), color.blue(), color.alpha())
                self.format_manager.set_format(row, col, format_info)
                item.setBackground(QBrush(color))
                self._mark_formats_changed()
            self.dataChanged.emit()
            
    def set_selected_cells_color(self, color):
        """Устанавливает цвет заливки для выделенных ячеек (по цвету)"""
        self._save_state()
        selected_items = self.selectedItems()
        if not selected_items:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Предупреждение", "Выберите ячейки для заливки")
            return
        
        brush = QBrush(color)
        for item in selected_items:
            row = item.row()
            col = item.column()
            format_info = self.format_manager.get_format(row, col) or {}
            format_info['background'] = (color.red(), color.green(), color.blue(), color.alpha())
            self.format_manager.set_format(row, col, format_info)
            item.setBackground(brush)
            self._mark_formats_changed()
        
        self.viewport().update()
        self.dataChanged.emit()
    
    # ========== ФОРМУЛЫ ==========
    
    def insert_formula_dialog(self):
        current_row = self.currentRow()
        current_col = self.currentColumn()
        if current_row < 0 or current_col < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите ячейку для формулы")
            return
        formula, ok = QInputDialog.getText(self, "Вставка формулы", 
            "Введите формулу (начинайте с =):\nПримеры:\n=SUM(A1:A10)\n=AVERAGE(B1:B5)\n=A1+B1")
        if ok and formula:
            self.set_formula(current_row, current_col, formula)
    
    def set_formula(self, row, col, formula):
        self._save_state()
        if not formula.startswith('='):
            formula = '=' + formula
        self.formulas[(row, col)] = formula
        result = self.evaluate_formula(formula, row, col)
        item = self.item(row, col)
        if not item:
            item = QTableWidgetItem()
            self.setItem(row, col, item)
        item.setText(str(result) if result is not None else "#ERROR")
        item.setData(Qt.UserRole + 1, formula)
        item.setForeground(QBrush(QColor(0, 100, 0)))
        self.dataChanged.emit()
    
    def evaluate_formula(self, formula, current_row, current_col):
        try:
            if formula.startswith('='):
                formula = formula[1:]
            
            sum_match = re.match(r'SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)', formula, re.IGNORECASE)
            if sum_match:
                start_col = self._col_letter_to_index(sum_match.group(1))
                start_row = int(sum_match.group(2))
                end_col = self._col_letter_to_index(sum_match.group(3))
                end_row = int(sum_match.group(4))
                total = 0
                for row in range(start_row - 1, end_row):
                    for col in range(start_col, end_col + 1):
                        item = self.item(row, col)
                        if item and item.text():
                            try:
                                total += float(item.text())
                            except:
                                pass
                return total
            
            avg_match = re.match(r'AVERAGE\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)', formula, re.IGNORECASE)
            if avg_match:
                start_col = self._col_letter_to_index(avg_match.group(1))
                start_row = int(avg_match.group(2))
                end_col = self._col_letter_to_index(avg_match.group(3))
                end_row = int(avg_match.group(4))
                total, count = 0, 0
                for row in range(start_row - 1, end_row):
                    for col in range(start_col, end_col + 1):
                        item = self.item(row, col)
                        if item and item.text():
                            try:
                                total += float(item.text())
                                count += 1
                            except:
                                pass
                return total / count if count > 0 else 0
            
            max_match = re.match(r'MAX\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)', formula, re.IGNORECASE)
            if max_match:
                start_col = self._col_letter_to_index(max_match.group(1))
                start_row = int(max_match.group(2))
                end_col = self._col_letter_to_index(max_match.group(3))
                end_row = int(max_match.group(4))
                max_val = float('-inf')
                for row in range(start_row - 1, end_row):
                    for col in range(start_col, end_col + 1):
                        item = self.item(row, col)
                        if item and item.text():
                            try:
                                max_val = max(max_val, float(item.text()))
                            except:
                                pass
                return max_val if max_val != float('-inf') else 0
            
            min_match = re.match(r'MIN\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)', formula, re.IGNORECASE)
            if min_match:
                start_col = self._col_letter_to_index(min_match.group(1))
                start_row = int(min_match.group(2))
                end_col = self._col_letter_to_index(min_match.group(3))
                end_row = int(min_match.group(4))
                min_val = float('inf')
                for row in range(start_row - 1, end_row):
                    for col in range(start_col, end_col + 1):
                        item = self.item(row, col)
                        if item and item.text():
                            try:
                                min_val = min(min_val, float(item.text()))
                            except:
                                pass
                return min_val if min_val != float('inf') else 0
            
            def replace_cell_ref(match):
                ref = match.group(0)
                col_letter = re.match(r'[A-Z]+', ref).group(0)
                row_num = int(re.search(r'\d+', ref).group(0))
                col = self._col_letter_to_index(col_letter)
                item = self.item(row_num - 1, col)
                if item and item.text():
                    try:
                        return str(float(item.text()))
                    except:
                        return '0'
                return '0'
            
            expr = re.sub(r'[A-Z]+\d+', replace_cell_ref, formula)
            allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith('__')}
            allowed_names.update({'abs': abs, 'round': round})
            return eval(expr, {"__builtins__": {}}, allowed_names)
            
        except Exception as e:
            self.logger.error(f"Ошибка формулы {formula}: {e}")
            return "#ERROR"
    
    def _col_letter_to_index(self, col_letter):
        result = 0
        for char in col_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def _index_to_col_letter(self, index):
        result = ""
        index += 1
        while index > 0:
            index -= 1
            result = chr(ord('A') + (index % 26)) + result
            index //= 26
        return result
    
    # ========== ОБЪЕДИНЕНИЕ ЯЧЕЕК ==========
    
    def merge_selected_cells(self):
        self._save_state()
        ranges = self.selectedRanges()
        if not ranges:
            QMessageBox.warning(self, "Предупреждение", "Выберите ячейки для объединения")
            return
        sel = ranges[0]
        for row in range(sel.topRow(), sel.bottomRow() + 1):
            for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                if self.rowSpan(row, col) > 1 or self.columnSpan(row, col) > 1:
                    QMessageBox.warning(self, "Предупреждение", "Некоторые ячейки уже объединены")
                    return
        self.setSpan(sel.topRow(), sel.leftColumn(), sel.rowCount(), sel.columnCount())
        merge_info = {
            'top': sel.topRow(),
            'left': sel.leftColumn(),
            'rows': sel.rowCount(),
            'cols': sel.columnCount()
        }
        self.merged_cells.append(merge_info)
        top_left = self.item(sel.topRow(), sel.leftColumn())
        if top_left:
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                    if row != sel.topRow() or col != sel.leftColumn():
                        item = self.item(row, col)
                        if item:
                            item.setText("")
        self.dataChanged.emit()
    
    def unmerge_selected_cells(self):
        self._save_state()
        ranges = self.selectedRanges()
        if not ranges:
            row, col = self.currentRow(), self.currentColumn()
            if row >= 0 and col >= 0:
                if self.rowSpan(row, col) > 1 or self.columnSpan(row, col) > 1:
                    self._unmerge_cell(row, col)
            return
        sel = ranges[0]
        for row in range(sel.topRow(), sel.bottomRow() + 1):
            for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                if self.rowSpan(row, col) > 1 or self.columnSpan(row, col) > 1:
                    self._unmerge_cell(row, col)
        self.dataChanged.emit()
    
    def _unmerge_cell(self, row, col):
        if self.rowSpan(row, col) == 1 and self.columnSpan(row, col) == 1:
            return
        rows = self.rowSpan(row, col)
        cols = self.columnSpan(row, col)
        for r in range(row, -1, -1):
            if self.rowSpan(r, col) == rows and self.columnSpan(r, col) == cols and r <= row:
                top_row = r
                break
        else:
            top_row = row
        for c in range(col, -1, -1):
            if self.rowSpan(top_row, c) == rows and self.columnSpan(top_row, c) == cols and c <= col:
                left_col = c
                break
        else:
            left_col = col
        self.setSpan(top_row, left_col, 1, 1)
        self.merged_cells = [m for m in self.merged_cells 
                           if not (m['top'] == top_row and m['left'] == left_col)]
    
    # ========== ВСТАВКА/УДАЛЕНИЕ СТРОК/СТОЛБЦОВ ==========
    
    def insert_row_above(self):
        self._save_state()
        row = self.currentRow()
        if row >= 0:
            self.insertRow(row)
            self.dataChanged.emit()
    
    def insert_row_below(self):
        self._save_state()
        row = self.currentRow()
        if row >= 0:
            self.insertRow(row + 1)
            self.dataChanged.emit()
    
    def insert_column_left(self):
        self._save_state()
        col = self.currentColumn()
        if col >= 0:
            self.insertColumn(col)
            self.dataChanged.emit()
    
    def insert_column_right(self):
        self._save_state()
        col = self.currentColumn()
        if col >= 0:
            self.insertColumn(col + 1)
            self.dataChanged.emit()
    
    def delete_selected_rows(self):
        rows = set(item.row() for item in self.selectedItems())
        if not rows:
            return
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить {len(rows)} строк?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._save_state()
            for row in sorted(rows, reverse=True):
                self.removeRow(row)
            self.dataChanged.emit()
    
    def delete_selected_columns(self):
        cols = set(item.column() for item in self.selectedItems())
        if not cols:
            return
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить {len(cols)} столбцов?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._save_state()
            for col in sorted(cols, reverse=True):
                self.removeColumn(col)
            self.dataChanged.emit()
    
    # ========== ФОРМАТИРОВАНИЕ ==========
    
    def set_alignment(self, horizontal=None, vertical=None):
        self._save_state()
        for item in self.selectedItems():
            row = item.row()
            col = item.column()
            align = int(item.textAlignment())
            if horizontal is not None:
                align &= ~int(Qt.AlignHorizontal_Mask)
                align |= int(horizontal)
            if vertical is not None:
                align &= ~int(Qt.AlignVertical_Mask)
                align |= int(vertical)
            item.setTextAlignment(align)
            format_info = self.format_manager.get_format(row, col) or {}
            format_info['alignment'] = align
            self.format_manager.set_format(row, col, format_info)
            self._mark_formats_changed()
        self.dataChanged.emit()
    
    def set_border(self, border_type):
        self._save_state()
        cells = set()
        for item in self.selectedItems():
            cells.add((item.row(), item.column()))
        for row, col in cells:
            item = self.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.setItem(row, col, item)
            self._apply_border_to_item(item, border_type, 'all', row, col)
        self.viewport().update()
        self.dataChanged.emit()
    
    def set_individual_border(self, side, border_type):
        self._save_state()
        cells = set()
        for item in self.selectedItems():
            cells.add((item.row(), item.column()))
        for row, col in cells:
            item = self.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.setItem(row, col, item)
            self._apply_border_to_item(item, border_type, side, row, col)
        self.viewport().update()
        self.dataChanged.emit()
    
    def _apply_border_to_item(self, item, border_type, side, row, col):
        borders = self.format_manager.get_format(row, col)
        if borders is None or not isinstance(borders, dict):
            borders = {
                'top': self.BORDER_NONE,
                'bottom': self.BORDER_NONE,
                'left': self.BORDER_NONE,
                'right': self.BORDER_NONE
            }
        
        if side == 'all':
            borders['top'] = border_type
            borders['bottom'] = border_type
            borders['left'] = border_type
            borders['right'] = border_type
        else:
            if side in borders:
                borders[side] = border_type
        
        self.format_manager.set_format(row, col, borders)
        self._mark_formats_changed()
        item.setData(Qt.UserRole + 2, borders)
    
    def _get_border_width(self, border_type):
        if border_type == self.BORDER_THIN:
            return 1
        elif border_type == self.BORDER_MEDIUM:
            return 2
        elif border_type == self.BORDER_THICK:
            return 3
        elif border_type == self.BORDER_DOUBLE:
            return 2
        return 0
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)
        try:
            drawn_borders = set()
            for row in range(self.rowCount()):
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if not item:
                        continue
                    borders = item.data(Qt.UserRole + 2)
                    if not borders or not isinstance(borders, dict):
                        continue
                    rect = self.visualRect(self.model().index(row, col))
                    border_type = borders.get('top', 0)
                    if border_type != 0:
                        key = (row, col, 'top')
                        if key not in drawn_borders:
                            has_top_neighbor_bottom = False
                            if row > 0:
                                neighbor = self.item(row - 1, col)
                                if neighbor:
                                    neighbor_borders = neighbor.data(Qt.UserRole + 2)
                                    if neighbor_borders and isinstance(neighbor_borders, dict):
                                        if neighbor_borders.get('bottom', 0) != 0:
                                            has_top_neighbor_bottom = True
                            if not has_top_neighbor_bottom:
                                pen = QPen(Qt.black)
                                pen.setWidth(self._get_border_width(border_type))
                                painter.setPen(pen)
                                if border_type == self.BORDER_DOUBLE:
                                    offset = 1
                                    painter.drawLine(rect.topLeft().x(), rect.topLeft().y() - offset,
                                                     rect.topRight().x(), rect.topRight().y() - offset)
                                    painter.drawLine(rect.topLeft().x(), rect.topLeft().y() + offset,
                                                     rect.topRight().x(), rect.topRight().y() + offset)
                                else:
                                    painter.drawLine(rect.topLeft(), rect.topRight())
                                drawn_borders.add(key)
                    border_type = borders.get('bottom', 0)
                    if border_type != 0:
                        key = (row, col, 'bottom')
                        if key not in drawn_borders:
                            has_bottom_neighbor_top = False
                            if row + 1 < self.rowCount():
                                neighbor = self.item(row + 1, col)
                                if neighbor:
                                    neighbor_borders = neighbor.data(Qt.UserRole + 2)
                                    if neighbor_borders and isinstance(neighbor_borders, dict):
                                        if neighbor_borders.get('top', 0) != 0:
                                            has_bottom_neighbor_top = True
                            if not has_bottom_neighbor_top:
                                pen = QPen(Qt.black)
                                pen.setWidth(self._get_border_width(border_type))
                                painter.setPen(pen)
                                if border_type == self.BORDER_DOUBLE:
                                    offset = 1
                                    painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y() - offset,
                                                     rect.bottomRight().x(), rect.bottomRight().y() - offset)
                                    painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y() + offset,
                                                     rect.bottomRight().x(), rect.bottomRight().y() + offset)
                                else:
                                    painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                                drawn_borders.add(key)
                    border_type = borders.get('left', 0)
                    if border_type != 0:
                        key = (row, col, 'left')
                        if key not in drawn_borders:
                            has_left_neighbor_right = False
                            if col > 0:
                                neighbor = self.item(row, col - 1)
                                if neighbor:
                                    neighbor_borders = neighbor.data(Qt.UserRole + 2)
                                    if neighbor_borders and isinstance(neighbor_borders, dict):
                                        if neighbor_borders.get('right', 0) != 0:
                                            has_left_neighbor_right = True
                            if not has_left_neighbor_right:
                                pen = QPen(Qt.black)
                                pen.setWidth(self._get_border_width(border_type))
                                painter.setPen(pen)
                                if border_type == self.BORDER_DOUBLE:
                                    offset = 1
                                    painter.drawLine(rect.topLeft().x() - offset, rect.topLeft().y(),
                                                     rect.bottomLeft().x() - offset, rect.bottomLeft().y())
                                    painter.drawLine(rect.topLeft().x() + offset, rect.topLeft().y(),
                                                     rect.bottomLeft().x() + offset, rect.bottomLeft().y())
                                else:
                                    painter.drawLine(rect.topLeft(), rect.bottomLeft())
                                drawn_borders.add(key)
                    border_type = borders.get('right', 0)
                    if border_type != 0:
                        key = (row, col, 'right')
                        if key not in drawn_borders:
                            has_right_neighbor_left = False
                            if col + 1 < self.columnCount():
                                neighbor = self.item(row, col + 1)
                                if neighbor:
                                    neighbor_borders = neighbor.data(Qt.UserRole + 2)
                                    if neighbor_borders and isinstance(neighbor_borders, dict):
                                        if neighbor_borders.get('left', 0) != 0:
                                            has_right_neighbor_left = True
                            if not has_right_neighbor_left:
                                pen = QPen(Qt.black)
                                pen.setWidth(self._get_border_width(border_type))
                                painter.setPen(pen)
                                if border_type == self.BORDER_DOUBLE:
                                    offset = 1
                                    painter.drawLine(rect.topRight().x() - offset, rect.topRight().y(),
                                                     rect.bottomRight().x() - offset, rect.bottomRight().y())
                                    painter.drawLine(rect.topRight().x() + offset, rect.topRight().y(),
                                                     rect.bottomRight().x() + offset, rect.bottomRight().y())
                                else:
                                    painter.drawLine(rect.topRight(), rect.bottomRight())
                                drawn_borders.add(key)
            # ===== ПОДСВЕТКА ВЫДЕЛЕНИЯ (фиолетовая рамка вокруг диапазона) =====
            pen_sel = QPen(QColor('#6c63ff'))
            pen_sel.setWidth(2)
            for rng in self.selectedRanges():
                top_left = self.visualRect(self.model().index(rng.topRow(), rng.leftColumn()))
                bottom_right = self.visualRect(self.model().index(rng.bottomRow(), rng.rightColumn()))
                if top_left.isValid() and bottom_right.isValid():
                    sel_rect = top_left.united(bottom_right)
                    painter.setPen(pen_sel)
                    painter.drawRect(sel_rect)
            # ===== КУРСОР (оранжевая рамка вокруг текущей ячейки) =====
            cur = self.currentIndex()
            if cur.isValid():
                rect = self.visualRect(cur)
                if rect.isValid():
                    pen_cur = QPen(QColor('#ff9800'))
                    pen_cur.setWidth(2)
                    painter.setPen(pen_cur)
                    painter.drawRect(rect)
        finally:
            painter.end()

    def set_cell_font(self):
        self._save_state()
        
        selected_items = self.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите ячейки для форматирования")
            return
        
        current_font = selected_items[0].font()
        font, ok = QFontDialog.getFont(current_font, self, "Выберите шрифт")
        
        if ok and isinstance(font, QFont):
            for item in selected_items:
                row = item.row()
                col = item.column()
                item.setFont(font)
                
                format_info = self.format_manager.get_format(row, col) or {}
                if 'font' not in format_info:
                    format_info['font'] = {}
                format_info['font'].update({
                    'family': font.family(),
                    'point_size': font.pointSize(),
                    'bold': font.bold(),
                    'italic': font.italic(),
                    'underline': font.underline(),
                    'strikeout': font.strikeOut()
                })
                self.format_manager.set_format(row, col, format_info)
                self._mark_formats_changed()
            
            self.viewport().update()
            self.dataChanged.emit()
    
    def change_font_size(self, delta):
        self._save_state()
        for item in self.selectedItems():
            row = item.row()
            col = item.column()
            font = item.font()
            if isinstance(font, QFont):
                size = font.pointSize()
                if size > 0:
                    font.setPointSize(max(6, min(72, size + delta)))
                    item.setFont(font)
                    
                    format_info = self.format_manager.get_format(row, col) or {}
                    if 'font' not in format_info:
                        format_info['font'] = {}
                    format_info['font']['point_size'] = font.pointSize()
                    self.format_manager.set_format(row, col, format_info)
                    self._mark_formats_changed()
        self.dataChanged.emit()
    
    def set_font_size(self, size):
        self._save_state()
        for item in self.selectedItems():
            row = item.row()
            col = item.column()
            font = item.font()
            if isinstance(font, QFont):
                font.setPointSize(size)
                item.setFont(font)
                
                format_info = self.format_manager.get_format(row, col) or {}
                if 'font' not in format_info:
                    format_info['font'] = {}
                format_info['font']['point_size'] = size
                self.format_manager.set_format(row, col, format_info)
                self._mark_formats_changed()
        self.dataChanged.emit()
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = 1 if event.angleDelta().y() > 0 else -1
            self.change_font_size(delta)
        else:
            super().wheelEvent(event)
            
    def set_all_rows_height(self, height):
        self._save_state()
        for row in range(self.rowCount()):
            self.setRowHeight(row, height)
        self.dataChanged.emit()
        
    def set_all_rows_height_dialog(self):
        current_height = 20
        if self.rowCount() > 0:
            current_height = self.rowHeight(0)
        
        height, ok = QInputDialog.getInt(
            self,
            "Высота строк",
            "Введите высоту строк в пикселях (10-200):",
            current_height,
            10,
            200,
            1
        )
        
        if ok and height > 0:
            self.set_all_rows_height(height)
    
    def toggle_bold(self):
        self._save_state()
        
        selected_items = self.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите ячейки для форматирования")
            return
        
        first_font = selected_items[0].font()
        make_bold = not first_font.bold()
        
        for item in selected_items:
            row = item.row()
            col = item.column()
            font = item.font()
            font.setBold(make_bold)
            item.setFont(font)
            
            format_info = self.format_manager.get_format(row, col) or {}
            if 'font' not in format_info:
                format_info['font'] = {}
            format_info['font']['bold'] = make_bold
            self.format_manager.set_format(row, col, format_info)
            self._mark_formats_changed()
        
        self.viewport().update()
        self.dataChanged.emit()
    
    def _extract_format_info(self, item):
        if not item:
            return None
        
        format_info = {
            'foreground': None,
            'background': None,
            'font': None,
            'alignment': item.textAlignment(),
            'borders': None
        }
        
        if item.foreground().color().isValid():
            color = item.foreground().color()
            if color != QColor(0, 0, 0):
                format_info['foreground'] = (color.red(), color.green(), color.blue(), color.alpha())
        
        if item.background().color().isValid():
            color = item.background().color()
            if color != QColor(255, 255, 255):
                format_info['background'] = (color.red(), color.green(), color.blue(), color.alpha())
        
        font = item.font()
        default_font = QFont()
        
        if (font.family() != default_font.family() or
            font.pointSize() != default_font.pointSize() or
            font.bold() != default_font.bold() or
            font.italic() != default_font.italic() or
            font.underline() != default_font.underline() or
            font.strikeOut() != default_font.strikeOut()):
            
            format_info['font'] = {
                'family': font.family(),
                'point_size': font.pointSize(),
                'bold': font.bold(),
                'italic': font.italic(),
                'underline': font.underline(),
                'strikeout': font.strikeOut()
            }
        
        borders = item.data(Qt.UserRole + 2)
        if borders and isinstance(borders, dict):
            format_info['borders'] = borders.copy()
        
        return format_info

    def _apply_format_info(self, item, row, col):
        format_info = self.format_manager.get_format(row, col)
        if not format_info:
            # Нет форматирования — светлый текст на тёмном фоне
            item.setForeground(QBrush(self._default_text_color()))
            return
        # Фон ячейки
        bg_light = False
        if format_info.get('background'):
            r, g, b, a = format_info['background']
            color = QColor(r, g, b, a)
            item.setBackground(QBrush(color))
            bg_light = color.lightness() > 128
        else:
            item.setBackground(QBrush(Qt.transparent))
        # Текст: явный цвет из формата, иначе автоподбор по фону
        if format_info.get('foreground'):
            r, g, b, a = format_info['foreground']
            item.setForeground(QBrush(QColor(r, g, b, a)))
        else:
            if bg_light:
                item.setForeground(QBrush(QColor(0, 0, 0)))
            else:
                item.setForeground(QBrush(self._default_text_color()))
        if format_info.get('font'):
            font_info = format_info['font']
            font = QFont()
            font.setFamily(font_info.get('family', 'Arial'))
            if font_info.get('point_size'):
                font.setPointSize(font_info['point_size'])
            font.setBold(font_info.get('bold', False))
            font.setItalic(font_info.get('italic', False))
            font.setUnderline(font_info.get('underline', False))
            font.setStrikeOut(font_info.get('strikeout', False))
            item.setFont(font)
        else:
            item.setFont(QFont())
        if format_info.get('alignment') is not None:
            item.setTextAlignment(format_info['alignment'])
        else:
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if format_info.get('borders'):
            borders = format_info['borders']
            if isinstance(borders, dict):
                full_borders = {
                    'top': borders.get('top', self.BORDER_NONE),
                    'bottom': borders.get('bottom', self.BORDER_NONE),
                    'left': borders.get('left', self.BORDER_NONE),
                    'right': borders.get('right', self.BORDER_NONE)
                }
                item.setData(Qt.UserRole + 2, full_borders)
            else:
                item.setData(Qt.UserRole + 2, None)

    def _paste_simple_text(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        
        rows = text.split('\n')
        current = self.currentIndex()
        if not current.isValid():
            return
        
        self._save_state()
        
        start_row = current.row()
        start_col = current.column()
        
        for r, row_data in enumerate(rows):
            if start_row + r >= self.rowCount():
                self.insertRow(self.rowCount())
            
            cols = row_data.split('\t')
            for c, col_data in enumerate(cols):
                if start_col + c >= self.columnCount():
                    self.insertColumn(self.columnCount())
                
                item = self.item(start_row + r, start_col + c)
                if not item:
                    item = QTableWidgetItem()
                    self.setItem(start_row + r, start_col + c, item)
                item.setText(col_data)
        
        self.dataChanged.emit()
        
    def _paste_to_cell(self, start_row, start_col, source_data):
        source_rows = len(source_data)
        source_cols = len(source_data[0]) if source_rows > 0 else 0
        
        for r in range(source_rows):
            target_row = start_row + r
            if target_row >= self.rowCount():
                self.insertRow(self.rowCount())
            
            for c in range(source_cols):
                target_col = start_col + c
                if target_col >= self.columnCount():
                    self.insertColumn(self.columnCount())
                
                if r < len(source_data) and c < len(source_data[r]):
                    cell_data = source_data[r][c]
                    item = self.item(target_row, target_col)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(target_row, target_col, item)
                    
                    text = cell_data.get('text', '')
                    item.setText(text)
                    
                    formula = cell_data.get('formula')
                    if formula:
                        item.setData(Qt.UserRole + 1, formula)
                        result = self.evaluate_formula(formula, target_row, target_col)
                        if result is not None:
                            item.setText(str(result))
                        item.setForeground(QBrush(QColor(0, 100, 0)))
                    
                    format_info = cell_data.get('format')
                    if format_info:
                        self.format_manager.set_format(target_row, target_col, format_info)
                        self._apply_format_info(item, target_row, target_col)
                        self._mark_formats_changed()
                    
    def _paste_simple_text_to_selection(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        
        rows_data = [row.split('\t') for row in text.split('\n') if row]
        if not rows_data:
            return
        
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            current = self.currentIndex()
            if not current.isValid():
                return
            self._paste_simple_text_to_cell(current.row(), current.column(), rows_data)
            return
        
        self._save_state()
        
        for sel in selected_ranges:
            top = sel.topRow()
            left = sel.leftColumn()
            bottom = sel.bottomRow()
            right = sel.rightColumn()
            
            target_rows = bottom - top + 1
            target_cols = right - left + 1
            
            for row_offset in range(target_rows):
                for col_offset in range(target_cols):
                    source_row = row_offset % source_rows
                    source_col = col_offset % source_cols
                    
                    target_row = top + row_offset
                    target_col = left + col_offset
                    
                    if target_row >= self.rowCount():
                        self.insertRow(self.rowCount())
                    if target_col >= self.columnCount():
                        self.insertColumn(self.columnCount())
                    
                    if source_row < len(rows_data) and source_col < len(rows_data[source_row]):
                        cell_text = rows_data[source_row][source_col]
                    else:
                        cell_text = ""
                    
                    item = self.item(target_row, target_col)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(target_row, target_col, item)
                    item.setText(cell_text)
        
        self.dataChanged.emit()
        
    def _paste_simple_text_to_cell(self, start_row, start_col, rows_data):
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        for r in range(source_rows):
            target_row = start_row + r
            if target_row >= self.rowCount():
                self.insertRow(self.rowCount())
            
            for c in range(source_cols):
                target_col = start_col + c
                if target_col >= self.columnCount():
                    self.insertColumn(self.columnCount())
                
                if r < len(rows_data) and c < len(rows_data[r]):
                    item = self.item(target_row, target_col)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(target_row, target_col, item)
                    item.setText(rows_data[r][c])
    
    def setItem(self, row, column, item):
        """Переопределяем setItem для применения форматирования"""
        super().setItem(row, column, item)
        # Цвет текста по умолчанию — по теме (светлый на тёмном фоне)
        if item and not item.foreground().color().isValid():
            item.setForeground(QBrush(self._default_text_color()))
        self._apply_format_info(item, row, column)
        self.dataChanged.emit()

    def save_formats_to_dict(self):
        return self.format_manager.get_all_formats()
    
    def load_formats_from_dict(self, formats_dict):
        self.format_manager.set_from_dict(formats_dict)
        self._formats_loaded = True
        for (row, col), format_data in formats_dict.items():
            item = self.item(row, col)
            if item:
                self._apply_format_info(item, row, col)
                if item:
                    item._formatted = True
        self.viewport().update()
    
    def clear_all_formats(self):
        self.format_manager.clear_all()
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QBrush(Qt.transparent))
                    item.setForeground(QBrush(self._default_text_color()))
                    item.setFont(QFont())
                    item.setData(Qt.UserRole + 2, None)
        self.viewport().update()


    def _get_dark_style(self):
        """Тёмный стиль таблицы (БЕЗ фонов ячеек — заливку рисует делегат)"""
        return """
            QTableView {
                color: #e4e4ef;
                selection-background-color: #6c63ff;
                selection-color: #ffffff;
                gridline-color: #2a2a4a;
            }
            QTableView::item:selected {
                background-color: #6c63ff;
                color: #ffffff;
            }
            QTableView::item:selected:!active {
                background-color: #5a52e0;
            }
            QHeaderView::section {
                background-color: #16213e;
                color: #a8a8d0;
                padding: 4px;
                border: 1px solid #2a2a4a;
                font-weight: bold;
            }
            QHeaderView::section:hover {
                background-color: #1f2b47;
            }
            QHeaderView::section:horizontal {
                border-right: 1px solid #2a2a4a;
            }
            QHeaderView::section:vertical {
                border-bottom: 1px solid #2a2a4a;
            }
        """