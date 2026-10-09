# -*- coding: utf-8 -*-

"""
Менеджер настроек приложения с использованием ConfigDB
Все настройки хранятся в config.db, а не в JSON файлах
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt

from database.config_db import get_config_db
from utils.paths import paths


class SettingsManager:
    """Менеджер настроек приложения"""
    
    def __init__(self):
        self.logger = logging.getLogger('CoinCollector.SettingsManager')
        self.config_db = get_config_db()
        
        # Загружаем настройки
        self.settings = self._load_all_settings()
        
        self.logger.info("SettingsManager инициализирован с ConfigDB")
    
    def _load_all_settings(self) -> Dict[str, Any]:
        """Загружает все настройки из ConfigDB"""
        settings = {}
        
        # Загружаем все категории
        categories = ['window', 'backup', 'gdrive', 'yearly', 'filters', 
                      'columns', 'statistics', 'tree', 'icons', 'table']
        
        for category in categories:
            cat_settings = self.config_db.get_category(category)
            settings.update(cat_settings)
        
        return settings
    
    # ========== ОБЩИЕ МЕТОДЫ ==========
    
    def get(self, key: str, default=None) -> Any:
        """Возвращает значение настройки"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any, category: str = None) -> bool:
        """Устанавливает значение настройки"""
        try:
            self.config_db.set(key, value, category)
            self.settings[key] = value
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настройки {key}: {e}")
            return False
    
    def save_settings(self):
        """Сохраняет все настройки (заглушка, т.к. ConfigDB сохраняет сразу)"""
        pass
    
    def load_settings(self):
        """Загружает все настройки (заглушка, т.к. ConfigDB загружает сразу)"""
        self.settings = self._load_all_settings()
    
    # ========== НАСТРОЙКИ ОКНА ==========
    
    def get_window_settings(self) -> Dict[str, Any]:
        """Возвращает настройки окна"""
        return self.config_db.get('window_settings', {})
    
    def set_window_settings(self, settings: Dict[str, Any]) -> bool:
        """Сохраняет настройки окна"""
        return self.config_db.set('window_settings', settings, 'window')
    
    # ========== ТЕМЫ ==========
    
    def get_theme(self) -> str:
        """Возвращает сохранённую тему"""
        return self.get('saved_theme', 'Светлая')
    
    def set_theme(self, theme_name: str) -> bool:
        """Сохраняет тему"""
        return self.set('saved_theme', theme_name, 'window')
    
    # ========== НАСТРОЙКИ ТАБЛИЦЫ ==========
    
    def get_table_columns(self) -> list:
        """Возвращает настройки колонок таблицы"""
        return self.get('table_columns', [])
    
    def set_table_columns(self, columns: list) -> bool:
        """Сохраняет настройки колонок таблицы"""
        return self.set('table_columns', columns, 'table')
    
    def get_column_order(self) -> list:
        """Возвращает порядок колонок"""
        return self.get('column_order', [])
    
    def set_column_order(self, order: list) -> bool:
        """Сохраняет порядок колонок"""
        return self.set('column_order', order, 'table')
    
    def get_sort_settings(self) -> tuple:
        """Возвращает настройки сортировки"""
        return self.get('sort_column', None), self.get('sort_order', 0)
    
    def set_sort_settings(self, column: str, order: int) -> bool:
        """Сохраняет настройки сортировки"""
        return self.set('sort_column', column, 'table') and self.set('sort_order', order, 'table')
    
    # ========== ИКОНКИ ==========
    
    def get_country_icon_path(self, country_id: int) -> Optional[str]:
        """Возвращает путь к иконке страны"""
        icons = self.get('country_icons', {})
        icon_data = icons.get(str(country_id))
        
        if isinstance(icon_data, dict):
            return icon_data.get('path')
        return icon_data
    
    def get_country_custom_icons(self) -> Dict[str, Any]:
        """Возвращает все пользовательские иконки стран"""
        return self.get('country_icons', {})
    
    def set_country_custom_icon(self, country_id: int, icon_path: str) -> bool:
        """Сохраняет иконку для страны"""
        icons = self.get('country_icons', {})
        icons[str(country_id)] = {
            'path': icon_path,
            'type': 'custom'
        }
        return self.set('country_icons', icons, 'icons')
    
    def remove_country_custom_icon(self, country_id: int) -> bool:
        """Удаляет иконку страны"""
        icons = self.get('country_icons', {})
        if str(country_id) in icons:
            del icons[str(country_id)]
            return self.set('country_icons', icons, 'icons')
        return True
    
    def get_continent_icon(self, continent_name: str, is_extinct: bool = False) -> Optional[str]:
        """Возвращает иконку континента"""
        icons = self.get('continent_icons', {})
        key = f"{'extinct_' if is_extinct else ''}{continent_name}"
        icon_data = icons.get(key)
        
        if isinstance(icon_data, dict):
            return icon_data.get('path') or icon_data.get('icon')
        return icon_data
    
    def set_continent_icon(self, continent_name: str, icon_data: Any, is_extinct: bool = False) -> bool:
        """Сохраняет иконку континента"""
        icons = self.get('continent_icons', {})
        key = f"{'extinct_' if is_extinct else ''}{continent_name}"
        icons[key] = icon_data
        return self.set('continent_icons', icons, 'icons')
    
    def get_folder_icon(self, folder_path: str) -> Optional[str]:
        """Возвращает иконку папки"""
        icons = self.get('folder_icons', {})
        icon_data = icons.get(folder_path)
        
        if isinstance(icon_data, dict):
            return icon_data.get('path') or icon_data.get('icon')
        return icon_data
    
    def set_folder_icon(self, folder_path: str, icon_data: Any) -> bool:
        """Сохраняет иконку папки"""
        icons = self.get('folder_icons', {})
        icons[folder_path] = icon_data
        return self.set('folder_icons', icons, 'icons')
    
    # ========== СТРУКТУРА ДЕРЕВА ==========
    
    def get_tree_structure(self) -> Dict[str, Any]:
        """Возвращает структуру дерева"""
        return self.get('tree_structure', {})
    
    def save_tree_structure(self, tree_widget) -> bool:
        """Сохраняет структуру дерева"""
        try:
            structure = self._extract_tree_structure(tree_widget)
            return self.set('tree_structure', structure, 'tree')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения структуры дерева: {e}")
            return False
    
    def load_tree_structure(self, tree_widget, all_item, extinct_item, 
                           continent_items, extinct_continent_items, collection_item) -> bool:
        """Загружает структуру дерева"""
        try:
            structure = self.get('tree_structure', {})
            if not structure:
                return False
            
            return self._apply_tree_structure(
                tree_widget, structure, all_item, extinct_item,
                continent_items, extinct_continent_items, collection_item
            )
        except Exception as e:
            self.logger.error(f"Ошибка загрузки структуры дерева: {e}")
            return False
    
    def get_country_positions(self) -> Dict[str, Any]:
        """Возвращает позиции стран в дереве"""
        return self.get('country_positions', {})
    
    def set_country_positions(self, positions: Dict[str, Any]) -> bool:
        """Сохраняет позиции стран в дереве"""
        return self.set('country_positions', positions, 'tree')
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _extract_tree_structure(self, tree_widget) -> Dict[str, Any]:
        """Извлекает структуру дерева"""
        structure = {
            'expanded': [],
            'folders': [],
            'country_positions': {}
        }
        
        root = tree_widget.invisibleRootItem()
        self._extract_item_structure(root, structure)
        
        return structure
    
    def _extract_item_structure(self, parent_item, structure, path=""):
        """Рекурсивно извлекает структуру элементов"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            text = child.text(0)
            country_id = child.data(0, Qt.UserRole)
            
            if country_id is not None:
                structure['country_positions'][str(country_id)] = {
                    'parent': path,
                    'text': text
                }
            else:
                clean_text = text
                import re
                clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', clean_text)
                
                if clean_text not in ['КОЛЛЕКЦИЯ', 'Все страны', 'Исчезнувшие страны']:
                    is_continent = clean_text in ['Европа', 'Азия', 'Америка', 'Африка', 'Океания']
                    if not is_continent:
                        structure['folders'].append(clean_text)
                
                if child.isExpanded():
                    structure['expanded'].append(f"{path}/{clean_text}" if path else clean_text)
                
                self._extract_item_structure(child, structure, f"{path}/{clean_text}" if path else clean_text)
    
    def _apply_tree_structure(self, tree_widget, structure, all_item, extinct_item,
                             continent_items, extinct_continent_items, collection_item) -> bool:
        """Применяет структуру дерева"""
        # Эта логика перенесена в CountryTreeWidget
        return True
    
    # ========== НАСТРОЙКИ NUMISTA ==========
    
    def get_numista_api_key(self) -> Optional[str]:
        """Возвращает API ключ Numista"""
        return self.get('numista_api_key')
    
    def get_numista_client_id(self) -> Optional[str]:
        """Возвращает Client ID Numista"""
        return self.get('numista_client_id')
    
    def get_numista_client_name(self) -> Optional[str]:
        """Возвращает Client Name Numista"""
        return self.get('numista_client_name')
    
    def set_numista_credentials(self, api_key: str, client_id: str = None, client_name: str = None) -> bool:
        """Сохраняет учетные данные Numista"""
        success = self.set('numista_api_key', api_key, 'general')
        if client_id:
            success = success and self.set('numista_client_id', client_id, 'general')
        if client_name:
            success = success and self.set('numista_client_name', client_name, 'general')
        return success
    
    # ========== НАСТРОЙКИ БЕКАПА ==========
    
    def get_backup_settings(self) -> Dict[str, Any]:
        """Возвращает настройки бекапа"""
        return self.get('backup_settings', {})
    
    def set_backup_settings(self, settings: Dict[str, Any]) -> bool:
        """Сохраняет настройки бекапа"""
        return self.set('backup_settings', settings, 'backup')