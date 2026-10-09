# -*- coding: utf-8 -*-

"""
Методы MainWindow для работы с панелями
"""

from PySide6.QtWidgets import QMessageBox, QInputDialog, QApplication
from PySide6.QtCore import Qt, QTimer


class PanelHandlersMixin:
    """Примесь с методами управления панелями"""
    
    def toggle_right_panel(self):
        """Скрывает или показывает правую панель"""
        if self.right_panel_visible:
            sizes = self.main_splitter.sizes()
            self.left_panel_size = sizes[0]
            self.center_panel_size = sizes[1]
            self.right_panel_size = sizes[2]
            
            self.right_panel.hide()
            self.right_panel_visible = False
            
            self.table_panel.update_toggle_panel_action(False)
            
            self.save_settings()
            self.status_bar.showMessage("Правая панель скрыта", 2000)
        else:
            self.right_panel.show()
            self.right_panel_visible = True
            
            self.main_splitter.setSizes([self.left_panel_size, self.center_panel_size, self.right_panel_size])
            
            self.table_panel.update_toggle_panel_action(True)
            
            self.save_settings()
            self.status_bar.showMessage("Правая панель показана", 2000)
    
    def on_splitter_moved(self, pos, index):
        """Обработчик изменения размера сплиттера"""
        if self._updating_splitter:
            return
        
        self._updating_splitter = True
        try:
            sizes = self.main_splitter.sizes()
            if index == 0 and sizes[0] != self.left_panel_size:
                sizes[0] = self.left_panel_size
                self.main_splitter.setSizes(sizes)
            elif index == 2 and sizes[2] != self.right_panel_size:
                sizes[2] = self.right_panel_size
                self.main_splitter.setSizes(sizes)
        finally:
            self._updating_splitter = False
    
    def configure_columns(self):
        """Открывает диалог настройки колонок"""
        if hasattr(self, 'table_panel'):
            self.table_panel._configure_columns()
        else:
            from gui.dialogs.column_selector import ColumnSelectorDialog
            current_keys = [col["key"] for col in self.table_panel.current_columns] if self.table_panel.current_columns else []
            dialog = ColumnSelectorDialog(self, current_keys)
            if dialog.exec():
                selected_columns = dialog.get_selected_columns()
                if selected_columns:
                    self.table_panel._apply_column_settings(selected_columns)
    
    def manage_custom_fields(self):
        """Открывает диалог управления пользовательскими полями"""
        from gui.dialogs.custom_fields_dialog import CustomFieldsDialog
        dialog = CustomFieldsDialog(self.db_manager, self)
        dialog.fields_changed.connect(self.on_custom_fields_changed)
        if dialog.exec():
            self.on_custom_fields_changed()
    
    def on_custom_fields_changed(self):
        """Обработчик изменения пользовательских полей"""
        if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'table'):
            for i, col in enumerate(self.table_panel.current_columns):
                if i < self.table_panel.table.columnCount():
                    col['width'] = self.table_panel.table.columnWidth(i)
        
        if hasattr(self, 'table_panel'):
            self.table_panel.refresh_columns()
        
        if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'table'):
            for i, col in enumerate(self.table_panel.current_columns):
                if i < self.table_panel.table.columnCount():
                    width = col.get('width', 100)
                    if width > 0:
                        self.table_panel.table.setColumnWidth(i, width)
        
        self.status_bar.showMessage("✅ Пользовательские поля обновлены", 3000)
    
    def add_custom_level(self):
        """Добавляет новый пользовательский уровень (папку) в дерево"""
        level_name, ok = QInputDialog.getText(self, "Новый уровень", "Введите название нового уровня:")
        if ok and level_name:
            if self.country_tree.add_custom_level(level_name):
                self.status_bar.showMessage(f"Уровень '{level_name}' добавлен", 3000)
                self.settings_manager.save_tree_structure(self.country_tree)
    
    def delete_custom_level(self):
        """Удаляет выбранный пользовательский уровень"""
        current_item = self.country_tree.currentItem()
        if self.country_tree.delete_custom_level(current_item):
            self.status_bar.showMessage("Уровень удален", 3000)
            self.settings_manager.save_tree_structure(self.country_tree)
    
    def expand_all_tree(self):
        """Разворачивает все элементы дерева"""
        self.country_tree.expand_all()
        self.status_bar.showMessage("Все уровни развернуты", 2000)
    
    def collapse_all_tree(self):
        """Сворачивает все элементы дерева"""
        self.country_tree.collapse_all()
        self.status_bar.showMessage("Все уровни свернуты", 2000)