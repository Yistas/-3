# -*- coding: utf-8 -*-

"""
Настройки резервного копирования для Coin Collector
С использованием ConfigDB
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from database.config_db import get_config_db
from utils.paths import paths


class BackupSettings:
    """Класс для управления настройками резервного копирования"""
    
    # Стандартные настройки по умолчанию
    DEFAULT_SETTINGS = {
        'auto_backup_enabled': True,
        'auto_backup_interval_days': 1,
        'max_auto_backups': 5,
        'max_normal_backups': 3,
        'max_full_backups': 2,
        'backup_dir': 'backups',
        'normal_backup_folders': [
            "database",
            "gui",
            "utils",
            "custom_icons"
        ],
        'full_backup_folders': [
            "database",
            "gui",
            "utils",
            "custom_icons",
            "logs",
            "venv"
        ],
        'config_files': [
            "settings.json",
            "coins.db",
            "requirements.txt",
            "main.py",
            "create_project_structure.py",
            "check_installation.py",
            "test_imports.py",
            "view_logs.py",
            "run.bat",
            "install.bat"
        ],
        'exclude_patterns': [
            "*.pyc",
            "__pycache__",
            "*.tmp",
            "*.log",
            ".git",
            ".idea",
            ".vscode",
            "backups"
        ],
        'notify_on_backup': True,
        'notify_on_restore': True,
        'last_auto_backup': None,
        'last_backup_check': None
    }
    
    def __init__(self):
        self.logger = logging.getLogger('CoinCollector.BackupSettings')
        self.data_dir = paths.get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load_settings()
    
    def load_settings(self) -> bool:
        """Загружает настройки из ConfigDB"""
        try:
            config_db = get_config_db()
            loaded = config_db.get('backup_settings')
            
            if loaded:
                for key, value in loaded.items():
                    if key in self.settings:
                        self.settings[key] = value
                self.logger.info(f"Настройки бекапа загружены из ConfigDB")
                return True
            else:
                self.logger.info("Настройки бекапа не найдены, используются настройки по умолчанию")
                self.save_settings()
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке настроек бекапа: {e}")
            return False
    
    def save_settings(self) -> bool:
        """Сохраняет настройки в ConfigDB"""
        try:
            config_db = get_config_db()
            config_db.set('backup_settings', self.settings, 'backup')
            self.logger.info(f"Настройки бекапа сохранены в ConfigDB")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении настроек бекапа: {e}")
            return False
    
    def get(self, key: str, default=None):
        """Возвращает значение настройки по ключу"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value):
        """Устанавливает значение настройки"""
        self.settings[key] = value
        self.save_settings()
    
    def update(self, settings_dict: Dict):
        """Обновляет несколько настроек"""
        self.settings.update(settings_dict)
        self.save_settings()
    
    def reset_to_defaults(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()
        self.logger.info("Настройки бекапа сброшены к значениям по умолчанию")
    
    def should_create_auto_backup(self) -> bool:
        """Проверяет, нужно ли создавать автоматический бекап"""
        if not self.get('auto_backup_enabled'):
            return False
        
        last_backup = self.get('last_auto_backup')
        if not last_backup:
            return True
        
        try:
            last_time = datetime.fromisoformat(last_backup)
            interval_days = self.get('auto_backup_interval_days', 1)
            next_time = last_time + timedelta(days=interval_days)
            return datetime.now() >= next_time
        except:
            return True
    
    def update_last_auto_backup(self):
        """Обновляет время последнего автоматического бекапа"""
        self.set('last_auto_backup', datetime.now().isoformat())
    
    def get_backup_dir(self) -> Path:
        """Возвращает путь к папке с бекапами"""
        return paths.get_backups_dir()
    
    def get_normal_folders(self) -> List[str]:
        """Возвращает список папок для обычного бекапа"""
        return self.get('normal_backup_folders', [])
    
    def get_full_folders(self) -> List[str]:
        """Возвращает список папок для полного бекапа"""
        return self.get('full_backup_folders', [])
    
    def get_config_files(self) -> List[str]:
        """Возвращает список конфигурационных файлов"""
        return self.get('config_files', [])
    
    def get_exclude_patterns(self) -> List[str]:
        """Возвращает список паттернов для исключения"""
        return self.get('exclude_patterns', [])
    
    def get_max_backups(self, backup_type: str) -> int:
        """Возвращает максимальное количество бекапов для указанного типа"""
        key = f'max_{backup_type}_backups'
        return self.get(key, 5)
    
    def should_notify(self, action: str) -> bool:
        """Проверяет, нужно ли показывать уведомление"""
        key = f'notify_on_{action}'
        return self.get(key, True)