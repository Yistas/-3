# -*- coding: utf-8 -*-

"""
Диалог настройки цветов для погодовки
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QColorDialog, QInputDialog,
                               QAbstractItemView, QLabel, QCheckBox, QWidget)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QBrush


class ColorSettingsDialog(QDialog):
    """Диалог для настройки цветов"""
    
    colors_changed = Signal()
    
    def __init__(self, color_settings, parent=None):
        super().__init__(parent)
        self.color_settings = color_settings
        self.setWindowTitle("Настройка цветов")
        self.setMinimumSize(800, 500)
        
        self.init_ui()
        self.load_current_colors()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("🎨 Настройка цветов для заливки ячеек")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 5px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Пояснение
        info = QLabel("Настройте цвета для заливки ячеек в погодовке.\n"
                      "Цвета с галочкой 'В легенде' отображаются в панели легенды.\n"
                      "Цвета с галочкой 'Считать %' участвуют в подсчете процентов.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Таблица цветов
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Цвет", "Название", "Код", "Описание", "Вкл.", "В легенде", "Считать %"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.table.itemDoubleClicked.connect(self.on_color_double_clicked)
        
        layout.addWidget(self.table)
        
        # Панель кнопок
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить цвет")
        add_btn.clicked.connect(self.add_color)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self.edit_color)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_color)
        button_layout.addWidget(delete_btn)
        
        reset_btn = QPushButton("🔄 Сбросить")
        reset_btn.clicked.connect(self.reset_colors)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # Кнопки OK/Отмена
        ok_btn = QPushButton("✅ OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setMinimumHeight(30)
        ok_btn.setMinimumWidth(80)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(30)
        cancel_btn.setMinimumWidth(80)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_current_colors(self):
        """Загружает текущие цвета из настроек в таблицу"""
        self.table.setRowCount(len(self.color_settings.colors))
        
        for row, (name, data) in enumerate(self.color_settings.colors.items()):
            # Цвет (образец)
            color_item = QTableWidgetItem("  ")
            color_item.setBackground(QBrush(QColor(data["code"])))
            color_item.setFlags(color_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, color_item)
            
            # Название
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, name)
            self.table.setItem(row, 1, name_item)
            
            # Код цвета
            code_item = QTableWidgetItem(data["code"])
            code_item.setFlags(code_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, code_item)
            
            # Описание
            desc_item = QTableWidgetItem(data.get("description", ""))
            self.table.setItem(row, 3, desc_item)
            
            # Включен
            enabled_check = QCheckBox()
            enabled_check.setChecked(data.get("enabled", True))
            enabled_check.setProperty("color_name", name)
            enabled_check.setProperty("setting", "enabled")
            enabled_check.stateChanged.connect(self.on_checkbox_toggled)
            
            enabled_widget = QWidget()
            enabled_layout = QHBoxLayout()
            enabled_layout.addWidget(enabled_check)
            enabled_layout.setAlignment(Qt.AlignCenter)
            enabled_layout.setContentsMargins(0, 0, 0, 0)
            enabled_widget.setLayout(enabled_layout)
            self.table.setCellWidget(row, 4, enabled_widget)
            
            # Показывать в легенде
            legend_check = QCheckBox()
            legend_check.setChecked(data.get("show_in_legend", True))
            legend_check.setProperty("color_name", name)
            legend_check.setProperty("setting", "show_in_legend")
            legend_check.stateChanged.connect(self.on_checkbox_toggled)
            
            legend_widget = QWidget()
            legend_layout = QHBoxLayout()
            legend_layout.addWidget(legend_check)
            legend_layout.setAlignment(Qt.AlignCenter)
            legend_layout.setContentsMargins(0, 0, 0, 0)
            legend_widget.setLayout(legend_layout)
            self.table.setCellWidget(row, 5, legend_widget)
            
            # Считать процент
            percent_check = QCheckBox()
            percent_check.setChecked(data.get("count_percentage", True))
            percent_check.setProperty("color_name", name)
            percent_check.setProperty("setting", "count_percentage")
            percent_check.stateChanged.connect(self.on_checkbox_toggled)
            
            percent_widget = QWidget()
            percent_layout = QHBoxLayout()
            percent_layout.addWidget(percent_check)
            percent_layout.setAlignment(Qt.AlignCenter)
            percent_layout.setContentsMargins(0, 0, 0, 0)
            percent_widget.setLayout(percent_layout)
            self.table.setCellWidget(row, 6, percent_widget)
        
        self.table.resizeColumnsToContents()

    def on_checkbox_toggled(self, state):
        """Обработчик переключения чекбокса"""
        checkbox = self.sender()
        if not checkbox:
            return
        
        color_name = checkbox.property("color_name")
        setting = checkbox.property("setting")
        
        if not color_name or not setting:
            return
        
        enabled = (state == 2)
        
        if setting == "enabled":
            self.color_settings.colors[color_name]["enabled"] = enabled
        elif setting == "show_in_legend":
            self.color_settings.colors[color_name]["show_in_legend"] = enabled
        elif setting == "count_percentage":
            self.color_settings.colors[color_name]["count_percentage"] = enabled
        
        self.colors_changed.emit()
    
    def on_color_double_clicked(self, item):
        """Обработчик двойного клика по ячейке"""
        row = item.row()
        color_name = self.table.item(row, 1).data(Qt.UserRole)
        self.edit_color(color_name)
    
    def edit_color(self, color_name=None):
        """Редактирует цвет"""
        if color_name is None:
            current_row = self.table.currentRow()
            if current_row < 0:
                QMessageBox.warning(self, "Предупреждение", "Выберите цвет для редактирования")
                return
            color_name = self.table.item(current_row, 1).data(Qt.UserRole)
        
        color_data = self.color_settings.colors.get(color_name)
        if not color_data:
            return
        
        # Выбор цвета
        current_color = QColor(color_data["code"])
        new_color = QColorDialog.getColor(current_color, self, f"Выберите цвет для {color_name}")
        
        if not new_color.isValid():
            return
        
        new_code = new_color.name()
        
        # Ввод описания
        new_desc, ok = QInputDialog.getText(
            self, "Описание цвета",
            f"Введите описание для цвета '{color_name}':",
            text=color_data.get("description", "")
        )
        
        if ok:
            # Обновляем в памяти
            self.color_settings.colors[color_name]["code"] = new_code
            self.color_settings.colors[color_name]["description"] = new_desc
            # Обновляем таблицу
            self.load_current_colors()
            self.colors_changed.emit()
            QMessageBox.information(self, "Успех", f"Цвет '{color_name}' обновлен")
    
# ===== gui/widgets/yearly_table/color_settings_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ МЕТОД add_color

    def add_color(self):
        """Добавляет новый цвет"""
        name, ok = QInputDialog.getText(self, "Новый цвет", "Введите название цвета:")
        if not ok or not name:
            return
        
        if name in self.color_settings.colors:
            QMessageBox.warning(self, "Предупреждение", f"Цвет '{name}' уже существует")
            return
        
        # Выбор цвета - первый аргумент цвет по умолчанию, второй родитель
        color = QColorDialog.getColor(QColor("#4a6fa5"), self, f"Выберите цвет для {name}")
        if not color.isValid():
            return
        
        code = color.name()
        
        desc, ok = QInputDialog.getText(self, "Описание цвета", f"Введите описание для цвета '{name}':")
        if not ok:
            desc = ""
        
        self.color_settings.colors[name] = {
            "code": code,
            "description": desc,
            "enabled": True,
            "show_in_legend": True,
            "count_percentage": True
        }
        self.load_current_colors()
        self.colors_changed.emit()
        QMessageBox.information(self, "Успех", f"Цвет '{name}' добавлен")

    def delete_color(self):
        """Удаляет выбранный цвет"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите цвет для удаления")
            return
        
        color_name = self.table.item(current_row, 1).data(Qt.UserRole)
        
        if color_name in self.color_settings.DEFAULT_COLORS:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить стандартные цвета")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить цвет '{color_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.color_settings.colors[color_name]
            self.load_current_colors()
            self.colors_changed.emit()
            QMessageBox.information(self, "Успех", f"Цвет '{color_name}' удален")
    
    def reset_colors(self):
        """Сбрасывает настройки цветов"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Сбросить все настройки цветов к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.color_settings.colors = self.color_settings.DEFAULT_COLORS.copy()
            self.load_current_colors()
            self.colors_changed.emit()
            QMessageBox.information(self, "Успех", "Настройки цветов сброшены")
    
    def accept(self):
        """Сохраняет настройки при нажатии OK"""
        self.color_settings.save_colors()
        self.colors_changed.emit()
        super().accept()
    
    def reject(self):
        """Отменяет изменения при нажатии Отмена"""
        self.color_settings.load_colors()
        self.load_current_colors()
        super().reject()