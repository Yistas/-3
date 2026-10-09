# -*- coding: utf-8 -*-

"""
Модель данных для таблицы продаж
"""

import re
from datetime import datetime
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal


class SalesTableModel(QAbstractTableModel):
    """Модель данных для таблицы продаж"""
    
    data_changed = Signal()
    
    HEADERS = [
        "ID", "Год", "Сумма+", "Сумма-", "ТРАТЫ", "Бонусы+", "Бонусы-",
        "Почта+", "Почта-", "Итог", "Продажа", "Примечание"
    ]
    
    COLUMN_KEYS = [
        'id', 'date', 'income', 'expense', 'costs', 'bonus_plus', 'bonus_minus',
        'post_plus', 'post_minus', 'total', 'sale', 'notes'
    ]
    
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self._data = []
        self.db_manager = db_manager
    
    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()
    
    def get_sale(self, row):
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return super().headerData(section, orientation, role)
    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        
        # Колонку ID нельзя редактировать
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._data):
            return None
        
        sale = self._data[row]
        
        if role == Qt.DisplayRole:
            return self._get_display_value(sale, col)
        
        elif role == Qt.TextAlignmentRole:
            if col == 0:  # ID
                return Qt.AlignCenter
            elif col == 1:  # Год
                return Qt.AlignCenter
            elif col in [2, 3, 4, 5, 6, 7, 8, 9, 10]:  # Числовые колонки
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        elif role == Qt.UserRole:
            value = self._get_display_value(sale, col)
            if value:
                try:
                    # Пробуем преобразовать в число для сортировки
                    cleaned = re.sub(r'[^\d.-]', '', str(value))
                    if cleaned:
                        return float(cleaned)
                except:
                    pass
            return value
        
        elif role == Qt.ForegroundRole:
            # Подсветка итога (колонка 9)
            if col == 9:
                total = (sale.income or 0) - (sale.expense or 0) - (sale.costs or 0) + \
                        (sale.bonus_plus or 0) - (sale.bonus_minus or 0) + \
                        (sale.post_plus or 0) - (sale.post_minus or 0)
                if total < 0:
                    from PySide6.QtGui import QColor
                    return QColor("#dc3545")  # Красный для отрицательного итога
                elif total > 0:
                    from PySide6.QtGui import QColor
                    return QColor("#28a745")  # Зелёный для положительного итога
            return None
        
        return None
    
    def _get_display_value(self, sale, col):
        """Возвращает отображаемое значение для ячейки"""
        try:
            if col == 0:  # ID
                return str(sale.id) if sale.id else ""
            elif col == 1:  # Год
                return str(sale.date) if sale.date else ""
            elif col == 2:  # Сумма+ (доход)
                val = sale.income if hasattr(sale, 'income') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 3:  # Сумма- (расход)
                val = sale.expense if hasattr(sale, 'expense') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 4:  # ТРАТЫ
                val = sale.costs if hasattr(sale, 'costs') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 5:  # Бонусы+
                val = sale.bonus_plus if hasattr(sale, 'bonus_plus') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 6:  # Бонусы-
                val = sale.bonus_minus if hasattr(sale, 'bonus_minus') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 7:  # Почта+
                val = sale.post_plus if hasattr(sale, 'post_plus') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 8:  # Почта-
                val = sale.post_minus if hasattr(sale, 'post_minus') else 0
                return f"{val:,.2f}" if val and isinstance(val, (int, float)) else ""
            elif col == 9:  # Итог (вычисляемое поле)
                income = sale.income if hasattr(sale, 'income') and isinstance(sale.income, (int, float)) else 0
                expense = sale.expense if hasattr(sale, 'expense') and isinstance(sale.expense, (int, float)) else 0
                costs = sale.costs if hasattr(sale, 'costs') and isinstance(sale.costs, (int, float)) else 0
                bonus_plus = sale.bonus_plus if hasattr(sale, 'bonus_plus') and isinstance(sale.bonus_plus, (int, float)) else 0
                bonus_minus = sale.bonus_minus if hasattr(sale, 'bonus_minus') and isinstance(sale.bonus_minus, (int, float)) else 0
                post_plus = sale.post_plus if hasattr(sale, 'post_plus') and isinstance(sale.post_plus, (int, float)) else 0
                post_minus = sale.post_minus if hasattr(sale, 'post_minus') and isinstance(sale.post_minus, (int, float)) else 0
                
                total = income - expense - costs + bonus_plus - bonus_minus + post_plus - post_minus
                return f"{total:,.2f}" if total != 0 else ""
            elif col == 10:  # Продажа (текст!)
                return sale.sale or "" if hasattr(sale, 'sale') else ""
            elif col == 11:  # Примечание
                return sale.notes or "" if hasattr(sale, 'notes') else ""
        except Exception as e:
            print(f"Ошибка в _get_display_value: {e}")
            return ""
        return ""

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._data):
            return False
        
        # ID нельзя редактировать
        if col == 0:
            return False
        
        sale = self._data[row]
        
        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        self.data_changed.emit()
        return True