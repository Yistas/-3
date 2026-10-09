# -*- coding: utf-8 -*-

"""
Прокси-модель для сортировки сделок
"""

import logging
from PySide6.QtCore import Qt, QSortFilterProxyModel


class DealsSortProxyModel(QSortFilterProxyModel):
    """Прокси-модель для сортировки сделок с защитой от OverflowError"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.DealsProxy')

    def lessThan(self, left, right):
        try:
            left_data = left.data(Qt.UserRole)
            right_data = right.data(Qt.UserRole)

            if left_data == right_data:
                return False

            try:
                left_num = float(left_data) if left_data is not None else -999999999
                right_num = float(right_data) if right_data is not None else -999999999

                if abs(left_num) > 1e15 or abs(right_num) > 1e15:
                    return str(left_data).lower() < str(right_data).lower()

                return left_num < right_num
            except (OverflowError, ValueError, TypeError):
                left_str = str(left_data).lower() if left_data is not None else ""
                right_str = str(right_data).lower() if right_data is not None else ""
                return left_str < right_str

        except (OverflowError, ValueError, TypeError, AttributeError) as e:
            self.logger.debug(f"Ошибка сортировки: {e}")
            try:
                return str(left.data(Qt.DisplayRole)).lower() < str(right.data(Qt.DisplayRole)).lower()
            except:
                return False