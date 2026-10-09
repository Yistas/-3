# -*- coding: utf-8 -*-
"""
Менеджер тем для приложения с поддержкой пользовательских тем
Современный дизайн с тёмной темой
"""
import json
import logging
from pathlib import Path
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QListWidgetItem, QWidget,
                               QFormLayout, QColorDialog, QGroupBox, QMessageBox,
                               QInputDialog, QScrollArea, QLineEdit, QTextEdit)

from PySide6.QtWidgets import QProxyStyle, QStyle
from PySide6.QtGui import QPen


class BranchIndicatorStyle(QProxyStyle):
    """Стиль, который сам рисует «плюс/минус» у веток дерева.
    Работает надёжнее, чем image: url(...) в stylesheet."""

    def __init__(self, base_style=None):
        super().__init__(base_style)
        self.branch_color = QColor('#a8a8d0')

    def set_branch_color(self, color):
        """Обновляет цвет индикаторов под текущую тему"""
        self.branch_color = QColor(color)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorBranch:
            has_children = bool(option.state & QStyle.StateFlag.State_Children)
            if not has_children:
                return
            is_open = bool(option.state & QStyle.StateFlag.State_Open)

            painter.save()
            pen = QPen(self.branch_color)
            pen.setWidth(2)
            painter.setPen(pen)

            rect = option.rect
            center = rect.center()
            half = max(3, min(rect.width(), rect.height()) // 2 - 3)

            # Горизонтальная линия (есть всегда → «минус»)
            painter.drawLine(center.x() - half, center.y(),
                             center.x() + half, center.y())
            # Вертикальная линия (только у свёрнутой ветки → «плюс»)
            if not is_open:
                painter.drawLine(center.x(), center.y() - half,
                                 center.x(), center.y() + half)
            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)

class ThemeManager:
    """Класс для управления темами оформления"""

    # ===== СОВРЕМЕННАЯ ТЁМНАЯ ТЕМА =====
    DARK_THEME = {
        'name': 'Тёмная',
        'type': 'dark',
        # Основные поверхности
        'window_bg': '#0f0f1a',
        'window_text': '#e4e4ef',
        'base': '#1a1a2e',
        'alternate_base': '#16213e',
        'text': '#e4e4ef',
        # Кнопки и элементы управления
        'button': '#16213e',
        'button_text': '#e4e4ef',
        'highlight': '#6c63ff',
        'highlight_text': '#ffffff',
        # Подсказки
        'tooltip_bg': '#2a2a4a',
        'tooltip_text': '#e4e4ef',
        # Ссылки
        'link': '#7c74ff',
        # Таблицы
        'table_header': '#16213e',
        'table_header_text': '#a8a8d0',
        # Границы
        'border': '#2a2a4a',
        'border_focus': '#6c63ff',
        # Отключённые элементы
        'disabled': '#5a5a7a',
        # Комбобоксы
        'combo_bg': '#16213e',
        'combo_text': '#e4e4ef',
        'combo_popup_bg': '#1a1a2e',
        'combo_popup_text': '#e4e4ef',
        'combo_selected_bg': '#6c63ff',
        'combo_selected_text': '#ffffff',
        'arrow_color': '#a8a8d0',
        'arrow_hover_color': '#6c63ff',
        # Дополнительные цвета для современного дизайна
        'surface': '#16213e',
        'surface_hover': '#1f2b47',
        'surface_active': '#253352',
        'accent': '#6c63ff',
        'accent_hover': '#7c74ff',
        'accent_pressed': '#5a52e0',
        'success': '#4caf50',
        'warning': '#ff9800',
        'error': '#f44336',
        'info': '#2196f3',
        'card_bg': '#1a1a2e',
        'card_border': '#2a2a4a',
        'scrollbar_bg': '#1a1a2e',
        'scrollbar_handle': '#3a3a5a',
        'scrollbar_hover': '#6c63ff',
        'tab_bg': '#0f0f1a',
        'tab_selected': '#16213e',
        'tab_text': '#8888aa',
        'tab_selected_text': '#e4e4ef',
        'input_bg': '#16213e',
        'input_border': '#2a2a4a',
        'input_focus_border': '#6c63ff',
        'group_box_border': '#2a2a4a',
        'status_bar_bg': '#0f0f1a',
        'menu_bg': '#1a1a2e',
        'menu_hover': '#253352',
        'menu_text': '#e4e4ef',
        'menu_separator': '#2a2a4a',
    }

    # Светлая тема (оставляем как есть)
    LIGHT_THEME = {
        'name': 'Светлая',
        'type': 'light',
        'window_bg': '#f5f7fa',
        'window_text': '#1a1a2e',
        'base': '#ffffff',
        'alternate_base': '#f8f9fa',
        'text': '#1a1a2e',
        'button': '#e9ecef',
        'button_text': '#1a1a2e',
        'highlight': '#4a6fa5',
        'highlight_text': '#ffffff',
        'tooltip_bg': '#2a2a4a',
        'tooltip_text': '#ffffff',
        'link': '#4a6fa5',
        'table_header': '#4a6fa5',
        'table_header_text': '#ffffff',
        'border': '#dee2e6',
        'border_focus': '#4a6fa5',
        'disabled': '#adb5bd',
        'combo_bg': '#ffffff',
        'combo_text': '#1a1a2e',
        'combo_popup_bg': '#ffffff',
        'combo_popup_text': '#1a1a2e',
        'combo_selected_bg': '#4a6fa5',
        'combo_selected_text': '#ffffff',
        'arrow_color': '#495057',
        'arrow_hover_color': '#4a6fa5',
        'surface': '#ffffff',
        'surface_hover': '#f8f9fa',
        'surface_active': '#e9ecef',
        'accent': '#4a6fa5',
        'accent_hover': '#5a7fb5',
        'accent_pressed': '#3a5f95',
        'success': '#28a745',
        'warning': '#ffc107',
        'error': '#dc3545',
        'info': '#17a2b8',
        'card_bg': '#ffffff',
        'card_border': '#e9ecef',
        'scrollbar_bg': '#f8f9fa',
        'scrollbar_handle': '#ced4da',
        'scrollbar_hover': '#4a6fa5',
        'tab_bg': '#f5f7fa',
        'tab_selected': '#ffffff',
        'tab_text': '#6c757d',
        'tab_selected_text': '#4a6fa5',
        'input_bg': '#ffffff',
        'input_border': '#ced4da',
        'input_focus_border': '#4a6fa5',
        'group_box_border': '#dee2e6',
        'status_bar_bg': '#f5f7fa',
        'menu_bg': '#ffffff',
        'menu_hover': '#f8f9fa',
        'menu_text': '#1a1a2e',
        'menu_separator': '#e9ecef',
    }

    # Синяя тема
    BLUE_THEME = {
        'name': 'Синяя',
        'type': 'light',
        'window_bg': '#e8f0fe',
        'window_text': '#1a3e6f',
        'base': '#ffffff',
        'alternate_base': '#f0f7ff',
        'text': '#1a3e6f',
        'button': '#4a6fa5',
        'button_text': '#ffffff',
        'highlight': '#1e88e5',
        'highlight_text': '#ffffff',
        'tooltip_bg': '#1a3e6f',
        'tooltip_text': '#ffffff',
        'link': '#1e88e5',
        'table_header': '#1e88e5',
        'table_header_text': '#ffffff',
        'border': '#bbdef5',
        'border_focus': '#1e88e5',
        'disabled': '#90a4ae',
        'combo_bg': '#ffffff',
        'combo_text': '#1a3e6f',
        'combo_popup_bg': '#ffffff',
        'combo_popup_text': '#1a3e6f',
        'combo_selected_bg': '#1e88e5',
        'combo_selected_text': '#ffffff',
        'arrow_color': '#1a3e6f',
        'arrow_hover_color': '#1e88e5',
        'surface': '#ffffff',
        'surface_hover': '#f0f7ff',
        'surface_active': '#e3f2fd',
        'accent': '#1e88e5',
        'accent_hover': '#42a5f5',
        'accent_pressed': '#1565c0',
        'success': '#2e7d32',
        'warning': '#f57f17',
        'error': '#c62828',
        'info': '#0277bd',
        'card_bg': '#ffffff',
        'card_border': '#bbdef5',
        'scrollbar_bg': '#f0f7ff',
        'scrollbar_handle': '#90caf9',
        'scrollbar_hover': '#1e88e5',
        'tab_bg': '#e8f0fe',
        'tab_selected': '#ffffff',
        'tab_text': '#5c7ea8',
        'tab_selected_text': '#1e88e5',
        'input_bg': '#ffffff',
        'input_border': '#bbdef5',
        'input_focus_border': '#1e88e5',
        'group_box_border': '#bbdef5',
        'status_bar_bg': '#e8f0fe',
        'menu_bg': '#ffffff',
        'menu_hover': '#e3f2fd',
        'menu_text': '#1a3e6f',
        'menu_separator': '#bbdef5',
    }

    # Тёмно-синяя тема (альтернативная тёмная)
    DARK_BLUE_THEME = {
        'name': 'Тёмно-синяя',
        'type': 'dark',
        'window_bg': '#0a1929',
        'window_text': '#e3f2fd',
        'base': '#0d2137',
        'alternate_base': '#0f2a44',
        'text': '#e3f2fd',
        'button': '#0f2a44',
        'button_text': '#e3f2fd',
        'highlight': '#2196f3',
        'highlight_text': '#ffffff',
        'tooltip_bg': '#1a3a5c',
        'tooltip_text': '#e3f2fd',
        'link': '#64b5f6',
        'table_header': '#0f2a44',
        'table_header_text': '#90caf9',
        'border': '#1a3a5c',
        'border_focus': '#2196f3',
        'disabled': '#546e7a',
        'combo_bg': '#0f2a44',
        'combo_text': '#e3f2fd',
        'combo_popup_bg': '#0d2137',
        'combo_popup_text': '#e3f2fd',
        'combo_selected_bg': '#2196f3',
        'combo_selected_text': '#ffffff',
        'arrow_color': '#90caf9',
        'arrow_hover_color': '#2196f3',
        'surface': '#0f2a44',
        'surface_hover': '#133352',
        'surface_active': '#1a3f61',
        'accent': '#2196f3',
        'accent_hover': '#42a5f5',
        'accent_pressed': '#1976d2',
        'success': '#4caf50',
        'warning': '#ff9800',
        'error': '#f44336',
        'info': '#03a9f4',
        'card_bg': '#0d2137',
        'card_border': '#1a3a5c',
        'scrollbar_bg': '#0d2137',
        'scrollbar_handle': '#1a3a5c',
        'scrollbar_hover': '#2196f3',
        'tab_bg': '#0a1929',
        'tab_selected': '#0f2a44',
        'tab_text': '#5c8ab5',
        'tab_selected_text': '#e3f2fd',
        'input_bg': '#0f2a44',
        'input_border': '#1a3a5c',
        'input_focus_border': '#2196f3',
        'group_box_border': '#1a3a5c',
        'status_bar_bg': '#0a1929',
        'menu_bg': '#0d2137',
        'menu_hover': '#1a3f61',
        'menu_text': '#e3f2fd',
        'menu_separator': '#1a3a5c',
    }

    # Словарь всех предопределенных тем
    PRESET_THEMES = {
        'dark': DARK_THEME,
        'light': LIGHT_THEME,
        'blue': BLUE_THEME,
        'dark_blue': DARK_BLUE_THEME,
    }

    def __init__(self):
        self.logger = logging.getLogger('CoinCollector.ThemeManager')
        self.current_theme = self.DARK_THEME.copy()
        self.custom_themes = {}
        self.themes_dir = Path("themes")
        self.themes_dir.mkdir(exist_ok=True)
        self._branch_style = None
        self.load_custom_themes()

    def load_custom_themes(self):
        """Загружает пользовательские темы из папки themes"""
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme = json.load(f)
                if 'name' in theme:
                    self.custom_themes[theme['name']] = theme
            except Exception as e:
                self.logger.error(f"Ошибка загрузки темы {theme_file}: {e}")

    def save_custom_theme(self, theme):
        """Сохраняет пользовательскую тему"""
        name = theme.get('name', 'custom_theme')
        safe_name = "".join(c for c in name if c.isalnum() or c in ' _-')
        file_path = self.themes_dir / f"{safe_name}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(theme, f, ensure_ascii=False, indent=2)
            self.custom_themes[name] = theme
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения темы: {e}")
            return False

    def delete_custom_theme(self, theme_name):
        """Удаляет пользовательскую тему"""
        safe_name = "".join(c for c in theme_name if c.isalnum() or c in ' _-')
        file_path = self.themes_dir / f"{safe_name}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                if theme_name in self.custom_themes:
                    del self.custom_themes[theme_name]
                return True
            except Exception as e:
                self.logger.error(f"Ошибка удаления темы: {e}")
        return False

    def get_all_themes(self):
        """Возвращает список всех доступных тем"""
        themes = [t.copy() for t in self.PRESET_THEMES.values()]
        themes.extend([t.copy() for t in self.custom_themes.values()])
        return themes

    def get_theme_by_name(self, name):
        """Возвращает тему по имени"""
        for theme in self.get_all_themes():
            if theme['name'] == name:
                return theme
        return None

    def get_current_theme_name(self):
        """Возвращает имя текущей темы"""
        return self.current_theme.get('name', 'Тёмная')

    def is_dark(self):
        """Проверяет, является ли текущая тема тёмной"""
        return self.current_theme.get('type', 'dark') == 'dark'

    # ========== ГЕНЕРАЦИЯ СТИЛЕЙ ==========

    def _generate_stylesheet(self):
        """Генерирует CSS стили на основе текущей темы"""
        t = self.current_theme

        def c(key, fallback='#888888'):
            val = t.get(key, fallback)
            if isinstance(val, dict):
                return fallback
            return val

        window_bg = c('window_bg', '#0f0f1a')
        window_text = c('window_text', '#e4e4ef')
        base = c('base', '#1a1a2e')
        alternate_base = c('alternate_base', '#16213e')
        text = c('text', '#e4e4ef')
        button = c('button', '#16213e')
        button_text = c('button_text', '#e4e4ef')
        highlight = c('highlight', '#6c63ff')
        highlight_text = c('highlight_text', '#ffffff')
        tooltip_bg = c('tooltip_bg', '#2a2a4a')
        tooltip_text = c('tooltip_text', '#e4e4ef')
        link = c('link', '#7c74ff')
        table_header = c('table_header', '#16213e')
        table_header_text = c('table_header_text', '#a8a8d0')
        border = c('border', '#2a2a4a')
        disabled = c('disabled', '#5a5a7a')
        combo_bg = c('combo_bg', '#16213e')
        combo_text = c('combo_text', '#e4e4ef')
        combo_popup_bg = c('combo_popup_bg', '#1a1a2e')
        combo_popup_text = c('combo_popup_text', '#e4e4ef')
        combo_selected_bg = c('combo_selected_bg', '#6c63ff')
        combo_selected_text = c('combo_selected_text', '#ffffff')
        arrow_color = c('arrow_color', '#a8a8d0')
        arrow_hover = c('arrow_hover_color', '#6c63ff')
        surface_hover = c('surface_hover', '#1f2b47')
        surface_active = c('surface_active', '#253352')
        accent = c('accent', '#6c63ff')
        accent_pressed = c('accent_pressed', '#5a52e0')
        input_bg = c('input_bg', '#16213e')
        input_border = c('input_border', '#2a2a4a')
        input_focus = c('input_focus_border', '#6c63ff')
        group_border = c('group_box_border', '#2a2a4a')
        status_bg = c('status_bar_bg', '#0f0f1a')
        menu_bg = c('menu_bg', '#1a1a2e')
        menu_hover = c('menu_hover', '#253352')
        menu_text = c('menu_text', '#e4e4ef')
        menu_sep = c('menu_separator', '#2a2a4a')
        tab_bg = c('tab_bg', '#0f0f1a')
        tab_sel = c('tab_selected', '#16213e')
        tab_text = c('tab_text', '#8888aa')
        tab_sel_text = c('tab_selected_text', '#e4e4ef')
        scroll_bg = c('scrollbar_bg', '#1a1a2e')
        scroll_handle = c('scrollbar_handle', '#3a3a5a')
        scroll_hover = c('scrollbar_hover', '#6c63ff')

        return f"""
/* ===== БАЗА ===== */
QMainWindow {{ background-color: {window_bg}; }}
QDialog {{ background-color: {window_bg}; }}
QWidget {{ color: {text}; }}
QLabel {{ background: transparent; }}

/* ===== КНОПКИ ===== */
QPushButton {{
    background-color: {button};
    color: {button_text};
    border: 1px solid {border};
    padding: 5px 12px;
    border-radius: 6px;
}}
QPushButton:hover {{
    background-color: {surface_hover};
    border-color: {accent};
}}
QPushButton:pressed {{ background-color: {surface_active}; }}
QPushButton:disabled {{ color: {disabled}; border-color: {border}; }}

/* ===== ПОЛЯ ВВОДА ===== */
QLineEdit, QTextEdit, QPlainTextEdit,
QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {input_border};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {highlight};
    selection-color: {highlight_text};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus {{
    border-color: {input_focus};
}}

/* ===== COMBOBOX ===== */
QComboBox {{
    background-color: {combo_bg};
    color: {combo_text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    padding-right: 24px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {accent}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {arrow_color};
    width: 0; height: 0;
    margin-right: 7px;
}}
QComboBox:hover::down-arrow {{ border-top-color: {arrow_hover}; }}
QComboBox QAbstractItemView {{
    background-color: {combo_popup_bg};
    color: {combo_popup_text};
    border: 1px solid {border};
    border-radius: 6px;
    selection-background-color: {combo_selected_bg};
    selection-color: {combo_selected_text};
    outline: 0;
    padding: 4px;
}}

/* ===== ТАБЛИЦЫ ===== */
QTableWidget, QTableView {{
    background-color: {base};
    alternate-background-color: {alternate_base};
    color: {text};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent};
    selection-color: {highlight_text};
}}
QTableWidget::item, QTableView::item {{ padding: 3px; }}
QTableWidget::item:hover, QTableView::item:hover {{
    background-color: {surface_hover};
    color: {text};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {accent};
    color: {highlight_text};
}}
QHeaderView::section {{
    background-color: {table_header};
    color: {table_header_text};
    padding: 6px;
    border: none;
    border-right: 1px solid {border};
    border-bottom: 2px solid {accent};
    font-weight: bold;
}}
QHeaderView::section:hover {{ background-color: {surface_hover}; }}
QHeaderView::section:down {{ background-color: {surface_active}; }}

/* ===== ДЕРЕВО ===== */
QTreeWidget {{
    background-color: {base};
    alternate-background-color: {alternate_base};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent};
    selection-color: {highlight_text};
    outline: 0;
}}
QTreeWidget::item {{ padding: 4px; border-bottom: 1px solid {border}; }}
QTreeWidget::item:hover {{ background-color: {surface_hover}; }}
QTreeWidget::item:selected {{
    background-color: {accent};
    color: {highlight_text};
}}

/* ===== ВКЛАДКИ ===== */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 8px;
    background-color: {base};
}}
QTabBar::tab {{
    background-color: {tab_bg};
    color: {tab_text};
    padding: 8px 14px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{
    background-color: {tab_sel};
    color: {tab_sel_text};
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover:!selected {{
    background-color: {surface_hover};
    color: {text};
}}

/* ===== ГРУППЫ ===== */
QGroupBox {{
    border: 1px solid {group_border};
    border-radius: 10px;
    margin-top: 12px;
    font-weight: bold;
    color: {text};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {accent};
}}

/* ===== МЕНЮ ===== */
QMenuBar {{
    background-color: {window_bg};
    color: {window_text};
    border-bottom: 1px solid {border};
}}
QMenuBar::item {{ padding: 6px 12px; border-radius: 6px; }}
QMenuBar::item:selected {{ background-color: {menu_hover}; }}
QMenu {{
    background-color: {menu_bg};
    color: {menu_text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 24px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {menu_hover}; }}
QMenu::separator {{
    height: 1px;
    background-color: {menu_sep};
    margin: 4px 8px;
}}

/* ===== ТУЛБАР / СТАТУС ===== */
QToolBar {{
    background-color: {window_bg};
    border: none;
    border-bottom: 1px solid {border};
    spacing: 4px;
    padding: 3px;
}}
QToolButton {{
    background: transparent;
    color: {text};
    border-radius: 6px;
    padding: 5px;
}}
QToolButton:hover {{ background-color: {surface_hover}; }}
QToolButton:pressed {{ background-color: {surface_active}; }}
QStatusBar {{
    background-color: {status_bg};
    color: {tab_text};
    border-top: 1px solid {border};
}}

/* ===== СКРОЛЛБАРЫ ===== */
QScrollBar:vertical {{
    background-color: {scroll_bg};
    width: 12px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background-color: {scroll_handle};
    min-height: 24px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {scroll_hover}; }}
QScrollBar:horizontal {{
    background-color: {scroll_bg};
    height: 12px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background-color: {scroll_handle};
    min-width: 24px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {scroll_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ===== ЧЕКБОКСЫ / РАДИО ===== */
QCheckBox, QRadioButton {{ color: {text}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {border};
    border-radius: 4px;
    background-color: {input_bg};
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {border};
    border-radius: 9px;
    background-color: {input_bg};
}}
QRadioButton::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

/* ===== ПРОЧЕЕ ===== */
QProgressBar {{
    background-color: {input_bg};
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: {text};
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 5px; }}
QToolTip {{
    background-color: {tooltip_bg};
    color: {tooltip_text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 5px 9px;
}}
QSplitter::handle {{ background-color: {border}; }}
QSplitter::handle:hover {{ background-color: {accent}; }}
QListWidget {{
    background-color: {base};
    alternate-background-color: {alternate_base};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
}}
QListWidget::item {{ padding: 5px; border-radius: 4px; }}
QListWidget::item:hover {{ background-color: {surface_hover}; }}
QListWidget::item:selected {{
    background-color: {accent};
    color: {highlight_text};
}}
"""

    def _ui_fixes_stylesheet(self):
        """Финальные переопределения: применяются последними и перекрывают предыдущие правила"""
        t = self.current_theme
        if self.is_dark():
            btn_bg = '#262640'
            btn_border = '#3d3d5c'
            hover_bg = t.get('accent', '#6c63ff')
            hover_text = '#ffffff'
            item_hover = '#2e2e4d'
        else:
            btn_bg = t.get('button', '#e0e0e0')
            btn_border = t.get('border', '#c0c0c0')
            hover_bg = t.get('accent', '#4a6fa5')
            hover_text = '#ffffff'
            item_hover = t.get('alternate_base', '#f5f5f5')
        return f"""
/* ===== КНОПКИ (не меняем, они хорошие) ===== */
QPushButton {{
    background-color: {btn_bg};
    color: {t.get('text', '#e4e4ef')};
    border: 1px solid {btn_border};
    padding: 5px 12px;
    border-radius: 6px;
}}
QPushButton:hover {{
    background-color: {hover_bg};
    color: {hover_text};
    border-color: {hover_bg};
}}
QPushButton:pressed {{
    background-color: {t.get('accent_pressed', '#5a52e0')};
    color: #ffffff;
}}

/* ===== ТАБЛИЦЫ: убираем "кривые" рамки у ячеек ===== */
QTableWidget, QTableView {{
    background-color: {t.get('base', '#1a1a2e')};
    alternate-background-color: {t.get('alternate_base', '#16213e')};
    color: {t.get('text', '#e4e4ef')};
    gridline-color: {t.get('border', '#2a2a4a')};
    border: 1px solid {t.get('border', '#2a2a4a')};
    border-radius: 8px;
    selection-background-color: {t.get('accent', '#6c63ff')};
    selection-color: #ffffff;
    show-decoration-selected: 0;
}}
/* Убираем рамки/скругления/отступы у ячеек — остаются только ровные линии сетки */
QTableWidget::item, QTableView::item {{
    border: none;
    border-radius: 0px;
    margin: 0px;
    padding: 4px 6px;
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background-color: {item_hover};
    color: {t.get('text', '#e4e4ef')};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {t.get('accent', '#6c63ff')};
    color: #ffffff;
}}

/* ===== ЗАГОЛОВКИ ТАБЛИЦ (горизонтальные и вертикальные) ===== */
QHeaderView::section {{
    background-color: {t.get('table_header', '#16213e')};
    color: {t.get('table_header_text', '#a8a8d0')};
    padding: 6px;
    border: none;
    border-radius: 0px;
    border-right: 1px solid {t.get('border', '#2a2a4a')};
    border-bottom: 1px solid {t.get('border', '#2a2a4a')};
    font-weight: bold;
}}
QHeaderView::section:hover {{
    background-color: {item_hover};
    color: {t.get('text', '#e4e4ef')};
}}

/* ===== ВКЛАДКИ: компактные отступы ===== */
QTabBar::tab {{
    padding: 8px 14px;
}}
"""

    def apply_theme(self, app, theme_name='Тёмная'):
        """Применяет тему к приложению"""
        theme = None

        # Ищем в предопределённых
        for preset_key, preset_theme in self.PRESET_THEMES.items():
            if preset_theme.get('name') == theme_name:
                theme = preset_theme.copy()
                break

        # Ищем в пользовательских
        if theme is None and theme_name in self.custom_themes:
            theme = self.custom_themes[theme_name].copy()

        # Если не нашли — тёмная по умолчанию
        if theme is None:
            self.logger.warning(f"Тема '{theme_name}' не найдена, используется тёмная")
            theme = self.DARK_THEME.copy()

        self.current_theme = theme

        # Генерируем иконки веток дерева (плюс/минус)
        if hasattr(self, '_ensure_branch_icons'):
            self._ensure_branch_icons()

        palette = QPalette()

        def get_color(key):
            return QColor(self.current_theme.get(key, '#f0f0f0'))

        palette.setColor(QPalette.Window, get_color('window_bg'))
        palette.setColor(QPalette.WindowText, get_color('window_text'))
        palette.setColor(QPalette.Base, get_color('base'))
        palette.setColor(QPalette.AlternateBase, get_color('alternate_base'))
        palette.setColor(QPalette.Text, get_color('text'))
        palette.setColor(QPalette.Button, get_color('button'))
        palette.setColor(QPalette.ButtonText, get_color('button_text'))
        palette.setColor(QPalette.Highlight, get_color('highlight'))
        palette.setColor(QPalette.HighlightedText, get_color('highlight_text'))
        palette.setColor(QPalette.ToolTipBase, get_color('tooltip_bg'))
        palette.setColor(QPalette.ToolTipText, get_color('tooltip_text'))
        palette.setColor(QPalette.Link, get_color('link'))
        palette.setColor(QPalette.Disabled, QPalette.Text, get_color('disabled'))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, get_color('disabled'))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, get_color('disabled'))

        app.setPalette(palette)
        # Финальные переопределения идут последними и перекрывают проблемные правила
        app.setStyleSheet(self._generate_stylesheet() + self._ui_fixes_stylesheet())

        # Собственная отрисовка плюс/минус у веток дерева
        if hasattr(self, '_branch_style'):
            if self._branch_style is None:
                self._branch_style = BranchIndicatorStyle(app.style())
                app.setStyle(self._branch_style)
            self._branch_style.set_branch_color(
                self.current_theme.get('arrow_color', '#a8a8d0')
            )

        self.logger.info(f"Применена тема: {self.current_theme.get('name')}")

class ThemeManagerDialog(QDialog):
    """Диалог управления темами"""
    theme_changed = Signal(str)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("🎨 Управление темами")
        self.setMinimumSize(450, 350)
        self.init_ui()
        self.load_themes()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("🎨 Управление темами оформления")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 10px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.theme_list = QListWidget()
        self.theme_list.itemDoubleClicked.connect(self.apply_selected_theme)
        layout.addWidget(QLabel("Доступные темы:"))
        layout.addWidget(self.theme_list)

        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("✅ Применить")
        self.apply_btn.clicked.connect(self.apply_selected_theme)
        button_layout.addWidget(self.apply_btn)

        self.new_btn = QPushButton("➕ Создать")
        self.new_btn.clicked.connect(self.create_theme)
        button_layout.addWidget(self.new_btn)

        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_selected_theme)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("❌ Закрыть")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def load_themes(self):
        self.theme_list.clear()
        for theme in self.theme_manager.get_all_themes():
            item = QListWidgetItem(theme['name'])
            item.setData(Qt.UserRole, theme['name'])
            self.theme_list.addItem(item)

    def apply_selected_theme(self):
        current = self.theme_list.currentItem()
        if current:
            theme_name = current.data(Qt.UserRole)
            self.theme_changed.emit(theme_name)

    def create_theme(self):
        name, ok = QInputDialog.getText(self, "Новая тема", "Введите название темы:")
        if ok and name:
            new_theme = self.theme_manager.current_theme.copy()
            new_theme['name'] = name
            if self.theme_manager.save_custom_theme(new_theme):
                self.load_themes()
                QMessageBox.information(self, "Успех", f"Тема '{name}' создана")

    def delete_selected_theme(self):
        current = self.theme_list.currentItem()
        if not current:
            return
        theme_name = current.data(Qt.UserRole)
        if theme_name in [t['name'] for t in self.theme_manager.PRESET_THEMES.values()]:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить стандартные темы")
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить тему '{theme_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.theme_manager.delete_custom_theme(theme_name):
                self.load_themes()