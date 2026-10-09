# -*- coding: utf-8 -*-

"""
Навигация по таблице закупок (скролл к началу/концу)
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QAbstractItemView
from PySide6.QtCore import Qt


class PurchasesNavigationMixin:
    """Примесь с методами навигации по таблице закупок"""
    
    def _create_navigation_panel(self):
        """Создаёт панель навигации с кнопками вверх/вниз и счётчиком"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(5)
        
        # Кнопка "Наверх"
        self.top_btn = QPushButton("▲")
        self.top_btn.setFixedSize(28, 28)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.top_btn.clicked.connect(self._scroll_to_top)
        nav_layout.addWidget(self.top_btn)
        
        # Кнопка "Вниз"
        self.bottom_btn = QPushButton("▼")
        self.bottom_btn.setFixedSize(28, 28)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.bottom_btn.clicked.connect(self._scroll_to_bottom)
        nav_layout.addWidget(self.bottom_btn)
        
        # Счётчик записей
        self.purchase_count_label = QLabel("Записей: 0")
        self.purchase_count_label.setStyleSheet("color: #666; font-size: 11px; padding: 0 10px;")
        nav_layout.addWidget(self.purchase_count_label)
        
        nav_layout.addStretch()
        nav_widget.setLayout(nav_layout)
        
        return nav_widget
    
    def _scroll_to_top(self):
        """Прокручивает таблицу закупок к первой строке"""
        if not hasattr(self, 'purchases_table') or self.purchases_table is None:
            return
        
        table = self.purchases_table
        model = table.model()
        
        if model.rowCount() == 0:
            return
        
        if hasattr(table, 'proxy_model'):
            first_index = table.proxy_model.mapFromSource(model.index(0, 0))
        else:
            first_index = model.index(0, 0)
        
        if first_index.isValid():
            table.scrollTo(first_index, QAbstractItemView.PositionAtTop)
            table.setCurrentIndex(first_index)
            table.selectRow(first_index.row())
    
    def _scroll_to_bottom(self):
        """Прокручивает таблицу закупок к последней строке"""
        if not hasattr(self, 'purchases_table') or self.purchases_table is None:
            return
        
        table = self.purchases_table
        model = table.model()
        
        row_count = model.rowCount()
        if row_count == 0:
            return
        
        last_row = row_count - 1
        if hasattr(table, 'proxy_model'):
            last_index = table.proxy_model.mapFromSource(model.index(last_row, 0))
        else:
            last_index = model.index(last_row, 0)
        
        if last_index.isValid():
            table.scrollTo(last_index, QAbstractItemView.PositionAtBottom)
            table.setCurrentIndex(last_index)
            table.selectRow(last_index.row())
    
    def _update_purchase_count(self, count):
        """Обновляет счётчик записей"""
        if hasattr(self, 'purchase_count_label'):
            self.purchase_count_label.setText(f"Записей: {count}")