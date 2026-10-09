# -*- coding: utf-8 -*-

"""
Управление путями для портативной версии Coin Collector
"""

import os
import sys
from pathlib import Path


class Paths:
    """Класс для управления путями в портативной версии"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # ===== ОПРЕДЕЛЯЕМ КОРНЕВУЮ ПАПКУ =====
        if getattr(sys, 'frozen', False):
            # ЗАПУСК ИЗ .EXE (PyInstaller)
            # sys.executable указывает на CoinCollector.exe
            # Корневая папка = папка с .exe
            self._root_dir = Path(sys.executable).parent.resolve()
        else:
            # ЗАПУСК ИЗ PYTHON (разработка или из system_data/)
            # Проверяем, запущен ли main.py из system_data/
            # Если текущая рабочая директория содержит system_data, поднимаемся на уровень выше
            cwd = Path.cwd()
            if cwd.name == "system_data":
                # Запуск из system_data/ (портативная версия, но без .exe)
                self._root_dir = cwd.parent.resolve()
            else:
                # Запуск из корня проекта (разработка)
                # paths.py находится в PROJECT_ROOT/utils/paths.py
                # Поднимаемся на 2 уровня вверх: utils/ -> проект/
                self._root_dir = Path(__file__).parent.parent.resolve()
        
        # ===== ОСНОВНЫЕ ПУТИ =====
        # В портативной версии: root/system_data/
        # В разработке: root/system_data/ (для единообразия)
        self._system_data_dir = self._root_dir / "system_data"
        
        # Папка data внутри system_data/
        self._data_dir = self._system_data_dir / "data"
        
        # ===== ВТОРОСТЕПЕННЫЕ ПУТИ =====
        self._logs_dir = self._data_dir / "logs"
        self._backups_dir = self._data_dir / "backups"
        self._temp_dir = self._data_dir / "temp"
        self._coin_images_dir = self._data_dir / "coin_images"
        self._custom_images_dir = self._data_dir / "custom_images"
        self._custom_icons_dir = self._data_dir / "custom_icons"
        self._continent_maps_dir = self._data_dir / "continent_maps"
        self._yearly_tables_dir = self._data_dir / "yearly_tables"
        self._browser_data_dir = self._data_dir / "browser_data"
        
        # Временные подпапки
        self._price_dir = self._temp_dir / "price"
        self._obmen_dir = self._temp_dir / "obmen"
        
        # Создаём все папки
        self.ensure_directories()
    
    def ensure_directories(self):
        """Создаёт все необходимые директории (используя абсолютные пути)"""
        dirs = [
            self._system_data_dir,
            self._data_dir,
            self._logs_dir,
            self._backups_dir,
            self._temp_dir,
            self._coin_images_dir,
            self._custom_images_dir,
            self._custom_icons_dir,
            self._continent_maps_dir,
            self._yearly_tables_dir,
            self._browser_data_dir,
            self._price_dir,
            self._obmen_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    # ===== ГЕТТЕРЫ =====
    
    def get_root_dir(self) -> Path:
        """Возвращает корневую папку программы (с .exe или корень проекта)"""
        return self._root_dir
    
    def get_system_data_dir(self) -> Path:
        """Возвращает папку system_data/ (основная папка с данными)"""
        return self._system_data_dir
    
    def get_data_dir(self) -> Path:
        """Возвращает папку system_data/data/"""
        return self._data_dir
    
    def get_logs_dir(self) -> Path:
        """Возвращает папку для логов"""
        return self._logs_dir
    
    def get_backups_dir(self) -> Path:
        """Возвращает папку для бекапов"""
        return self._backups_dir
    
    def get_temp_dir(self) -> Path:
        """Возвращает папку для временных файлов"""
        return self._temp_dir
    
    def get_price_dir(self) -> Path:
        """Возвращает папку для файлов с ценами"""
        return self._price_dir
    
    def get_obmen_dir(self) -> Path:
        """Возвращает папку для файлов обмена"""
        return self._obmen_dir
    
    def get_coin_images_dir(self) -> Path:
        """Возвращает папку для изображений монет"""
        return self._coin_images_dir
    
    def get_custom_images_dir(self) -> Path:
        """Возвращает папку для пользовательских изображений (флаги, гербы)"""
        return self._custom_images_dir
    
    def get_custom_icons_dir(self) -> Path:
        """Возвращает папку для пользовательских иконок"""
        return self._custom_icons_dir
    
    def get_continent_maps_dir(self) -> Path:
        """Возвращает папку для карт континентов"""
        return self._continent_maps_dir
    
    def get_yearly_tables_dir(self) -> Path:
        """Возвращает папку для таблиц погодовки"""
        return self._yearly_tables_dir
    
    def get_browser_data_dir(self) -> Path:
        """Возвращает папку для данных браузера"""
        return self._browser_data_dir
    
    def get_project_root(self) -> Path:
        """Возвращает корневую папку проекта (алиас)"""
        return self._root_dir
    
    def get_launcher_dir(self) -> Path:
        """Возвращает папку, где находится лаунчер (CoinCollector.exe)"""
        return self._root_dir
    
    def normalize_path(self, path) -> Path:
        """Нормализует путь (убирает дублирование)"""
        if isinstance(path, str):
            path = Path(path)
        return path.resolve()


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_paths = None


def get_paths() -> Paths:
    """Возвращает глобальный экземпляр Paths"""
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths


# ===== ЭКСПОРТ ДЛЯ ИСПОЛЬЗОВАНИЯ =====
paths_instance = get_paths()
paths = paths_instance