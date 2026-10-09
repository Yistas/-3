# -*- coding: utf-8 -*-

"""
Кастомная таблица для продажи серебра с поддержкой Ctrl+C и Ctrl+V
"""

from PySide6.QtWidgets import QTableView, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent


class SilverTableView(QTableView):
    """Кастомная таблица для серебра с поддержкой копирования/вставки"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = parent
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSelectionMode(QTableView.ExtendedSelection)  # Включаем множественное выделение
        
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка нажатия клавиш в таблице"""
        
        # Ctrl+C - копирование
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
            self._copy_selected_cells()
            event.accept()
            return
        
        # Ctrl+V - вставка
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_V:
            self._paste_to_selected_cells()
            event.accept()
            return
        
        # Delete - очистка
        if event.key() == Qt.Key_Delete:
            self._clear_selected_cells()
            event.accept()
            return
        
        # F2 - редактирование
        if event.key() == Qt.Key_F2:
            current = self.currentIndex()
            if current.isValid():
                self.edit(current)
            event.accept()
            return
        
        # Tab - переход на следующую ячейку
        if event.key() == Qt.Key_Tab:
            current = self.currentIndex()
            if current.isValid():
                if current.column() < self.model().columnCount() - 1:
                    self.setCurrentIndex(self.model().index(current.row(), current.column() + 1))
                else:
                    if current.row() < self.model().rowCount() - 1:
                        self.setCurrentIndex(self.model().index(current.row() + 1, 0))
                event.accept()
                return
        
        # Enter - переход на следующую строку
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current = self.currentIndex()
            if current.isValid():
                if current.row() < self.model().rowCount() - 1:
                    self.setCurrentIndex(self.model().index(current.row() + 1, current.column()))
                event.accept()
                return
        
        super().keyPressEvent(event)
    
    def _copy_selected_cells(self):
        """Копирует выделенные ячейки (поддерживает множественное выделение)"""
        if not self._parent_tab:
            return
        
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        # Получаем все выделенные строки и колонки
        rows = {}
        min_row = float('inf')
        max_row = -1
        min_col = float('inf')
        max_col = -1
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            
            if row < min_row:
                min_row = row
            if row > max_row:
                max_row = row
            if col < min_col:
                min_col = col
            if col > max_col:
                max_col = col
            
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value
        
        # Строим полную матрицу от min_row до max_row и от min_col до max_col
        lines = []
        for row in range(min_row, max_row + 1):
            line = []
            for col in range(min_col, max_col + 1):
                if row in rows and col in rows[row]:
                    line.append(rows[row][col])
                else:
                    line.append("")
            lines.append("\t".join(line))
        
        # Формируем текст для буфера обмена
        text = "\n".join(lines)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        count = len(selected_indexes)
        if hasattr(self._parent_tab, 'status_label'):
            self._parent_tab.status_label.setText(f"📋 Скопировано {count} ячеек ({max_row - min_row + 1} x {max_col - min_col + 1})")
            self._parent_tab.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self._parent_tab.status_label.setStyleSheet("color: #666; font-size: 11px;"))
    
    def _paste_to_selected_cells(self):
        """Вставляет данные в выделенные ячейки (поддерживает множественное выделение)"""
        if not self._parent_tab:
            return
        
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        # Разбираем буфер обмена на строки и столбцы
        lines = text.strip().split("\n")
        rows_data = []
        max_cols = 0
        
        for line in lines:
            # Пробуем табуляцию, потом запятую
            if "\t" in line:
                row = line.split("\t")
            elif "," in line:
                row = line.split(",")
            else:
                row = [line]
            rows_data.append([cell.strip() for cell in row])
            if len(row) > max_cols:
                max_cols = len(row)
        
        if not rows_data:
            return
        
        # Получаем выделенные ячейки
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = self.currentIndex()
            if current.isValid():
                selected_indexes = [current]
            else:
                return
        
        # Сортируем по строкам и колонкам
        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        
        # Получаем стартовую позицию (минимальная строка и колонка)
        start_row = min(idx.row() for idx in selected_indexes)
        start_col = min(idx.column() for idx in selected_indexes)
        
        # Получаем модель и данные закупки
        model = self.model()
        if not model:
            return
        
        purchase_id = model.get_purchase_id()
        if not purchase_id:
            return
        
        # Находим закупку
        purchase = None
        for p in self._parent_tab.purchases:
            if p['id'] == purchase_id:
                purchase = p
                break
        
        if not purchase:
            return
        
        source_rows = len(rows_data)
        source_cols = max_cols
        
        self.setUpdatesEnabled(False)
        
        try:
            changes_made = False
            from .silver_model import SilverTableModel
            
            # Проходим по всем выделенным ячейкам
            for idx in selected_indexes:
                row = idx.row()
                col = idx.column()
                
                # Вычисляем источник данных (с повторением, как в Excel)
                source_row = (row - start_row) % source_rows
                source_col = (col - start_col) % source_cols
                
                if source_row < len(rows_data) and source_col < len(rows_data[source_row]):
                    value = rows_data[source_row][source_col]
                else:
                    value = ""
                
                # Получаем ключ колонки
                if col < len(SilverTableModel.COLUMN_KEYS):
                    field_name = SilverTableModel.COLUMN_KEYS[col]
                    
                    # Обновляем данные
                    if row < len(purchase['coins']):
                        coin = purchase['coins'][row]
                        if field_name in coin:
                            old_value = coin[field_name]
                            if str(old_value) != value:
                                # Преобразуем значение в правильный тип
                                if field_name in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                                    try:
                                        clean_value = value.replace(' ', '').replace(',', '.')
                                        coin[field_name] = float(clean_value) if clean_value else 0
                                    except (ValueError, TypeError):
                                        coin[field_name] = 0
                                elif field_name in ['avito', 'lave', 'meshok', 'ucoin']:
                                    coin[field_name] = value in ['✅', 'True', 'true', '1', 'Да', 'yes']
                                elif field_name == 'status':
                                    status_map = {'В продаже': 'in_sale', 'Продана': 'sold', 'В коллекции': 'in_collection'}
                                    coin[field_name] = status_map.get(value, 'in_sale')
                                else:
                                    coin[field_name] = value if value else None
                                
                                changes_made = True
                                self._parent_tab._dirty_purchases.add(purchase_id)
            
            if changes_made:
                # Обновляем модель
                model.set_data(purchase['coins'])
                self._parent_tab._save_dirty_purchases()
                
                if hasattr(self._parent_tab, 'status_label'):
                    self._parent_tab.status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
                    self._parent_tab.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                    QTimer.singleShot(2000, lambda: self._parent_tab.status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self._parent_tab.logger.error(f"Ошибка вставки: {e}")
            if hasattr(self._parent_tab, 'status_label'):
                self._parent_tab.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
        finally:
            self.setUpdatesEnabled(True)
    
    def _clear_selected_cells(self):
        """Очищает выделенные ячейки"""
        if not self._parent_tab:
            return
        
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        # Получаем модель
        model = self.model()
        if not model:
            return
        
        purchase_id = model.get_purchase_id()
        if not purchase_id:
            return
        
        # Находим закупку
        purchase = None
        for p in self._parent_tab.purchases:
            if p['id'] == purchase_id:
                purchase = p
                break
        
        if not purchase:
            return
        
        changes_made = False
        from .silver_model import SilverTableModel
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            
            if col < len(SilverTableModel.COLUMN_KEYS):
                field_name = SilverTableModel.COLUMN_KEYS[col]
                
                if row < len(purchase['coins']):
                    coin = purchase['coins'][row]
                    if field_name in coin:
                        if field_name == 'status':
                            coin[field_name] = 'in_sale'
                        elif field_name in ['avito', 'lave', 'meshok', 'ucoin']:
                            coin[field_name] = False
                        elif field_name in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                            coin[field_name] = 0
                        else:
                            coin[field_name] = None
                        
                        changes_made = True
                        self._parent_tab._dirty_purchases.add(purchase_id)
        
        if changes_made:
            model.set_data(purchase['coins'])
            self._parent_tab._save_dirty_purchases()
            
            if hasattr(self._parent_tab, 'status_label'):
                self._parent_tab.status_label.setText(f"🧹 Очищено {len(selected_indexes)} ячеек")
                self._parent_tab.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self._parent_tab.status_label.setStyleSheet("color: #666; font-size: 11px;"))