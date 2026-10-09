# -*- coding: utf-8 -*-

"""
Методы MainWindow для работы с деревом стран
"""

import traceback
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer
from database.models import Country, Coin


class TreeHandlersMixin:
    """Примесь с методами работы с деревом стран"""
    
    def load_country_tree(self, preserve_expanded=False):
        """Загружает дерево стран"""
        self.tree_panel.load_tree(preserve_expanded)
        
        # Авто-выбор КОЛЛЕКЦИИ после загрузки
        QTimer.singleShot(500, self.tree_panel.select_collection_item)
    
    def create_new_country(self, country_data):
        """Создает новую страну в базе данных"""
        try:
            existing = self.db_manager.session.query(Country).filter_by(name=country_data['name']).first()
            if existing:
                QMessageBox.warning(self, "Предупреждение", 
                                   f"Страна '{country_data['name']}' уже существует в базе данных.")
                return
            
            country = Country(
                name=country_data['name'],
                code=country_data['code'] or None,
                continent=country_data['continent'],
                is_extinct=country_data['is_extinct']
            )
            
            self.db_manager.session.add(country)
            self.db_manager.session.commit()
            
            self.logger.info(f"Добавлена новая страна: {country_data['name']}")
            self.status_bar.showMessage(f"✅ Страна '{country_data['name']}' добавлена", 3000)
            
            self.tree_panel.save_expanded_state()
            self.load_country_tree(preserve_expanded=True)
            self.detail_panel.refresh_country_combos()
            self.settings_manager.save_tree_structure(self.country_tree)
            
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении страны: {e}")
            self.db_manager.session.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить страну:\n{e}")
    
    def delete_country(self, country_id):
        """Удаляет страну"""
        country = self.db_manager.session.query(Country).get(country_id)
        if not country:
            return
        
        coin_count = self.db_manager.session.query(Coin).filter_by(country_id=country_id).count()
        
        if coin_count > 0:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"У страны '{country.name}' есть {coin_count} монет.\n"
                f"При удалении страны все эти монеты также будут удалены!\n\n"
                f"Вы уверены, что хотите продолжить?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.tree_panel.save_expanded_state()
                self.db_manager.delete_country(country_id)
                self.logger.info(f"Удалена страна '{country.name}' вместе с {coin_count} монетами")
                self.status_bar.showMessage(f"✅ Страна и связанные монеты удалены", 3000)
                
                self.load_country_tree(preserve_expanded=True)
                self.load_coins()
                self.detail_panel.refresh_country_combos()
                self.settings_manager.save_tree_structure(self.country_tree)
                
                if self.current_filter_country_id == country_id:
                    self.current_filter_country_id = None
        else:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Удалить страну '{country.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.tree_panel.save_expanded_state()
                self.db_manager.delete_country_without_coins(country_id)
                self.logger.info(f"Удалена страна '{country.name}'")
                self.status_bar.showMessage(f"✅ Страна удалена", 3000)
                
                self.load_country_tree(preserve_expanded=True)
                self.detail_panel.refresh_country_combos()
                self.settings_manager.save_tree_structure(self.country_tree)
    
    def update_country_continent(self, country_id, new_continent, is_extinct):
        """Обновляет континент и статус исчезновения страны при перетаскивании"""
        try:
            country = self.db_manager.session.query(Country).get(country_id)
            if not country:
                return
            
            updated = False
            changes = []
            
            if new_continent != country.continent:
                old_continent = country.continent
                country.continent = new_continent
                updated = True
                changes.append(f"континент: {old_continent or 'не указан'} → {new_continent or 'не указан'}")
            
            if is_extinct != country.is_extinct:
                old_status = "исчезнувшая" if country.is_extinct else "существующая"
                new_status = "исчезнувшая" if is_extinct else "существующая"
                country.is_extinct = is_extinct
                updated = True
                changes.append(f"статус: {old_status} → {new_status}")
            
            if updated:
                self.db_manager.session.commit()
                self.logger.info(f"Страна '{country.name}' обновлена: {', '.join(changes)}")
                self.status_bar.showMessage(f"✅ Информация о стране обновлена", 3000)
                
                self.tree_panel.save_expanded_state()
                self.load_country_tree(preserve_expanded=True)
                self.settings_manager.save_tree_structure(self.country_tree)
                
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении континента страны: {e}")
            self.db_manager.session.rollback()
    
    def on_country_selected(self, country_id, country_name):
        """
        Обработчик выбора страны в дереве для обновления погодовки
        
        Args:
            country_id: ID страны или None для "Все страны"
            country_name: Название страны или "Вся коллекция" для корня
        """
        self.logger.info(f"on_country_selected: country_id={country_id}, country_name={country_name}")
        
        # Защита от рекурсии
        if hasattr(self, '_updating_yearly') and self._updating_yearly:
            self.logger.info("  ⏭️ Уже выполняется обновление погодовки, пропускаем")
            return
        
        self._updating_yearly = True
        
        try:
            # Обновляем погодовку
            if hasattr(self, 'yearly_table_tab') and self.yearly_table_tab:
                self.logger.info(f"  📅 Обновление погодовки для {country_name} (ID: {country_id})")
                self.yearly_table_tab.set_country(country_id, country_name)
            else:
                self.logger.warning("  ⚠️ yearly_table_tab не найден")
        except Exception as e:
            self.logger.error(f"  ❌ Ошибка обновления погодовки: {e}")
        finally:
            self._updating_yearly = False
    
    def _goto_country(self, country_id):
        """Переходит к стране в дереве и загружает её монеты"""
        if not country_id:
            return
        
        def find_item(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, Qt.UserRole) == country_id:
                    return child
                result = find_item(child)
                if result:
                    return result
            return None
        
        country_item = None
        for i in range(self.country_tree.topLevelItemCount()):
            item = self.country_tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == country_id:
                country_item = item
                break
            country_item = find_item(item)
            if country_item:
                break
        
        if country_item:
            parent = country_item.parent()
            while parent:
                self.country_tree.expandItem(parent)
                parent = parent.parent()
            
            self.country_tree.setCurrentItem(country_item)
            self.country_tree.scrollToItem(country_item)
            
            self.current_filter_country_id = country_id
            self.current_folder_country_ids = None
            self.load_coins()
            
            country = self.db_manager.session.query(Country).get(country_id)
            if country:
                self.detail_panel.show_country_info(country)
                self.on_country_selected(country_id, country.name)
            
            self.status_bar.showMessage(f"🌍 Загружены монеты страны: {country_item.text(0)}", 3000)
    
    def get_country_ids_from_folder(self, folder_item):
        """Рекурсивно собирает ID всех стран в папке и подпапках"""
        country_ids = []
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            country_id = child.data(0, Qt.UserRole)
            if country_id is not None:
                country_ids.append(country_id)
            else:
                country_ids.extend(self.get_country_ids_from_folder(child))
        return country_ids