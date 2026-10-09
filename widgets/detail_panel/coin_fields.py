# ===== gui/widgets/detail_panel/coin_fields.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Создание полей для редактирования монеты
"""

from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QPushButton
from PySide6.QtCore import QDate
from .base_panel import ClickableTextEdit
from database.models import Metal, Edge, StandardReference


class CoinFieldsMixin:
    """Миксин для создания полей редактирования"""
    
    FIELD_HEIGHT = 18
    DATE_HEIGHT = 20
    FIELD_WIDTH = 142      # Ширина для обычных полей и комбобоксов без кнопки
    COMBO_WIDTH = 132       # Ширина для комбобоксов с кнопкой
    
    COMBO_STYLE = "QComboBox { padding: 1px; font-size: 11px; }"
    LINE_EDIT_STYLE = "QLineEdit { padding: 1px; font-size: 11px; }"
    SPINBOX_STYLE = "QSpinBox { padding: 1px; font-size: 11px; }"
    DOUBLESPINBOX_STYLE = "QDoubleSpinBox { padding: 1px; font-size: 11px; }"
    DATEEDIT_STYLE = "QDateEdit { padding: 1px; font-size: 11px; }"
    REF_BUTTON_STYLE = """
        QPushButton { 
            padding: 0px; 
            font-size: 11px; 
            margin: 0px;
            max-height: 16px;
            min-height: 16px;
        }
    """
    
    def create_combo(self, editable=False, width=COMBO_WIDTH):
        combo = QComboBox()
        combo.setEditable(editable)
        combo.setFixedHeight(self.FIELD_HEIGHT)
        combo.setMinimumWidth(width)
        combo.setMaximumWidth(width)
        combo.setStyleSheet("""
            QComboBox {
                padding: 1px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #ccc;
            }
            QComboBox QAbstractItemView {
                min-width: 280px;
                max-width: 450px;
            }
        """)
        
        return combo
    
    def create_line_edit(self, placeholder=""):
        line_edit = QLineEdit()
        if placeholder:
            line_edit.setPlaceholderText(placeholder)
        line_edit.setFixedHeight(self.FIELD_HEIGHT)
        line_edit.setMinimumWidth(self.FIELD_WIDTH)
        line_edit.setStyleSheet(self.LINE_EDIT_STYLE)
        return line_edit
    
    def create_spinbox(self, range_min=-5000, range_max=2100):
        spin = QSpinBox()
        spin.setRange(range_min, range_max)
        spin.setSpecialValueText("—")
        spin.setFixedHeight(self.FIELD_HEIGHT)
        spin.setMinimumWidth(self.FIELD_WIDTH)
        spin.setStyleSheet(self.SPINBOX_STYLE)
        return spin
    
    def create_doublespinbox(self, range_min=0, range_max=10000, suffix="", decimals=2):
        dspin = QDoubleSpinBox()
        dspin.setRange(range_min, range_max)
        dspin.setSuffix(suffix)
        dspin.setDecimals(decimals)
        dspin.setSpecialValueText("—")
        dspin.setFixedHeight(self.FIELD_HEIGHT)
        dspin.setMinimumWidth(self.FIELD_WIDTH)
        dspin.setStyleSheet(self.DOUBLESPINBOX_STYLE)
        return dspin
    
    def create_dateedit(self):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        date_edit.setSpecialValueText("Не указана")
        date_edit.setFixedHeight(self.DATE_HEIGHT)
        date_edit.setMinimumWidth(self.FIELD_WIDTH)
        date_edit.setStyleSheet(self.DATEEDIT_STYLE)
        return date_edit
    
    def create_textedit(self, height=50):
        text_edit = ClickableTextEdit(self, "")
        text_edit.setFixedHeight(height)
        text_edit.setMinimumWidth(self.FIELD_WIDTH)
        return text_edit
    
    def create_ref_button(self, ref_type, tooltip):
        btn = QPushButton("📚")
        btn.setFixedSize(20, self.FIELD_HEIGHT)
        btn.clicked.connect(lambda: self.open_references(ref_type))
        btn.setToolTip(tooltip)
        btn.setStyleSheet(self.REF_BUTTON_STYLE)
        return btn
    
    def create_edit_fields(self):
        """Создает все поля для редактирования"""
        self.edit_fields = {}
        
        # ===== ОСНОВНАЯ ИНФОРМАЦИЯ =====
        
        self.edit_fields['country'] = self.create_combo(editable=True)
        self.edit_fields['country'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['country'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['country'].wheelEvent = lambda event: None
        
        self.edit_fields['catalog_number'] = self.create_line_edit("Y#123")
        self.edit_fields['catalog_number'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['catalog_number'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['catalog_number'].wheelEvent = lambda event: None
        
        self.edit_fields['denomination_value'] = self.create_line_edit("1,2,5,10")
        self.edit_fields['denomination_value'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['denomination_value'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['denomination_value'].wheelEvent = lambda event: None
        
        self.edit_fields['currency'] = self.create_combo()
        self.edit_fields['currency'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['currency'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['currency'].wheelEvent = lambda event: None
        
        self.edit_fields['year'] = self.create_spinbox()
        self.edit_fields['year'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['year'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['year'].wheelEvent = lambda event: None
        
        self.edit_fields['century'] = self.create_combo()
        self.edit_fields['century'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['century'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['century'].wheelEvent = lambda event: None
        self.edit_fields['century'].addItems(["", "XXI", "XX", "XIX", "XVIII", "XVII", "XVI", "XV", "XIV", "XIII", "XII", "XI", 
                                              "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I", "до н.э."])
        
        # ===== МОНЕТНЫЙ ДВОР =====
        
        self.edit_fields['mint'] = self.create_combo()
        self.edit_fields['mint'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['mint'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['mint'].wheelEvent = lambda event: None
        
        self.edit_fields['mint_mark'] = self.create_line_edit("ММД, СПМД")
        self.edit_fields['mint_mark'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['mint_mark'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['mint_mark'].wheelEvent = lambda event: None
        
        # ===== ХАРАКТЕРИСТИКИ =====
        
        self.edit_fields['edge'] = self.create_combo()
        self.edit_fields['edge'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['edge'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['edge'].wheelEvent = lambda event: None
        
        self.edit_fields['edge_description'] = self.create_textedit(50)
        self.edit_fields['edge_description'].field_name = "Описание гурта"
        self.edit_fields['edge_description'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['edge_description'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['edge_description'].wheelEvent = lambda event: None
        
        self.edit_fields['metal'] = self.create_combo()
        self.edit_fields['metal'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['metal'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['metal'].wheelEvent = lambda event: None
        
        self.edit_fields['weight'] = self.create_doublespinbox(suffix=" г")
        self.edit_fields['weight'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['weight'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['weight'].wheelEvent = lambda event: None
        
        self.edit_fields['diameter'] = self.create_doublespinbox(range_max=500, suffix=" мм")
        self.edit_fields['diameter'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['diameter'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['diameter'].wheelEvent = lambda event: None
        
        self.edit_fields['shape'] = self.create_combo()
        self.edit_fields['shape'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['shape'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['shape'].wheelEvent = lambda event: None
        
        # ===== СОСТОЯНИЕ =====
        
        self.edit_fields['condition'] = self.create_combo()
        self.edit_fields['condition'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['condition'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['condition'].wheelEvent = lambda event: None
        
        self.edit_fields['rarity'] = self.create_combo()
        self.edit_fields['rarity'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['rarity'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['rarity'].wheelEvent = lambda event: None
        
        self.edit_fields['storage_location'] = self.create_combo()
        self.edit_fields['storage_location'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['storage_location'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['storage_location'].wheelEvent = lambda event: None
        
        self.edit_fields['issue_type'] = self.create_combo()
        self.edit_fields['issue_type'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['issue_type'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['issue_type'].wheelEvent = lambda event: None
        
        self.edit_fields['avrev'] = self.create_combo()
        self.edit_fields['avrev'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['avrev'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['avrev'].wheelEvent = lambda event: None
        
        # ===== СТАТУС =====
        
        self.edit_fields['status'] = self.create_combo()
        self.edit_fields['status'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['status'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['status'].wheelEvent = lambda event: None
        
        # ===== ПОКУПКА =====
        
        self.edit_fields['purchase_date'] = self.create_dateedit()
        self.edit_fields['purchase_date'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_date'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_date'].wheelEvent = lambda event: None
        
        self.edit_fields['purchase_price'] = self.create_doublespinbox(range_max=10000000, suffix=" ₽")
        self.edit_fields['purchase_price'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_price'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_price'].wheelEvent = lambda event: None
        
        self.edit_fields['purchase_where'] = self.create_combo()
        self.edit_fields['purchase_where'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_where'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_where'].wheelEvent = lambda event: None
        self.edit_fields['purchase_where'].addItems(["", "EBAY", "Lave.ru", "UCOIN", "Авито", "БАНК", "Подарок", "Магазин", "Мешок", "Молоток"])
        
        self.edit_fields['purchase_country'] = self.create_combo()
        self.edit_fields['purchase_country'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['purchase_country'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['purchase_country'].wheelEvent = lambda event: None
        self.edit_fields['purchase_country'].setEditable(True)
        
        self.edit_fields['acquisition_type'] = self.create_combo()
        self.edit_fields['acquisition_type'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['acquisition_type'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['acquisition_type'].wheelEvent = lambda event: None
        
        self.edit_fields['sale_price'] = self.create_doublespinbox(range_max=10000000, suffix=" ₽")
        self.edit_fields['sale_price'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['sale_price'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['sale_price'].wheelEvent = lambda event: None
        
        self.edit_fields['purchase_info'] = self.create_textedit(50)
        self.edit_fields['purchase_info'].field_name = "Информация о покупке"
        self.edit_fields['purchase_info'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_info'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['purchase_info'].wheelEvent = lambda event: None
        
        self.edit_fields['coin_info'] = self.create_textedit(50)
        self.edit_fields['coin_info'].field_name = "Информация о монете"
        self.edit_fields['coin_info'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['coin_info'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['coin_info'].wheelEvent = lambda event: None
        
        self.edit_fields['ucoin_url'] = self.create_line_edit("https://ru.ucoin.net/...")
        self.edit_fields['ucoin_url'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['ucoin_url'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['ucoin_url'].wheelEvent = lambda event: None
        
        self.edit_fields['meshok_url'] = self.create_line_edit("https://meshok.net/...")
        self.edit_fields['meshok_url'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['meshok_url'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['meshok_url'].wheelEvent = lambda event: None
        
        # ===== РЫНОЧНАЯ ЦЕНА =====
        
        self.edit_fields['market_price'] = self.create_doublespinbox(range_max=10000000, suffix=" ₽")
        self.edit_fields['market_price'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['market_price'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['market_price'].wheelEvent = lambda event: None
        
        self.edit_fields['market_price_date'] = self.create_dateedit()
        self.edit_fields['market_price_date'].setMinimumWidth(self.FIELD_WIDTH)
        self.edit_fields['market_price_date'].setMaximumWidth(self.FIELD_WIDTH)
        self.edit_fields['market_price_date'].wheelEvent = lambda event: None
        
        # ===== ПЕРИОД (СПРАВОЧНИК) =====
        
        self.edit_fields['period_id'] = self.create_combo()
        self.edit_fields['period_id'].setMinimumWidth(self.COMBO_WIDTH)
        self.edit_fields['period_id'].setMaximumWidth(self.COMBO_WIDTH)
        self.edit_fields['period_id'].wheelEvent = lambda event: None

    # ========== ЗАГРУЗКА СПРАВОЧНИКОВ ==========
    
    def load_countries_to_combo(self):
        """Загружает страны в комбобокс"""
        combo = self.edit_fields['country']
        combo.blockSignals(True)
        combo.clear()
        for country in self.db_manager.get_all_countries():
            combo.addItem(country.name, country.id)
        combo.blockSignals(False)
        print(f"  Загружено стран: {combo.count()}")
    
    def load_currencies_to_combo(self):
        """Загружает валюты в комбобокс"""
        combo = self.edit_fields['currency']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for currency in self.db_manager.get_all_currencies():
            combo.addItem(currency.get_display_text(), currency.id)
        combo.blockSignals(False)
        print(f"  Загружено валют: {combo.count()}")
    
    def load_mints_to_combo(self):
        """Загружает монетные дворы в комбобокс"""
        combo = self.edit_fields['mint']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for mint in self.db_manager.get_all_mints():
            combo.addItem(mint.get_display_text(), mint.id)
        combo.blockSignals(False)
        print(f"  Загружено монетных дворов: {combo.count()}")
    
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
        print(f"  Загружено металлов: {combo.count()}")
    
    def load_edges_to_combo(self):
        """Загружает типы гурта в комбобокс"""
        combo = self.edit_fields['edge']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for edge in self.db_manager.session.query(Edge).order_by(Edge.name).all():
            combo.addItem(edge.name, edge.id)
        combo.blockSignals(False)
        print(f"  Загружено гуртов: {combo.count()}")
    
    def load_purchase_countries_to_combo(self):
        """Загружает страны приобретения в комбобокс"""
        combo = self.edit_fields['purchase_country']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        for country in self.db_manager.get_all_purchase_countries():
            combo.addItem(country.name, country.id)
        combo.blockSignals(False)
        print(f"  Загружено стран приобретения: {combo.count()}")
    
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
        print(f"  Загружено периодов: {combo.count()}")
    
    def load_condition_combo(self):
        """Загружает справочник сохранности"""
        if 'condition' not in self.edit_fields:
            print("❌ load_condition_combo: поле 'condition' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['condition']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='condition').count()
        print(f"  📊 condition: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='condition'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено сохранностей: {combo.count()}")
    
    def load_rarity_combo(self):
        """Загружает справочник редкости"""
        if 'rarity' not in self.edit_fields:
            print("❌ load_rarity_combo: поле 'rarity' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['rarity']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='rarity').count()
        print(f"  📊 rarity: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='rarity'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено редкостей: {combo.count()}")
    
    def load_shape_combo(self):
        """Загружает справочник форм"""
        if 'shape' not in self.edit_fields:
            print("❌ load_shape_combo: поле 'shape' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['shape']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='shape').count()
        print(f"  📊 shape: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='shape'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено форм: {combo.count()}")
    
    def load_issue_type_combo(self):
        """Загружает справочник типов выпуска"""
        if 'issue_type' not in self.edit_fields:
            print("❌ load_issue_type_combo: поле 'issue_type' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['issue_type']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='issue_type').count()
        print(f"  📊 issue_type: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='issue_type'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено типов выпуска: {combo.count()}")
    
    def load_avrev_combo(self):
        """Загружает справочник АВ/РЕВ"""
        if 'avrev' not in self.edit_fields:
            print("❌ load_avrev_combo: поле 'avrev' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['avrev']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='avrev').count()
        print(f"  📊 avrev: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='avrev'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено АВ/РЕВ: {combo.count()}")
    
    def load_status_combo(self):
        """Загружает справочник статусов"""
        if 'status' not in self.edit_fields:
            print("❌ load_status_combo: поле 'status' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['status']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='status').count()
        print(f"  📊 status: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='status'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено статусов: {combo.count()}")
    
    def load_acquisition_type_combo(self):
        """Загружает справочник типов приобретения"""
        if 'acquisition_type' not in self.edit_fields:
            print("❌ load_acquisition_type_combo: поле 'acquisition_type' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['acquisition_type']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='acquisition_type').count()
        print(f"  📊 acquisition_type: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='acquisition_type'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено типов приобретения: {combo.count()}")
    
    def load_storage_location_combo(self):
        """Загружает справочник мест хранения (альбом)"""
        if 'storage_location' not in self.edit_fields:
            print("❌ load_storage_location_combo: поле 'storage_location' не найдено в edit_fields")
            return
        
        combo = self.edit_fields['storage_location']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        count = self.db_manager.session.query(StandardReference).filter_by(field_key='storage_location').count()
        print(f"  📊 storage_location: найдено записей в БД: {count}")
        
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='storage_location'
        ).order_by(StandardReference.sort_order).all()
        
        for ref in refs:
            combo.addItem(ref.name, ref.id)
            print(f"    - {ref.name} (ID: {ref.id})")
        
        combo.blockSignals(False)
        print(f"  ✅ Загружено мест хранения: {combo.count()}")
    
    def load_all_combos(self):
        """Загружает все комбобоксы"""
        print("=" * 60)
        print("🔄 load_all_combos called")
        print(f"  edit_fields keys: {list(self.edit_fields.keys())}")
        print("=" * 60)
        
        self.load_countries_to_combo()
        self.load_currencies_to_combo()
        self.load_mints_to_combo()
        self.load_metals_to_combo()
        self.load_edges_to_combo()
        self.load_purchase_countries_to_combo()
        self.load_periods_to_combo()
        
        print("-" * 40)
        print("ЗАГРУЗКА СТАНДАРТНЫХ СПРАВОЧНИКОВ:")
        print("-" * 40)
        
        self.load_condition_combo()
        self.load_rarity_combo()
        self.load_storage_location_combo()
        self.load_issue_type_combo()
        self.load_avrev_combo()
        self.load_acquisition_type_combo()
        self.load_status_combo()
        self.load_shape_combo()
        
        print("=" * 60)