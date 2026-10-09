# -*- coding: utf-8 -*-

"""
Общий виджет для выбора и отображения изображений
"""

import os
from PySide6.QtWidgets import QLabel, QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class ImageSelector(QLabel):
    """Виджет для выбора и отображения изображения"""

    def __init__(self, parent=None, image_type="", editable=True):
        super().__init__(parent)
        self.image_type = image_type
        self.image_path = None
        self.editable = editable
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setMaximumSize(100, 100)
        self.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 2px dashed #ccc;
                border-radius: 5px;
                padding: 2px;
            }
            QLabel:hover {
                background-color: #e9ecef;
                border-color: #4a6fa5;
            }
        """)
        if editable:
            self.setText("📷\nНажмите\nдля загрузки")
            self.setToolTip(f"Нажмите для загрузки изображления {image_type}")
        else:
            self.setText("📷\nНет фото")

    def mousePressEvent(self, event):
        if not self.editable:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Выберите изображение {self.image_type}",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*.*)"
        )

        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path):
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                95, 95,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            self.image_path = file_path
            self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(file_path)}\nНажмите для замены")

    def clear_image(self):
        self.clear()
        self.image_path = None
        if self.editable:
            self.setText("📷\nНажмите\nдля загрузки")
            self.setToolTip(f"Нажмите для загрузки изображения {self.image_type}")
        else:
            self.setText("📷\nНет фото")

    def get_image_path(self):
        return self.image_path

    def set_image_from_path(self, image_path):
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    95, 95,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(scaled_pixmap)
                self.image_path = image_path
                self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(image_path)}")
                return True
        return False
