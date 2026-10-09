# ===== database/models.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Модели данных для Coin Collector
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from datetime import datetime
import logging
Base = declarative_base()


class Country(Base):
    """Модель страны"""
    __tablename__ = 'countries'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(10), nullable=True)  # Код страны (ISO)
    
    # География
    continent = Column(String(50), nullable=True)
    capital = Column(String(100), nullable=True)
    area = Column(Integer, nullable=True)  # Площадь в км²
    population = Column(Integer, nullable=True)  # Население
    
    # Государственное устройство
    government_type = Column(String(100), nullable=True)  # Форма правления
    independence_date = Column(String(50), nullable=True)  # Дата независимости
    
    # Культура
    language = Column(String(100), nullable=True)  # Официальный язык
    religion = Column(String(100), nullable=True)  # Основная религия
    
    # Коды
    iso2 = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    iso3 = Column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    ioc_code = Column(String(3), nullable=True)  # Код МОК
    
    # Валюта
    currency_name = Column(String(100), nullable=True)
    currency_code = Column(String(3), nullable=True)  # ISO 4217
    
    # Статус
    is_extinct = Column(Boolean, default=False)  # Исчезнувшая страна
    
    # Преемники (для исторической преемственности)
    # Связь многие-ко-многим с самой собой
    successors = relationship(
        'Country',
        secondary='country_successors',
        primaryjoin='Country.id==country_successors.c.extinct_country_id',
        secondaryjoin='Country.id==country_successors.c.modern_country_id',
        backref='predecessors'
    )
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
     
    def __repr__(self):
        return f"<Country(id={self.id}, name='{self.name}')>"
    
    def get_formatted_area(self):
        """Возвращает отформатированную площадь"""
        if not self.area:
            return None
        if self.area >= 1_000_000:
            return f"{self.area / 1_000_000:.2f} млн км²"
        return f"{self.area:,} км²".replace(',', ' ')
    
    def get_formatted_population(self):
        """Возвращает отформатированное население"""
        if not self.population:
            return None
        if self.population >= 1_000_000:
            return f"{self.population / 1_000_000:.2f} млн"
        return f"{self.population:,}".replace(',', ' ')
    
    def get_successors_display(self):
        """Возвращает строковое представление преемников"""
        if not self.successors:
            return ""
        return ", ".join([s.name for s in self.successors])


# Таблица для связи исчезнувших стран с современными (многие-ко-многим)
class CountrySuccessor(Base):
    __tablename__ = 'country_successors'
    
    id = Column(Integer, primary_key=True)
    extinct_country_id = Column(Integer, ForeignKey('countries.id'))
    modern_country_id = Column(Integer, ForeignKey('countries.id'))
    created_at = Column(DateTime, default=datetime.now)


class Currency(Base):
    """Модель валюты (справочник)"""
    __tablename__ = 'currencies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # Название валюты
    code = Column(String(3), nullable=True)  # Код валюты (ISO 4217)
    symbol = Column(String(10), nullable=True)  # Символ валюты
    exchange_rate = Column(Float, nullable=True)  # Курс к рублю
    description = Column(Text, nullable=True)  # Описание
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь с монетами
    coins = relationship("Coin", back_populates="currency_obj")
    
    def __repr__(self):
        return f"<Currency(id={self.id}, name='{self.name}')>"
    
    def get_display_text(self):
        """Возвращает текст для отображения в комбобоксе"""
        parts = []
        if self.name:
            parts.append(self.name)
        if self.code:
            parts.append(f"({self.code})")
        if self.symbol:
            parts.append(self.symbol)
        return " ".join(parts)


class Mint(Base):
    """Модель монетного двора (справочник)"""
    __tablename__ = 'mints'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)  # Полное название
    short_name = Column(String(50), nullable=True)  # Краткое название
    mark = Column(String(20), nullable=True)  # Знак/обозначение на монетах
    
    # Расположение
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=True)
    city = Column(String(100), nullable=True)
    
    # История
    founded_year = Column(Integer, nullable=True)
    closed_year = Column(Integer, nullable=True)
    
    # Контакты
    website = Column(String(200), nullable=True)
    
    # Описание
    description = Column(Text, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    country = relationship("Country", foreign_keys=[country_id])
    coins = relationship("Coin", back_populates="mint_obj")
    
    def __repr__(self):
        return f"<Mint(id={self.id}, name='{self.name}')>"
    
    def get_display_text(self):
        """Возвращает текст для отображения в комбобоксе"""
        parts = [self.name]
        if self.city:
            parts.append(f"({self.city})")
        return " ".join(parts)
    
    def get_full_name(self):
        """Возвращает полное название с городом и страной"""
        parts = [self.name]
        if self.city:
            parts.append(self.city)
        if self.country:
            parts.append(self.country.name)
        return ", ".join(parts)


class Continent(Base):
    """Модель континента"""
    __tablename__ = 'continents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    map_image_path = Column(String(500), nullable=True)  # Путь к карте континента
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Continent(id={self.id}, name='{self.name}')>"


class Metal(Base):
    """Модель металла (справочник)"""
    __tablename__ = 'metals'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)  # Название металла
    purity = Column(String(20), nullable=True)  # Проба/чистота (например, "999", "925")
    description = Column(Text, nullable=True)  # Описание
    
    # Текущий курс (ручное обновление)
    current_price = Column(Float, nullable=True)  # Текущая цена за грамм
    price_currency = Column(String(10), default='RUB')
    price_date = Column(Date, nullable=True)  # Дата курса
    
    # Биржевой тикер для автоматического обновления цен
    ticker_moex = Column(String(20), nullable=True)  # Тикер на Московской бирже (например, 'SLVRUB_TOM')
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    coins = relationship("Coin", back_populates="metal_obj")
    price_history = relationship("MetalPriceHistory", back_populates="metal", order_by="desc(MetalPriceHistory.date)")
    
    def __repr__(self):
        return f"<Metal(id={self.id}, name='{self.name}')>"
    
    def get_display_text(self):
        """Возвращает текст для отображения в комбобоксе"""
        if self.purity:
            return f"{self.name} {self.purity}"
        return self.name
    
    def get_full_name(self):
        """Возвращает полное название с пробой"""
        return self.get_display_text()
    
    def get_purity_decimal(self):
        """Возвращает пробу в десятичном виде (например, 925 -> 0.925)"""
        if self.purity:
            try:
                return float(self.purity) / 1000
            except (ValueError, TypeError):
                return 1.0
        return 1.0


class MetalPriceHistory(Base):
    """Модель для хранения исторических цен на металлы с биржи"""
    __tablename__ = 'metal_price_history'
    
    id = Column(Integer, primary_key=True)
    metal_id = Column(Integer, ForeignKey('metals.id'), nullable=False)
    date = Column(Date, nullable=False, default=datetime.now().date)
    close_price = Column(Float, nullable=False)  # Цена закрытия (в рублях за грамм)
    currency = Column(String(10), default='RUB')  # Валюта цены
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь со справочником металлов
    metal = relationship("Metal", back_populates="price_history")
    
    # Уникальность: для одного металла может быть только одна запись на дату
    __table_args__ = (UniqueConstraint('metal_id', 'date', name='_metal_date_uc'),)
    
    def __repr__(self):
        return f"<MetalPriceHistory(metal={self.metal_id}, date={self.date}, price={self.close_price})>"


class Edge(Base):
    """Модель гурта (справочник)"""
    __tablename__ = 'edges'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # Название типа гурта
    description = Column(Text, nullable=True)  # Описание
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь с монетами
    coins = relationship("Coin", back_populates="edge_obj")
    
    def __repr__(self):
        return f"<Edge(id={self.id}, name='{self.name}')>"


class PurchaseCountry(Base):
    """Модель страны, из которой приобретена монета (справочник)"""
    __tablename__ = 'purchase_countries'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Название страны
    description = Column(Text, nullable=True)  # Описание
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь с монетами
    coins = relationship("Coin", back_populates="purchase_country_obj")
    
    def __repr__(self):
        return f"<PurchaseCountry(id={self.id}, name='{self.name}')>"
    
    def get_display_text(self):
        """Возвращает текст для отображения в комбобоксе"""
        return self.name


class Period(Base):
    """Модель периода (справочник)"""
    __tablename__ = 'periods'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)  # Название периода
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=False)
    start_year = Column(Integer, nullable=True)  # Начальный год периода
    end_year = Column(Integer, nullable=True)    # Конечный год периода
    description = Column(Text, nullable=True)   # Описание периода
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь со страной
    country = relationship("Country", foreign_keys=[country_id])
    
    def __repr__(self):
        return f"<Period(id={self.id}, name='{self.name}', country_id={self.country_id})>"
    
    def get_display_text(self):
        """Возвращает текст для отображения в комбобоксе"""
        parts = [self.name]
        if self.start_year and self.end_year:
            parts.append(f"({self.start_year}-{self.end_year})")
        elif self.start_year:
            parts.append(f"(с {self.start_year})")
        elif self.end_year:
            parts.append(f"(до {self.end_year})")
        return " ".join(parts)
    
    def get_full_name(self):
        """Возвращает полное название с годами"""
        return self.get_display_text()



class FieldSettings(Base):
    """Модель настроек полей (как стандартных, так и пользовательских)"""
    __tablename__ = 'field_settings'
    
    id = Column(Integer, primary_key=True)
    field_key = Column(String(100), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)
    field_type = Column(String(20), nullable=False, default='text')
    is_standard = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    show_in_table = Column(Boolean, default=True)
    show_in_form = Column(Boolean, default=True)
    show_in_view = Column(Boolean, default=True)  # НОВОЕ ПОЛЕ - показывать в режиме просмотра
    show_in_edit = Column(Boolean, default=True)   # НОВОЕ ПОЛЕ - показывать в режиме редактирования
    sort_order = Column(Integer, default=0)
    default_value = Column(String(200), nullable=True)
    options = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<FieldSettings(id={self.id}, key='{self.field_key}', name='{self.name}')>"


class MarketPriceHistory(Base):
    """Модель для хранения истории рыночных цен монет"""
    __tablename__ = 'market_price_history'
    
    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'), nullable=False)
    
    # Данные монеты на момент сохранения (для отчета, даже если монета будет удалена)
    country_name = Column(String(100), nullable=True)  # Страна
    denomination = Column(String(50), nullable=True)   # Номинал
    year = Column(Integer, nullable=True)              # Год
    mint_mark = Column(String(20), nullable=True)      # Знак МД
    
    # Цена и дата
    market_price = Column(Float, nullable=False)       # Рыночная цена
    price_date = Column(Date, nullable=False)          # Дата цены (из файла)
    
    # Дополнительная информация
    source_file = Column(String(200), nullable=True)   # Имя файла-источника
    created_at = Column(DateTime, default=datetime.now)
    
    # Связь с монетой
    coin = relationship("Coin", foreign_keys=[coin_id])
    
    def __repr__(self):
        return f"<MarketPriceHistory(coin_id={self.coin_id}, price={self.market_price}, date={self.price_date})>"


class Coin(Base):
    """Модель монеты"""
    __tablename__ = 'coins'
    
    __table_args__ = (
        Index('ix_coin_country_id', 'country_id'),
        Index('ix_coin_metal_id', 'metal_id'),
        Index('ix_coin_currency_id', 'currency_id'),
        Index('ix_coin_mint_id', 'mint_id'),
        Index('ix_coin_year', 'year'),
    )
    
    id = Column(Integer, primary_key=True)
    
    # Связи со справочниками - ДОБАВИТЬ index=True
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=False, index=True)
    currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=True, index=True)
    mint_id = Column(Integer, ForeignKey('mints.id'), nullable=True, index=True)
    metal_id = Column(Integer, ForeignKey('metals.id'), nullable=True, index=True)  # ← ДОБАВИТЬ index=True
    edge_id = Column(Integer, ForeignKey('edges.id'), nullable=True, index=True)
    period_id = Column(Integer, ForeignKey('periods.id'), nullable=True, index=True)
    
    # Основная информация
    catalog_number = Column(String(50), nullable=True, index=True)
    denomination_value = Column(String(50), nullable=True)
    currency = Column(String(50), nullable=True)
    century = Column(String(20), nullable=True)
    year = Column(Integer, nullable=True, index=True)  # ← УЖЕ ЕСТЬ index=True, ПРОВЕРИТЬ
    year_on_coin = Column(String(50), nullable=True)
    
    # Монетный двор
    mint = Column(String(200), nullable=True)
    mint_mark = Column(String(20), nullable=True)
    
    # Металл и характеристики
    weight = Column(Float, nullable=True)
    diameter = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    shape = Column(String(50), nullable=True)
    
    # Тираж и качество
    mintage = Column(Integer, nullable=True)
    quality = Column(String(50), nullable=True)
    
    # Состояние и редкость
    condition = Column(String(20), nullable=True)
    rarity = Column(String(20), nullable=True)
    
    # Дополнительные характеристики
    obverse_description = Column(Text, nullable=True)
    reverse_description = Column(Text, nullable=True)
    edge_description = Column(Text, nullable=True)
    
    # Граверы и дизайнеры
    engraver = Column(String(200), nullable=True)
    designer = Column(String(200), nullable=True)
    
    # Каталожные номера (дополнительные)
    catalog_number_1 = Column(String(50), nullable=True)
    catalog_number_2 = Column(String(50), nullable=True)
    catalog_number_3 = Column(String(50), nullable=True)
    
    # Тип выпуска
    issue_type = Column(String(50), nullable=True)
    
    # Где куплена/место покупки
    purchase_where = Column(String(100), nullable=True)
    
    # Информация о покупке
    purchase_info = Column(Text, nullable=True)
    
    # Информация о монете
    coin_info = Column(Text, nullable=True)
    
    # Место хранения/Альбом
    storage_location = Column(String(100), nullable=True)
    
    # АВ/РЕВ
    avrev = Column(String(50), nullable=True)
    
    # Изображения
    obverse_image = Column(String(500), nullable=True)
    reverse_image = Column(String(500), nullable=True)
    main_image_path = Column(String(500), nullable=True)
    
    # Ссылки
    ucoin_url = Column(String(500), nullable=True)
    meshok_url = Column(String(500), nullable=True)
    
    # Информация о покупке
    purchase_date = Column(Date, nullable=True, index=True)
    purchase_price = Column(Float, nullable=True)
    purchase_commission = Column(Float, nullable=True)
    purchase_country_id = Column(Integer, ForeignKey('purchase_countries.id'), nullable=True)
    acquisition_type = Column(String(50), nullable=True)
    
    # Информация о продаже
    sale_date = Column(Date, nullable=True)
    sale_price = Column(Float, nullable=True)
    
    # Рыночная цена
    market_price = Column(Float, nullable=True)
    market_price_date = Column(Date, nullable=True)
    
    # Статус в коллекции
    status = Column(String(20), default='in_collection', index=True)
    quantity = Column(Integer, default=1)
    
    # Выделение (чекбокс)
    selected = Column(Boolean, default=False, index=True)
    
    # Заметки
    notes = Column(Text, nullable=True)
    
    # Пользовательские данные (JSON)
    custom_data = Column(Text, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    country = relationship("Country", foreign_keys=[country_id])
    currency_obj = relationship("Currency", foreign_keys=[currency_id], back_populates="coins")
    mint_obj = relationship("Mint", foreign_keys=[mint_id], back_populates="coins")
    metal_obj = relationship("Metal", foreign_keys=[metal_id], back_populates="coins")
    edge_obj = relationship("Edge", foreign_keys=[edge_id], back_populates="coins")
    purchase_country_obj = relationship("PurchaseCountry", foreign_keys=[purchase_country_id], back_populates="coins")
    period_obj = relationship("Period", foreign_keys=[period_id])
    
    # НОВЫЕ ПОЛЯ ДЛЯ СТАНДАРТНЫХ СПРАВОЧНИКОВ (по ID)
    condition_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True, index=True)
    rarity_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True, index=True)
    shape_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True)
    issue_type_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True)
    avrev_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True)
    status_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True, index=True)
    acquisition_type_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True)
    storage_location_id = Column(Integer, ForeignKey('standard_references.id'), nullable=True)
    
    # Связи со справочниками
    condition_ref = relationship("StandardReference", foreign_keys=[condition_id])
    rarity_ref = relationship("StandardReference", foreign_keys=[rarity_id])
    shape_ref = relationship("StandardReference", foreign_keys=[shape_id])
    issue_type_ref = relationship("StandardReference", foreign_keys=[issue_type_id])
    avrev_ref = relationship("StandardReference", foreign_keys=[avrev_id])
    status_ref = relationship("StandardReference", foreign_keys=[status_id])
    acquisition_type_ref = relationship("StandardReference", foreign_keys=[acquisition_type_id])
    storage_location_ref = relationship("StandardReference", foreign_keys=[storage_location_id])
    
    def __repr__(self):
        return f"<Coin(id={self.id}, catalog='{self.catalog_number}')>"
    
    def get_full_name(self):
        """Возвращает полное название монеты"""
        parts = []
        if self.country:
            parts.append(self.country.name)
        if self.denomination_value:
            parts.append(self.denomination_value)
        if self.currency:
            parts.append(self.currency)
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts)
    
    def get_custom_value(self, field_key):
        """Возвращает значение пользовательского поля"""
        if not self.custom_data:
            return None
        try:
            import json
            data = json.loads(self.custom_data)
            return data.get(field_key)
        except:
            return None
    
    def set_custom_value(self, field_key, value):
        """Устанавливает значение пользовательского поля"""
        import json
        data = {}
        if self.custom_data:
            try:
                data = json.loads(self.custom_data)
            except:
                pass
        data[field_key] = value
        self.custom_data = json.dumps(data, ensure_ascii=False)

class CoinImage(Base):
    """Модель для хранения дополнительных изображений монеты"""
    __tablename__ = 'coin_images'
    
    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'), nullable=False)
    image_path = Column(String(500), nullable=False)
    description = Column(String(200), nullable=True)  # Описание изображения
    is_primary = Column(Boolean, default=False)  # Основное изображение
    sort_order = Column(Integer, default=0)  # Порядок сортировки
    created_at = Column(DateTime, default=datetime.now)
    
    # Связь с монетой
    coin = relationship("Coin", foreign_keys=[coin_id])
    
    def __repr__(self):
        return f"<CoinImage(id={self.id}, coin_id={self.coin_id})>"


def init_db(db_path="coins.db"):
    """Инициализирует базу данных"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine


# Для обратной совместимости добавляем алиасы
MetalPrice = MetalPriceHistory

class CustomReference(Base):
    """Модель пользовательского справочника"""
    __tablename__ = 'custom_references'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # Название справочника
    field_key = Column(String(50), nullable=False)  # К какому полю привязан
    value = Column(String(200), nullable=False)  # Значение
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<CustomReference(id={self.id}, name='{self.name}', value='{self.value}')>"
        
        
# ===== database/models.py =====
# ДОБАВИТЬ МОДЕЛЬ ДЛЯ СТАНДАРТНЫХ СПРАВОЧНИКОВ (если ещё нет)

class StandardReference(Base):
    """Модель для хранения значений стандартных справочников (редкость, сохранность и т.д.)"""
    __tablename__ = 'standard_references'
    
    id = Column(Integer, primary_key=True)
    field_key = Column(String(50), nullable=False)  # rarity, condition, shape и т.д.
    value = Column(String(100), nullable=False)      # Значение
    name = Column(String(100), nullable=False)       # Отображаемое имя
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (UniqueConstraint('field_key', 'value', name='_field_value_uc'),)
    
    def __repr__(self):
        return f"<StandardReference(field='{self.field_key}', value='{self.value}')>"
        
        
# ===== database/models.py =====
# ЗАМЕНИТЬ СУЩЕСТВУЮЩУЮ МОДЕЛЬ Purchase И ДОБАВИТЬ ImportCountry

class ImportCountry(Base):
    """Модель для стран из импорта закупок (отдельно от стран коллекции)"""
    __tablename__ = 'import_countries'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    continent = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь с закупками
    purchases = relationship("Purchase", back_populates="import_country")
    
    def __repr__(self):
        return f"<ImportCountry(id={self.id}, name='{self.name}')>"

class Purchase(Base):
    """Модель для таблицы закупок"""
    __tablename__ = 'purchases'
    
    id = Column(Integer, primary_key=True)
    
    # Признак попадания в коллекцию и цена
    in_collection = Column(Boolean, default=False)
    collection_price = Column(Float, nullable=True)
    
    # Номер закупки
    purchase_number = Column(String(50), nullable=True)
    ag = Column(Boolean, default=False, nullable=True)    
    # Партия закупки (№Пок)
    purchase_batch = Column(String(100), nullable=True)
    
    # Страна из справочника импортированных стран
    import_country_id = Column(Integer, ForeignKey('import_countries.id'), nullable=True)
    continent = Column(String(50), nullable=True)
    
    # Номинал и валюта
    denomination_value = Column(String(50), nullable=True)
    currency = Column(String(50), nullable=True)
    
    # Год
    year = Column(Integer, nullable=True)
    
    # Служебное поле
    location_found = Column(String(100), nullable=True)
    
    # Количество
    quantity = Column(Integer, default=1)
    
    # Комментарии
    comments = Column(Text, nullable=True)
    
    # Обмен на ucoin
    ucoin_exchange = Column(Boolean, default=False)
    ucoin_exchange_count = Column(Integer, default=0)
    
    # Продажи
    sold_count = Column(String(50), nullable=True)
    sold_sum = Column(Float, nullable=True)
    
    # Итого
    total = Column(Float, nullable=True)
    
    # Ручные затраты
    manual_costs = Column(Float, nullable=True)  # <-- ДОБАВЛЕНО
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    import_country = relationship("ImportCountry", foreign_keys=[import_country_id], back_populates="purchases")
    
    def __repr__(self):
        country_name = self.import_country.name if self.import_country else "?"
        return f"<Purchase(id={self.id}, country='{country_name}', batch='{self.purchase_batch}')>"


# ===== database/models.py =====
# ДОБАВИТЬ КЛАСС PurchaseArchive

class PurchaseArchive(Base):
    """Модель для таблицы архивных закупок"""
    __tablename__ = 'purchases_archive'
    
    id = Column(Integer, primary_key=True)
    
    # Признак попадания в коллекцию и цена
    in_collection = Column(Boolean, default=False)
    collection_price = Column(Float, nullable=True)
    
    # Номер закупки
    purchase_number = Column(String(50), nullable=True)
    ag = Column(Boolean, default=False, nullable=True)    
    # Партия закупки (№Пок)
    purchase_batch = Column(String(100), nullable=True)
    
    # Страна из справочника импортированных стран
    import_country_id = Column(Integer, ForeignKey('import_countries.id'), nullable=True)
    continent = Column(String(50), nullable=True)
    
    # Номинал и валюта
    denomination_value = Column(String(50), nullable=True)
    currency = Column(String(50), nullable=True)
    
    # Год
    year = Column(Integer, nullable=True)
    
    # Служебное поле
    location_found = Column(String(100), nullable=True)
    
    # Количество
    quantity = Column(Integer, default=1)
    
    # Комментарии
    comments = Column(Text, nullable=True)
    
    # Обмен на ucoin
    ucoin_exchange = Column(Boolean, default=False)
    ucoin_exchange_count = Column(Integer, default=0)
    
    # Продажи
    sold_count = Column(String(50), nullable=True)
    sold_sum = Column(Float, nullable=True)
    
    # Итого
    total = Column(Float, nullable=True)
    
    # Ручные затраты
    manual_costs = Column(Float, nullable=True)
    
    # Дата архивации
    archived_at = Column(DateTime, default=datetime.now)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    import_country = relationship("ImportCountry", foreign_keys=[import_country_id])
    
    def __repr__(self):
        country_name = self.import_country.name if self.import_country else "?"
        return f"<PurchaseArchive(id={self.id}, country='{country_name}')>"

class MetalHolding(Base):
    """Модель для учета металлов (серебро/золото) с привязкой к бирже"""
    __tablename__ = 'metal_holdings'
    
    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey('purchases.id'), nullable=True)
    
    # Идентификация
    number = Column(String(20), nullable=True)  # Номер (00001)
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=True)
    denomination_value = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    
    # Тип металла
    metal_type = Column(String(10), nullable=True)  # 'AG' или 'AU'
    metal_id = Column(Integer, ForeignKey('metals.id'), nullable=True)
    
    # Вес и проба
    weight = Column(Float, nullable=True)  # Общий вес
    purity = Column(Float, nullable=True)  # Проба (0.0-1.0)
    pure_weight = Column(Float, nullable=True)  # Чистый вес (= weight * purity)
    
    # Цена металла (из биржи)
    metal_ticker = Column(String(20), nullable=True)  # SLVRUB_TOM, GLDRUB_TOM
    metal_price = Column(Float, nullable=True)  # Текущая цена за грамм
    
    # Расчетная стоимость
    calculated_value = Column(Float, nullable=True)  # = pure_weight * metal_price
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    country = relationship("Country", foreign_keys=[country_id])
    metal = relationship("Metal", foreign_keys=[metal_id])
    purchase = relationship("Purchase", foreign_keys=[purchase_id])
    
    def calculate_pure_weight(self):
        """Рассчитывает чистый вес металла"""
        if self.weight and self.purity:
            self.pure_weight = self.weight * self.purity
        return self.pure_weight
    
    def calculate_value(self):
        """Рассчитывает стоимость металла"""
        if self.pure_weight and self.metal_price:
            self.calculated_value = self.pure_weight * self.metal_price
        return self.calculated_value


class Deal(Base):
    """Модель для учета сделок (обмен/продажа)"""
    __tablename__ = 'deals'
    
    id = Column(Integer, primary_key=True)
    
    # Тип сделки
    deal_type = Column(String(20), nullable=True)  # 'purchase', 'sale', 'exchange'
    
    # Участники
    buyer = Column(String(100), nullable=True)  # Покупатель (НИК)
    seller = Column(String(100), nullable=True)  # Продавец
    
    # Информация о монете
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=True)
    denomination_value = Column(String(50), nullable=True)
    currency = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    
    # Цены
    purchase_price = Column(Float, nullable=True)  # Цена покупки
    sale_price = Column(Float, nullable=True)  # Цена продажи
    commission = Column(Float, nullable=True)  # Комиссия
    shipping_cost = Column(Float, nullable=True)  # Доставка
    delivery = Column(String(50), nullable=True)  # ДОСТ
    
    # Платформа
    platform = Column(String(50), nullable=True)  # UCOIN, Авито, Lave, Мешок
    
    # Даты
    deal_date = Column(Date, nullable=True)
    
    # Статус
    status = Column(String(20), default='pending')  # pending, completed, cancelled
    
    # Дополнительные поля для таблицы сделок
    zak = Column(String(50), nullable=True)  # Зак
    amount = Column(String(50), nullable=True)  # Сумма
    discount = Column(String(50), nullable=True)  # Скидка
    money = Column(String(50), nullable=True)  # бабки
    discount2 = Column(String(50), nullable=True)  # Скидка2 (Ск2)
    total = Column(String(50), nullable=True)  # ИТОГ
    reserve = Column(String(50), nullable=True)  # Резерв
    collect = Column(String(50), nullable=True)  # Собр
    scan = Column(String(50), nullable=True)  # СКАН
    send = Column(String(50), nullable=True)  # Отосл
    approve = Column(String(50), nullable=True)  # Согл
    payment = Column(String(50), nullable=True)  # Оплата
    check = Column(String(50), nullable=True)  # Пров
    pack = Column(String(50), nullable=True)  # Упак
    post = Column(String(50), nullable=True)  # Почта
    arrived = Column(String(50), nullable=True)  # ДОШЛО
    number = Column(String(50), nullable=True)  # №
    type = Column(String(50), nullable=True)  # Тип
    where = Column(String(50), nullable=True)  # Где
    
    # Цвета ячеек
    cell_colors = Column(Text, nullable=True)  # JSON словарь цветов ячеек {"col_index": "hex"}
    
    # Примечания
    notes = Column(Text, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    country = relationship("Country", foreign_keys=[country_id])
    
    def __repr__(self):
        return f"<Deal(id={self.id}, buyer='{self.buyer}')>"
    
    def calculate_net_profit(self):
        """Чистая прибыль = sale_price - purchase_price - commission - shipping_cost"""
        net = 0
        if self.sale_price:
            net += self.sale_price
        if self.purchase_price:
            net -= self.purchase_price
        if self.commission:
            net -= self.commission
        if self.shipping_cost:
            net -= self.shipping_cost
        return net
    
    def get_cell_color(self, col_index):
        """Возвращает цвет ячейки или None"""
        if not self.cell_colors:
            return None
        try:
            import json
            from PySide6.QtGui import QColor
            colors = json.loads(self.cell_colors)
            hex_color = colors.get(str(col_index))
            if hex_color:
                return QColor(hex_color)
        except:
            pass
        return None
    
    def set_cell_color(self, col_index, color):
        """Устанавливает цвет ячейки"""
        import json
        colors = {}
        if self.cell_colors:
            try:
                colors = json.loads(self.cell_colors)
            except:
                pass
        if color:
            colors[str(col_index)] = color
        else:
            colors.pop(str(col_index), None)
        self.cell_colors = json.dumps(colors) if colors else None
        
        
# ===== database/models.py =====
# ДОБАВИТЬ МОДЕЛИ ДЛЯ ЗАМЕТОК

class NotebookCategory(Base):
    """Категории для заметок"""
    __tablename__ = 'notebook_categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(20), default="#4a6fa5")  # Цвет категории
    icon = Column(String(10), default="📁")       # Иконка
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    notes = relationship("NotebookNote", back_populates="category_rel")


class NotebookNote(Base):
    """Заметки и задачи"""
    __tablename__ = 'notebook_notes'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)           # Текст заметки (для типа note)
    note_type = Column(String(20), default='note')  # 'note', 'task', 'checklist'
    
    # Категория
    category_id = Column(Integer, ForeignKey('notebook_categories.id'), nullable=True)
    category_rel = relationship("NotebookCategory", back_populates="notes")
    
    # Статус
    is_pinned = Column(Boolean, default=False)      # Закреплена
    is_archived = Column(Boolean, default=False)    # В архиве
    is_trashed = Column(Boolean, default=False)     # В корзине
    
    # Цвет (индивидуальный для заметки)
    color = Column(String(20), nullable=True)
    
    # Напоминание
    remind_at = Column(DateTime, nullable=True)
    remind_sent = Column(Boolean, default=False)
    
    # Вложения (JSON список путей к файлам)
    attachments = Column(Text, nullable=True)       # JSON array
    
    # Метки (теги) - JSON список
    tags = Column(Text, nullable=True)              # JSON array
    
    # Версия
    version = Column(Integer, default=1)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at = Column(DateTime, nullable=True)    # Дата удаления в корзину
    
    # Связи
    tasks = relationship("NotebookTask", back_populates="note", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<NotebookNote(id={self.id}, title='{self.title}')>"


class NotebookTask(Base):
    """Задачи внутри заметки типа task/checklist"""
    __tablename__ = 'notebook_tasks'
    
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey('notebook_notes.id'), nullable=False)
    text = Column(String(500), nullable=False)
    is_checked = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    note = relationship("NotebookNote", back_populates="tasks")
    
    def __repr__(self):
        return f"<NotebookTask(id={self.id}, text='{self.text[:50]}')>"


class NotebookReminder(Base):
    """Отдельные напоминания (не привязанные к заметкам)"""
    __tablename__ = 'notebook_reminders'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    text = Column(Text, nullable=True)
    remind_at = Column(DateTime, nullable=False)
    is_done = Column(Boolean, default=False)
    repeat_type = Column(String(20), default='none')  # 'none', 'daily', 'weekly', 'monthly'
    created_at = Column(DateTime, default=datetime.now)


class Sale(Base):
    """Модель для учёта продаж"""
    __tablename__ = 'sales'
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=True)           # ГОД
    lom_plus = Column(Float, default=0)             # ЛОМ+
    ag_plus = Column(Float, default=0)              # AG+
    bonus_plus = Column(Float, default=0)           # Бонусы+
    bonus_minus = Column(Float, default=0)          # Бонусы-
    post_plus = Column(Float, default=0)            # Почта+
    post_minus = Column(Float, default=0)           # Почта-
    purchases = Column(Float, default=0)            # Закупки
    purchase_ag = Column(Float, default=0)          # Закупка AG
    costs = Column(Float, default=0)                # ТРАТЫ
    sale_type = Column(String(50), default='Продажа')  # Тип: Продажа, Обмен, Закупка
    deal_number = Column(Integer, nullable=True)    # №№Сделки
    notes = Column(Text, nullable=True)             # Примечание
    total = Column(Float, default=0)                # Итог (вычисляемое)
    balance = Column(Float, default=0)              # Баланс (нарастающий)
    
    # Цвета ячеек (JSON)
    cell_colors = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def calculate_total(self):
        """Рассчитывает итог по формуле: total = сумма ВСЕХ полей"""
        total = (self.lom_plus or 0) + (self.ag_plus or 0) + \
                (self.bonus_plus or 0) + (self.bonus_minus or 0) + \
                (self.post_plus or 0) + (self.post_minus or 0) + \
                (self.purchases or 0) + (self.purchase_ag or 0) + \
                (self.costs or 0)
        self.total = total
        return self.total
    
    def get_cell_color(self, col_index):
        """Возвращает цвет ячейки или None"""
        if not self.cell_colors:
            return None
        try:
            import json
            from PySide6.QtGui import QColor
            colors = json.loads(self.cell_colors)
            hex_color = colors.get(str(col_index))
            if hex_color:
                return QColor(hex_color)
        except:
            pass
        return None
    
    def set_cell_color(self, col_index, color):
        """Устанавливает цвет ячейки"""
        import json
        colors = {}
        if self.cell_colors:
            try:
                colors = json.loads(self.cell_colors)
            except:
                pass
        if color:
            colors[str(col_index)] = color
        else:
            colors.pop(str(col_index), None)
        self.cell_colors = json.dumps(colors) if colors else None
    
    def __repr__(self):
        return f"<Sale(id={self.id}, year={self.year})>"
        
        
class SilverPurchase(Base):
    """Модель закупки серебра"""
    __tablename__ = 'silver_purchases'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=True)
    number_ag = Column(String(50), nullable=True)  # №ЗакAG
    number = Column(String(50), nullable=True)     # №Зак
    source = Column(String(200), nullable=True)    # Откуда
    purchase_sum = Column(Float, default=0)        # Сумма закупки
    quantity = Column(Integer, default=1)          # Количество монет
    min_price = Column(Float, default=0)           # Min цена (себестоимость)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    coins = relationship("SilverCoin", back_populates="purchase", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SilverPurchase(id={self.id}, number='{self.number}')>"


class SilverCoin(Base):
    """Модель монеты в закупке серебра"""
    __tablename__ = 'silver_coins'
    
    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey('silver_purchases.id'), nullable=False)
    
    # Статус: in_sale, sold, in_collection
    status = Column(String(20), default='in_sale')
    
    # Данные монеты
    country = Column(String(100), nullable=True)
    denomination = Column(String(50), nullable=True)
    year = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    number = Column(String(50), nullable=True)     # № (генерируется автоматически)
    
    # Цены
    collection_price = Column(Float, default=0)   # Цена в коллекцию
    sale_price = Column(Float, default=0)         # Цена продажи
    min_price = Column(Float, default=0)          # MIN цена (себестоимость)
    plan_price = Column(Float, default=0)         # Плановая цена
    
    # Площадки
    avito = Column(Boolean, default=False)
    lave = Column(Boolean, default=False)
    meshok = Column(Boolean, default=False)
    ucoin = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    purchase = relationship("SilverPurchase", back_populates="coins")
    
    def __repr__(self):
        return f"<SilverCoin(id={self.id}, number='{self.number}')>"
        
def ensure_ag_column(db_manager):
    """Безопасная миграция: добавляет колонку 'ag' в таблицы purchases и
    purchases_archive, если её там ещё нет. Идемпотентна.
    Вызывается ПЕРЕД любым запросом к таблице purchases."""
    import logging
    try:
        from sqlalchemy import text, inspect
        logger = logging.getLogger('CoinCollector.DB')
        engine = db_manager.session.get_bind()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for table in ('purchases', 'purchases_archive'):
            if table not in tables:
                continue
            cols = [c['name'] for c in inspector.get_columns(table)]
            if 'ag' not in cols:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE {table} "
                        f"ADD COLUMN ag BOOLEAN DEFAULT 0"))
                logger.info(
                    f"✅ Миграция: в таблицу {table} добавлена колонка 'ag'")
        return True
    except Exception as e:
        import logging
        logging.getLogger('CoinCollector.DB').error(
            f"Ошибка миграции колонки 'ag': {e}")
        return False