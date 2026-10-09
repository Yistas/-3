# -*- coding: utf-8 -*-

"""
Виджет дерева стран с поддержкой drag & drop и контекстного меню
"""

import logging
import os
import re
from pathlib import Path
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox,
                               QInputDialog, QAbstractItemView, QStyle)
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QAction, QIcon, QPixmap
from database.models import Country, Coin
from gui.dialogs.add_country_dialog import AddCountryDialog


class CountryTreeWidget(QTreeWidget):
    """Кастомный виджет дерева стран с обработкой drop"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.logger = logging.getLogger('CoinCollector.GUI.CountryTree')
        self.expanded_state = {}
        self.setHeaderLabel("Структура стран")
        self.setIndentation(15)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        # Включаем drag & drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        # Включаем контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # Подключаем сигнал изменения элемента
        self.itemChanged.connect(self.on_item_changed)
        self.itemClicked.connect(self.on_item_selected)
        # Принудительно включаем отображение значков
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setExpandsOnDoubleClick(True)
        self.setIndentation(12)
        # ВАЖНО: никакого захардкоженного света — применяем текущую тему
        self.update_style()
        # Таймер для принудительного обновления значков
        QTimer.singleShot(500, self._force_update_branches)
        self._save_in_progress = False

    def paintEvent(self, event):
        """Рисуем дерево, а поверх — свои плюсики/минусы в зоне веток"""
        super().paintEvent(event)

        from PySide6.QtGui import QPainter, QPen, QColor

        # Цвета из текущей темы
        arrow_color = QColor('#a8a8d0')
        base_color = QColor('#1a1a2e')
        alt_color = QColor('#16213e')
        if hasattr(self.main_window, 'theme_manager'):
            theme = self.main_window.theme_manager.current_theme
            arrow_color = QColor(theme.get('arrow_color', '#a8a8d0'))
            base_color = QColor(theme.get('base', '#1a1a2e'))
            alt_color = QColor(theme.get('alternate_base', '#16213e'))

        painter = QPainter(self.viewport())
        try:
            indent = self.indentation()
            pen = QPen(arrow_color)
            pen.setWidth(2)
            vp_height = self.viewport().height()

            def draw_item(item):
                if item.childCount() > 0:
                    vr = self.visualItemRect(item)
                    if vr.isValid() and vr.bottom() >= 0 and vr.top() <= vp_height:
                        # Закрашиваем "тёмную полоску" цветом фона строки
                        row = self.indexFromItem(item).row()
                        br = QRect(vr.x() - indent, vr.y(), indent, vr.height())
                        painter.fillRect(br, alt_color if row % 2 else base_color)
                        # Рисуем плюс/минус по центру зоны ветки
                        painter.setPen(pen)
                        cx = br.center().x()
                        cy = br.center().y()
                        half = max(3, indent // 2 - 4)
                        # горизонтальная линия (минус) — всегда
                        painter.drawLine(cx - half, cy, cx + half, cy)
                        # вертикальная линия — только у свёрнутой ветки (плюс)
                        if not item.isExpanded():
                            painter.drawLine(cx, cy - half, cx, cy + half)
                if item.isExpanded():
                    for i in range(item.childCount()):
                        draw_item(item.child(i))

            for i in range(self.topLevelItemCount()):
                draw_item(self.topLevelItem(i))
        finally:
            painter.end()

    def _force_update_branches(self):
        """Принудительно обновляет отображение веток"""
        def update_item(item):
            if item and item.childCount() > 0:
                # Сохраняем и восстанавливаем состояние раскрытия для перерисовки
                was_expanded = item.isExpanded()
                item.setExpanded(not was_expanded)
                item.setExpanded(was_expanded)
            # Рекурсивно обрабатываем дочерние элементы
            if item:
                for i in range(item.childCount()):
                    update_item(item.child(i))
        
        # Обрабатываем корневые элементы
        for i in range(self.topLevelItemCount()):
            update_item(self.topLevelItem(i))
        
        # Принудительно обновляем виджет
        self.viewport().update()
        self.logger.debug("Принудительное обновление веток выполнено")

    def dropEvent(self, event):
        """Обработчик события сброса элемента при перетаскивании"""
        # Сохраняем информацию о перемещаемом элементе ДО вызова стандартного dropEvent
        source_item = self.currentItem()
        if not source_item:
            super().dropEvent(event)
            return
        
        # Сохраняем ID перемещаемой страны и её текущие данные
        source_country_id = source_item.data(0, Qt.UserRole)
        
        # Если это папка (нет country_id), просто выполняем стандартный drop
        if source_country_id is None:
            super().dropEvent(event)
            self.logger.info("Перемещена папка")
            return
        
        # Сохраняем информацию о стране до перемещения
        country = self.main_window.db_manager.session.query(Country).get(source_country_id)
        if not country:
            super().dropEvent(event)
            return
        
        # Сохраняем исходные значения для сравнения
        old_continent = country.continent
        old_is_extinct = country.is_extinct
        
        # Запоминаем позицию, куда будет сброшен элемент
        drop_position = event.position().toPoint()
        target_item = self.itemAt(drop_position)
        drop_indicator = self.dropIndicatorPosition()
        
        # Вызываем стандартную обработку drop
        super().dropEvent(event)
        
        # Определяем нового родителя на основе того, куда был сброшен элемент
        new_parent = None
        
        if drop_indicator == QAbstractItemView.OnItem:
            # Сбросили прямо на элемент
            new_parent = target_item
        elif drop_indicator in [QAbstractItemView.BelowItem, QAbstractItemView.AboveItem]:
            # Сбросили между элементами - родитель = родитель целевого элемента
            if target_item:
                new_parent = target_item.parent()
            if not new_parent:
                new_parent = self.invisibleRootItem()
        else:
            new_parent = self.invisibleRootItem()
        
        if not new_parent or new_parent == self.invisibleRootItem():
            self.logger.info("Не удалось определить родителя после перетаскивания")
            QTimer.singleShot(7000, lambda: self._safe_save_structure())
            return
        
        # ===== ОПРЕДЕЛЕНИЕ КОНТЕКСТА (континент + is_extinct) =====
        new_continent = None
        new_is_extinct = False
        
        # Список континентов для проверки
        continents = ["Европа", "Азия", "Америка", "Африка", "Океания"]
        
        # Поднимаемся вверх по дереву от нового родителя, чтобы найти контекст
        check_item = new_parent
        
        while check_item is not None and hasattr(check_item, 'text'):
            check_text = check_item.text(0)
            # Очищаем текст от эмодзи
            clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', check_text)
            clean_text = clean_text.strip()
            
            self.logger.debug(f"  Проверка элемента: '{check_text}' (очищен: '{clean_text}')")
            
            # Проверяем, является ли элемент континентом
            if clean_text in continents and new_continent is None:
                new_continent = clean_text
                self.logger.debug(f"  Найден континент: {new_continent}")
            
            # Проверяем, находимся ли в разделе "Исчезнувшие страны"
            if "Исчезнувшие страны" in check_text:
                new_is_extinct = True
                self.logger.debug(f"  Найден раздел 'Исчезнувшие страны'")
                # Как только нашли раздел "Исчезнувшие страны", дальше можно не подниматься
                # но продолжаем для поиска континента, если он ещё не найден
                if new_continent is not None:
                    break
            
            # Проверяем, находимся ли в разделе "Все страны"
            if "Все страны" in check_text:
                new_is_extinct = False
                self.logger.debug(f"  Найден раздел 'Все страны'")
                if new_continent is not None:
                    break
            
            # Проверяем корень "КОЛЛЕКЦИЯ"
            if "КОЛЛЕКЦИЯ" in check_text:
                self.logger.debug(f"  Достигнут корень 'КОЛЛЕКЦИЯ'")
                break
            
            # Поднимаемся на уровень выше
            if hasattr(check_item, 'parent'):
                check_item = check_item.parent()
            else:
                break
        
        # Проверяем, изменились ли значения
        continent_changed = (new_continent != old_continent)
        extinct_changed = (new_is_extinct != old_is_extinct)
        
        self.logger.info(f"Результат перетаскивания для '{country.name}':")
        self.logger.info(f"  Континент: {old_continent} → {new_continent} (изменён: {continent_changed})")
        self.logger.info(f"  Статус: исчезнувшая={old_is_extinct} → исчезнувшая={new_is_extinct} (изменён: {extinct_changed})")
        
        if continent_changed or extinct_changed:
            # Обновляем страну в базе данных
            changes = []
            if continent_changed:
                changes.append(f"континент: {old_continent or 'не указан'} → {new_continent or 'не указан'}")
            if extinct_changed:
                old_status = "исчезнувшая" if old_is_extinct else "существующая"
                new_status = "исчезнувшая" if new_is_extinct else "существующая"
                changes.append(f"статус: {old_status} → {new_status}")
            
            self.logger.info(f"Страна '{country.name}' обновлена: {', '.join(changes)}")
            
            if hasattr(self.main_window, 'update_country_continent'):
                self.main_window.update_country_continent(source_country_id, new_continent, new_is_extinct)
        else:
            self.logger.info(f"Страна '{country.name}' не изменила континент/статус")
        
        # Сохраняем структуру
        QTimer.singleShot(7000, lambda: self._safe_save_structure())

    def mouseReleaseEvent(self, event):
        """Обработчик отпускания кнопки мыши"""
        super().mouseReleaseEvent(event)
        # Сохраняем структуру после завершения операции с мышью, но с большей задержкой
        if event.button() == Qt.LeftButton:
            QTimer.singleShot(7000, lambda: self._safe_save_structure())
    
    def _safe_save_structure(self):
        """Безопасное сохранение структуры с проверкой"""
        if hasattr(self.main_window, 'settings_manager'):
            self.main_window.settings_manager.save_tree_structure(self)
    
    def on_item_changed(self, item, column):
        """Обработчик изменения элемента (переименование и т.д.)"""
        # Сохраняем структуру при изменении, но с большой задержкой
        self.logger.debug(f"Элемент изменен: {item.text(0)}")
        QTimer.singleShot(7000, lambda: self._safe_save_structure())
    
    def show_context_menu(self, position):
        """Показывает контекстное меню для элемента дерева"""
        item = self.itemAt(position)
        if not item:
            return
        
        country_id = item.data(0, Qt.UserRole)
        
        # Создаем меню
        menu = QMenu()
        
        if country_id is not None:
            # Это страна
            menu.setTitle("Страна")
            
            # Действие для смены иконки
            change_icon_action = QAction("🖼️ Сменить иконку", self)
            change_icon_action.triggered.connect(lambda: self.change_country_icon(item, country_id))
            menu.addAction(change_icon_action)
            
            # Если есть пользовательская иконка, добавляем пункт для её удаления
            icon_path = self.main_window.settings_manager.get_country_icon_path(country_id)
            if icon_path and os.path.exists(icon_path):
                remove_icon_action = QAction("🗑️ Убрать пользовательскую иконку", self)
                remove_icon_action.triggered.connect(lambda: self.remove_country_icon(item, country_id))
                menu.addAction(remove_icon_action)
            
            menu.addSeparator()
            
            # Действие для переименования
            rename_action = QAction("✏️ Переименовать", self)
            rename_action.triggered.connect(lambda: self.rename_country(item, country_id))
            menu.addAction(rename_action)
            
            # Действие для удаления
            delete_action = QAction("🗑️ Удалить страну", self)
            delete_action.triggered.connect(lambda: self.main_window.delete_country(country_id))
            menu.addAction(delete_action)
            
        else:
            # Это папка/континент
            menu.setTitle("Папка")
            
            change_icon_action = QAction("🖼️ Сменить иконку", self)
            change_icon_action.triggered.connect(lambda: self.change_folder_icon(item))
            menu.addAction(change_icon_action)
            
            menu.addSeparator()
            
            # Действие для добавления страны в эту папку
            add_country_action = QAction("➕ Добавить страну сюда", self)
            add_country_action.triggered.connect(lambda: self.add_country_to_folder(item))
            menu.addAction(add_country_action)
        
        # Показываем меню
        if not menu.isEmpty():
            menu.exec(self.viewport().mapToGlobal(position))
    
    def change_country_icon(self, item, country_id):
        """Изменяет иконку для страны"""
        from gui.icon_selector import IconSelectorDialog
        from utils.paths import paths
        
        # Получаем текущую иконку
        current_icon = self.main_window.settings_manager.get_country_icon_path(country_id)
        if not current_icon or not os.path.exists(current_icon):
            current_icon = None
        
        dialog = IconSelectorDialog(self, current_icon)
        if dialog.exec():
            icon, icon_type = dialog.get_selected_icon()
            
            if icon:
                if icon_type == 'emoji':
                    QMessageBox.information(self, "Информация", 
                        "Для стран можно использовать только пользовательские иконки.\n"
                        "Выберите 'Свои иконки' и загрузите изображение.")
                    return
                    
                elif icon_type == 'custom':
                    if self.main_window.settings_manager.set_country_custom_icon(country_id, icon):
                        pixmap = QPixmap(icon)
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            item.setIcon(0, QIcon(scaled_pixmap))
                        
                        self.update_country_item_text(item, country_id)
                        
                        self.logger.info(f"Иконка для страны {country_id} изменена")
                        self.main_window.status_bar.showMessage("Иконка обновлена", 2000)

    def remove_country_icon(self, item, country_id):
        """Удаляет пользовательскую иконку для страны"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Убрать пользовательскую иконку?\n"
            "Страна будет отображаться без иконки.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.main_window.settings_manager.remove_country_custom_icon(country_id)
            self.update_country_item_text(item, country_id)
            item.setIcon(0, QIcon())
            
            self.logger.info(f"Пользовательская иконка для страны {country_id} удалена")
            self.main_window.status_bar.showMessage("Иконка удалена", 2000)
            
            # Сохраняем структуру после удаления иконки
            QTimer.singleShot(100, lambda: self.main_window.settings_manager.save_tree_structure(self))
    
    def change_folder_icon(self, item):
        """Изменяет иконку для папки/континента"""
        from gui.icon_selector import IconSelectorDialog
        from utils.paths import paths
        
        text = item.text(0)
        
        # Определяем, является ли элемент континентом
        is_continent = "📌" in text and any(cont in text for cont in ["Европа", "Азия", "Америка", "Африка", "Океания"])
        
        emoji_match = re.match(r'([\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2})', text)
        current_emoji = emoji_match.group(1) if emoji_match else "📁"
        
        dialog = IconSelectorDialog(self, current_emoji, for_folder=True)
        dialog.setWindowTitle("Выбор иконки для папки")
        
        if dialog.exec():
            icon, icon_type = dialog.get_selected_icon()
            
            if icon:
                if icon_type == 'emoji':
                    # Устанавливаем emoji
                    if emoji_match:
                        new_text = text.replace(current_emoji, icon, 1)
                    else:
                        new_text = f"{icon} {text}"
                    
                    item.setText(0, new_text)
                    item.setIcon(0, QIcon())  # Убираем пользовательскую иконку, если была
                    
                    self.logger.info(f"Иконка папки изменена на emoji {icon}")
                    
                    # Если это континент, сохраняем иконку отдельно
                    if is_continent:
                        continent_name = text.replace("📌", "").strip()
                        parent_item = item.parent()
                        is_extinct = False
                        if parent_item and "Исчезнувшие страны" in parent_item.text(0):
                            is_extinct = True
                        self.main_window.settings_manager.set_continent_icon(continent_name, icon, is_extinct)
                    
                elif icon_type == 'custom':
                    # Устанавливаем пользовательскую иконку
                    pixmap = QPixmap(icon)
                    if not pixmap.isNull():
                        import shutil
                        from datetime import datetime
                        
                        # Сохраняем в data/custom_icons/
                        icons_dir = paths.get_custom_icons_dir()
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        file_ext = os.path.splitext(icon)[1] or '.png'
                        new_filename = f"folder_{timestamp}{file_ext}"
                        new_path = icons_dir / new_filename
                        
                        # Копируем файл
                        shutil.copy2(icon, new_path)
                        
                        # Масштабируем и устанавливаем иконку
                        scaled_pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        item.setIcon(0, QIcon(scaled_pixmap))
                        
                        # СОХРАНЯЕМ путь к иконке В ДАННЫХ ЭЛЕМЕНТА
                        item.setData(0, Qt.UserRole + 1, str(new_path))
                        
                        # Убираем emoji из текста, если он там был
                        clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', text)
                        item.setText(0, clean_text)
                        
                        # Сохраняем информацию об иконке в настройках
                        folder_path = self._get_item_path(item)
                        icon_info = {
                            'type': 'custom',
                            'path': str(new_path)
                        }
                        
                        self.logger.info(f"Иконка папки изменена на пользовательскую: {new_path}")
                        self.logger.info(f"Путь папки: {folder_path}")
                        
                        # Если это континент, сохраняем в continent_icons
                        if is_continent:
                            continent_name = text.replace("📌", "").strip()
                            parent_item = item.parent()
                            is_extinct = False
                            if parent_item and "Исчезнувшие страны" in parent_item.text(0):
                                is_extinct = True
                            
                            self.main_window.settings_manager.set_continent_icon(continent_name, icon_info, is_extinct)
                        
                        # Сохраняем информацию об иконке папки
                        if folder_path:
                            self.main_window.settings_manager.set_folder_icon(folder_path, icon_info)
                            # Принудительно сохраняем настройки
                            self.main_window.settings_manager.save_settings()
                
                self.main_window.status_bar.showMessage("Иконка папки обновлена", 2000)

    def _get_item_path(self, item):
        """Возвращает путь к элементу в дереве"""
        path_parts = []
        current = item
        
        while current:
            text = current.text(0)
            # Убираем emoji из текста для пути
            clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', text)
            path_parts.insert(0, clean_text)
            current = current.parent()
        
        return '/'.join(path_parts)
    
    def update_country_item_text(self, item, country_id):
        """Обновляет текст элемента страны"""
        text = item.text(0)
        
        match = re.match(r'[^\w\s]*\s*(.+?)(?:\s*\((\d+)\))?$', text)
        if match:
            country_name = match.group(1).strip()
            coin_count = match.group(2)
        else:
            country_name = text
            coin_count = None
        
        if not coin_count:
            coin_count = self.main_window.db_manager.session.query(Coin).filter_by(country_id=country_id).count()
        else:
            coin_count = int(coin_count)
        
        if coin_count > 0:
            item.setText(0, f"{country_name} ({coin_count})")
        else:
            item.setText(0, country_name)
    
    def add_country_to_folder(self, folder_item):
        """Добавляет новую страну в указанную папку"""
        folder_text = folder_item.text(0)
        folder_name = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', folder_text)
        
        is_extinct = "Исчезнувшие" in folder_text
        
        dialog = AddCountryDialog(self.main_window.db_manager, self)
        
        if folder_name in ["Европа", "Азия", "Америка", "Африка", "Океания"]:
            dialog.continent_combo.setCurrentText(folder_name)
        
        if is_extinct:
            dialog.extinct_check.setChecked(True)
        
        if dialog.exec():
            country_data = dialog.get_country_data()
            if country_data['name']:
                self.main_window.create_new_country(country_data)
    
    def rename_country(self, item, country_id):
        """Переименовывает страну"""
        current_text = item.text(0)
        base_name = current_text.split(' (')[0]
        
        country = self.main_window.db_manager.session.query(Country).get(country_id)
        
        dialog = AddCountryDialog(self.main_window.db_manager, self, 
                                  initial_name=base_name,
                                  default_continent=country.continent if country else None,
                                  is_extinct=country.is_extinct if country else False)
        dialog.setWindowTitle("Редактирование страны")
        
        if dialog.exec():
            country_data = dialog.get_country_data()
            if country_data['name'] and country_data['name'] != base_name:
                try:
                    existing = self.main_window.db_manager.session.query(Country).filter_by(name=country_data['name']).first()
                    if existing and existing.id != country_id:
                        QMessageBox.warning(self, "Предупреждение", 
                                           f"Страна '{country_data['name']}' уже существует в базе данных.")
                        return
                    
                    country.name = country_data['name']
                    country.code = country_data['code']
                    country.continent = country_data['continent']
                    country.is_extinct = country_data['is_extinct']
                    self.main_window.db_manager.session.commit()
                    
                    self.logger.info(f"Страна обновлена: {country_data['name']}")
                    self.main_window.status_bar.showMessage(f"✅ Страна обновлена", 3000)
                    
                    self.main_window.save_expanded_state()
                    self.main_window.load_country_tree(preserve_expanded=True)
                    self.main_window.detail_panel.refresh_country_combos()
                    
                    # Сохраняем структуру дерева после переименования
                    self.main_window.settings_manager.save_tree_structure(self)
                    
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении страны: {e}")
                    self.main_window.db_manager.session.rollback()
                    QMessageBox.critical(self, "Ошибка", f"Не удалось обновить страну:\n{e}")
    
    def load_country_tree(self, preserve_expanded=False):
        """Загружает дерево стран с распределением по континентам"""
        self.logger.info("Загрузка дерева стран")
        
        # Отключаем обновление на время построения
        self.setUpdatesEnabled(False)
        self.blockSignals(True)
        
        try:
            # Получаем все страны из БД
            countries = self.main_window.db_manager.get_all_countries()
            self.logger.info(f"Количество стран в БД: {len(countries)}")
            
            if preserve_expanded:
                self.save_expanded_state()
            
            self.clear()
            
            dir_icon = self.style().standardIcon(QStyle.SP_DirClosedIcon)
            
            # === КОРНЕВОЙ ЭЛЕМЕНТ "КОЛЛЕКЦИЯ" ===
            collection_item = QTreeWidgetItem(self)
            collection_item.setText(0, "📚 КОЛЛЕКЦИЯ")
            collection_item.setData(0, Qt.UserRole, None)
            collection_item.setIcon(0, dir_icon)
            collection_item.setExpanded(True)
            collection_item.setFlags(collection_item.flags() | Qt.ItemIsDropEnabled)
            
            # Корневой элемент "Все страны" (теперь внутри КОЛЛЕКЦИИ)
            all_item = QTreeWidgetItem(collection_item)
            all_item.setText(0, "🌍 Все страны")
            all_item.setData(0, Qt.UserRole, None)
            all_item.setIcon(0, dir_icon)
            all_item.setExpanded(True)
            all_item.setFlags(all_item.flags() | Qt.ItemIsDropEnabled)
            
            # Элемент "Исчезнувшие страны" (теперь внутри КОЛЛЕКЦИИ)
            extinct_item = QTreeWidgetItem(collection_item)
            extinct_item.setText(0, "💀 Исчезнувшие страны")
            extinct_item.setData(0, Qt.UserRole, None)
            extinct_item.setIcon(0, dir_icon)
            extinct_item.setExpanded(False)
            extinct_item.setFlags(extinct_item.flags() | Qt.ItemIsDropEnabled)
            
            # Список континентов
            continents = ["Европа", "Азия", "Америка", "Африка", "Океания"]
            
            # Создаем континенты под "Все страны"
            continent_items = {}
            for continent_name in continents:
                continent_item = QTreeWidgetItem(all_item)
                continent_item.setText(0, f"📌 {continent_name}")
                continent_item.setData(0, Qt.UserRole, None)
                continent_item.setIcon(0, dir_icon)
                continent_item.setExpanded(False)
                continent_item.setFlags(continent_item.flags() | Qt.ItemIsDropEnabled)
                continent_items[continent_name] = continent_item
            
            # Создаем континенты под "Исчезнувшие страны"
            extinct_continent_items = {}
            for continent_name in continents:
                continent_item = QTreeWidgetItem(extinct_item)
                continent_item.setText(0, f"📌 {continent_name}")
                continent_item.setData(0, Qt.UserRole, None)
                continent_item.setIcon(0, dir_icon)
                continent_item.setExpanded(False)
                continent_item.setFlags(continent_item.flags() | Qt.ItemIsDropEnabled)
                extinct_continent_items[continent_name] = continent_item
            
            # === СТРОИМ КАРТУ ВСЕХ СТАНДАРТНЫХ ЭЛЕМЕНТОВ ===
            parent_map = {
                "КОЛЛЕКЦИЯ": collection_item,
                "Все страны": all_item,
                "Исчезнувшие страны": extinct_item,
            }
            parent_map["КОЛЛЕКЦИЯ/Все страны"] = all_item
            parent_map["КОЛЛЕКЦИЯ/Исчезнувшие страны"] = extinct_item
            
            for name, item in continent_items.items():
                parent_map[f"Все страны/{name}"] = item
                parent_map[f"КОЛЛЕКЦИЯ/Все страны/{name}"] = item
            
            for name, item in extinct_continent_items.items():
                parent_map[f"Исчезнувшие страны/{name}"] = item
                parent_map[f"КОЛЛЕКЦИЯ/Исчезнувшие страны/{name}"] = item
            
            # === ЗАГРУЗКА СОХРАНЕННЫХ ПОЛЬЗОВАТЕЛЬСКИХ ПАПОК ===
            self.main_window.settings_manager.load_tree_structure(
                self, all_item, extinct_item, 
                continent_items, extinct_continent_items, collection_item
            )
            
            # === ОБНОВЛЯЕМ parent_map ПОСЛЕ ЗАГРУЗКИ ПОЛЬЗОВАТЕЛЬСКИХ ПАПОК ===
            def update_parent_map(parent_item, base_path=""):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    child_text = child.text(0)
                    clean_child_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', child_text)
                    child_path = f"{base_path}/{clean_child_text}" if base_path else clean_child_text
                    
                    if child.data(0, Qt.UserRole) is None:
                        parent_map[child_path] = child
                    
                    update_parent_map(child, child_path)
            
            update_parent_map(collection_item)
            
            # === РАСПРЕДЕЛЕНИЕ СТРАН ===
            added_countries = set()
            country_positions = self.main_window.settings_manager.settings.get('country_positions', {})
            
            # Шаг 1: кэшируем иконки стран
            # ПРИОРИТЕТ: файл флага data/country_flags/{id}.png (не теряется при пересборке),
            # затем пользовательская иконка из настроек (config.db)
            country_icons = {}
            for country in countries:
                icon = self._flag_icon(country.id, 16, 16)
                if icon is None:
                    icon_path = self.main_window.settings_manager.get_country_icon_path(country.id)
                    if icon_path and os.path.exists(icon_path):
                        pixmap = QPixmap(icon_path)
                        if not pixmap.isNull():
                            icon = QIcon(pixmap.scaled(
                                16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                if icon:
                    country_icons[country.id] = icon
            
            # Шаг 2: распределяем страны по сохранённым позициям
            for country in countries:
                saved_pos = country_positions.get(str(country.id))
                if saved_pos:
                    parent_path = saved_pos.get('parent', '')
                    if parent_path:
                        parent_item = parent_map.get(parent_path)
                        if parent_item:
                            self._add_country_to_tree_fast(parent_item, country, country_icons)
                            added_countries.add(country.id)
                            continue
            
            # Шаг 3: по континентам из БД
            for country in countries:
                if country.id in added_countries:
                    continue
                
                if country.continent and country.continent in continents:
                    if country.is_extinct:
                        parent_item = extinct_continent_items.get(country.continent)
                    else:
                        parent_item = continent_items.get(country.continent)
                    
                    if parent_item:
                        self._add_country_to_tree_fast(parent_item, country, country_icons)
                        added_countries.add(country.id)
            
            # Шаг 4: оставшиеся в корневые папки
            for country in countries:
                if country.id not in added_countries:
                    if country.is_extinct:
                        parent_item = extinct_item
                    else:
                        parent_item = all_item
                    self._add_country_to_tree_fast(parent_item, country, country_icons)
                    added_countries.add(country.id)
            
            self.logger.info(f"Всего добавлено стран: {len(added_countries)}")
            
            if preserve_expanded and hasattr(self, 'expanded_state'):
                QTimer.singleShot(100, self.restore_expanded_state)
            
            self.logger.info("Дерево стран загружено")
            
        finally:
            # Включаем обновление
            self.blockSignals(False)
            self.setUpdatesEnabled(True)

    def _find_item_by_path(self, path):
        """Находит элемент дерева по пути"""
        if not path:
            return None
        
        # Разбиваем путь на части
        parts = path.split('/')
        current_item = None
        
        # Ищем в корневых элементах (теперь ищем внутри КОЛЛЕКЦИИ)
        root = self.topLevelItem(0)  # КОЛЛЕКЦИЯ
        if not root:
            return None
        
        if root.text(0) != parts[0]:
            # Если первый элемент не КОЛЛЕКЦИЯ, ищем по-старому
            for i in range(self.topLevelItemCount()):
                item = self.topLevelItem(i)
                if item.text(0) == parts[0]:
                    current_item = item
                    break
        else:
            current_item = root
            parts = parts[1:]  # Убираем КОЛЛЕКЦИЮ из пути
        
        if not current_item:
            return None
        
        # Ищем вложенные элементы
        for part in parts:
            found = False
            for i in range(current_item.childCount()):
                child = current_item.child(i)
                if child.text(0) == part:
                    current_item = child
                    found = True
                    break
            if not found:
                return None
        
        return current_item
    
    def _add_country_to_tree(self, parent_item, country):
        """Вспомогательный метод для добавления страны в дерево"""
        if parent_item is None:
            self.logger.error(f"Родительский элемент для страны {country.name} равен None!")
            return
            
        from database.models import Coin
        coin_count = self.main_window.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
        
        self.logger.debug(f"Добавление страны {country.name} в родитель {parent_item.text(0)}")
        
        country_item = QTreeWidgetItem(parent_item)
        
        icon_path = self.main_window.settings_manager.get_country_icon_path(country.id)
        
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                country_item.setIcon(0, QIcon(scaled_pixmap))
        
        if coin_count > 0:
            country_item.setText(0, f"{country.name} ({coin_count})")
        else:
            country_item.setText(0, country.name)
        
        country_item.setData(0, Qt.UserRole, country.id)
        country_item.setToolTip(0, f"Показать монеты {country.name}")
        country_item.setFlags(country_item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
    
    def get_country_ids_from_folder(self, folder_item):
        """Рекурсивно собирает ID всех стран в папке и подпапках"""
        country_ids = []
        
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            country_id = child.data(0, Qt.UserRole)
            
            if country_id is not None:
                # Это страна
                country_ids.append(country_id)
            else:
                # Это вложенная папка - рекурсивно собираем из неё
                country_ids.extend(self.get_country_ids_from_folder(child))
        
        return country_ids
    
    def on_item_selected(self, item, column):
        """Обработчик выбора элемента в дереве"""
        if not item:
            return
        
        # Защита от рекурсии
        if hasattr(self, '_processing_selection') and self._processing_selection:
            return
        
        self._processing_selection = True
        
        try:
            country_id = item.data(0, Qt.UserRole)
            item_text = item.text(0)
            
            # Проверяем, является ли элемент "КОЛЛЕКЦИЯ"
            if "КОЛЛЕКЦИЯ" in item_text and country_id is None:
                self.logger.info("Выбрана КОЛЛЕКЦИЯ - показываем дашборд и загружаем все монеты")
                
                # Показываем дашборд на боковой панели
                if hasattr(self.main_window, 'detail_panel'):
                    self.main_window.detail_panel.show_dashboard()
                
                # Получаем ВСЕ страны (и существующие, и исчезнувшие)
                countries = self.main_window.db_manager.get_all_countries()
                country_ids = [c.id for c in countries]
                
                # Устанавливаем фильтр - показываем все монеты
                self.main_window.current_filter_country_id = None
                self.main_window.current_folder_country_ids = country_ids
                
                # Загружаем все монеты
                self.main_window.load_coins()
                
                # Для погодовки показываем "Вся коллекция"
                if hasattr(self.main_window, 'on_country_selected'):
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(50, lambda: self.main_window.on_country_selected(None, "Вся коллекция"))
                
                # Переключаемся на вкладку с монетами в центральной части
                if hasattr(self.main_window, 'center_tab_widget'):
                    self.main_window.center_tab_widget.setCurrentIndex(0)
                
                return
            
            # Проверяем, выбран ли элемент "Все страны" или "Исчезнувшие страны"
            if ("Все страны" in item_text or "Исчезнувшие страны" in item_text) and country_id is None:
                self.logger.info(f"Выбрана папка: {item_text} - показываем статистику")
                
                # Показываем статистику на боковой панели
                if hasattr(self.main_window, 'detail_panel'):
                    self.main_window.detail_panel.show_statistics()
                    if "Все страны" in item_text:
                        self.main_window.detail_panel.show_all_countries_stats()
                    else:
                        self.main_window.detail_panel.show_extinct_countries_stats()
                
                # Загружаем монеты для выбранной папки
                if "Все страны" in item_text:
                    countries = self.main_window.db_manager.session.query(Country).filter_by(is_extinct=False).all()
                else:
                    countries = self.main_window.db_manager.session.query(Country).filter_by(is_extinct=True).all()
                
                country_ids = [c.id for c in countries]
                
                # Устанавливаем фильтр
                self.main_window.current_filter_country_id = None
                self.main_window.current_folder_country_ids = country_ids
                
                # Загружаем монеты
                self.main_window.load_coins()
                
                # Для погодовки
                if hasattr(self.main_window, 'on_country_selected'):
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(50, lambda: self.main_window.on_country_selected(None, item_text))
                
                # Переключаемся на вкладку с монетами в центральной части
                if hasattr(self.main_window, 'center_tab_widget'):
                    self.main_window.center_tab_widget.setCurrentIndex(0)
                
                return
            
            if country_id is not None:
                # Выбрана конкретная страна - показываем вкладку "Страна"
                self.logger.info(f"Выбрана страна: {item_text} - показываем информацию о стране")
                
                # Показываем страну на боковой панели
                if hasattr(self.main_window, 'detail_panel'):
                    self.main_window.detail_panel.show_country_info_by_id(country_id)
                
                # Устанавливаем фильтр
                self.main_window.current_filter_country_id = country_id
                if hasattr(self.main_window, 'current_folder_country_ids'):
                    delattr(self.main_window, 'current_folder_country_ids')
                
                # Загружаем монеты для этой страны
                self.main_window.load_coins()
                
                country_name = item.text(0).split(' (')[0]
                
                # Вызываем обработчик выбора страны для обновления погодовки
                if hasattr(self.main_window, 'on_country_selected'):
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(50, lambda: self.main_window.on_country_selected(country_id, country_name))
                
                # Переключаемся на вкладку с монетами в центральной части
                if hasattr(self.main_window, 'center_tab_widget'):
                    self.main_window.center_tab_widget.setCurrentIndex(0)
                
                return
            
            else:
                # Выбрана папка - определяем её тип
                item_text = item.text(0)
                
                # Убираем эмодзи из текста для проверки
                import re
                clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', item_text)
                
                # Список континентов для проверки
                continents_list = ["Европа", "Азия", "Америка", "Африка", "Океания"]
                
                # Проверяем, является ли элемент континентом (по очищенному тексту)
                is_continent = clean_text in continents_list
                
                if is_continent:
                    # Это континент - показываем статистику
                    continent_name = clean_text
                    
                    # Определяем, находимся ли мы в разделе исчезнувших стран
                    parent_item = item.parent()
                    is_in_extinct = False
                    if parent_item:
                        parent_text = parent_item.text(0)
                        if "Исчезнувшие страны" in parent_text:
                            is_in_extinct = True
                    
                    self.logger.info(f"Выбран континент: {continent_name} - показываем статистику")
                    
                    # Показываем статистику на боковой панели
                    if hasattr(self.main_window, 'detail_panel'):
                        self.main_window.detail_panel.show_statistics()
                        if is_in_extinct:
                            self.main_window.detail_panel.show_extinct_continent_stats(continent_name)
                        else:
                            self.main_window.detail_panel.show_continent_stats(continent_name)
                    
                    # Получаем страны с учетом раздела
                    query = self.main_window.db_manager.session.query(Country).filter_by(continent=continent_name)
                    
                    if is_in_extinct:
                        query = query.filter_by(is_extinct=True)
                    else:
                        query = query.filter_by(is_extinct=False)
                    
                    countries = query.all()
                    country_ids = [c.id for c in countries]
                    
                    # Устанавливаем фильтр по странам
                    self.main_window.current_filter_country_id = None
                    self.main_window.current_folder_country_ids = country_ids
                    
                    # Загружаем монеты для отфильтрованных стран
                    self.main_window.load_coins()
                    
                    # Для континента вызываем обработчик с None
                    if hasattr(self.main_window, 'on_country_selected'):
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(50, lambda: self.main_window.on_country_selected(None, continent_name))
                    
                    # Переключаемся на вкладку с монетами в центральной части
                    if hasattr(self.main_window, 'center_tab_widget'):
                        self.main_window.center_tab_widget.setCurrentIndex(0)
                    
                    return
                
                else:
                    # Обычная пользовательская папка - показываем статистику
                    country_ids = self.get_country_ids_from_folder(item)
                    
                    self.logger.info(f"Выбрана папка: {item_text} - показываем статистику")
                    
                    # Показываем статистику на боковой панели
                    if hasattr(self.main_window, 'detail_panel'):
                        self.main_window.detail_panel.show_statistics()
                        self.main_window.detail_panel.show_folder_stats(item_text, country_ids)
                    
                    # Устанавливаем фильтр по папке
                    self.main_window.current_filter_country_id = None
                    self.main_window.current_folder_country_ids = country_ids
                    
                    # Загружаем монеты для стран в папке
                    self.main_window.load_coins()
                    
                    # Переключаемся на вкладку с монетами в центральной части
                    if hasattr(self.main_window, 'center_tab_widget'):
                        self.main_window.center_tab_widget.setCurrentIndex(0)
                    
                    return
                    
        finally:
            self._processing_selection = False

    def save_expanded_state(self):
        """Сохраняет состояние развернутых узлов дерева"""
        self.expanded_state = {}
        root = self.invisibleRootItem()
        self._save_expanded_state_recursive(root)
    
    def _save_expanded_state_recursive(self, parent_item):
        """Рекурсивно сохраняет состояние развернутых узлов"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            country_id = child.data(0, Qt.UserRole)
            if country_id is not None:
                key = f"country_{country_id}"
            else:
                key = f"folder_{child.text(0)}"
            
            self.expanded_state[key] = child.isExpanded()
            self._save_expanded_state_recursive(child)
    
    def restore_expanded_state(self):
        """Восстанавливает состояние развернутых узлов дерева"""
        if hasattr(self, 'expanded_state'):
            root = self.invisibleRootItem()
            self._restore_expanded_state_recursive(root)
    
    def _restore_expanded_state_recursive(self, parent_item):
        """Рекурсивно восстанавливает состояние развернутых узлов"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            country_id = child.data(0, Qt.UserRole)
            if country_id is not None:
                key = f"country_{country_id}"
            else:
                key = f"folder_{child.text(0)}"
            
            if key in self.expanded_state:
                child.setExpanded(self.expanded_state[key])
            
            self._restore_expanded_state_recursive(child)
    
    def add_custom_level(self, level_name):
        """Добавляет новый пользовательский уровень (папку) в дерево"""
        if level_name:
            self.save_expanded_state()
            
            current_item = self.currentItem()
            
            # Определяем родителя для новой папки
            if not current_item or current_item == self.topLevelItem(0):
                # Если ничего не выбрано — добавляем в КОЛЛЕКЦИЮ
                parent_item = self.topLevelItem(0)  # КОЛЛЕКЦИЯ
            else:
                country_id = current_item.data(0, Qt.UserRole)
                
                if country_id is not None:
                    # Выбрана страна — добавляем рядом (в того же родителя)
                    parent_item = current_item.parent()
                    if not parent_item:
                        parent_item = self.topLevelItem(0)  # КОЛЛЕКЦИЯ
                else:
                    # Выбрана папка — проверяем, можно ли добавить в неё
                    text = current_item.text(0)
                    
                    # Нельзя добавить внутрь континента или стандартной папки
                    is_standard = any(keyword in text for keyword in 
                                     ["Все страны", "Исчезнувшие страны", "КОЛЛЕКЦИЯ"])
                    
                    continents_list = ["Европа", "Азия", "Америка", "Африка", "Океания"]
                    clean_text = re.sub(r'^[\U0001F300-\U0001F9FF\U00002000-\U000026FF]{1,2}\s*', '', text)
                    is_continent = clean_text in continents_list
                    
                    if is_standard or is_continent:
                        # Для стандартных папок и континентов — добавляем рядом (в родителя)
                        parent_item = current_item.parent()
                        if not parent_item:
                            parent_item = self.topLevelItem(0)
                    else:
                        # Для пользовательских папок — добавляем внутрь
                        parent_item = current_item
            
            new_item = QTreeWidgetItem(parent_item)
            new_item.setText(0, f"📁 {level_name}")
            new_item.setData(0, Qt.UserRole, None)
            
            # Устанавливаем иконку папки
            dir_icon = self.style().standardIcon(QStyle.SP_DirIcon)
            new_item.setIcon(0, dir_icon)
            
            new_item.setExpanded(True)
            new_item.setFlags(new_item.flags() | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            
            self.logger.info(f"Добавлен новый уровень: {level_name} в родитель: {parent_item.text(0)}")
            return True
        return False

    def delete_custom_level(self, item):
        """Удаляет выбранный пользовательский уровень"""
        if not item:
            return False
        
        if item.data(0, Qt.UserRole) is not None:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить страну. Удаляйте только пользовательские уровни.")
            return False
        
        text = item.text(0)
        if "Все страны" in text or "Исчезнувшие страны" in text or "📌" in text or "КОЛЛЕКЦИЯ" in text:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить стандартные элементы дерева.")
            return False
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить уровень '{text}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.save_expanded_state()
            
            parent = item.parent() or self.invisibleRootItem()
            while item.childCount() > 0:
                child = item.takeChild(0)
                parent.addChild(child)
            
            parent.removeChild(item)
            
            self.logger.info(f"Удален уровень: {text}")
            return True
        return False
    
    def expand_all(self):
        """Разворачивает все элементы дерева"""
        self.expandAll()
    
    def collapse_all(self):
        """Сворачивает все элементы дерева"""
        self.collapseAll()
        root = self.topLevelItem(0)
        if root:
            self.expandItem(root)
            
    def update_style(self):
        """Обновляет стиль дерева в соответствии с текущей темой"""
        if not hasattr(self.main_window, 'theme_manager'):
            return
        theme = self.main_window.theme_manager.current_theme
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {theme.get('base', '#1a1a2e')};
                color: {theme.get('text', '#e4e4ef')};
                border: 1px solid {theme.get('border', '#2a2a4a')};
                alternate-background-color: {theme.get('alternate_base', '#16213e')};
                selection-background-color: {theme.get('highlight', '#6c63ff')};
                selection-color: {theme.get('highlight_text', '#ffffff')};
            }}
            QTreeWidget::item {{
                padding: 2px 2px;
                border-bottom: 1px solid {theme.get('border', '#2a2a4a')};
                min-height: 20px;
            }}
            QTreeWidget::item:hover {{
                background-color: {theme.get('surface_hover', '#1f2b47')};
            }}
            QTreeWidget::item:selected {{
                background-color: {theme.get('highlight', '#6c63ff')};
                color: {theme.get('highlight_text', '#ffffff')};
            }}
        """)
        # Перерисовываем плюсики/минусы новыми цветами
        self.viewport().update()

    def showEvent(self, event):
        """Переопределяем showEvent для принудительного обновления значков"""
        super().showEvent(event)
        # Принудительно обновляем отображение веток (без вызова self.update())
        self.viewport().update()
        # Перебираем все элементы и принудительно обновляем их состояние
        self._force_update_branches()
    
    def update(self) -> None:
        """Обновляет виджет - переопределение для совместимости с QWidget"""
        # Вызываем родительский update для перерисовки
        super().update()
        
        
    def _add_country_to_tree_fast(self, parent_item, country, country_icons):
        """Быстрое добавление страны без лишних запросов к БД"""
        if parent_item is None:
            return
        
        # Считаем монеты быстро (можно закэшировать)
        coin_count = getattr(country, '_coin_count', None)
        if coin_count is None:
            from database.models import Coin
            coin_count = self.main_window.db_manager.session.query(Coin).filter_by(
                country_id=country.id
            ).count()
            country._coin_count = coin_count
        
        country_item = QTreeWidgetItem(parent_item)
        
        # Устанавливаем иконку из кэша
        if country.id in country_icons:
            country_item.setIcon(0, country_icons[country.id])
        
        # Устанавливаем текст
        if coin_count > 0:
            country_item.setText(0, f"{country.name} ({coin_count})")
        else:
            country_item.setText(0, country.name)
        
        country_item.setData(0, Qt.UserRole, country.id)
        country_item.setToolTip(0, f"Показать монеты {country.name}")
        country_item.setFlags(country_item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        
    def paintEvent(self, event):
        """Рисуем дерево, а поверх — свои плюсики/минусы в зоне веток"""
        super().paintEvent(event)

        # ВАЖНО: QRect живёт в QtCore, а НЕ в QtGui!
        from PySide6.QtGui import QPainter, QPen, QColor
        from PySide6.QtCore import QRect

        # Цвета из текущей темы
        arrow_color = QColor('#a8a8d0')
        base_color = QColor('#1a1a2e')
        alt_color = QColor('#16213e')
        if hasattr(self.main_window, 'theme_manager'):
            theme = self.main_window.theme_manager.current_theme
            arrow_color = QColor(theme.get('arrow_color', '#a8a8d0'))
            base_color = QColor(theme.get('base', '#1a1a2e'))
            alt_color = QColor(theme.get('alternate_base', '#16213e'))

        painter = QPainter(self.viewport())
        try:
            indent = self.indentation()
            pen = QPen(arrow_color)
            pen.setWidth(2)
            vp_height = self.viewport().height()

            def draw_item(item):
                if item.childCount() > 0:
                    vr = self.visualItemRect(item)
                    if vr.isValid() and vr.bottom() >= 0 and vr.top() <= vp_height:
                        # Закрашиваем "тёмную полоску" цветом фона строки
                        row = self.indexFromItem(item).row()
                        br = QRect(vr.x() - indent, vr.y(), indent, vr.height())
                        painter.fillRect(br, alt_color if row % 2 else base_color)
                        # Рисуем плюс/минус по центру зоны ветки
                        painter.setPen(pen)
                        cx = br.center().x()
                        cy = br.center().y()
                        half = max(3, indent // 2 - 4)
                        # горизонтальная линия (минус) — всегда
                        painter.drawLine(cx - half, cy, cx + half, cy)
                        # вертикальная линия — только у свёрнутой ветки (плюс)
                        if not item.isExpanded():
                            painter.drawLine(cx, cy - half, cx, cy + half)
                if item.isExpanded():
                    for i in range(item.childCount()):
                        draw_item(item.child(i))

            for i in range(self.topLevelItemCount()):
                draw_item(self.topLevelItem(i))
        finally:
            painter.end()
            
    # ================= ФЛАГИ СТРАН (data/country_flags) =================
    def _flags_dir(self):
        """Папка флагов: data/country_flags (синхронизируется с Google Drive)"""
        from utils.paths import paths
        d = paths.get_data_dir() / "country_flags"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _flag_icon(self, country_id, width=20, height=14):
        """Иконка флага страны (кэш). None, если флага нет."""
        if not country_id:
            return None
        cache = getattr(self, '_flag_icon_cache', None)
        if cache is None:
            self._flag_icon_cache = {}
            cache = self._flag_icon_cache
        key = (country_id, width, height)
        if key in cache:
            return cache[key]
        icon = None
        try:
            from utils.flag_storage import load_icon
            icon = load_icon(country_id, width, height)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки флага: {e}")
        cache[key] = icon
        return icon

    def setup_flag_context_menu(self):
        """Подключает контекстное меню загрузки флага (вызывать в __init__)"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_country_context_menu)

    def _show_country_context_menu(self, pos):
        """ПКМ на стране: загрузка/удаление флага"""
        item = self.itemAt(pos)
        if not item:
            return
        cid = item.data(0, Qt.UserRole)
        if not cid:
            return
        menu = QMenu(self)
        load_act = QAction("🏳️ Загрузить флаг страны...", self)
        load_act.triggered.connect(lambda: self._load_country_flag(item))
        menu.addAction(load_act)
        remove_act = QAction("🗑️ Убрать флаг", self)
        remove_act.triggered.connect(lambda: self._remove_country_flag(item))
        menu.addAction(remove_act)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _load_country_flag(self, item):
        """Диалог выбора файла -> сохраняем в data/country_flags/{id}.png ->
        обновляем дерево, таблицу и вкладку страны"""
        cid = item.data(0, Qt.UserRole)
        if not cid:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите флаг страны", str(self._flags_dir()),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*)")
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Флаг страны", "Не удалось открыть файл изображения")
            return
        if pix.save(str(self._flags_dir() / f"{cid}.png"), "PNG"):
            self.logger.info(f"🏳️ Флаг сохранён: {cid}.png (синхронизируется с Google Drive)")
            self.refresh_flags()
            self._notify_flag_changed()
        else:
            QMessageBox.warning(self, "Флаг страны", "Не удалось сохранить флаг")

    def _remove_country_flag(self, item):
        """Удаляет файл флага страны"""
        cid = item.data(0, Qt.UserRole)
        if not cid:
            return
        path = self._flags_dir() / f"{cid}.png"
        if path.exists():
            path.remove()
            self.logger.info(f"🗑️ Флаг удалён: {cid}.png")
            self.refresh_flags()
            self._notify_flag_changed()

    def refresh_flags(self):
        """Обновляет иконки флагов на ВСЕХ пунктах стран дерева"""
        self._flag_icon_cache = {}
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            cid = item.data(0, Qt.UserRole)
            if cid:
                icon = self._flag_icon(cid)
                if icon:
                    item.setIcon(0, icon)
            for c in range(item.childCount()):
                stack.append(item.child(c))

    def _notify_flag_changed(self):
        """Уведомляет таблицу и вкладку страны о смене флагов"""
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if w.__class__.__name__ == 'MainWindow':
                tp = getattr(w, 'table_panel', None)
                if tp is not None:
                    if hasattr(tp, '_flag_icon_cache'):
                        tp._flag_icon_cache = {}
                    if hasattr(tp, '_render_page'):
                        tp._render_page()
                dp = getattr(w, 'detail_panel', None)
                ct = getattr(dp, 'country_tab', None) if dp else None
                if ct is not None and hasattr(ct, 'refresh_country_flag'):
                    ct.refresh_country_flag()
                break