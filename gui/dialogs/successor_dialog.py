# -*- coding: utf-8 -*-
"""
Диалог «Историческая преемственность стран».
Связи хранятся ПО НАЗВАНИЯМ в таблице country_successor_links:
страны-преемники НЕ создаются в БД и НЕ попадают в дерево стран —
они используются только для отображения территорий на карте.
"""
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget,
                               QGroupBox, QMessageBox, QTableWidget,
                               QTableWidgetItem, QHeaderView,
                               QAbstractItemView, QSplitter, QWidget,
                               QGridLayout)
from PySide6.QtCore import Qt, Signal
from database.models import Country

try:
    from utils.historical_countries import MODERN_COUNTRIES_RU_TO_EN
except Exception:
    MODERN_COUNTRIES_RU_TO_EN = {}

ID_COL_WIDTH = 50


class SuccessorDialog(QDialog):
    """Диалог управления множественными связями стран-преемников"""
    data_updated = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.SuccessorDialog')
        self.db_manager = db_manager
        self.current_country_id = None
        self.setWindowTitle("Историческая преемственность стран")
        self.setMinimumSize(1000, 700)
        layout = QVBoxLayout()
        self.setLayout(layout)
        title_label = QLabel("🏛️ Историческая преемственность стран")
        title_label.setStyleSheet("""
            font-weight: bold; font-size: 16px; padding: 8px;
            background-color: #4a6fa5; color: white; border-radius: 3px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        info_label = QLabel(
            "Одной исчезнувшей стране можно назначить НЕСКОЛЬКО преемников.\n"
            "Выделите их в правой таблице (Ctrl/Shift+клик) и нажмите\n"
            "«🔗 Установить связь» (заменить список) или "
            "«➕ Добавить выбранных» (дополнить список).\n"
            "Преемники не создаются в коллекции — они нужны только для карты."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info_label)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.addWidget(self.create_extinct_panel())
        splitter.addWidget(self.create_modern_panel())
        splitter.setSizes([480, 520])
        layout.addWidget(splitter)
        layout.addWidget(self.create_control_panel())
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        close_btn.setMinimumWidth(100)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)
        self.load_data()

    # ================= ПАНЕЛИ =================
    def create_extinct_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        title = QLabel("🏚️ Исчезнувшие страны")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; "
                            "background-color: #dc3545; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        self.extinct_table = QTableWidget()
        self.extinct_table.setColumnCount(3)
        self.extinct_table.setHorizontalHeaderLabels(["ID", "Страна", "Преемники"])
        header = self.extinct_table.horizontalHeader()
        # Ширины как на эталоне: ID узкая фикс., Страна и Преемники растягиваются
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.extinct_table.setColumnWidth(0, ID_COL_WIDTH)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.extinct_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extinct_table.setAlternatingRowColors(True)
        self.extinct_table.itemClicked.connect(self.on_extinct_selected)
        layout.addWidget(self.extinct_table)
        return panel

    def create_modern_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        title = QLabel("🌍 Все современные страны (преемники)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; "
                            "background-color: #28a745; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        self.modern_table = QTableWidget()
        self.modern_table.setColumnCount(2)
        self.modern_table.setHorizontalHeaderLabels(["ID", "Страна"])
        header = self.modern_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.modern_table.setColumnWidth(0, ID_COL_WIDTH)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.modern_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.modern_table.setAlternatingRowColors(True)
        self.modern_table.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.modern_table)
        selected_group = QGroupBox("Выбранные преемники")
        selected_layout = QVBoxLayout()
        self.selected_list = QListWidget()
        self.selected_list.setMaximumHeight(100)
        selected_layout.addWidget(self.selected_list)
        selected_group.setLayout(selected_layout)
        layout.addWidget(selected_group)
        return panel

    def create_control_panel(self):
        panel = QGroupBox("Управление связями")
        layout = QGridLayout()
        layout.addWidget(QLabel("Текущая страна:"), 0, 0)
        self.current_country_label = QLabel("—")
        self.current_country_label.setStyleSheet("font-weight: bold; color: #4a6fa5;")
        layout.addWidget(self.current_country_label, 0, 1)
        layout.addWidget(QLabel("Текущие преемники:"), 1, 0)
        self.current_successors_label = QLabel("—")
        self.current_successors_label.setWordWrap(True)
        layout.addWidget(self.current_successors_label, 1, 1)
        button_layout = QHBoxLayout()
        self.link_btn = QPushButton("🔗 Установить связь (заменить)")
        self.link_btn.clicked.connect(self.link_countries)
        self.link_btn.setMinimumHeight(35)
        self.link_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.link_btn)
        self.add_btn = QPushButton("➕ Добавить выбранных")
        self.add_btn.clicked.connect(self.add_successors)
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        button_layout.addWidget(self.add_btn)
        self.remove_btn = QPushButton("🗑️ Удалить выбранного")
        self.remove_btn.clicked.connect(self.remove_selected_successor)
        self.remove_btn.setMinimumHeight(35)
        self.remove_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        button_layout.addWidget(self.remove_btn)
        self.clear_btn = QPushButton("🔄 Очистить все")
        self.clear_btn.clicked.connect(self.clear_successors)
        self.clear_btn.setMinimumHeight(35)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout, 2, 0, 1, 2)
        panel.setLayout(layout)
        return panel

    # ================= СЛУЖЕБНЫЕ =================
    def _successor_names_for(self, country):
        """Названия преемников: таблица связей + старое отношение (объединение)."""
        names = []
        try:
            for n in (self.db_manager.get_successor_names(country.id) or []):
                if n not in names:
                    names.append(n)
        except Exception:
            pass
        try:
            for s in (country.successors or []):
                nm = getattr(s, 'name', None) or str(s)
                if nm and nm not in names:
                    names.append(nm)
        except Exception:
            pass
        return names

    # ================= ДАННЫЕ =================
    def load_data(self):
        try:
            countries = self.db_manager.get_all_countries()
            extinct_countries = [c for c in countries if c.is_extinct]
            self.extinct_table.setRowCount(len(extinct_countries))
            for row, country in enumerate(extinct_countries):
                id_item = QTableWidgetItem(str(country.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, country.id)
                self.extinct_table.setItem(row, 0, id_item)
                name_item = QTableWidgetItem(country.name)
                name_item.setData(Qt.UserRole, country.id)
                self.extinct_table.setItem(row, 1, name_item)
                names = self._successor_names_for(country)
                succ_item = QTableWidgetItem(', '.join(names))
                succ_item.setData(Qt.UserRole, names)
                self.extinct_table.setItem(row, 2, succ_item)
            # === ПРАВАЯ ТАБЛИЦА: справочник + страны коллекции + уже связанные ===
            names_set = set(MODERN_COUNTRIES_RU_TO_EN.keys())
            id_by_name = {}
            for c in countries:
                if not c.is_extinct:
                    names_set.add(c.name)
                    id_by_name[c.name] = c.id
            for c in extinct_countries:
                for n in self._successor_names_for(c):
                    names_set.add(n)
            names = sorted(names_set)
            self.modern_table.setRowCount(len(names))
            for row, name in enumerate(names):
                cid = id_by_name.get(name)
                id_item = QTableWidgetItem(str(cid) if cid else '—')
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, cid if cid else -1)
                id_item.setData(Qt.UserRole + 1, name)
                self.modern_table.setItem(row, 0, id_item)
                name_item = QTableWidgetItem(name)
                name_item.setData(Qt.UserRole, cid if cid else -1)
                name_item.setData(Qt.UserRole + 1, name)
                if cid is None:
                    name_item.setToolTip(
                        "Страны нет в коллекции — будет использована только для карты")
                self.modern_table.setItem(row, 1, name_item)
            self.extinct_table.resizeColumnsToContents()
            self.modern_table.resizeColumnsToContents()
            # Возвращаем фиксированную ширину ID после resizeColumnsToContents
            self.extinct_table.setColumnWidth(0, ID_COL_WIDTH)
            self.modern_table.setColumnWidth(0, ID_COL_WIDTH)
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {e}")

    def on_extinct_selected(self, item):
        row = item.row()
        self.current_country_id = self.extinct_table.item(row, 0).data(Qt.UserRole)
        country_name = self.extinct_table.item(row, 1).text()
        self.current_country_label.setText(country_name)
        country = self.db_manager.session.query(Country).get(self.current_country_id)
        self.modern_table.clearSelection()
        self.selected_list.clear()
        names = self._successor_names_for(country) if country else []
        if names:
            self.current_successors_label.setText(", ".join(names))
            for r in range(self.modern_table.rowCount()):
                it = self.modern_table.item(r, 1)
                if it and it.text() in names:
                    self.modern_table.selectRow(r)
                    self.selected_list.addItem(it.text())
        else:
            self.current_successors_label.setText("—")

    def _selected_modern_names(self):
        names = []
        for row in self.modern_table.selectionModel().selectedRows():
            it = self.modern_table.item(row.row(), 1)
            if it:
                names.append(it.text())
        return names

    # ================= ДЕЙСТВИЯ =================
    def link_countries(self):
        """ЗАМЕНЯЕТ список преемников на выбранный (страны НЕ создаются)."""
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите исчезнувшую страну")
            return
        names = self._selected_modern_names()
        if not names:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите одну или несколько стран-преемников")
            return
        extinct_name = self.extinct_table.item(self.extinct_table.currentRow(), 1).text()
        msg = (f"Установить связь:\n{extinct_name} → {', '.join(names)}?\n\n"
               f"Все монеты {extinct_name} будут отображаться на карте как эти страны.")
        reply = QMessageBox.question(self, "Подтверждение", msg,
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db_manager.set_successor_names(
                self.current_country_id, names)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.data_updated.emit()
                self.load_data()
                self.select_extinct_country(self.current_country_id)
            else:
                QMessageBox.critical(self, "Ошибка", message)

    def add_successors(self):
        """ДОБАВЛЯЕТ всех выбранных преемников к имеющимся (страны НЕ создаются)."""
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите исчезнувшую страну")
            return
        names = self._selected_modern_names()
        if not names:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите одну или несколько стран-преемников")
            return
        success, message = self.db_manager.add_successor_names(
            self.current_country_id, names)
        if success:
            QMessageBox.information(self, "Успех", message)
            self.data_updated.emit()
            self.load_data()
            self.select_extinct_country(self.current_country_id)
        else:
            QMessageBox.warning(self, "Предупреждение", message)

    def remove_selected_successor(self):
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите исчезнувшую страну")
            return
        current_item = self.selected_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите преемника для удаления")
            return
        succ_name = current_item.text()
        success, message = self.db_manager.remove_successor_name(
            self.current_country_id, succ_name)
        if success:
            QMessageBox.information(self, "Успех", message)
            self.data_updated.emit()
            self.load_data()
            self.select_extinct_country(self.current_country_id)
        else:
            QMessageBox.warning(self, "Предупреждение", message)

    def clear_successors(self):
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите исчезнувшую страну")
            return
        reply = QMessageBox.question(self, "Подтверждение",
                                     "Удалить всех преемников для этой страны?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db_manager.set_successor_names(
                self.current_country_id, [])
            if success:
                QMessageBox.information(self, "Успех", message)
                self.data_updated.emit()
                self.load_data()

    def select_extinct_country(self, country_id):
        for row in range(self.extinct_table.rowCount()):
            if self.extinct_table.item(row, 0).data(Qt.UserRole) == country_id:
                self.extinct_table.selectRow(row)
                self.on_extinct_selected(self.extinct_table.item(row, 0))
                break