# -*- coding: utf-8 -*-
"""
Загрузка и сохранение настроек MainWindow через ConfigDB
"""
import os
import json
from database.config_db import get_config_db


class SettingsMixin:
    """Примесь с методами загрузки/сохранения настроек"""

    def load_settings(self):
        """Загружает сохраненные настройки из ConfigDB"""
        try:
            config_db = get_config_db()
            # Загружаем настройки окна
            window_settings = config_db.get('window_settings', {})
            self.left_panel_size = window_settings.get('left_panel_size', 280)
            self.center_panel_size = window_settings.get('center_panel_size', 700)
            self.right_panel_size = window_settings.get('right_panel_size', 400)
            self.right_panel_visible = window_settings.get('right_panel_visible', True)

            # Колонки таблицы
            column_info = window_settings.get('table_columns', [])
            if column_info:
                self.table_panel.load_columns_from_settings(column_info)

            # Порядок колонок
            column_order = window_settings.get('column_order', [])
            if column_order:
                self.table_panel.apply_column_order(column_order)

            # Сортировка
            self.table_panel.sort_column = window_settings.get('sort_column', None)
            self.table_panel.sort_order = window_settings.get('sort_order', 0)

            # Тема (по умолчанию — Тёмная)
            saved_theme = window_settings.get('theme', 'Тёмная')
            # Миграция старых значений на новые имена
            if saved_theme == 'light':
                saved_theme = 'Светлая'
            elif saved_theme == 'dark':
                saved_theme = 'Тёмная'
            # Одноразовая миграция: старая светлая тема заменяется на тёмную
            if saved_theme == 'Светлая':
                saved_theme = 'Тёмная'
            self.saved_theme = saved_theme

            from PySide6.QtWidgets import QApplication
            self.theme_manager.apply_theme(QApplication.instance(), saved_theme)
            self.logger.info(f"Настройки загружены из ConfigDB, тема: {saved_theme}")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке настроек: {e}")

    def save_settings(self):
        """Сохраняет настройки в ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            if hasattr(self, 'main_splitter'):
                sizes = self.main_splitter.sizes()
                self.left_panel_size = sizes[0]
                self.center_panel_size = sizes[1]
                self.right_panel_size = sizes[2]
            window_settings = {
                'window_geometry': self.saveGeometry().toBase64().data().decode(),
                'window_state': self.saveState().toBase64().data().decode(),
                'theme': self.theme_manager.get_current_theme_name(),
                'right_panel_visible': self.right_panel_visible,
                'left_panel_size': self.left_panel_size,
                'center_panel_size': self.center_panel_size,
                'right_panel_size': self.right_panel_size,
                'table_columns': self.table_panel.get_columns_info(),
                'column_order': self.table_panel.get_column_order(),
                'sort_column': self.table_panel.sort_column,
                'sort_order': self.table_panel.sort_order
            }
            config_db.set('window_settings', window_settings, 'window')
            self.logger.info(f"Настройки сохранены в ConfigDB, тема: {window_settings['theme']}")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении настроек: {e}")

    def apply_panel_settings(self):
        """Применяет загруженные настройки панели"""
        if hasattr(self, 'right_panel') and self.right_panel:
            if not self.right_panel_visible:
                self.right_panel.hide()
                self.table_panel.update_toggle_panel_action(False)
            else:
                self.right_panel.show()
                self.table_panel.update_toggle_panel_action(True)
        if hasattr(self, 'main_splitter'):
            self.main_splitter.setSizes([
                self.left_panel_size,
                self.center_panel_size,
                self.right_panel_size
            ])
        # Восстанавливаем видимость левой панели
        if hasattr(self, 'left_panel'):
            if not hasattr(self, '_left_panel_visible_setting'):
                self.left_panel.show()