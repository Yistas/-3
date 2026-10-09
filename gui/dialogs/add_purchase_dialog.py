# -*- coding: utf-8 -*-

"""
Диалог добавления новой закупки серебра
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QLineEdit, QDateEdit, QDoubleSpinBox, QSpinBox, QLabel, QWidget,
    QMessageBox
)
from PySide6.QtCore import Qt, QDate


class AddPurchaseDialog(QDialog):
    """Диалог добавления новой закупки с созданием монет"""

    def __init__(self, parent=None, existing_numbers=None):
        super().__init__(parent)
        self.existing_numbers = existing_numbers or set()
        self.setWindowTitle("➕ Новая закупка серебра")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.setLayout(layout)

        title = QLabel("➕ Новая закупка серебра")
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

        form_widget = QWidget()
        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(5, 5, 5, 5)
        form_widget.setLayout(form_layout)

        # Дата
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        form_layout.addRow("📅 Дата:", self.date_edit)

        # №ЗакAG (автоматически)
        self.number_ag_edit = QLineEdit()
        self.number_ag_edit.setReadOnly(True)
        self.number_ag_edit.setStyleSheet("background-color: #f0f0f0;")
        form_layout.addRow("🏷️ №ЗакAG:", self.number_ag_edit)

        # №Зак
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("например: 001")
        self.number_edit.textChanged.connect(self.on_number_changed)
        form_layout.addRow("🔢 №Зак*:", self.number_edit)

        self.number_warning = QLabel()
        self.number_warning.setStyleSheet("color: #dc3545; font-size: 10px;")
        self.number_warning.hide()
        form_layout.addRow("", self.number_warning)

        # Откуда
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Источник закупки")
        form_layout.addRow("📍 Откуда:", self.source_edit)

        # Сумма закупки
        self.purchase_sum_edit = QDoubleSpinBox()
        self.purchase_sum_edit.setRange(0, 10000000)
        self.purchase_sum_edit.setPrefix("₽ ")
        self.purchase_sum_edit.setDecimals(2)
        self.purchase_sum_edit.setMinimumHeight(30)
        form_layout.addRow("💰 Сумма закупки:", self.purchase_sum_edit)

        # Количество монет
        self.quantity_edit = QSpinBox()
        self.quantity_edit.setRange(1, 10000)
        self.quantity_edit.setValue(1)
        self.quantity_edit.setMinimumHeight(30)
        form_layout.addRow("🔢 Количество монет:", self.quantity_edit)

        # MIN цена (автоматически)
        self.min_price_label = QLabel("—")
        self.min_price_label.setStyleSheet("color: #666; font-weight: bold;")
        form_layout.addRow("💰 MIN цена:", self.min_price_label)

        # Обновление MIN цены
        def update_min_price():
            total = self.purchase_sum_edit.value()
            qty = self.quantity_edit.value()
            if qty > 0 and total > 0:
                min_price = total / qty
                self.min_price_label.setText(f"{min_price:.2f} ₽ за монету")
                self.min_price_label.setStyleSheet("color: #28a745; font-weight: bold;")
            else:
                self.min_price_label.setText("—")
                self.min_price_label.setStyleSheet("color: #666; font-weight: bold;")

        self.purchase_sum_edit.valueChanged.connect(update_min_price)
        self.quantity_edit.valueChanged.connect(update_min_price)

        layout.addWidget(form_widget)

        # Кнопки
        button_layout = QHBoxLayout()

        self.ok_btn = QPushButton("✅ Создать")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setMinimumHeight(35)
        self.ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.ok_btn)

        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def on_number_changed(self):
        number = self.number_edit.text().strip()
        if number and number in self.existing_numbers:
            self.number_warning.setText(f"⚠️ Закупка с №{number} уже существует!")
            self.number_warning.show()
            self.ok_btn.setEnabled(False)
        else:
            self.number_warning.hide()
            self.ok_btn.setEnabled(True)

    def get_data(self):
        return {
            'date': self.date_edit.date().toPython(),
            'number_ag': self.number_ag_edit.text().strip(),
            'number': self.number_edit.text().strip(),
            'source': self.source_edit.text().strip(),
            'purchase_sum': self.purchase_sum_edit.value(),
            'quantity': self.quantity_edit.value(),
            'min_price': self.purchase_sum_edit.value() / self.quantity_edit.value() if self.quantity_edit.value() > 0 else 0,
        }