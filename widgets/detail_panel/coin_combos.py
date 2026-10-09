# ===== gui/widgets/detail_panel/coin_combos.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Загрузка данных в комбобоксы для CoinTab
"""

import logging
from database.models import Metal, Edge, StandardReference


class CoinCombosMixin:
    """Миксин для загрузки данных в комбобоксы"""
    
    def load_countries_to_combo(self):
        """Загружает страны в комбобокс"""
        combo = self.edit_fields['country']
        combo.blockSignals(True)
        combo.clear()
        for country in self.db_manager.get_all_countries():
            combo.addItem(country.name, country.id)
        combo.blockSignals(False)
    
    def load_currencies_to_combo(self):
        """Загружает валюты в комбобокс"""
        combo = self.edit_fields['currency']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for currency in self.db_manager.get_all_currencies():
            combo.addItem(currency.get_display_text(), currency.id)
        combo.blockSignals(False)
    
    def load_mints_to_combo(self):
        """Загружает монетные дворы в комбобокс"""
        combo = self.edit_fields['mint']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for mint in self.db_manager.get_all_mints():
            combo.addItem(mint.get_display_text(), mint.id)
        combo.blockSignals(False)
    
    def load_metals_to_combo(self):
        """Загружает металлы в комбобокс"""
        combo = self.edit_fields['metal']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        metals = self.db_manager.session.query(Metal).order_by(Metal.name).all()
        
        silver, gold, other = [], [], []
        for metal in metals:
            name_lower = metal.name.lower()
            purity = 0
            if metal.purity:
                try:
                    purity = int(metal.purity)
                except:
                    pass
            if 'серебро' in name_lower or 'silver' in name_lower:
                silver.append((metal, purity))
            elif 'золото' in name_lower or 'gold' in name_lower:
                gold.append((metal, purity))
            else:
                other.append((metal, purity))
        
        silver.sort(key=lambda x: x[1], reverse=True)
        gold.sort(key=lambda x: x[1], reverse=True)
        other.sort(key=lambda x: x[1], reverse=True)
        
        for metal, _ in silver:
            combo.addItem(metal.get_display_text(), metal.id)
        for metal, _ in gold:
            combo.addItem(metal.get_display_text(), metal.id)
        for metal, _ in other:
            combo.addItem(metal.get_display_text(), metal.id)
        
        combo.blockSignals(False)
    
    def load_edges_to_combo(self):
        """Загружает типы гурта в комбобокс"""
        combo = self.edit_fields['edge']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for edge in self.db_manager.session.query(Edge).order_by(Edge.name).all():
            combo.addItem(edge.name, edge.id)
        combo.blockSignals(False)
    
    def load_purchase_countries_to_combo(self):
        """Загружает страны приобретения в комбобокс"""
        combo = self.edit_fields['purchase_country']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for country in self.db_manager.get_all_purchase_countries():
            combo.addItem(country.name, country.id)
        combo.blockSignals(False)
    
    def load_periods_to_combo(self):
        """Загружает периоды в комбобокс с фильтрацией по выбранной стране"""
        if 'period_id' not in self.edit_fields:
            return
        
        combo = self.edit_fields['period_id']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        # Получаем выбранную страну
        country_id = self.edit_fields['country'].currentData()
        
        if country_id:
            periods = self.db_manager.get_periods_by_country(country_id)
        else:
            periods = self.db_manager.get_all_periods()
        
        for period in periods:
            combo.addItem(period.get_display_text(), period.id)
        
        combo.blockSignals(False)
    
    def load_condition_to_combo(self):
        """Загружает справочник сохранности в комбобокс"""
        if 'condition' not in self.edit_fields:
            return
        
        combo = self.edit_fields['condition']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='condition'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено сохранностей: {len(refs)}")
    
    def load_rarity_to_combo(self):
        """Загружает справочник редкости в комбобокс"""
        if 'rarity' not in self.edit_fields:
            return
        
        combo = self.edit_fields['rarity']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='rarity'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено редкостей: {len(refs)}")
    
    def load_shape_to_combo(self):
        """Загружает справочник форм в комбобокс"""
        if 'shape' not in self.edit_fields:
            return
        
        combo = self.edit_fields['shape']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='shape'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено форм: {len(refs)}")
    
    def load_issue_type_to_combo(self):
        """Загружает справочник типов выпуска в комбобокс"""
        if 'issue_type' not in self.edit_fields:
            return
        
        combo = self.edit_fields['issue_type']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='issue_type'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено типов выпуска: {len(refs)}")
    
    def load_avrev_to_combo(self):
        """Загружает справочник АВ/РЕВ в комбобокс"""
        if 'avrev' not in self.edit_fields:
            return
        
        combo = self.edit_fields['avrev']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='avrev'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено АВ/РЕВ: {len(refs)}")
    
    def load_status_to_combo(self):
        """Загружает справочник статусов в комбобокс"""
        if 'status' not in self.edit_fields:
            return
        
        combo = self.edit_fields['status']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        from database.models import StandardReference
        statuses = self.db_manager.session.query(StandardReference).filter_by(
            field_key='status'
        ).order_by(StandardReference.sort_order).all()
        
        for status in statuses:
            combo.addItem(status.name, status.id)
        
        combo.blockSignals(False)
    
    def load_acquisition_type_to_combo(self):
        """Загружает справочник типов приобретения в комбобокс"""
        if 'acquisition_type' not in self.edit_fields:
            return
        
        combo = self.edit_fields['acquisition_type']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='acquisition_type'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено типов приобретения: {len(refs)}")
    
    def load_storage_location_to_combo(self):
        """Загружает справочник мест хранения в комбобокс"""
        if 'storage_location' not in self.edit_fields:
            return
        
        combo = self.edit_fields['storage_location']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='storage_location'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
        
        combo.blockSignals(False)
        self.logger.debug(f"Загружено мест хранения: {len(refs)}")
    
    def load_all_combos(self):
        self.load_countries_to_combo()
        self.load_currencies_to_combo()
        self.load_mints_to_combo()
        self.load_metals_to_combo()
        self.load_edges_to_combo()
        self.load_purchase_countries_to_combo()
        self.load_periods_to_combo()
        self.load_condition_to_combo()
        self.load_rarity_to_combo()
        self.load_shape_to_combo()
        self.load_issue_type_to_combo()
        self.load_avrev_to_combo()
        self.load_status_to_combo()  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
        self.load_acquisition_type_to_combo()
        self.load_storage_location_to_combo()