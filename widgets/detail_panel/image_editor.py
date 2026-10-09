# -*- coding: utf-8 -*-

"""
Редактор изображений с поддержкой переключения между аверсом и реверсом
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QFrame, QToolBar, QMessageBox,
                               QWidget, QSizePolicy, QComboBox)
from PySide6.QtCore import Qt, QRect, QPoint, QSize, Signal
from PySide6.QtGui import (QPixmap, QPainter, QPen, QColor, QTransform, QAction,
                           QMouseEvent, QWheelEvent, QCursor)


class ImageViewer(QWidget):
    """Виджет для просмотра изображения с поддержкой масштабирования и панорамирования"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.current_pixmap = None
        self.scaled_pixmap = None
        self.scale_factor = 1.0
        self.zoom_min = 0.1
        self.zoom_max = 5.0
        
        # Панорамирование
        self.pan_start = None
        self.pan_offset = QPoint(0, 0)
        self.is_panning = False
        
        # Обрезка
        self.crop_mode = False
        self.selection_rect = None
        self.drag_start = None
        self.is_dragging = False
        self.is_moving = False
        self.move_start = None
        self.move_start_rect = None
        
        self.img_x = 0
        self.img_y = 0
        
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
    
    def set_pixmap(self, pixmap):
        """Устанавливает изображение"""
        self.current_pixmap = pixmap
        self.scale_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.selection_rect = None
        self.update_display()
    
    def get_pixmap(self):
        """Возвращает текущее изображение"""
        return self.current_pixmap
    
    def set_crop_mode(self, enabled):
        """Включает/выключает режим обрезки"""
        self.crop_mode = enabled
        if not enabled:
            self.selection_rect = None
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.CrossCursor)
        self.update_display()
    
    def update_display(self):
        """Обновляет отображение с учётом размера виджета"""
        if not self.current_pixmap or self.current_pixmap.isNull():
            self.update()
            return
        
        # Вычисляем размер для масштабирования с сохранением пропорций
        widget_size = self.size()
        pixmap_size = self.current_pixmap.size()
        
        if widget_size.width() > 0 and widget_size.height() > 0:
            # Масштабируем под размер виджета с учётом текущего масштаба
            scale_w = widget_size.width() / pixmap_size.width()
            scale_h = widget_size.height() / pixmap_size.height()
            fit_scale = min(scale_w, scale_h)
            
            # Применяем пользовательский масштаб
            total_scale = fit_scale * self.scale_factor
            
            new_size = QSize(
                int(pixmap_size.width() * total_scale),
                int(pixmap_size.height() * total_scale)
            )
            
            self.scaled_pixmap = self.current_pixmap.scaled(
                new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            self.scaled_pixmap = self.current_pixmap
        
        self.update()
    
    def paintEvent(self, event):
        """Отрисовка изображения и области обрезки"""
        if not hasattr(self, 'scaled_pixmap') or not self.scaled_pixmap:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(43, 43, 43))
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignCenter, "Нет изображения")
            return
        
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(43, 43, 43))
        
        # Центрируем изображение с учётом панорамирования
        self.img_x = (self.width() - self.scaled_pixmap.width()) // 2 + self.pan_offset.x()
        self.img_y = (self.height() - self.scaled_pixmap.height()) // 2 + self.pan_offset.y()
        
        painter.drawPixmap(self.img_x, self.img_y, self.scaled_pixmap)
        
        # Рисуем область обрезки
        if self.crop_mode and self.selection_rect:
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QColor(0, 0, 0, 100))
            painter.drawRect(self.rect())
            
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QColor(0, 0, 0, 0))
            
            # Преобразуем координаты выделения
            scale_x = self.scaled_pixmap.width() / self.current_pixmap.width()
            scale_y = self.scaled_pixmap.height() / self.current_pixmap.height()
            
            view_rect = QRect(
                self.img_x + int(self.selection_rect.x() * scale_x),
                self.img_y + int(self.selection_rect.y() * scale_y),
                int(self.selection_rect.width() * scale_x),
                int(self.selection_rect.height() * scale_y)
            )
            painter.drawRect(view_rect)
            
            # Уголки
            corner_size = 10
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(view_rect.topLeft(), view_rect.topLeft() + QPoint(corner_size, 0))
            painter.drawLine(view_rect.topLeft(), view_rect.topLeft() + QPoint(0, corner_size))
            painter.drawLine(view_rect.topRight(), view_rect.topRight() + QPoint(-corner_size, 0))
            painter.drawLine(view_rect.topRight(), view_rect.topRight() + QPoint(0, corner_size))
            painter.drawLine(view_rect.bottomLeft(), view_rect.bottomLeft() + QPoint(corner_size, 0))
            painter.drawLine(view_rect.bottomLeft(), view_rect.bottomLeft() + QPoint(0, -corner_size))
            painter.drawLine(view_rect.bottomRight(), view_rect.bottomRight() + QPoint(-corner_size, 0))
            painter.drawLine(view_rect.bottomRight(), view_rect.bottomRight() + QPoint(0, -corner_size))
    
    def _view_to_image_point(self, view_point):
        """Преобразует координаты виджета в координаты изображения"""
        if not hasattr(self, 'scaled_pixmap') or not self.scaled_pixmap:
            return None
        
        x = (view_point.x() - self.img_x) / self.scaled_pixmap.width() * self.current_pixmap.width()
        y = (view_point.y() - self.img_y) / self.scaled_pixmap.height() * self.current_pixmap.height()
        
        if x < 0 or x > self.current_pixmap.width() or y < 0 or y > self.current_pixmap.height():
            return None
        
        return QPoint(int(x), int(y))
    
    def mousePressEvent(self, event: QMouseEvent):
        """Обработка нажатия мыши"""
        if self.crop_mode:
            pos = event.pos()
            img_point = self._view_to_image_point(pos)
            
            if img_point is None:
                return
            
            if event.button() == Qt.RightButton:
                if self.selection_rect and self.selection_rect.contains(img_point):
                    self.apply_crop()
                return
            
            if event.button() == Qt.LeftButton:
                if self.selection_rect and self.selection_rect.contains(img_point):
                    self.is_moving = True
                    self.move_start = img_point
                    self.move_start_rect = self.selection_rect
                else:
                    self.is_dragging = True
                    self.drag_start = img_point
                    self.selection_rect = None
            return
        
        # Режим панорамирования
        if event.button() == Qt.LeftButton and self.scale_factor > 1.0:
            self.is_panning = True
            self.pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Обработка движения мыши"""
        if self.crop_mode:
            pos = event.pos()
            img_point = self._view_to_image_point(pos)
            
            if img_point is None:
                return
            
            if self.is_moving and self.move_start:
                delta_x = img_point.x() - self.move_start.x()
                delta_y = img_point.y() - self.move_start.y()
                
                new_rect = QRect(
                    self.move_start_rect.x() + delta_x,
                    self.move_start_rect.y() + delta_y,
                    self.move_start_rect.width(),
                    self.move_start_rect.height()
                )
                
                if new_rect.x() < 0:
                    new_rect.setX(0)
                if new_rect.y() < 0:
                    new_rect.setY(0)
                if new_rect.right() > self.current_pixmap.width():
                    new_rect.setRight(self.current_pixmap.width())
                if new_rect.bottom() > self.current_pixmap.height():
                    new_rect.setBottom(self.current_pixmap.height())
                
                self.selection_rect = new_rect
                self.update_display()
                return
            
            if self.is_dragging and self.drag_start:
                self.selection_rect = QRect(self.drag_start, img_point).normalized()
                self.update_display()
            return
        
        # Панорамирование
        if self.is_panning and self.pan_start:
            delta = event.position().toPoint() - self.pan_start
            self.pan_offset += delta
            self.pan_start = event.position().toPoint()
            self.update_display()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Обработка отпускания мыши"""
        if self.crop_mode:
            self.is_dragging = False
            self.is_moving = False
            self.move_start = None
            
            if self.selection_rect and (self.selection_rect.width() < 5 or self.selection_rect.height() < 5):
                self.selection_rect = None
                self.update_display()
            return
        
        if event.button() == Qt.LeftButton:
            self.is_panning = False
            self.pan_start = None
            if self.scale_factor > 1.0:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        super().mouseReleaseEvent(event)
    
    def apply_crop(self):
        """Применяет обрезку и возвращает результат"""
        if not self.selection_rect:
            return None
        
        if not self.current_pixmap or self.current_pixmap.isNull():
            return None
        
        if self.selection_rect.width() < 5 or self.selection_rect.height() < 5:
            self.selection_rect = None
            self.update_display()
            return None
        
        # Копируем выделенную область
        cropped = self.current_pixmap.copy(self.selection_rect)
        
        if not cropped.isNull():
            # Заменяем текущее изображение обрезанным
            self.current_pixmap = cropped
            self.selection_rect = None
            self.scale_factor = 1.0
            self.pan_offset = QPoint(0, 0)
            self.update_display()
            return cropped
        
        return None
    
    def wheelEvent(self, event: QWheelEvent):
        """Масштабирование колесиком мыши"""
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        
        delta = event.angleDelta().y()
        old_scale = self.scale_factor
        
        if delta > 0:
            self.scale_factor = min(self.zoom_max, self.scale_factor * 1.1)
        else:
            self.scale_factor = max(self.zoom_min, self.scale_factor * 0.9)
        
        # Корректируем панорамирование
        scale_ratio = self.scale_factor / old_scale
        self.pan_offset = QPoint(
            int(self.pan_offset.x() * scale_ratio),
            int(self.pan_offset.y() * scale_ratio)
        )
        
        self.update_display()
    
    def resizeEvent(self, event):
        """Обновляет отображение при изменении размера окна"""
        self.update_display()
        super().resizeEvent(event)
    
    def reset_view(self):
        """Сбрасывает масштаб и позицию"""
        self.scale_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.selection_rect = None
        self.update_display()


class ImageEditorDialog(QDialog):
    """Диалог для редактирования изображений с переключением между аверсом и реверсом"""
    
    def __init__(self, obverse_path=None, reverse_path=None, parent=None):
        super().__init__(parent)
        
        # Обрабатываем пути (могут быть None или пустые строки)
        self.obverse_path = obverse_path if obverse_path and obverse_path != "None" else None
        self.reverse_path = reverse_path if reverse_path and reverse_path != "None" else None
        
        self.current_side = 'obverse'
        
        # Загружаем изображения
        self.obverse_pixmap = None
        self.reverse_pixmap = None
        
        if self.obverse_path and isinstance(self.obverse_path, str) and self.obverse_path:
            try:
                self.obverse_pixmap = QPixmap(self.obverse_path)
                if self.obverse_pixmap.isNull():
                    self.obverse_pixmap = None
            except Exception as e:
                print(f"Ошибка загрузки аверса: {e}")
                self.obverse_pixmap = None
        
        if self.reverse_path and isinstance(self.reverse_path, str) and self.reverse_path:
            try:
                self.reverse_pixmap = QPixmap(self.reverse_path)
                if self.reverse_pixmap.isNull():
                    self.reverse_pixmap = None
            except Exception as e:
                print(f"Ошибка загрузки реверса: {e}")
                self.reverse_pixmap = None
        
        self.current_pixmap = self.obverse_pixmap
        self.initial_pixmap = self.current_pixmap
        
        self.setWindowTitle("Редактор изображений")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Панель переключения сторон
        switch_layout = QHBoxLayout()
        switch_layout.addStretch()
        
        self.obverse_btn = QPushButton("🪙 Аверс")
        self.obverse_btn.clicked.connect(lambda: self.switch_side('obverse'))
        self.obverse_btn.setFixedSize(100, 30)
        self.obverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
        """)
        switch_layout.addWidget(self.obverse_btn)
        
        self.reverse_btn = QPushButton("🪙 Реверс")
        self.reverse_btn.clicked.connect(lambda: self.switch_side('reverse'))
        self.reverse_btn.setFixedSize(100, 30)
        self.reverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
        """)
        switch_layout.addWidget(self.reverse_btn)
        
        switch_layout.addStretch()
        layout.addLayout(switch_layout)
        
        # Панель инструментов
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Область с изображением
        self.image_viewer = ImageViewer()
        if self.current_pixmap and not self.current_pixmap.isNull():
            self.image_viewer.set_pixmap(self.current_pixmap)
        layout.addWidget(self.image_viewer)
        
        # Информационная строка
        self.info_label = QLabel("Колесико мыши - масштаб, зажатая левая кнопка - перемещение")
        self.info_label.setStyleSheet("color: #aaa; padding: 5px; background-color: #3c3c3c;")
        layout.addWidget(self.info_label)
        
        # Обновляем состояние кнопок
        self.update_buttons_state()
    
    def update_buttons_state(self):
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
                }
            """)
            self.reverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
        else:
            self.obverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
            self.reverse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6fa5;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
    
    def set_current_side(self, side):
        """Устанавливает текущую отображаемую сторону"""
        if side == 'obverse' and self.obverse_pixmap and not self.obverse_pixmap.isNull():
            self.current_side = 'obverse'
            self.current_pixmap = self.obverse_pixmap
            self.initial_pixmap = self.obverse_pixmap
            self.image_viewer.set_pixmap(self.current_pixmap)
            self.update_buttons_state()
        elif side == 'reverse' and self.reverse_pixmap and not self.reverse_pixmap.isNull():
            self.current_side = 'reverse'
            self.current_pixmap = self.reverse_pixmap
            self.initial_pixmap = self.reverse_pixmap
            self.image_viewer.set_pixmap(self.current_pixmap)
            self.update_buttons_state()
        else:
            # Если запрошенной стороны нет, показываем ту, что есть
            if self.obverse_pixmap and not self.obverse_pixmap.isNull():
                self.current_side = 'obverse'
                self.current_pixmap = self.obverse_pixmap
                self.initial_pixmap = self.obverse_pixmap
                self.image_viewer.set_pixmap(self.current_pixmap)
                self.update_buttons_state()
            elif self.reverse_pixmap and not self.reverse_pixmap.isNull():
                self.current_side = 'reverse'
                self.current_pixmap = self.reverse_pixmap
                self.initial_pixmap = self.reverse_pixmap
                self.image_viewer.set_pixmap(self.current_pixmap)
                self.update_buttons_state()
    
    def switch_side(self, side):
        """Переключает между аверсом и реверсом"""
        # Сохраняем текущее изображение перед переключением
        current = self.image_viewer.get_pixmap()
        if current and not current.isNull():
            if self.current_side == 'obverse':
                self.obverse_pixmap = current
            else:
                self.reverse_pixmap = current
        
        self.current_side = side
        
        if side == 'obverse':
            self.current_pixmap = self.obverse_pixmap
            self.initial_pixmap = self.obverse_pixmap
        else:
            self.current_pixmap = self.reverse_pixmap
            self.initial_pixmap = self.reverse_pixmap
        
        if self.current_pixmap and not self.current_pixmap.isNull():
            self.image_viewer.set_pixmap(self.current_pixmap)
            self.update_buttons_state()
        else:
            empty_pixmap = QPixmap(400, 300)
            empty_pixmap.fill(QColor(43, 43, 43))
            self.image_viewer.set_pixmap(empty_pixmap)
            QMessageBox.warning(self, "Предупреждение", f"Изображение {side} не загружено")
    
    def create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(28, 28))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #3c3c3c;
                padding: 2px;
            }
            QToolButton {
                background-color: #5a5a5a;
                color: white;
                border-radius: 3px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #4a6fa5;
            }
        """)
        
        # Кнопка обрезки
        self.crop_action = QAction("✂️ Обрезка", self)
        self.crop_action.setCheckable(True)
        self.crop_action.triggered.connect(self.toggle_crop_mode)
        toolbar.addAction(self.crop_action)
        
        toolbar.addSeparator()
        
        # Поворот влево
        rotate_left_action = QAction("↩️ Повернуть влево", self)
        rotate_left_action.triggered.connect(lambda: self.rotate(-90))
        toolbar.addAction(rotate_left_action)
        
        # Поворот вправо
        rotate_right_action = QAction("↪️ Повернуть вправо", self)
        rotate_right_action.triggered.connect(lambda: self.rotate(90))
        toolbar.addAction(rotate_right_action)
        
        toolbar.addSeparator()
        
        # Сброс
        reset_action = QAction("🔄 Сбросить", self)
        reset_action.triggered.connect(self.reset_view)
        toolbar.addAction(reset_action)
        
        toolbar.addSeparator()
        
        # Кнопки OK/Отмена
        ok_action = QAction("✅ Применить", self)
        ok_action.triggered.connect(self.accept)
        toolbar.addAction(ok_action)
        
        cancel_action = QAction("❌ Отмена", self)
        cancel_action.triggered.connect(self.reject)
        toolbar.addAction(cancel_action)
        
        return toolbar
    
    def toggle_crop_mode(self):
        """Переключает режим обрезки"""
        self.image_viewer.set_crop_mode(self.crop_action.isChecked())
        if self.crop_action.isChecked():
            self.info_label.setText("Режим обрезки: выделите область левой кнопкой, затем кликните правой кнопкой внутри выделения")
        else:
            self.info_label.setText("Колесико мыши - масштаб, зажатая левая кнопка - перемещение")
    
    def rotate(self, angle):
        """Поворачивает текущее изображение"""
        current = self.image_viewer.get_pixmap()
        if not current or current.isNull():
            return
        
        transform = QTransform()
        transform.rotate(angle)
        rotated = current.transformed(transform, Qt.SmoothTransformation)
        
        if not rotated.isNull():
            self.image_viewer.set_pixmap(rotated)
            
            # Сохраняем в соответствующую переменную
            if self.current_side == 'obverse':
                self.obverse_pixmap = rotated
            else:
                self.reverse_pixmap = rotated
            
            self.current_pixmap = rotated
    
    def reset_view(self):
        """Сбрасывает изменения текущего изображения"""
        if self.current_side == 'obverse':
            if self.obverse_path and isinstance(self.obverse_path, str) and self.obverse_path:
                self.current_pixmap = QPixmap(self.obverse_path)
                self.obverse_pixmap = self.current_pixmap
            else:
                self.current_pixmap = None
                self.obverse_pixmap = None
        else:
            if self.reverse_path and isinstance(self.reverse_path, str) and self.reverse_path:
                self.current_pixmap = QPixmap(self.reverse_path)
                self.reverse_pixmap = self.current_pixmap
            else:
                self.current_pixmap = None
                self.reverse_pixmap = None
        
        self.initial_pixmap = self.current_pixmap
        
        if self.current_pixmap and not self.current_pixmap.isNull():
            self.image_viewer.set_pixmap(self.current_pixmap)
        else:
            empty_pixmap = QPixmap(400, 300)
            empty_pixmap.fill(QColor(43, 43, 43))
            self.image_viewer.set_pixmap(empty_pixmap)
        
        self.crop_action.setChecked(False)
        self.image_viewer.set_crop_mode(False)
        self.info_label.setText("Колесико мыши - масштаб, зажатая левая кнопка - перемещение")
        QMessageBox.information(self, "Успех", "Изображение сброшено к исходному")
    
    def get_obverse_pixmap(self):
        """Возвращает изображение аверса"""
        if self.current_side == 'obverse':
            current = self.image_viewer.get_pixmap()
            if current and not current.isNull():
                return current
        return self.obverse_pixmap
    
    def get_reverse_pixmap(self):
        """Возвращает изображение реверса"""
        if self.current_side == 'reverse':
            current = self.image_viewer.get_pixmap()
            if current and not current.isNull():
                return current
        return self.reverse_pixmap
    
    def accept(self):
        """При принятии сохраняем текущее изображение"""
        current = self.image_viewer.get_pixmap()
        if current and not current.isNull():
            if self.current_side == 'obverse':
                self.obverse_pixmap = current
            else:
                self.reverse_pixmap = current
        super().accept()
    
    def closeEvent(self, event):
        event.accept()