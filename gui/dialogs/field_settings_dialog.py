# ===== gui/dialogs/field_settings_dialog.py =====

# -*- coding: utf-8 -*-

"""
Диалог управления всеми полями (стандартными и пользовательскими)
"""

import json
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QGroupBox, QAbstractItemView,
                               QWidget, QInputDialog, QComboBox, QLineEdit,
                               QTextEdit, QFormLayout, QCheckBox, QSpinBox,
                               QTabWidget)
from PySide6.QtCore import Qt, Signal


class FieldSettingsDialog(QDialog):
    """Диалог для управления всеми полями"""
    
    fields_changed = Signal()
    
    FIELD_TYPES = [
        ("Текст", "text"),
        ("Число", "number"),
        ("Дата", "date"),
        ("Флаг (Да/Нет)", "boolean"),
        ("Список", "list"),
        ("Многострочный текст", "textarea"),
    ]
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.FieldSettingsDialog')
        
        self.setWindowTitle("Управление полями")
        self.setMinimumSize(1100, 650)
        
        self.init_ui()
        self.load_fields()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📊 Управление полями монет")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Пояснение
        info = QLabel(
            "Здесь вы можете настраивать отображение всех полей монет.\n"
            "Можно скрывать/показывать поля, менять их названия и порядок."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Панель инструментов
        toolbar = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить поле")
        self.add_btn.clicked.connect(self.add_custom_field)
        toolbar.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_field)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_custom_field)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        self.reset_btn = QPushButton("🔄 Сбросить стандартные")
        self.reset_btn.clicked.connect(self.reset_standard_fields)
        toolbar.addWidget(self.reset_btn)
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_fields)
        toolbar.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Таблица полей
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Ключ", "Название", "Категория", "Тип", 
            "В таблице", "В форме", "В просмотре", "В редактировании", "Порядок"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.table)
        
        # Кнопки OK/Отмена
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_fields(self):
        """Загружает список полей в таблицу с чекбоксами"""
        try:
            fields = self.db_manager.get_all_field_settings()
            
            self.table.setRowCount(len(fields))
            self.table.setSortingEnabled(False)
            
            for row, field in enumerate(fields):
                # Ключ
                key_item = QTableWidgetItem(field.field_key)
                key_item.setData(Qt.UserRole, field.id)
                key_item.setData(Qt.UserRole + 1, field.is_standard)
                self.table.setItem(row, 0, key_item)
                
                # Название
                name_item = QTableWidgetItem(field.name)
                name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 1, name_item)
                
                # Категория
                cat_item = QTableWidgetItem(field.category or "—")
                self.table.setItem(row, 2, cat_item)
                
                # Тип
                type_name = "Текст"
                for t_name, t_value in self.FIELD_TYPES:
                    if t_value == field.field_type:
                        type_name = t_name
                        break
                type_item = QTableWidgetItem(type_name)
                type_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, type_item)
                
                # В таблице — чекбокс
                self._add_checkbox_to_table(row, 4, field.show_in_table, field.field_key, "show_in_table")
                
                # В форме — чекбокс
                self._add_checkbox_to_table(row, 5, field.show_in_form, field.field_key, "show_in_form")
                
                # В просмотре — чекбокс
                show_in_view = getattr(field, 'show_in_view', True)
                self._add_checkbox_to_table(row, 6, show_in_view, field.field_key, "show_in_view")
                
                # В редактировании — чекбокс
                show_in_edit = getattr(field, 'show_in_edit', True)
                self._add_checkbox_to_table(row, 7, show_in_edit, field.field_key, "show_in_edit")
                
                # Порядок
                order_item = QTableWidgetItem(str(field.sort_order))
                order_item.setTextAlignment(Qt.AlignCenter)
                order_item.setFlags(order_item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 8, order_item)
                
                # Подсветка для пользовательских полей
                if not field.is_standard:
                    for col in range(9):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(Qt.lightGray)
            
            self.table.setSortingEnabled(True)
            
            # Принудительно подгоняем ширину всех колонок
            for col in range(self.table.columnCount()):
                if col == 1:
                    # Для колонки "Название" вычисляем максимальную ширину текста
                    max_width = 150  # Минимальная ширина
                    font_metrics = self.table.fontMetrics()
                    for row in range(self.table.rowCount()):
                        item = self.table.item(row, col)
                        if item:
                            text_width = font_metrics.horizontalAdvance(item.text()) + 40
                            if text_width > max_width:
                                max_width = text_width
                    self.table.setColumnWidth(col, min(max_width, 500))
                else:
                    self.table.resizeColumnToContents(col)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки полей: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить поля: {e}")
    
    def _on_checkbox_toggled(self, state):
        """Обработчик переключения чекбокса в таблице"""
        checkbox = self.sender()
        if not checkbox:
            return
        
        field_key = checkbox.property("field_key")
        setting = checkbox.property("setting")
        
        if not field_key or not setting:
            return
        
        value = (state == 2)  # Qt.Checked = 2
        
        self.db_manager.update_field_settings(field_key, {setting: value})
        self.fields_changed.emit()
    
    def on_item_double_clicked(self, item):
        """Обработчик двойного клика для быстрого редактирования названия и порядка"""
        row = item.row()
        col = item.column()
        field_key = self.table.item(row, 0).text()
        
        if col == 1:  # Название
            new_name, ok = QInputDialog.getText(self, "Изменить название", 
                f"Новое название для поля '{field_key}':",
                text=item.text())
            if ok and new_name:
                self.db_manager.update_field_settings(field_key, {'name': new_name})
                self.load_fields()
                self.fields_changed.emit()
        
        elif col == 8:  # Порядок
            try:
                new_order, ok = QInputDialog.getInt(self, "Изменить порядок", 
                    f"Новый порядок для поля '{field_key}':",
                    value=int(item.text()) if item.text().isdigit() else 0, 
                    min=0, max=1000)
                if ok:
                    self.db_manager.update_field_settings(field_key, {'sort_order': new_order})
                    self.load_fields()
                    self.fields_changed.emit()
            except:
                pass
    
    def edit_field(self):
        """Редактирует выбранное поле"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите поле для редактирования")
            return
        
        field_key = self.table.item(current_row, 0).text()
        is_standard = self.table.item(current_row, 0).data(Qt.UserRole + 1)
        
        if is_standard:
            # Стандартное поле - только название и видимость
            current_name = self.table.item(current_row, 1).text()
            new_name, ok = QInputDialog.getText(self, "Редактирование поля", 
                f"Название поля '{field_key}':",
                text=current_name)
            if ok and new_name:
                self.db_manager.update_field_settings(field_key, {'name': new_name})
                self.load_fields()
                self.fields_changed.emit()
        else:
            # Пользовательское поле - полное редактирование
            field = self.db_manager.get_field_settings_by_id(
                self.table.item(current_row, 0).data(Qt.UserRole)
            )
            if field:
                dialog = CustomFieldEditDialog(self.db_manager, field, self)
                if dialog.exec():
                    self.load_fields()
                    self.fields_changed.emit()
    
    def add_custom_field(self):
        """Добавляет новое пользовательское поле"""
        dialog = CustomFieldEditDialog(self.db_manager, None, self)
        if dialog.exec():
            self.load_fields()
            self.fields_changed.emit()
            QMessageBox.information(self, "Успех", "Поле добавлено.\nПерезапустите программу для применения изменений.")
    
    def delete_custom_field(self):
        """Удаляет пользовательское поле"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите поле для удаления")
            return
        
        field_key = self.table.item(current_row, 0).text()
        is_standard = self.table.item(current_row, 0).data(Qt.UserRole + 1)
        
        if is_standard:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить стандартное поле")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить поле '{field_key}'?\n\n"
            f"Все данные в этом поле будут потеряны!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_custom_field_by_key(field_key)
                if success:
                    self.load_fields()
                    self.fields_changed.emit()
                    QMessageBox.information(self, "Успех", message)
                else:
                    QMessageBox.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить поле: {e}")
    
    def reset_standard_fields(self):
        """Сбрасывает настройки стандартных полей"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Сбросить настройки всех стандартных полей к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.reset_standard_fields()
                self.load_fields()
                self.fields_changed.emit()
                QMessageBox.information(self, "Успех", "Настройки стандартных полей сброшены")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сбросить настройки: {e}")


class CustomFieldEditDialog(QDialog):
    """Диалог добавления/редактирования пользовательского поля"""
    
    FIELD_TYPES = [
        ("Текст", "text"),
        ("Число", "number"),
        ("Дата", "date"),
        ("Флаг (Да/Нет)", "boolean"),
        ("Список", "list"),
        ("Многострочный текст", "textarea"),
    ]
    
    def __init__(self, db_manager, field=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.field = field
        self.is_edit = field is not None
        
        self.setWindowTitle("Редактирование поля" if self.is_edit else "Добавление поля")
        self.setMinimumWidth(500)
        
        self.init_ui()
        
        if self.is_edit:
            self.load_field_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        form_layout = QFormLayout()
        
        # Название
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Источник, Качество, Редкость")
        form_layout.addRow("Название*:", self.name_edit)
        
        # Ключ (только для новых полей)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("например: source, quality, rarity (латиница)")
        self.key_edit.setToolTip("Технический ключ поля (только латиница, без пробелов)")
        if not self.is_edit:
            form_layout.addRow("Ключ*:", self.key_edit)
        else:
            key_label = QLabel(self.field.field_key)
            form_layout.addRow("Ключ:", key_label)
        
        # Тип поля
        self.type_combo = QComboBox()
        for name, value in self.FIELD_TYPES:
            self.type_combo.addItem(name, value)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        form_layout.addRow("Тип поля:", self.type_combo)
        
        # Категория
        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("например: Дополнительные")
        form_layout.addRow("Категория:", self.category_edit)
        
        # Значение по умолчанию
        self.default_edit = QLineEdit()
        self.default_edit.setPlaceholderText("Значение по умолчанию")
        form_layout.addRow("Значение по умолчанию:", self.default_edit)
        
        # Опции для списка
        self.options_group = QGroupBox("Опции для списка")
        self.options_group.setVisible(False)
        options_layout = QVBoxLayout()
        
        self.options_edit = QTextEdit()
        self.options_edit.setPlaceholderText("Введите варианты списка (каждый с новой строки)")
        self.options_edit.setMaximumHeight(100)
        options_layout.addWidget(self.options_edit)
        
        self.options_group.setLayout(options_layout)
        form_layout.addRow(self.options_group)
        
        # Порядок
        self.order_spin = QSpinBox()
        self.order_spin.setRange(0, 1000)
        self.order_spin.setValue(0)
        form_layout.addRow("Порядок:", self.order_spin)
        
        # Чекбоксы для отображения
        self.show_in_table_check = QCheckBox("Показывать в таблице")
        self.show_in_table_check.setChecked(True)
        form_layout.addRow("", self.show_in_table_check)
        
        self.show_in_form_check = QCheckBox("Показывать в форме")
        self.show_in_form_check.setChecked(True)
        form_layout.addRow("", self.show_in_form_check)
        
        self.show_in_view_check = QCheckBox("Показывать в просмотре")
        self.show_in_view_check.setChecked(True)
        form_layout.addRow("", self.show_in_view_check)
        
        self.show_in_edit_check = QCheckBox("Показывать в редактировании")
        self.show_in_edit_check.setChecked(True)
        form_layout.addRow("", self.show_in_edit_check)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_field)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def on_type_changed(self, index):
        """Обработчик изменения типа поля"""
        field_type = self.type_combo.currentData()
        self.options_group.setVisible(field_type == "list")
    
    def load_field_data(self):
        """Загружает данные поля для редактирования"""
        if not self.field:
            return
        
        self.name_edit.setText(self.field.name)
        self.type_combo.setCurrentIndex(0)
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.field.field_type:
                self.type_combo.setCurrentIndex(i)
                break
        
        self.category_edit.setText(self.field.category or "")
        self.default_edit.setText(self.field.default_value or "")
        
        if self.field.options:
            try:
                options = json.loads(self.field.options)
                self.options_edit.setText("\n".join(options))
            except:
                pass
        
        self.order_spin.setValue(self.field.sort_order or 0)
        self.show_in_table_check.setChecked(self.field.show_in_table)
        self.show_in_form_check.setChecked(self.field.show_in_form)
        self.show_in_view_check.setChecked(getattr(self.field, 'show_in_view', True))
        self.show_in_edit_check.setChecked(getattr(self.field, 'show_in_edit', True))
    
    def save_field(self):
        """Сохраняет поле"""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название поля")
            return
        
        if not self.is_edit:
            key = self.key_edit.text().strip()
            if not key:
                QMessageBox.warning(self, "Предупреждение", "Введите ключ поля")
                return
            
            import re
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', key):
                QMessageBox.warning(self, "Предупреждение", 
                    "Ключ должен начинаться с буквы и содержать только латиницу, цифры и подчеркивание")
                return
        else:
            key = self.field.field_key
        
        field_type = self.type_combo.currentData()
        
        options = None
        if field_type == "list":
            opts = [o.strip() for o in self.options_edit.toPlainText().strip().split('\n') if o.strip()]
            if opts:
                options = json.dumps(opts, ensure_ascii=False)
        
        data = {
            'name': name,
            'field_key': key,
            'field_type': field_type,
            'category': self.category_edit.text().strip() or None,
            'default_value': self.default_edit.text().strip() or None,
            'options': options,
            'sort_order': self.order_spin.value(),
            'show_in_table': self.show_in_table_check.isChecked(),
            'show_in_form': self.show_in_form_check.isChecked(),
            'show_in_view': self.show_in_view_check.isChecked(),
            'show_in_edit': self.show_in_edit_check.isChecked(),
            'is_standard': False
        }
        
        try:
            if self.is_edit:
                self.db_manager.update_field_settings(key, data)
                QMessageBox.information(self, "Успех", "Поле обновлено")
            else:
                self.db_manager.add_custom_field(data)
                QMessageBox.information(self, "Успех", "Поле добавлено")
            
            self.accept()
        except Exception as e:
            logging.getLogger('CoinCollector.GUI.FieldSettingsDialog').error(f"Ошибка сохранения поля: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить поле: {e}")