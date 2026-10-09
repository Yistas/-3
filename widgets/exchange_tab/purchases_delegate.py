# ===== gui/widgets/exchange_tab/purchases_delegate.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Делегат для редактирования ячеек таблицы закупок (с поддержкой вставки)
"""

import logging
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit
from PySide6.QtCore import Qt, QTimer


class PurchaseDelegate(QStyledItemDelegate):
    """Делегат для редактирования ячеек таблицы закупок"""
    
    COLUMN_KEYS = [
        'in_collection', 'collection_price', 'purchase_number', 'purchase_batch',
        'country', 'continent', 'denomination', 'currency', 'year',
        'location_found', 'quantity', 'comments', 'ucoin_exchange',
        'sold_count', 'sold_sum'
    ]
    
    # Типы колонок для правильного преобразования
    COLUMN_TYPES = {
        'in_collection': 'bool',
        'collection_price': 'float',
        'purchase_number': 'str',
        'purchase_batch': 'str',
        'country': 'str',
        'continent': 'str',
        'denomination': 'str',
        'currency': 'str',
        'year': 'int',
        'location_found': 'str',
        'quantity': 'int',
        'comments': 'str',
        'ucoin_exchange': 'int',
        'sold_count': 'str',
        'sold_sum': 'float',
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = None
        self.logger = logging.getLogger('CoinCollector.GUI.PurchaseDelegate')
    
    def set_parent_tab(self, tab):
        self._parent_tab = tab
    
    def createEditor(self, parent, option, index):
        """Создаёт редактор для ячейки"""
        editor = QLineEdit(parent)
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        editor.selectAll()
        editor.setFocus()
        
        # Подключаем сигнал для сохранения при потере фокуса
        editor.editingFinished.connect(lambda: self._commit_data(editor, index))
        
        return editor
    
    def _commit_data(self, editor, index):
        """Сохраняет данные из редактора"""
        if not editor or not self._parent_tab:
            return
        
        new_value = editor.text().strip()
        old_value = index.data(Qt.DisplayRole) or ""
        
        if new_value != old_value:
            # Получаем все выделенные индексы для массового редактирования
            table = self._parent_tab.purchases_table
            selected_indexes = table.selectionModel().selectedIndexes()
            
            if len(selected_indexes) > 1:
                # Массовое редактирование
                self._apply_mass_edit(selected_indexes, new_value)
            else:
                # Одиночное редактирование
                self._apply_single_edit(index, new_value)
        
        # Удаляем редактор
        editor.deleteLater()
    
    def _apply_single_edit(self, index, new_value):
        """Применяет одиночное редактирование"""
        row = index.row()
        source_model = self._parent_tab.model
        
        # Получаем purchase через get_purchase (учитывает фильтры)
        purchase = source_model.get_purchase(row)
        
        if purchase:
            col = index.column()
            column_key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
            if column_key:
                # Преобразуем значение в правильный тип
                converted_value = self._convert_value(column_key, new_value)
                self.logger.info(f"DELEGATE: single edit {column_key} = '{new_value}' -> {converted_value}")
                self._parent_tab._on_cell_edited(purchase, column_key, converted_value)
                
                # Немедленно обновляем отображение
                source_model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ForegroundRole])
    
    def _apply_mass_edit(self, selected_indexes, new_value):
        """Применяет массовое редактирование"""
        source_model = self._parent_tab.model
        changed_purchases = []
        
        for idx in selected_indexes:
            if idx.isValid():
                row = idx.row()
                purchase = source_model.get_purchase(row)
                if purchase and purchase not in changed_purchases:
                    col = idx.column()
                    column_key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                    if column_key:
                        # Преобразуем значение в правильный тип
                        converted_value = self._convert_value(column_key, new_value)
                        self.logger.info(f"DELEGATE: mass edit {column_key} = '{new_value}' -> {converted_value}")
                        self._parent_tab._on_cell_edited(purchase, column_key, converted_value)
                        changed_purchases.append(purchase)
        
        # Оповещаем модель о массовом изменении
        if selected_indexes:
            top_left = selected_indexes[0]
            bottom_right = selected_indexes[-1]
            source_model.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole])
    
    def _convert_value(self, column_key, value):
        """Преобразует значение в правильный тип для колонки"""
        if not value:
            if column_key in ['in_collection', 'ucoin_exchange']:
                return False
            if column_key in ['quantity']:
                return 1
            return None
        
        col_type = self.COLUMN_TYPES.get(column_key, 'str')
        
        if col_type == 'bool':
            # Для колонки in_collection
            if value in ['✅', 'True', 'true', '1', 'Да', 'yes']:
                return True
            elif value in ['❌', 'False', 'false', '0', 'Нет', 'no', '']:
                return False
            else:
                # Если значение не распознано, пробуем как число
                try:
                    num_val = int(value)
                    return num_val != 0
                except:
                    return False
        
        elif col_type == 'int':
            try:
                return int(float(value))
            except:
                return None
        
        elif col_type == 'float':
            try:
                # Заменяем запятую на точку
                return float(value.replace(',', '.'))
            except:
                return None
        
        else:
            return value if value else None
    
    def setEditorData(self, editor, index):
        """Устанавливает данные в редактор из модели"""
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
    
    def setModelData(self, editor, model, index):
        """Сохраняет данные из редактора в модель (вызывается при редактировании)"""
        new_value = editor.text().strip()
        old_value = index.data(Qt.DisplayRole) or ""
        
        if new_value != old_value and self._parent_tab:
            row = index.row()
            purchase = model.get_purchase(row)
            if purchase:
                col = index.column()
                column_key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                if column_key:
                    # Преобразуем значение в правильный тип
                    converted_value = self._convert_value(column_key, new_value)
                    self.logger.info(f"DELEGATE: setModelData {column_key} = '{new_value}' -> {converted_value}")
                    self._parent_tab._on_cell_edited(purchase, column_key, converted_value)