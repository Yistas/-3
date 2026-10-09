# -*- coding: utf-8 -*-

"""
Настройки цветов для погодовки через ConfigDB
"""

import json
from pathlib import Path
from database.config_db import get_config_db


class ColorSettings:
    """Класс для управления настройками цветов"""
    
    DEFAULT_COLORS = {
        "Красный": {"code": "#ff6b6b", "description": "Важные монеты", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Оранжевый": {"code": "#ffa500", "description": "Требует внимания", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Желтый": {"code": "#ffd966", "description": "Планируемая покупка", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Зеленый": {"code": "#90ee90", "description": "В коллекции", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Голубой": {"code": "#87ceeb", "description": "На продажу", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Синий": {"code": "#4a6fa5", "description": "Редкие монеты", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Фиолетовый": {"code": "#9b59b6", "description": "Юбилейные", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Розовый": {"code": "#ffb6c1", "description": "Подарки", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Серый": {"code": "#d3d3d3", "description": "Дубликаты", "enabled": True, "show_in_legend": True, "count_percentage": True},
        "Белый": {"code": "#ffffff", "description": "Сброс цвета", "enabled": True, "show_in_legend": False, "count_percentage": False}
    }
    
    def __init__(self):
        self.colors = {}
        self.load_colors()
    
    def load_colors(self):
        """Загружает настройки цветов из ConfigDB"""
        try:
            config_db = get_config_db()
            loaded = config_db.get('color_settings')
            
            if loaded:
                self.colors = loaded
            else:
                self.colors = self.DEFAULT_COLORS.copy()
                self.save_colors()
            
            # Добавляем недостающие цвета из DEFAULT_COLORS
            for name, data in self.DEFAULT_COLORS.items():
                if name not in self.colors:
                    self.colors[name] = data
            
            self.save_colors()
            
            print(f"📁 Загружены настройки цветов из ConfigDB")
            
        except Exception as e:
            print(f"Ошибка загрузки настроек цветов: {e}")
            self.colors = self.DEFAULT_COLORS.copy()
        
        return self.colors
    
    def save_colors(self):
        """Сохраняет настройки цветов в ConfigDB"""
        try:
            config_db = get_config_db()
            config_db.set('color_settings', self.colors, 'yearly')
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек цветов: {e}")
            return False
    
    def get_color_code(self, color_name):
        """Возвращает код цвета по имени"""
        if color_name in self.colors and self.colors[color_name]["enabled"]:
            return self.colors[color_name]["code"]
        return None
    
    def get_enabled_colors(self):
        """Возвращает список включенных цветов"""
        result = {}
        for name, data in self.colors.items():
            if data.get("enabled", True):
                result[name] = data
        return result
    
    def get_legend_colors(self):
        """Возвращает список цветов для отображения в легенде"""
        result = {}
        for name, data in self.colors.items():
            if data.get("show_in_legend", True) and data.get("enabled", True):
                result[name] = data
        return result
    
    def should_count_percentage(self, color_name):
        """Возвращает, нужно ли считать процент для этого цвета"""
        if color_name in self.colors:
            return self.colors[color_name].get("count_percentage", True)
        return True
    
    def update_color(self, color_name, code=None, description=None, enabled=None, 
                     show_in_legend=None, count_percentage=None):
        """Обновляет настройки цвета"""
        if color_name in self.colors:
            if code is not None:
                self.colors[color_name]["code"] = code
            if description is not None:
                self.colors[color_name]["description"] = description
            if enabled is not None:
                self.colors[color_name]["enabled"] = enabled
            if show_in_legend is not None:
                self.colors[color_name]["show_in_legend"] = show_in_legend
            if count_percentage is not None:
                self.colors[color_name]["count_percentage"] = count_percentage
            self.save_colors()
            return True
        return False
    
    def add_color(self, color_name, code, description="", show_in_legend=True, count_percentage=True):
        """Добавляет новый цвет"""
        if color_name not in self.colors:
            self.colors[color_name] = {
                "code": code,
                "description": description,
                "enabled": True,
                "show_in_legend": show_in_legend,
                "count_percentage": count_percentage
            }
            self.save_colors()
            return True
        return False
    
    def delete_color(self, color_name):
        """Удаляет цвет"""
        if color_name in self.colors and color_name not in self.DEFAULT_COLORS:
            del self.colors[color_name]
            self.save_colors()
            return True
        return False
    
    def reset_to_defaults(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        self.colors = self.DEFAULT_COLORS.copy()
        self.save_colors()