# -*- coding: utf-8 -*-

"""
Диалог для просмотра изображения в полном размере
с поддержкой масштабирования, панорамирования и переключения аверс/реверс
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QToolBar, QWidget)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QPixmap, QAction, QPainter, QColor


class ImageViewerDialog(QDialog):
    """Диалог для просмотра изображения в полном размере"""
    
    def __init__(self, obverse_pixmap=None, reverse_pixmap=None, title="Просмотр изображения", parent=None):
        super().__init__(parent)
        
        # Принимаем строки (пути) или QPixmap
        if isinstance(obverse_pixmap, str):
            self.obverse_pixmap = QPixmap(obverse_pixmap) if obverse_pixmap and obverse_pixmap != "None" else None
        else:
            self.obverse_pixmap = obverse_pixmap
        
        if isinstance(reverse_pixmap, str):
            self.reverse_pixmap = QPixmap(reverse_pixmap) if reverse_pixmap and reverse_pixmap != "None" else None
        else:
            self.reverse_pixmap = reverse_pixmap
        
        self.current_side = 'obverse'
        
        # Определяем текущее изображение
        if self.obverse_pixmap and not self.obverse_pixmap.isNull():
            self.original_pixmap = self.obverse_pixmap
        elif self.reverse_pixmap and not self.reverse_pixmap.isNull():
            self.original_pixmap = self.reverse_pixmap
            self.current_side = 'reverse'
        else:
            self.original_pixmap = None
        
        self.scale_factor = 1.0
        self._manual_zoom = False
        
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Панель инструментов
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        
        # Кнопки переключения аверс/реверс
        self.obverse_btn = QPushButton("🪙 Аверс")
        self.obverse_btn.setFixedSize(80, 28)
        self.obverse_btn.clicked.connect(lambda: self.switch_side('obverse'))
        self.obverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        toolbar.addWidget(self.obverse_btn)
        
        self.reverse_btn = QPushButton("🪙 Реверс")
        self.reverse_btn.setFixedSize(80, 28)
        self.reverse_btn.clicked.connect(lambda: self.switch_side('reverse'))
        self.reverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        toolbar.addWidget(self.reverse_btn)
        
        toolbar.addSeparator()
        
        self.fit_action = QAction("📐 По размеру", self)
        self.fit_action.triggered.connect(self.fit_to_window)
        toolbar.addAction(self.fit_action)
        
        zoom_out_action = QAction("🔍−", self)
        zoom_out_action.triggered.connect(lambda: self.zoom(0.9))
        toolbar.addAction(zoom_out_action)
        
        self.zoom_label = QLabel("100%")
        toolbar.addWidget(self.zoom_label)
        
        zoom_in_action = QAction("🔍+", self)
        zoom_in_action.triggered.connect(lambda: self.zoom(1.1))
        toolbar.addAction(zoom_in_action)
        
        toolbar.addSeparator()
        
        reset_action = QAction("🔄 100%", self)
        reset_action.triggered.connect(self.reset_view)
        toolbar.addAction(reset_action)
        
        toolbar.addSeparator()
        
        close_action = QAction("❌ Закрыть", self)
        close_action.triggered.connect(self.accept)
        toolbar.addAction(close_action)
        
        layout.addWidget(toolbar)
        
        # Виджет для отображения изображения с панорамированием
        self.image_widget = ImageWidget()
        self.image_widget.setStyleSheet("background-color: #1e1e1e;")
        
        # Устанавливаем pixmap
        if self.original_pixmap and not self.original_pixmap.isNull():
            self.fit_to_window()
        else:
            self.image_widget.set_no_image()
        
        layout.addWidget(self.image_widget)
        
        # Обновляем состояние кнопок
        self.update_buttons()
    
    def update_buttons(self):
        """Обновляет состояние кнопок переключения"""
        has_obverse = bool(self.obverse_pixmap and not self.obverse_pixmap.isNull())
        has_reverse = bool(self.reverse_pixmap and not self.reverse_pixmap.isNull())
        
        self.obverse_btn.setEnabled(has_obverse)
        self.reverse_btn.setEnabled(has_reverse)
        
        if self.current_side == 'obverse':
            self.obverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6fa5;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
            self.reverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
        else:
            self.obverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
            self.reverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6fa5;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
    
    def switch_side(self, side):
        """Переключает между аверсом и реверсом"""
        if side == self.current_side:
            return
        
        self.current_side = side
        
        if side == 'obverse':
            self.original_pixmap = self.obverse_pixmap
        else:
            self.original_pixmap = self.reverse_pixmap
        
        if self.original_pixmap and not self.original_pixmap.isNull():
            self._manual_zoom = False
            self.fit_to_window()
        else:
            self.image_widget.set_no_image()
        
        self.update_buttons()
    
    def fit_to_window(self):
        """Подгоняет изображение под размер окна"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        
        self._manual_zoom = False
        self.image_widget.pan_offset = QPoint(0, 0)
        
        available_size = self.image_widget.size() - QSize(10, 10)
        
        if available_size.width() > 0 and available_size.height() > 0:
            scaled = self.original_pixmap.scaled(
                available_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_widget.current_pixmap = scaled
            
            w_scale = scaled.width() / self.original_pixmap.width()
            h_scale = scaled.height() / self.original_pixmap.height()
            self.scale_factor = min(w_scale, h_scale)
            self.update_zoom_label()
            self.image_widget.update()
    
    def resizeEvent(self, event):
        """При изменении размера окна подгоняем изображение"""
        super().resizeEvent(event)
        if hasattr(self, '_manual_zoom') and not self._manual_zoom:
            self.fit_to_window()
    
    def zoom(self, factor):
        """Масштабирует изображение"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        
        self._manual_zoom = True
        self.scale_factor *= factor
        self.scale_factor = max(0.1, min(5.0, self.scale_factor))
        self.update_display()
    
    def update_display(self):
        """Обновляет отображение с текущим масштабом"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        
        new_size = self.original_pixmap.size() * self.scale_factor
        scaled = self.original_pixmap.scaled(
            new_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_widget.current_pixmap = scaled
        self.update_zoom_label()
        
        # Обновляем курсор
        if self.image_widget.current_pixmap:
            pw = self.image_widget.current_pixmap.width()
            ph = self.image_widget.current_pixmap.height()
            if pw > self.image_widget.width() or ph > self.image_widget.height():
                self.image_widget.setCursor(Qt.OpenHandCursor)
            else:
                self.image_widget.setCursor(Qt.ArrowCursor)
        
        self.image_widget.update()
    
    def update_zoom_label(self):
        """Обновляет метку масштаба"""
        percent = int(self.scale_factor * 100)
        self.zoom_label.setText(f"{percent}%")
    
    def reset_view(self):
        """Сбрасывает масштаб к 100%"""
        self._manual_zoom = True
        self.scale_factor = 1.0
        self.image_widget.pan_offset = QPoint(0, 0)
        self.update_display()
    
    def wheelEvent(self, event):
        """Обработчик колесика мыши для масштабирования"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom(1.1)
        elif delta < 0:
            self.zoom(0.9)


class ImageWidget(QWidget):
    """Виджет для отображения изображения с поддержкой панорамирования"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        
        # Панорамирование
        self.pan_offset = QPoint(0, 0)
        self.pan_start = None
        self.is_panning = False
        self.current_pixmap = None
    
    def set_no_image(self):
        """Показывает заглушку"""
        self.current_pixmap = None
        self.pan_offset = QPoint(0, 0)
        self.update()
    
    def paintEvent(self, event):
        """Отрисовка с учётом панорамирования"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        
        if self.current_pixmap and not self.current_pixmap.isNull():
            x = (self.width() - self.current_pixmap.width()) // 2 + self.pan_offset.x()
            y = (self.height() - self.current_pixmap.height()) // 2 + self.pan_offset.y()
            painter.drawPixmap(x, y, self.current_pixmap)
        else:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "📷\nНет изображения")
    
    def mousePressEvent(self, event):
        """Нажатие мыши для панорамирования"""
        if event.button() == Qt.LeftButton and self.current_pixmap:
            pw = self.current_pixmap.width()
            ph = self.current_pixmap.height()
            if pw > self.width() or ph > self.height():
                self.is_panning = True
                self.pan_start = event.position().toPoint()
                self.setCursor(Qt.ClosedHandCursor)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Движение мыши для панорамирования"""
        if self.is_panning and self.pan_start is not None:
            delta = event.position().toPoint() - self.pan_start
            self.pan_offset += delta
            self.pan_start = event.position().toPoint()
            self.update()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Отпускание мыши"""
        if event.button() == Qt.LeftButton:
            self.is_panning = False
            self.pan_start = None
            if self.current_pixmap:
                pw = self.current_pixmap.width()
                ph = self.current_pixmap.height()
                if pw > self.width() or ph > self.height():
                    self.setCursor(Qt.OpenHandCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
        
        super().mouseReleaseEvent(event)