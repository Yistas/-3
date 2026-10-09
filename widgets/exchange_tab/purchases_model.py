# ===== gui/widgets/exchange_tab/purchases_model.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Модель данных для таблицы закупок (PurchasesTableModel)
"""

import re
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal


class PurchasesTableModel(QAbstractTableModel):
    """Модель данных для таблицы закупок"""
    
    data_changed = Signal()  # <-- СИГНАЛ ДЛЯ ОБНОВЛЕНИЯ СУММ В СДЕЛКАХ
    
    HEADERS = [
        "КОЛ", "ЦК", "№Зак", "№Пок", "Страна", "Континент", "Номинал", "Валюта",
        "ГОД", "МЕСТО", "КОЛ", "КОМЕНТЫ", "Обмен", "Продано", "Сумма"
    ]
    
    COLUMN_KEYS = [
        'in_collection', 'collection_price', 'purchase_number', 'purchase_batch',
        'country', 'continent', 'denomination', 'currency', 'year',
        'location_found', 'quantity', 'comments', 'ucoin_exchange',
        'sold_count', 'sold_sum'
    ]
    
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self._data = []
        self.db_manager = db_manager
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
    
    def set_data(self, data):
        """Устанавливает данные и оповещает об изменении"""
        self.beginResetModel()
        self._data = data
        self.endResetModel()
    
    def get_purchase(self, row):
        """Возвращает объект Purchase для строки"""
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
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        try:
            row = index.row()
            col = index.column()
            
            if row < 0 or row >= len(self._data):
                return None
            
            purchase = self._data[row]
            
            if role == Qt.DisplayRole:
                return self._get_display_value(purchase, col)
            
            elif role == Qt.TextAlignmentRole:
                if col in [0, 2, 3, 5, 8, 10, 12, 13]:
                    return Qt.AlignCenter
                elif col in [1, 14]:
                    return Qt.AlignRight | Qt.AlignVCenter
                return Qt.AlignLeft | Qt.AlignVCenter
            
            elif role == Qt.ForegroundRole:
                from PySide6.QtGui import QColor
                
                if col == 0 and purchase.in_collection:
                    return QColor("#28a745")
                if col == 12 and purchase.ucoin_exchange:
                    return QColor("#4a6fa5")
                if col == 13 and purchase.sold_count:
                    try:
                        if float(str(purchase.sold_count).replace(',', '.')) > 0:
                            return QColor("#28a745")
                    except:
                        pass
                if col == 14 and purchase.sold_sum and purchase.sold_sum > 0:
                    return QColor("#28a745")
                return None
            
            elif role == Qt.UserRole:
                return purchase.id
            
        except Exception:
            pass
        
        return None

# ===== gui/widgets/exchange_tab/purchases_model.py =====
# ЗАМЕНИТЬ МЕТОД setData

    def setData(self, index, value, role=Qt.EditRole):
        """Устанавливает данные в ячейку"""
        if not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._data):
            return False
        
        purchase = self._data[row]
        field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
        
        if field_name and field_name != 'row_number':
            # Сохраняем старое значение
            old_value = getattr(purchase, field_name, None)
            
            # Устанавливаем новое значение
            setattr(purchase, field_name, value)
            
            # Оповещаем об изменении
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ForegroundRole])
            self.data_changed.emit()  # Сигнал для пересчёта сумм в сделках
            
            # Для немедленного сохранения можно вызывать метод из ExchangeTab
            if hasattr(self.parent(), '_on_cell_edited') and hasattr(self.parent(), '_save_timer'):
                self.parent()._on_cell_edited(purchase, field_name, value)
            
            return True
        
        return False

# ===== gui/widgets/exchange_tab/purchases_model.py =====
# НАЙТИ МЕТОД _get_display_value И ИСПРАВИТЬ КОЛОНКУ 14 (sold_sum)

    def _get_display_value(self, purchase, col):
        """Возвращает отображаемое значение для колонки"""
        try:
            if col == 0:
                return "✅" if purchase.in_collection else ""
            elif col == 1:
                return f"{purchase.collection_price:.0f}" if purchase.collection_price else ""
            elif col == 2:
                return str(purchase.purchase_number or "")
            elif col == 3:
                return purchase.purchase_batch or ""
            elif col == 4:
                return purchase.import_country.name if purchase.import_country else "—"
            elif col == 5:
                return purchase.continent or ""
            elif col == 6:
                return purchase.denomination_value or ""
            elif col == 7:
                return purchase.currency or ""
            elif col == 8:
                return str(purchase.year) if purchase.year else ""
            elif col == 9:
                return purchase.location_found or ""
            elif col == 10:
                return str(purchase.quantity) if purchase.quantity else ""
            elif col == 11:
                return purchase.comments or ""
            elif col == 12:
                if purchase.ucoin_exchange:
                    return str(purchase.ucoin_exchange_count) if purchase.ucoin_exchange_count else "✅"
                elif purchase.ucoin_exchange_count == 0:
                    return "0"
                return ""
            elif col == 13:
                return str(purchase.sold_count) if purchase.sold_count else ""
            elif col == 14:
                # === ИСПРАВЛЕНО: колонка СУММА (sold_sum) ===
                # Для архивных записей НЕ показываем значок в этой колонке
                # Значок "📦" должен быть только в колонке ИТОГ (total)
                if hasattr(purchase, '_is_archived') and purchase._is_archived:
                    # Всё равно показываем сумму, если она есть
                    if purchase.sold_sum:
                        return f"{purchase.sold_sum:.2f}"
                    return ""
                # Показываем реальную сумму продажи
                return f"{purchase.sold_sum:.2f}" if purchase.sold_sum else ""
        except Exception:
            pass
        return ""

    def sort(self, column, order=Qt.AscendingOrder):
        """Сортировка данных в模型中"""
        self._sort_column = column
        self._sort_order = order
        
        self.layoutAboutToBeChanged.emit()
        
        def sort_key(purchase):
            value = self._get_display_value(purchase, column)
            return self._natural_sort_key(value)
        
        self._data.sort(key=sort_key, reverse=(order == Qt.DescendingOrder))
        
        self.layoutChanged.emit()
    
    def _natural_sort_key(self, value):
        """Естественная сортировка: 1, 2, 10, 100"""
        if value is None:
            return (1, 0, "", "")
        s = str(value).strip()
        if not s:
            return (1, 0, "", "")
        
        parts = re.split(r'(\d+)', s)
        
        result = []
        for part in parts:
            if part == '':
                continue
            if part.isdigit():
                result.append((0, int(part), '', ''))
            else:
                result.append((1, 0, part.lower(), part))
        
        if not result:
            return (1, 0, s.lower(), s)
        
        return result[0] if result else (1, 0, s.lower(), s)