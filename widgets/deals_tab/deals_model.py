# -*- coding: utf-8 -*-

"""
Модель данных для таблицы сделок
"""

import re
import logging
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyle


class DealsTableModel(QAbstractTableModel):
    """Модель данных для таблицы сделок"""

    data_changed = Signal()

    HEADERS = [
        "ID", "НИК", "Сумма", "Закрыто", "АРХИВ",
        "Резерв", "Собр", "СКАН", "Отосл", "Согл", "Оплата",
        "Пров", "Упак", "Почта", "ДОШЛО", "№ПОК", "Тип", "Где"
    ]

    COLUMN_KEYS = [
        'id', 'buyer', 'amount', 'delivery', 'total',
        'reserve', 'collect', 'scan', 'send', 'approve', 'payment',
        'check', 'pack', 'post', 'arrived', 'number', 'type', 'where'
    ]

    CHECKBOX_COLUMNS = {
        5: 'reserve', 6: 'collect', 7: 'scan', 8: 'send',
        9: 'approve', 10: 'payment', 11: 'check', 12: 'pack',
        13: 'post', 14: 'arrived'
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._parent_tab = None
        self.logger = logging.getLogger('CoinCollector.GUI.DealsModel')

    def set_parent_tab(self, tab):
        self._parent_tab = tab

    def set_data(self, data):
        self.logger.debug(f"set_data: {len(data)} записей")
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_deal(self, row):
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
        deal = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""

        if role == Qt.DisplayRole:
            if key == 'id':
                return str(deal.id) if deal.id else ""
            if key in self.CHECKBOX_COLUMNS.values():
                value = getattr(deal, key, None)
                return "✅" if value in [True, "True", "true", "1", "✅"] else "❌"
            value = getattr(deal, key, None)
            if key in ['amount', 'total', 'number'] and value is not None:
                try:
                    if isinstance(value, (int, float)):
                        return f"{value:.2f}" if key in ['amount', 'total'] else str(value)
                    return str(value)
                except:
                    return str(value)
            return str(value) if value is not None else ""

        elif role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            if col == 3:
                return Qt.AlignCenter
            if col in [2, 15]:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.UserRole:
            if key == 'id':
                return deal.id if deal.id else -1
            value = getattr(deal, key, None)
            if value is None:
                return ""
            if key in ['amount', 'total']:
                try:
                    return float(str(value).replace(',', '.'))
                except:
                    return str(value)
            return str(value)

        elif role == Qt.ForegroundRole:
            if key == 'delivery' and getattr(deal, 'delivery', None) == '✅':
                return QColor("#28a745")
            if key == 'total' and getattr(deal, 'total', None) == "📦":
                return QColor("#dc3545")
            return None

        return None

    def setData(self, index, value, role=Qt.EditRole):
        """Устанавливает данные в ячейку"""
        if not index.isValid() or role != Qt.EditRole:
            return False

        if index.column() == 0:
            return False

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self._data):
            return False

        deal = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""

        if key and key != 'id':
            self.logger.debug(f"setData: row={row}, col={col}, key={key}, value={value}")

            # Преобразуем значение для чекбоксов
            if key in self.CHECKBOX_COLUMNS.values():
                if isinstance(value, bool):
                    new_value = "✅" if value else "❌"
                elif isinstance(value, str):
                    new_value = "✅" if value in ["✅", "True", "true", "1"] else "❌"
                else:
                    new_value = "✅" if value else "❌"
            else:
                new_value = str(value) if value and str(value).strip() else None

            # Обновляем объект
            setattr(deal, key, new_value)

            # Оповещаем родительскую вкладку о сохранении
            if self._parent_tab:
                self._parent_tab._on_deal_edited(deal, key, new_value)

            # Оповещаем об изменении данных в модели
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ForegroundRole])
            self.data_changed.emit()

            return True

        return False