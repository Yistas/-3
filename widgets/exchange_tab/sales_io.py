# -*- coding: utf-8 -*-

"""
Импорт/экспорт продаж (заглушка)
"""

from PySide6.QtCore import QThread, Signal


class ImportSalesThread(QThread):
    """Поток для импорта продаж"""
    progress = Signal(int, int, str)
    finished = Signal(int, int, int)
    error = Signal(str)
    
    def __init__(self, db_manager, file_path):
        super().__init__()
        self.db_manager = db_manager
        self.file_path = file_path
        self._is_running = True
    
    def run(self):
        # Заглушка
        self.finished.emit(0, 0, 0)
    
    def stop(self):
        self._is_running = False