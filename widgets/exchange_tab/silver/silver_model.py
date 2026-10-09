# -*- coding: utf-8 -*-

"""
Модель данных для таблицы монет серебра
"""

import logging
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor

STATUS_COLORS = {
    "in_sale": QColor(70, 52, 10),        # янтарный — В продаже
    "sold": QColor(22, 68, 28),           # зелёный — Продана
    "in_collection": QColor(24, 46, 82),  # синий — В коллекции
}

STATUS_NAMES = {
    "in_sale": "В продаже",
    "sold": "Продана",
    "in_collection": "В коллекции",
}

STATUS_COMBO_COLORS = {
    "В продаже": "#ffd700",
    "Продана": "#90ee90",
    "В коллекции": "#87ceeb",
}


class SilverTableModel(QAbstractTableModel):
    """Модель данных для таблицы монет серебра"""

    HEADERS = [
        "Статус", "Страна", "Номинал", "Год", "Примечания",
        "№", "Цена в коллекцию", "Цена продажи",
        "Авито", "LAVE", "Мешок", "UCOIN",
        "MIN", "План"
    ]

    COLUMN_KEYS = [
        'status', 'country', 'denomination', 'year', 'notes',
        'number', 'collection_price', 'sale_price',
        'avito', 'lave', 'meshok', 'ucoin',
        'min_price', 'plan_price'
    ]

    data_changed = Signal()  # Сигнал при изменении данных

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []  # Список словарей с данными монет
        self._purchase_id = None
        self.logger = logging.getLogger('CoinCollector.SilverModel')

    def set_purchase_id(self, purchase_id):
        """Устанавливает ID закупки для сохранения"""
        self._purchase_id = purchase_id

    def set_data(self, data):
        """Устанавливает данные и оповещает об изменении"""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_coin(self, row):
        """Возвращает монету по строке"""
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
        # Колонка № не редактируется
        if index.column() == 5:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._data):
            return None
        coin = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""
        if key == 'status':
            if role == Qt.DisplayRole:
                return STATUS_NAMES.get(coin.get('status', 'in_sale'), "В продаже")
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.ForegroundRole:
                status = coin.get('status', 'in_sale')
                color = STATUS_COLORS.get(status, QColor(255, 255, 255, 0))
                return color
            return None
        # === ЧЕКБОКСЫ ПЛОЩАДОК: ТОЛЬКО эмодзи ✅/❌ ===
        # CheckStateRole не возвращаем: из-за него view рисовал второй
        # (системный) чекбокс рядом с эмодзи — двойной индикатор.
        if key in ['avito', 'lave', 'meshok', 'ucoin']:
            if role == Qt.DisplayRole:
                return "✅" if coin.get(key, False) else "❌"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.EditRole:
                return coin.get(key, False)
            return None
        if role == Qt.DisplayRole:
            value = coin.get(key)
            if value is None or value == "":
                return ""
            if key in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                try:
                    val = float(value)
                    return f"{val:.2f}" if val > 0 else ""
                except (ValueError, TypeError):
                    return str(value)
            return str(value)
        elif role == Qt.TextAlignmentRole:
            # Цены (Цена К, Цена П, MIN, План) — ВЫРАВНИВАНИЕ СПРАВА
            if col in [6, 7, 12, 13]:
                return Qt.AlignRight | Qt.AlignVCenter
            # Страна (1), Номинал (2), Примечания (4) — ВЫРАВНИВАНИЕ СЛЕВА
            if col in [1, 2, 4]:
                return Qt.AlignLeft | Qt.AlignVCenter
            # Остальное (Статус, Год, №, площадки) — по центру
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            status = coin.get('status', 'in_sale')
            return STATUS_COLORS.get(status, QColor(255, 255, 255, 0))
        elif role == Qt.ForegroundRole:
            if key == 'status':
                status = coin.get('status', 'in_sale')
                status_name = STATUS_NAMES.get(status, "В продаже")
                color_hex = STATUS_COMBO_COLORS.get(status_name, "#ffffff")
                return QColor(color_hex)
            return None
        elif role == Qt.UserRole:
            value = coin.get(key)
            if key in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                try:
                    return float(value) if value else 0
                except (ValueError, TypeError):
                    return 0
            return value
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self._data):
            return False

        coin = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""

        if key == 'status':
            # Статус приходит как строка "В продаже" -> преобразуем
            status_map = {v: k for k, v in STATUS_NAMES.items()}
            new_status = status_map.get(value, 'in_sale')
            if coin.get('status') != new_status:
                coin['status'] = new_status
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.BackgroundRole])
                self.data_changed.emit()
                return True
            return False

        if key in ['avito', 'lave', 'meshok', 'ucoin']:
            # Чекбоксы
            if isinstance(value, bool):
                coin[key] = value
            else:
                coin[key] = value in [True, "True", "true", "1", "✅", "Да"]
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            self.data_changed.emit()
            return True

        if key in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
            try:
                if isinstance(value, str):
                    # Убираем пробелы и заменяем запятую на точку
                    clean_value = value.replace(' ', '').replace(',', '.')
                    value = float(clean_value) if clean_value else 0
                else:
                    value = float(value) if value else 0
                coin[key] = value
                self.dataChanged.emit(index, index, [Qt.DisplayRole])
                self.data_changed.emit()
                return True
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Ошибка преобразования {key}={value}: {e}")
                return False

        # Текстовые поля
        if value is not None and str(value).strip():
            coin[key] = str(value).strip()
        else:
            coin[key] = None
        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        self.data_changed.emit()
        return True

    def get_purchase_id(self):
        """Возвращает ID закупки"""
        return self._purchase_id
