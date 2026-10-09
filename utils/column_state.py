# -*- coding: utf-8 -*-
"""
Универсальное сохранение/восстановление ширины и порядка колонок
для любой таблицы (QTableView / QTableWidget) через QSettings.
"""
from PySide6.QtCore import QSettings, QTimer


class ColumnStateHelper:
    """Автосохранение ширины/порядка колонок таблицы"""

    @staticmethod
    def attach(table, settings_key):
        """Привязывает восстановление + автосохранение колонок к таблице"""
        ColumnStateHelper.restore(table, settings_key)
        header = table.horizontalHeader()
        timer = QTimer(table)
        timer.setSingleShot(True)
        timer.setInterval(500)
        timer.timeout.connect(lambda t=table, k=settings_key: ColumnStateHelper.save(t, k))
        table.setProperty('_col_state_timer', timer)
        header.sectionResized.connect(lambda *a: timer.start())
        header.sectionMoved.connect(lambda *a: timer.start())

    @staticmethod
    def save(table, settings_key):
        """Пишет ширины и порядок колонок в QSettings"""
        try:
            settings = QSettings('CoinCollector', 'ColumnStates')
            header = table.horizontalHeader()
            widths = [table.columnWidth(li) for li in range(table.columnCount())]
            order = [header.visualIndex(li) for li in range(table.columnCount())]
            settings.setValue(settings_key + '_widths', widths)
            settings.setValue(settings_key + '_order', order)
        except Exception:
            pass

    @staticmethod
    def restore(table, settings_key):
        """Восстанавливает ширины и порядок колонок (с конвертацией строк в int)"""
        try:
            settings = QSettings('CoinCollector', 'ColumnStates')
            widths = settings.value(settings_key + '_widths', []) or []
            order = settings.value(settings_key + '_order', []) or []
            try:
                widths = [int(w) for w in widths]
            except (TypeError, ValueError):
                widths = []
            for li, w in enumerate(widths):
                if li < table.columnCount() and w and w > 0:
                    table.setColumnWidth(li, w)
            try:
                order = [int(o) for o in order]
            except (TypeError, ValueError):
                order = []
            header = table.horizontalHeader()
            if len(order) == table.columnCount():
                for vi, li in enumerate(order):
                    if 0 <= li < table.columnCount():
                        cur_vi = header.visualIndex(li)
                        if cur_vi != vi:
                            header.moveSection(cur_vi, vi)
        except Exception:
            pass