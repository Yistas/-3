# -*- coding: utf-8 -*-

"""
Навигация по таблице продаж (заглушка)
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt


class SalesNavigationMixin:
    """Примесь с методами навигации"""
    
    def _create_navigation_panel(self):
        nav_widget = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_widget.setLayout(nav_layout)
        return nav_widget
    
    def _scroll_to_top(self):
        pass
    
    def _scroll_to_bottom(self):
        pass