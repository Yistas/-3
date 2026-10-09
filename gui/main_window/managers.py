# -*- coding: utf-8 -*-

"""
Инициализация менеджеров MainWindow
"""

from pathlib import Path

from gui.theme_manager import ThemeManager
from gui.panels.tree_panel import TreePanelManager
from gui.panels.table_panel import TablePanelManager
from utils.backup_manager import BackupManager
from utils.backup_settings import BackupSettings
from utils.settings_manager import SettingsManager
from utils.refresh_manager import RefreshManager
from database.db_manager import DatabaseManager


class ManagersMixin:
    """Примесь с инициализацией менеджеров"""
    
    def _init_managers(self):
        """Инициализация всех менеджеров"""
        # Тема
        self.theme_manager = ThemeManager()
        
        # Бекапы
        self.backup_settings = BackupSettings()
        self.backup_manager = BackupManager(self.backup_settings)
        self.backup_manager.create_auto_backup()
        
        # Настройки
        self.settings_manager = SettingsManager()
        
        # База данных (из папки data/)
        data_db = Path("data/coins.db")
        if data_db.exists():
            db_path = str(data_db)
        elif Path("coins.db").exists():
            db_path = "coins.db"
        else:
            Path("data").mkdir(exist_ok=True)
            db_path = "data/coins.db"
        
        self.db_manager = DatabaseManager(db_path)
        
        # Панели
        self.tree_panel = TreePanelManager(self)
        self.table_panel = TablePanelManager(self)
        
        # Подключаем RefreshManager
        self.refresh_manager = RefreshManager()
        self.refresh_manager.references_changed.connect(self.on_references_changed)
        self.refresh_manager.fields_changed.connect(self.on_fields_changed)
        self.refresh_manager.data_changed.connect(self.on_data_changed)