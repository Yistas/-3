# ===== gui/widgets/detail_panel/base_panel.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ
# -*- coding: utf-8 -*-
"""
Базовые классы для панели деталей (тёмная тема)
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QLabel, QSizePolicy, QFileDialog, QDialog,
                               QVBoxLayout, QHBoxLayout, QTextEdit,
                               QPushButton, QMessageBox, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QPixmap, QResizeEvent, QFont


def _get_theme():
    """Возвращает словарь текущей темы из главного окна"""
    try:
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                return widget.theme_manager.current_theme
    except Exception:
        pass
    return {}


class ImageLabel(QLabel):
    """Кастомный QLabel для изображений с автоматическим масштабированием"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(40, 40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        t = _get_theme()
        self.setStyleSheet(f"""
            background-color: {t.get('surface', '#16213e')};
            border: 1px solid {t.get('border', '#2a2a4a')};
            border-radius: 2px;
        """)

    def setPixmap(self, pixmap):
        """Сохраняет оригинал и масштабирует под текущий размер"""
        self.original_pixmap = pixmap
        self.update_display()

    def clear(self):
        """ПОЛНАЯ очистка: сбрасывает и сохранённый оригинал,
        чтобы старая картинка не «всплывала» при перерисовке/ресайзе"""
        self.original_pixmap = None
        super().clear()

    def update_display(self):
        """Перерисовка с масштабированием под текущий размер виджета"""
        if self.original_pixmap and not self.original_pixmap.isNull():
            w = max(20, self.width() - 6)
            h = max(20, self.height() - 6)
            scaled = self.original_pixmap.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()

class ImageSelector(QLabel):
    """Виджет для выбора и отображения изображения с поддержкой Drag & Drop"""
    image_changed = Signal(str)

    def __init__(self, parent=None, image_type="", editable=True):
        super().__init__(parent)
        self.image_type = image_type
        self.image_path = None
        self.editable = editable
        self.current_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setMaximumSize(100, 100)
        self._apply_base_style()
        if editable:
            self.setText("📷\nНажмите\nдля загрузки\nили перетащите")
            self.setToolTip(f"Нажмите для загрузки изображения {image_type}\nИли перетащите файл сюда")
            self.setAcceptDrops(True)
        else:
            self.setText("📷\nНет фото")
            self.setVisible(True)

    def _apply_base_style(self):
        """Базовый стиль (тёмный)"""
        t = _get_theme()
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {t.get('surface', '#16213e')};
                border: 2px dashed {t.get('scrollbar_handle', '#3a3a5a')};
                border-radius: 5px;
                padding: 2px;
                color: {t.get('tab_text', '#8888aa')};
            }}
            QLabel:hover {{
                background-color: {t.get('surface_hover', '#1f2b47')};
                border-color: {t.get('accent', '#6c63ff')};
            }}
        """)

    def dragEnterEvent(self, event):
        if not self.editable:
            return
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self._is_image_file(urls[0].toLocalFile()):
                event.acceptProposedAction()
                t = _get_theme()
                self.setStyleSheet(f"""
                    QLabel {{
                        background-color: {t.get('surface_hover', '#1f2b47')};
                        border: 2px solid {t.get('accent', '#6c63ff')};
                        border-radius: 5px;
                        padding: 2px;
                        color: {t.get('text', '#e4e4ef')};
                    }}
                """)

    def dragLeaveEvent(self, event):
        self._apply_base_style()

    def dropEvent(self, event):
        """Обработчик Drop события"""
        if not self.editable:
            return
        self._apply_base_style()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self._is_image_file(file_path):
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    self.current_pixmap = pixmap
                    self.image_path = file_path
                    scaled_pixmap = pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.setPixmap(scaled_pixmap)
                    self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(file_path)}\n"
                                    f"Размер: {pixmap.width()}x{pixmap.height()}")
                    self.image_changed.emit(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _is_image_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        return ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']

    def mousePressEvent(self, event):
        if not self.editable:
            return
        if event.button() == Qt.RightButton and self.current_pixmap:
            self.show_context_menu()
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Выберите изображение {self.image_type}",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Все файлы (*.*)"
        )
        if file_path:
            self.load_image(file_path)

    def show_context_menu(self):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        view_action = menu.addAction("👁️ Просмотр в полном размере")
        view_action.triggered.connect(self.view_full_size)
        edit_action = menu.addAction("✂️ Редактировать")
        edit_action.triggered.connect(self.edit_image)
        menu.addSeparator()
        save_action = menu.addAction("💾 Сохранить как...")
        save_action.triggered.connect(self.save_image_as)
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Удалить")
        delete_action.triggered.connect(self.clear_image)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def load_image(self, file_path):
        """Загружает изображение из файла"""
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.image_path = file_path
            scaled_pixmap = pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
            self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(file_path)}\n"
                            f"Размер: {pixmap.width()}x{pixmap.height()}\nПКМ для меню")
            self.image_changed.emit(file_path)
        else:
            self.setText("❌\nОшибка\nзагрузки")
            self.setToolTip(f"Не удалось загрузить изображение:\n{file_path}")

    def update_display(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self.setText("")
        else:
            self.clear()
            if self.editable:
                self.setText("📷\nНажмите\nдля загрузки\nили перетащите")
            else:
                self.setText("📷\nНет фото")

    def get_image_path(self):
        """Возвращает путь к изображению"""
        if self.image_path and Path(self.image_path).exists():
            return self.image_path
        if self.current_pixmap and not self.current_pixmap.isNull():
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                self.current_pixmap.save(tmp.name)
                self.image_path = tmp.name
                return self.image_path
        return self.image_path

    def clear_image(self):
        """Очищает изображение"""
        self.current_pixmap = None
        self.image_path = None
        self.update_display()
        if self.editable:
            self.setToolTip(f"Нажмите для загрузки изображения {self.image_type}\nИли перетащите файл сюда")
        else:
            self.setToolTip("")
        self.image_changed.emit("")

    def get_pixmap(self):
        return self.current_pixmap

    def set_image_from_path(self, image_path):
        """Устанавливает изображение из пути"""
        if not image_path:
            return False
        path_obj = Path(image_path)
        if not path_obj.exists():
            from utils.paths import paths
            root_dir = paths.get_root_dir()
            possible_paths = [
                root_dir / image_path,
                root_dir / "system_data" / image_path,
                root_dir / "data" / image_path,
                Path(image_path),
            ]
            found = False
            for possible in possible_paths:
                if possible.exists():
                    path_obj = possible
                    found = True
                    break
            if not found:
                file_name = Path(image_path).name
                for ext in ['', '.png', '.jpg', '.jpeg']:
                    possible = root_dir / "system_data" / "data" / "coin_images" / f"{file_name}{ext}"
                    if possible.exists():
                        path_obj = possible
                        found = True
                        break
            if not found:
                return False
        pixmap = QPixmap(str(path_obj))
        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.image_path = str(path_obj)
            scaled_pixmap = pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
            self.setToolTip(f"Изображение {self.image_type}\n{path_obj.name}\n"
                            f"Размер: {pixmap.width()}x{pixmap.height()}\nПКМ для меню")
            return True
        return False

    def view_full_size(self):
        if self.current_pixmap:
            from gui.dialogs.image_viewer_dialog import ImageViewerDialog
            dialog = ImageViewerDialog(self.current_pixmap, f"{self.image_type.capitalize()} - просмотр", self)
            dialog.exec()

    def edit_image(self):
        """Редактирование изображения (обрезка, масштабирование, поворот)"""
        if not self.current_pixmap:
            return
        from utils.paths import paths
        temp_dir = paths.get_data_dir() / "coin_images"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"temp_edit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        self.current_pixmap.save(str(temp_path))
        try:
            from gui.widgets.detail_panel.image_editor import ImageEditorDialog
            dialog = ImageEditorDialog(str(temp_path), None, self)
            if dialog.exec():
                edited_pixmap = dialog.get_obverse_pixmap()
                if edited_pixmap and not edited_pixmap.isNull():
                    self.current_pixmap = edited_pixmap
                    if self.image_path and os.path.exists(self.image_path):
                        save_path = self.image_path
                    else:
                        save_path = temp_dir / f"{self.image_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    edited_pixmap.save(str(save_path))
                    self.image_path = str(save_path)
                    scaled_pixmap = edited_pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.setPixmap(scaled_pixmap)
                    self.image_changed.emit(str(save_path))
                    QMessageBox.information(self, "Успех", "Изображение обновлено")
        except Exception as e:
            print(f"Ошибка при редактировании изображения: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть редактор изображений:\n{e}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass

    def save_image_as(self):
        if not self.current_pixmap:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить изображение",
            f"{self.image_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG (*.png);;JPEG (*.jpg);;Все файлы (*.*)"
        )
        if file_path:
            self.current_pixmap.save(file_path)
            QMessageBox.information(self, "Успех", f"Изображение сохранено:\n{file_path}")


class TextEditDialog(QDialog):
    """Диалог для редактирования большого текста"""

    def __init__(self, title="Редактирование текста", initial_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        self.setMinimumSize(400, 300)
        self.setModal(True)
        t = _get_theme()
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('window_bg', '#0f0f1a')}; }}")
        layout = QVBoxLayout()
        self.setLayout(layout)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14px;
            padding: 8px;
            background-color: {t.get('accent', '#6c63ff')};
            color: #ffffff;
            border-radius: 3px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFixedHeight(40)
        layout.addWidget(title_label)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t.get('surface', '#16213e')};
                color: {t.get('text', '#e4e4ef')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border-color: {t.get('accent', '#6c63ff')};
            }}
        """)
        self.text_edit.setFont(QFont("Courier New", 11))
        layout.addWidget(self.text_edit)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_btn = QPushButton("✅ Сохранить")
        save_btn.clicked.connect(self.accept)
        save_btn.setFixedHeight(35)
        save_btn.setMinimumWidth(150)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 3px;")
        button_layout.addWidget(save_btn)
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedHeight(35)
        cancel_btn.setMinimumWidth(150)
        cancel_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; border-radius: 3px;")
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        self.text_edit.setFocus()

    def get_text(self):
        return self.text_edit.toPlainText()


class ClickableTextEdit(QTextEdit):
    """Текстовое поле, которое открывает диалог при клике"""

    def __init__(self, parent=None, field_name=""):
        super().__init__(parent)
        self.field_name = field_name
        self.setReadOnly(False)
        self.setFixedHeight(50)
        self.setMinimumWidth(177)
        self.setMaximumWidth(177)
        t = _get_theme()
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t.get('surface', '#16213e')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 3px;
                padding: 3px;
                font-size: 11px;
            }}
            QTextEdit:focus {{
                border-color: {t.get('accent', '#6c63ff')};
                background-color: {t.get('surface_hover', '#1f2b47')};
            }}
        """)

    def mouseDoubleClickEvent(self, event):
        self.open_dialog()

    def mousePressEvent(self, event):
        self.open_dialog()

    def open_dialog(self):
        dialog = TextEditDialog(
            title=f"Редактирование: {self.field_name}",
            initial_text=self.toPlainText(),
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            self.setPlainText(dialog.get_text())


class BaseDetailTab:
    """Базовый класс для вкладок деталей"""

    def __init__(self, db_manager, parent=None):
        self.db_manager = db_manager
        self.parent = parent
        self.logger = logging.getLogger(f'CoinCollector.GUI.{self.__class__.__name__}')

    def _theme(self):
        """Возвращает словарь текущей темы"""
        try:
            return self.parent.parent_window.theme_manager.current_theme
        except Exception:
            return {}