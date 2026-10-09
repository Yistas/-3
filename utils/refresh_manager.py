# -*- coding: utf-8 -*-

"""
Менеджер для централизованного обновления интерфейса после изменений в справочниках
"""

import logging
from PySide6.QtCore import QObject, Signal


class RefreshManager(QObject):
    """Централизованный менеджер обновлений"""
    
    # Сигналы для разных типов обновлений
    references_changed = Signal(str)  # параметр: имя справочника
    fields_changed = Signal()         # изменились поля
    data_changed = Signal()           # общие данные
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self.logger = logging.getLogger('CoinCollector.RefreshManager')
        self._initialized = True
    
    def notify_reference_changed(self, ref_name):
        """Уведомить об изменении справочника"""
        self.logger.info(f"Справочник изменён: {ref_name}")
        self.references_changed.emit(ref_name)
        self.data_changed.emit()
    
    def notify_fields_changed(self):
        """Уведомить об изменении полей"""
        self.logger.info("Настройки полей изменены")
        self.fields_changed.emit()
        self.data_changed.emit()
    
    def refresh_all(self):
        """Принудительное обновление всего"""
        self.logger.info("Принудительное обновление всего интерфейса")
        self.data_changed.emit()