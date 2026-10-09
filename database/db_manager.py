# ===== database/db_manager.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Менеджер базы данных для Coin Collector
"""

import os
import shutil
import logging
import traceback
import json
from datetime import datetime
from pathlib import Path  # ← ДОБАВИТЬ ЭТУ СТРОКУ
from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import sessionmaker
from database.models import Base, Country, Coin, Currency, Mint, Edge, Metal, MetalPriceHistory, MarketPriceHistory, Period, PurchaseCountry, FieldSettings, Purchase, PurchaseArchive
from utils.paths import paths




class DatabaseManager:
    """Класс для работы с базой данных"""


    def __init__(self, db_path=None):
        """Инициализация менеджера базы данных.

        Порядок ВАЖЕН:
        1) путь к БД → 2) engine → 3) фабрика сессий SessionLocal
        (с expire_on_commit=False) → 4) self.session → 5) create_all.
        expire_on_commit=False отключает сброс загруженных атрибутов после
        commit — это устраняет DetachedInstanceError при ПКМ по таблице монет.
        """
        self.logger = logging.getLogger('CoinCollector.Database')
        try:
            # --- 1) Путь к файлу БД ---
            if db_path is None:
                from utils.paths import paths
                db_path = paths.get_data_dir() / 'coins.db'
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # --- 2) Движок SQLAlchemy ---
            self.engine = create_engine(
                f'sqlite:///{self.db_path}',
                echo=False,
                connect_args={'check_same_thread': False},
            )

            # --- 3) Фабрика сессий: expire_on_commit=False задаётся ЗДЕСЬ,
            #        ДО создания self.session (иначе AttributeError) ---
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
                expire_on_commit=False,
            )
            self.Session = self.SessionLocal   # ← совместимость со старым кодом (.Session())
            self.session = self.SessionLocal()

 

            # --- 5) Создание/обновление таблиц ---
            from database.models import Base
            Base.metadata.create_all(bind=self.engine)

            # (Если у вас здесь были дополнительные шаги инициализации —
            #  заполнение справочников, миграции и т.п. — оставьте их МЕЖДУ
            #  create_all и следующей строкой логирования.)

            self.logger.info(f"✅ База данных инициализирована: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Ошибка инициализации базы данных: {e}")
            self.logger.error(traceback.format_exc())
            raise

    def _update_schema(self):
        """Обновляет схему базы данных"""
        try:
            inspector = inspect(self.engine)
            
            # Обновляем таблицу countries
            try:
                columns_countries = [col['name'] for col in inspector.get_columns('countries')]
                
                if 'continent' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN continent VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка continent в таблицу countries")
                
                if 'is_extinct' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN is_extinct BOOLEAN DEFAULT 0"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка is_extinct в таблицу countries")
                
                if 'language' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN language VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка language в таблицу countries")
                
                if 'religion' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN religion VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка religion в таблицу countries")
                
                if 'iso2' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN iso2 VARCHAR(2)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка iso2 в таблицу countries")
                
                if 'iso3' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN iso3 VARCHAR(3)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка iso3 в таблицу countries")
                
                if 'capital' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN capital VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка capital в таблицу countries")
                
                if 'government_type' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN government_type VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка government_type в таблицу countries")
                
                if 'area' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN area INTEGER"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка area в таблицу countries")
                
                if 'population' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN population INTEGER"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка population в таблицу countries")
                
                if 'currency_name' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN currency_name VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка currency_name в таблицу countries")
                
                if 'currency_code' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN currency_code VARCHAR(3)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка currency_code в таблицу countries")
                
                if 'ioc_code' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN ioc_code VARCHAR(3)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка ioc_code в таблицу countries")
                
                if 'flag_url' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN flag_url VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка flag_url в таблицу countries")
                
                if 'anthem' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN anthem VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка anthem в таблицу countries")
                
                if 'independence_date' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN independence_date VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка independence_date в таблицу countries")
                
                if 'successor_id' not in columns_countries:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE countries ADD COLUMN successor_id INTEGER REFERENCES countries(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка successor_id в таблицу countries")
                
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении таблицы countries: {e}")
            
            # Создаём таблицу sales (продажи)
            try:
                if 'sales' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE sales (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date DATE,
                                income FLOAT DEFAULT 0,
                                expense FLOAT DEFAULT 0,
                                costs FLOAT DEFAULT 0,
                                bonus_plus FLOAT DEFAULT 0,
                                bonus_minus FLOAT DEFAULT 0,
                                post_plus FLOAT DEFAULT 0,
                                post_minus FLOAT DEFAULT 0,
                                sale FLOAT DEFAULT 0,
                                notes TEXT,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица sales создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы sales: {e}")            
            
            # Обновляем таблицу coins
            try:
                columns_coins = [col['name'] for col in inspector.get_columns('coins')]
                
                if 'catalog_number' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN catalog_number VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка catalog_number в таблицу coins")
                
                if 'currency' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN currency VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка currency в таблицу coins")
                
                if 'denomination_value' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN denomination_value VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка denomination_value в таблицу coins")
                
                if 'currency_id' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN currency_id INTEGER REFERENCES currencies(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка currency_id в таблицу coins")
                
                if 'mint_id' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN mint_id INTEGER REFERENCES mints(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка mint_id в таблицу coins")
                
                if 'metal_id' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN metal_id INTEGER REFERENCES metals(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка metal_id в таблицу coins")
                
                if 'edge_id' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN edge_id INTEGER REFERENCES edges(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка edge_id в таблицу coins")
                
                if 'century' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN century VARCHAR(20)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка century в таблицу coins")
                
                if 'shape' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN shape VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка shape в таблицу coins")
                
                if 'storage_location' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN storage_location VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка storage_location в таблицу coins")
                
                if 'issue_type' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN issue_type VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка issue_type в таблицу coins")
                
                if 'avrev' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN avrev VARCHAR(50)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка avrev в таблицу coins")
                
                if 'purchase_where' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN purchase_where VARCHAR(100)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка purchase_where в таблицу coins")
                
                if 'purchase_info' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN purchase_info TEXT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка purchase_info в таблицу coins")
                
                if 'coin_info' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN coin_info TEXT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка coin_info в таблицу coins")
                
                if 'obverse_image' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN obverse_image VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка obverse_image в таблицу coins")
                
                if 'reverse_image' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN reverse_image VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка reverse_image в таблицу coins")
                
                if 'selected' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN selected BOOLEAN DEFAULT 0"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка selected в таблицу coins")
                
                if 'market_price' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN market_price FLOAT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка market_price в таблицу coins")
                
                if 'market_price_date' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN market_price_date DATE"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка market_price_date в таблицу coins")
                
                if 'ucoin_url' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN ucoin_url VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка ucoin_url в таблицу coins")
                
                if 'meshok_url' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN meshok_url VARCHAR(500)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка meshok_url в таблицу coins")
                
                if 'period_id' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN period_id INTEGER REFERENCES periods(id)"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка period_id в таблицу coins")
                
                if 'custom_data' not in columns_coins:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE coins ADD COLUMN custom_data TEXT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка custom_data в таблицу coins")
                
                # НОВЫЕ КОЛОНКИ ДЛЯ СТАНДАРТНЫХ СПРАВОЧНИКОВ (по ID)
                ref_fields = [
                    ('condition_id', 'standard_references'),
                    ('rarity_id', 'standard_references'),
                    ('shape_id', 'standard_references'),
                    ('issue_type_id', 'standard_references'),
                    ('avrev_id', 'standard_references'),
                    ('status_id', 'standard_references'),
                    ('acquisition_type_id', 'standard_references'),
                    ('storage_location_id', 'standard_references'),
                ]
                
                for field_name, ref_table in ref_fields:
                    if field_name not in columns_coins:
                        with self.engine.connect() as conn:
                            conn.execute(text(f"ALTER TABLE coins ADD COLUMN {field_name} INTEGER REFERENCES {ref_table}(id)"))
                            conn.commit()
                            self.logger.info(f"✅ Добавлена колонка {field_name} в таблицу coins")
                
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении таблицы coins: {e}")
            
            # Создаём таблицу country_successors если её нет
            try:
                if 'country_successors' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE country_successors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                extinct_country_id INTEGER REFERENCES countries(id),
                                modern_country_id INTEGER REFERENCES countries(id),
                                created_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица country_successors создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы country_successors: {e}")
            
            # Создаём таблицу market_price_history если её нет
            try:
                if 'market_price_history' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE market_price_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                coin_id INTEGER NOT NULL REFERENCES coins(id),
                                country_name VARCHAR(100),
                                denomination VARCHAR(50),
                                year INTEGER,
                                mint_mark VARCHAR(20),
                                market_price FLOAT NOT NULL,
                                price_date DATE NOT NULL,
                                source_file VARCHAR(200),
                                created_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица market_price_history создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы market_price_history: {e}")
            
            # Создаём таблицу periods если её нет
            try:
                if 'periods' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE periods (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name VARCHAR(200) NOT NULL,
                                country_id INTEGER NOT NULL REFERENCES countries(id),
                                start_year INTEGER,
                                end_year INTEGER,
                                description TEXT,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица periods создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы periods: {e}")
            
            # Создаём таблицу field_settings если её нет
            try:
                if 'field_settings' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE field_settings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                field_key VARCHAR(100) NOT NULL UNIQUE,
                                name VARCHAR(100) NOT NULL,
                                category VARCHAR(50),
                                field_type VARCHAR(20) NOT NULL DEFAULT 'text',
                                is_standard BOOLEAN DEFAULT 1,
                                show_in_table BOOLEAN DEFAULT 1,
                                show_in_form BOOLEAN DEFAULT 1,
                                sort_order INTEGER DEFAULT 0,
                                default_value VARCHAR(200),
                                options TEXT,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица field_settings создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы field_settings: {e}")
            
            # Создаём таблицу custom_references если её нет
            try:
                if 'custom_references' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE custom_references (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                field_key VARCHAR(50) NOT NULL,
                                name VARCHAR(100) NOT NULL,
                                value VARCHAR(200) NOT NULL,
                                sort_order INTEGER DEFAULT 0,
                                is_active BOOLEAN DEFAULT 1,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица custom_references создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы custom_references: {e}")
            
            # Создаём таблицу standard_references если её нет
            try:
                if 'standard_references' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE standard_references (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                field_key VARCHAR(50) NOT NULL,
                                value VARCHAR(100) NOT NULL,
                                name VARCHAR(100) NOT NULL,
                                sort_order INTEGER DEFAULT 0,
                                is_active BOOLEAN DEFAULT 1,
                                created_at DATETIME,
                                updated_at DATETIME,
                                UNIQUE(field_key, value)
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица standard_references создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы standard_references: {e}")
            
            # ===== НОВЫЕ ТАБЛИЦЫ ДЛЯ ОБМЕНА/ПРОДАЖИ =====
            
            # Создаём таблицу deals если её нет
            try:
                if 'deals' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE deals (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                deal_type VARCHAR(20),
                                buyer VARCHAR(100),
                                seller VARCHAR(100),
                                country_id INTEGER REFERENCES countries(id),
                                denomination_value VARCHAR(50),
                                currency VARCHAR(50),
                                year INTEGER,
                                purchase_price FLOAT,
                                sale_price FLOAT,
                                commission FLOAT,
                                shipping_cost FLOAT,
                                platform VARCHAR(50),
                                deal_date DATE,
                                status VARCHAR(20) DEFAULT 'pending',
                                notes TEXT,
                                created_at DATETIME,
                                updated_at DATETIME,
                                zak VARCHAR(50),
                                amount VARCHAR(50),
                                discount VARCHAR(50),
                                money VARCHAR(50),
                                discount2 VARCHAR(50),
                                total VARCHAR(50),
                                reserve VARCHAR(50),
                                collect VARCHAR(50),
                                scan VARCHAR(50),
                                send VARCHAR(50),
                                approve VARCHAR(50),
                                payment VARCHAR(50),
                                check VARCHAR(50),
                                pack VARCHAR(50),
                                post VARCHAR(50),
                                arrived VARCHAR(50),
                                number VARCHAR(50),
                                type VARCHAR(50),
                                where VARCHAR(50),
                                cell_colors TEXT,
                                delivery VARCHAR(50)
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица deals создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы deals: {e}")
            
            # Создаём таблицу import_countries если её нет
            try:
                if 'import_countries' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE import_countries (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name VARCHAR(100) NOT NULL UNIQUE,
                                continent VARCHAR(50),
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица import_countries создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы import_countries: {e}")
            
            # Создаём/обновляем таблицу purchases
            try:
                if 'purchases' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE purchases (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                in_collection BOOLEAN DEFAULT 0,
                                collection_price FLOAT,
                                purchase_number VARCHAR(50),
                                purchase_batch VARCHAR(100),
                                import_country_id INTEGER REFERENCES import_countries(id),
                                continent VARCHAR(50),
                                denomination_value VARCHAR(50),
                                currency VARCHAR(50),
                                year INTEGER,
                                location_found VARCHAR(100),
                                quantity INTEGER DEFAULT 1,
                                comments TEXT,
                                ucoin_exchange BOOLEAN DEFAULT 0,
                                ucoin_exchange_count INTEGER DEFAULT 0,
                                sold_count VARCHAR(50),
                                sold_sum FLOAT,
                                total FLOAT,
                                manual_costs FLOAT,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица purchases создана")
                else:
                    # Проверяем наличие колонки manual_costs
                    columns_purchases = [col['name'] for col in inspector.get_columns('purchases')]
                    if 'manual_costs' not in columns_purchases:
                        with self.engine.connect() as conn:
                            conn.execute(text("ALTER TABLE purchases ADD COLUMN manual_costs FLOAT"))
                            conn.commit()
                            self.logger.info("✅ Добавлена колонка manual_costs в таблицу purchases")
                            
            except Exception as e:
                self.logger.error(f"Ошибка создания/обновления таблицы purchases: {e}")
            
            # Создаём/обновляем таблицу purchases_archive
            try:
                if 'purchases_archive' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE purchases_archive (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                in_collection BOOLEAN DEFAULT 0,
                                collection_price FLOAT,
                                purchase_number VARCHAR(50),
                                purchase_batch VARCHAR(100),
                                import_country_id INTEGER REFERENCES import_countries(id),
                                continent VARCHAR(50),
                                denomination_value VARCHAR(50),
                                currency VARCHAR(50),
                                year INTEGER,
                                location_found VARCHAR(100),
                                quantity INTEGER DEFAULT 1,
                                comments TEXT,
                                ucoin_exchange BOOLEAN DEFAULT 0,
                                ucoin_exchange_count INTEGER DEFAULT 0,
                                sold_count VARCHAR(50),
                                sold_sum FLOAT,
                                total FLOAT,
                                manual_costs FLOAT,
                                archived_at DATETIME,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица purchases_archive создана")
                else:
                    # Проверяем наличие колонки manual_costs
                    columns_archive = [col['name'] for col in inspector.get_columns('purchases_archive')]
                    if 'manual_costs' not in columns_archive:
                        with self.engine.connect() as conn:
                            conn.execute(text("ALTER TABLE purchases_archive ADD COLUMN manual_costs FLOAT"))
                            conn.commit()
                            self.logger.info("✅ Добавлена колонка manual_costs в таблицу purchases_archive")
                            
            except Exception as e:
                self.logger.error(f"Ошибка создания/обновления таблицы purchases_archive: {e}")
            
            # Создаём таблицу metal_holdings если её нет
            try:
                if 'metal_holdings' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE metal_holdings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                purchase_id INTEGER REFERENCES purchases(id),
                                number VARCHAR(20),
                                country_id INTEGER REFERENCES countries(id),
                                denomination_value VARCHAR(50),
                                year INTEGER,
                                metal_type VARCHAR(10),
                                metal_id INTEGER REFERENCES metals(id),
                                weight FLOAT,
                                purity FLOAT,
                                pure_weight FLOAT,
                                metal_ticker VARCHAR(20),
                                metal_price FLOAT,
                                calculated_value FLOAT,
                                created_at DATETIME,
                                updated_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица metal_holdings создана")
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы metal_holdings: {e}")
            
            # ===== НОВЫЕ ТАБЛИЦЫ ДЛЯ ЗАМЕТОК (ОРГАНАЙЗЕР) =====
            
            # Создаём таблицу категорий заметок
            try:
                if 'notebook_categories' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE notebook_categories (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name VARCHAR(50) NOT NULL UNIQUE,
                                color VARCHAR(20) DEFAULT '#4a6fa5',
                                icon VARCHAR(10) DEFAULT '📁',
                                sort_order INTEGER DEFAULT 0,
                                created_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица notebook_categories создана")
                        
                        # Добавляем категории по умолчанию
                        default_categories = [
                            ('Личное', '#4a6fa5', '👤'),
                            ('Работа', '#27ae60', '💼'),
                            ('Идеи', '#e67e22', '💡'),
                            ('Важное', '#e74c3c', '⭐'),
                            ('Проекты', '#9b59b6', '🚀'),
                        ]
                        for name, color, icon in default_categories:
                            conn.execute(text(
                                "INSERT INTO notebook_categories (name, color, icon) VALUES (?, ?, ?)"
                            ), (name, color, icon))
                        conn.commit()
                        
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы notebook_categories: {e}")
            
            # Создаём таблицу заметок
            try:
                if 'notebook_notes' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE notebook_notes (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                title VARCHAR(200) NOT NULL,
                                content TEXT,
                                note_type VARCHAR(20) DEFAULT 'note',
                                category_id INTEGER REFERENCES notebook_categories(id),
                                is_pinned BOOLEAN DEFAULT 0,
                                is_archived BOOLEAN DEFAULT 0,
                                is_trashed BOOLEAN DEFAULT 0,
                                color VARCHAR(20),
                                remind_at DATETIME,
                                remind_sent BOOLEAN DEFAULT 0,
                                attachments TEXT,
                                tags TEXT,
                                version INTEGER DEFAULT 1,
                                created_at DATETIME,
                                updated_at DATETIME,
                                deleted_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица notebook_notes создана")
                        
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы notebook_notes: {e}")
            
            # Создаём таблицу задач (для чек-листов)
            try:
                if 'notebook_tasks' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE notebook_tasks (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                note_id INTEGER NOT NULL REFERENCES notebook_notes(id) ON DELETE CASCADE,
                                text VARCHAR(500) NOT NULL,
                                is_checked BOOLEAN DEFAULT 0,
                                sort_order INTEGER DEFAULT 0,
                                created_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица notebook_tasks создана")
                        
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы notebook_tasks: {e}")
            
            # Создаём таблицу напоминаний
            try:
                if 'notebook_reminders' not in inspector.get_table_names():
                    with self.engine.connect() as conn:
                        conn.execute(text("""
                            CREATE TABLE notebook_reminders (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                title VARCHAR(200) NOT NULL,
                                text TEXT,
                                remind_at DATETIME NOT NULL,
                                is_done BOOLEAN DEFAULT 0,
                                repeat_type VARCHAR(20) DEFAULT 'none',
                                created_at DATETIME
                            )
                        """))
                        conn.commit()
                        self.logger.info("✅ Таблица notebook_reminders создана")
                        
            except Exception as e:
                self.logger.error(f"Ошибка создания таблицы notebook_reminders: {e}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении схемы БД: {e}")

    def get_all_countries(self):
        try:
            return self.session.query(Country).order_by(Country.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка стран: {e}")
            raise
    
    def get_countries_by_continent(self, continent, extinct=False):
        try:
            return self.session.query(Country).filter(
                Country.continent == continent,
                Country.is_extinct == extinct
            ).order_by(Country.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения стран по континенту: {e}")
            return []
    
    def get_or_create_country(self, name, continent=None, is_extinct=False, code=None):
        if not name:
            return None
        
        try:
            country = self.session.query(Country).filter_by(name=name).first()
            if not country:
                country = Country(name=name, continent=continent, is_extinct=is_extinct, code=code)
                self.session.add(country)
                self.session.commit()
                self.logger.info(f"Создана новая страна: {name}")
            return country
        except Exception as e:
            self.logger.error(f"Ошибка при получении/создании страны {name}: {e}")
            self.session.rollback()
            raise
    
    def update_country(self, country_id, data):
        try:
            country = self.session.query(Country).get(country_id)
            if country:
                for key, value in data.items():
                    if hasattr(country, key):
                        setattr(country, key, value)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления страны {country_id}: {e}")
            self.session.rollback()
            raise

    def get_country_predecessors(self, country_id):
        try:
            country = self.session.get(Country, country_id)
            if country:
                if hasattr(country, 'predecessors') and country.predecessors:
                    return country.predecessors
            return []
        except Exception as e:
            self.logger.error(f"Ошибка при получении предшественников: {e}")
            return []

    def get_country_successors(self, country_id):
        """Возвращает список стран-преемников (объекты Country) для страны."""
        try:
            country = self.session.query(Country).get(country_id)
            if not country:
                return []
            return list(country.successors or [])
        except Exception as e:
            self.logger.error(f"Ошибка чтения преемников: {e}")
            return []

    def set_country_successors(self, country_id, successor_ids):
        """Устанавливает (ЗАМЕНЯЕТ) список преемников страны.
        Принимает ЛЮБОЕ количество ID."""
        try:
            country = self.session.query(Country).get(country_id)
            if not country:
                return False, "Страна не найдена"
            succ = []
            for sid in (successor_ids or []):
                s = self.session.query(Country).get(sid)
                if s and s.id != country.id and s not in succ:
                    succ.append(s)
            country.successors = succ
            self.session.commit()
            names = ', '.join(s.name for s in succ) or '—'
            return True, f"Установлено преемников: {len(succ)}\n{names}"
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка установки преемников: {e}")
            return False, str(e)

    def add_country_successors(self, country_id, successor_ids):
        """ДОБАВЛЯЕТ несколько преемников к уже имеющимся (не перезаписывает).
        Именно этот метод отсутствовал — на него делегирует add_country_successor."""
        try:
            country = self.session.query(Country).get(country_id)
            if not country:
                return False, "Страна не найдена"
            existing = {s.id for s in (country.successors or [])}
            added = 0
            for sid in (successor_ids or []):
                s = self.session.query(Country).get(sid)
                if s and s.id != country.id and s.id not in existing:
                    country.successors.append(s)
                    existing.add(s.id)
                    added += 1
            self.session.commit()
            return True, f"Добавлено преемников: {added}"
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка добавления преемников: {e}")
            return False, str(e)

    def add_country_successor(self, country_id, successor_id):
        """Добавляет одного преемника (совместимость со старыми вызовами)."""
        return self.add_country_successors(country_id, [successor_id])

    def remove_country_successor(self, country_id, successor_id):
        """Убирает одного преемника из списка."""
        try:
            country = self.session.query(Country).get(country_id)
            if not country:
                return False, "Страна не найдена"
            country.successors = [s for s in (country.successors or [])
                                  if s.id != successor_id]
            self.session.commit()
            return True, "Преемник удалён"
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка удаления преемника: {e}")
            return False, str(e)

    def get_all_effective_countries_for_map(self, coin_country_id):
        try:
            country = self.session.get(Country, coin_country_id)
            if country:
                if hasattr(country, 'successors') and country.successors:
                    return [s.id for s in country.successors]
                elif hasattr(country, 'successor_id') and country.successor_id:
                    return [country.successor_id]
            return [coin_country_id]
        except Exception as e:
            self.logger.error(f"Ошибка при определении стран для карты: {e}")
            return [coin_country_id]
    
    def delete_country(self, country_id):
        try:
            country = self.session.get(Country, country_id)
            if not country:
                return False
            
            coins = self.session.query(Coin).filter_by(country_id=country_id).all()
            for coin in coins:
                self.session.delete(coin)
            
            self.session.delete(country)
            self.session.commit()
            self.logger.info(f"Страна '{country.name}' удалена вместе с {len(coins)} монетами")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления страны {country_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_country_without_coins(self, country_id):
        try:
            country = self.session.get(Country, country_id)
            if not country:
                return False, "Страна не найдена"
            
            coin_count = self.session.query(Coin).filter_by(country_id=country_id).count()
            if coin_count > 0:
                return False, f"У страны есть {coin_count} монет"
            
            self.session.delete(country)
            self.session.commit()
            return True, "Страна удалена"
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления страны {country_id}: {e}")
            self.session.rollback()
            raise
    
    def get_country_statistics(self, country_id):
        try:
            country = self.session.get(Country, country_id)
            if not country:
                return None
            
            total_coins = self.session.query(Coin).filter_by(country_id=country_id).count()
            in_collection = self.session.query(Coin).filter_by(country_id=country_id, status='in_collection').count()
            want = self.session.query(Coin).filter_by(country_id=country_id, status='want').count()
            sold = self.session.query(Coin).filter_by(country_id=country_id, status='sold').count()
            lost = self.session.query(Coin).filter_by(country_id=country_id, status='lost').count()
            
            years = [y[0] for y in self.session.query(Coin.year).filter_by(country_id=country_id).all() if y[0]]
            year_min = min(years) if years else None
            year_max = max(years) if years else None
            
            total_purchase = self.session.query(func.sum(Coin.purchase_price)).filter_by(
                country_id=country_id, status='in_collection'
            ).scalar() or 0
            
            return {
                'total_coins': total_coins,
                'in_collection': in_collection,
                'want': want,
                'sold': sold,
                'lost': lost,
                'year_min': year_min,
                'year_max': year_max,
                'total_purchase': total_purchase
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении статистики по стране: {e}")
            return None
    
    def update_country_from_wikipedia(self, country_id, wiki_data):
        try:
            country = self.session.get(Country, country_id)
            if not country:
                return False, "Страна не найдена"
            
            updated_fields = []
            
            if 'capital' in wiki_data:
                country.capital = wiki_data['capital']
                updated_fields.append('capital')
            if 'area' in wiki_data:
                country.area = wiki_data['area']
                updated_fields.append('area')
            if 'population' in wiki_data:
                country.population = wiki_data['population']
                updated_fields.append('population')
            if 'continent' in wiki_data:
                country.continent = wiki_data['continent']
                updated_fields.append('continent')
            if 'government' in wiki_data:
                country.government_type = wiki_data['government']
                updated_fields.append('government_type')
            if 'currency' in wiki_data and isinstance(wiki_data['currency'], dict):
                country.currency_name = wiki_data['currency'].get('name')
                country.currency_code = wiki_data['currency'].get('code')
                updated_fields.extend(['currency_name', 'currency_code'])
            if 'iso_code' in wiki_data:
                iso = wiki_data['iso_code'].upper()
                if len(iso) == 2:
                    country.iso2 = iso
                    updated_fields.append('iso2')
                elif len(iso) == 3:
                    country.iso3 = iso
                    updated_fields.append('iso3')
            if 'flag_url' in wiki_data:
                country.flag_url = wiki_data['flag_url']
                updated_fields.append('flag_url')
            if 'anthem' in wiki_data:
                country.anthem = wiki_data['anthem']
                updated_fields.append('anthem')
            if 'independence' in wiki_data:
                country.independence_date = wiki_data['independence']
                updated_fields.append('independence_date')
            if 'url' in wiki_data:
                country.web_url = wiki_data['url']
                updated_fields.append('web_url')
            
            if updated_fields:
                country.updated_at = datetime.now()
                self.session.commit()
                return True, f"Обновлено полей: {', '.join(updated_fields)}"
            return False, "Нет данных для обновления"
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении страны из Wikipedia: {e}")
            self.session.rollback()
            return False, str(e)
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ВАЛЮТАМИ =====
    
    def get_all_currencies(self):
        try:
            return self.session.query(Currency).order_by(Currency.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка валют: {e}")
            return []
    
    def get_currency(self, currency_id):
        try:
            return self.session.get(Currency, currency_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения валюты {currency_id}: {e}")
            raise
    
    def add_currency(self, currency_data):
        try:
            currency = Currency(**currency_data)
            self.session.add(currency)
            self.session.commit()
            return currency.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления валюты: {e}")
            self.session.rollback()
            raise
    
    def update_currency(self, currency_id, currency_data):
        try:
            currency = self.session.get(Currency, currency_id)
            if currency:
                for key, value in currency_data.items():
                    setattr(currency, key, value)
                currency.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления валюты {currency_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_currency(self, currency_id):
        try:
            coin_count = self.session.query(Coin).filter_by(currency_id=currency_id).count()
            if coin_count > 0:
                return False, f"Валюта используется в {coin_count} монетах"
            
            currency = self.session.get(Currency, currency_id)
            if currency:
                self.session.delete(currency)
                self.session.commit()
                return True, "Валюта удалена"
            return False, "Валюта не найдена"
        except Exception as e:
            self.logger.error(f"Ошибка удаления валюты {currency_id}: {e}")
            self.session.rollback()
            raise
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С МОНЕТНЫМИ ДВОРАМИ =====
    
    def get_all_mints(self):
        try:
            return self.session.query(Mint).order_by(Mint.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка монетных дворов: {e}")
            return []
    
    def get_mint(self, mint_id):
        try:
            return self.session.get(Mint, mint_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения монетного двора {mint_id}: {e}")
            raise
    
    def get_mints_by_country(self, country_id):
        try:
            return self.session.query(Mint).filter_by(country_id=country_id).order_by(Mint.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения монетных дворов по стране: {e}")
            return []
    
    def add_mint(self, mint_data):
        try:
            mint = Mint(**mint_data)
            self.session.add(mint)
            self.session.commit()
            return mint.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления монетного двора: {e}")
            self.session.rollback()
            raise
    
    def update_mint(self, mint_id, mint_data):
        try:
            mint = self.session.get(Mint, mint_id)
            if mint:
                for key, value in mint_data.items():
                    setattr(mint, key, value)
                mint.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления монетного двора {mint_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_mint(self, mint_id):
        try:
            coin_count = self.session.query(Coin).filter_by(mint_id=mint_id).count()
            if coin_count > 0:
                return False, f"Монетный двор используется в {coin_count} монетах"
            
            mint = self.session.get(Mint, mint_id)
            if mint:
                self.session.delete(mint)
                self.session.commit()
                return True, "Монетный двор удален"
            return False, "Монетный двор не найдена"
        except Exception as e:
            self.logger.error(f"Ошибка удаления монетного двора {mint_id}: {e}")
            self.session.rollback()
            raise
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПЕРИОДАМИ =====
    
    def get_all_periods(self):
        try:
            return self.session.query(Period).order_by(Period.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка периодов: {e}")
            return []
    
    def get_periods_by_country(self, country_id):
        try:
            return self.session.query(Period).filter_by(country_id=country_id).order_by(Period.start_year).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения периодов по стране {country_id}: {e}")
            return []
    
    def get_period(self, period_id):
        try:
            return self.session.get(Period, period_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения периода {period_id}: {e}")
            raise
    
    def add_period(self, period_data):
        try:
            period = Period(**period_data)
            self.session.add(period)
            self.session.commit()
            return period.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления периода: {e}")
            self.session.rollback()
            raise
    
    def update_period(self, period_id, period_data):
        try:
            period = self.session.get(Period, period_id)
            if period:
                for key, value in period_data.items():
                    setattr(period, key, value)
                period.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления периода {period_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_period(self, period_id):
        try:
            coin_count = self.session.query(Coin).filter_by(period_id=period_id).count()
            if coin_count > 0:
                return False, f"Период используется в {coin_count} монетах"
            
            period = self.session.get(Period, period_id)
            if period:
                self.session.delete(period)
                self.session.commit()
                return True, "Период удален"
            return False, "Период не найден"
        except Exception as e:
            self.logger.error(f"Ошибка удаления периода {period_id}: {e}")
            self.session.rollback()
            raise
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С МОНЕТАМИ =====
    
    def add_coin(self, coin_data):
        try:
            self.logger.info(f"Добавление новой монеты: {coin_data.get('denomination_value', '')} {coin_data.get('currency', '')} {coin_data.get('year', '')}")
            
            if 'id' in coin_data:
                del coin_data['id']
            
            from sqlalchemy import text
            result = self.session.execute(text("SELECT MAX(id) FROM coins")).scalar()
            next_id = (result or 0) + 1
            
            coin_data['id'] = next_id
            
            coin = Coin(**coin_data)
            self.session.add(coin)
            self.session.commit()
            self.session.refresh(coin)
            
            self.logger.info(f"Монета добавлена с ID: {coin.id}")
            return coin.id
            
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении монеты: {e}")
            self.session.rollback()
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def update_coin(self, coin_id, coin_data):
        try:
            coin = self.session.get(Coin, coin_id)
            if not coin:
                return False
            
            for key, value in coin_data.items():
                if hasattr(coin, key):
                    setattr(coin, key, value)
            
            coin.updated_at = datetime.now()
            self.session.commit()
            self.logger.info(f"Монета ID {coin_id} обновлена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении монеты: {e}")
            self.session.rollback()
            return False
    
    def delete_coin(self, coin_id):
        try:
            coin = self.session.get(Coin, coin_id)
            if coin:
                self.session.delete(coin)
                self.session.commit()
                self.logger.info(f"Монета ID {coin_id} удалена")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка удаления монеты {coin_id}: {e}")
            self.session.rollback()
            raise
    
    def get_coin(self, coin_id):
        try:
            return self.session.get(Coin, coin_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения монеты {coin_id}: {e}")
            raise
    
    def get_all_coins(self):
        try:
            return self.session.query(Coin).order_by(Coin.created_at.desc()).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения всех монет: {e}")
            raise
    
    def update_coin_image(self, coin_id, side, image_path):
        try:
            coin = self.session.get(Coin, coin_id)
            if coin:
                if side == 'obverse':
                    coin.obverse_image = image_path
                elif side == 'reverse':
                    coin.reverse_image = image_path
                self.session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении изображения монеты: {e}")
            self.session.rollback()
        return False
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ СО СТРАНАМИ ПРИОБРЕТЕНИЯ (СПРАВОЧНИК) =====
    
    def get_all_purchase_countries(self):
        try:
            return self.session.query(PurchaseCountry).order_by(PurchaseCountry.name).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка стран приобретения: {e}")
            return []
    
    def get_purchase_country(self, country_id):
        try:
            return self.session.get(PurchaseCountry, country_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения страны приобретения {country_id}: {e}")
            raise
    
    def add_purchase_country(self, country_data):
        try:
            country = PurchaseCountry(**country_data)
            self.session.add(country)
            self.session.commit()
            return country.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления страны приобретения: {e}")
            self.session.rollback()
            raise
    
    def update_purchase_country(self, country_id, country_data):
        try:
            country = self.session.get(PurchaseCountry, country_id)
            if country:
                for key, value in country_data.items():
                    setattr(country, key, value)
                country.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления страны приобретения {country_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_purchase_country(self, country_id):
        try:
            coin_count = self.session.query(Coin).filter_by(purchase_country_id=country_id).count()
            if coin_count > 0:
                return False, f"Страна приобретения используется в {coin_count} монетах"
            
            country = self.session.get(PurchaseCountry, country_id)
            if country:
                self.session.delete(country)
                self.session.commit()
                return True, "Страна приобретения удалена"
            return False, "Страна приобретения не найдена"
        except Exception as e:
            self.logger.error(f"Ошибка удаления страны приобретения {country_id}: {e}")
            self.session.rollback()
            raise
    
    def get_or_create_purchase_country(self, name):
        if not name:
            return None
        
        try:
            country = self.session.query(PurchaseCountry).filter_by(name=name).first()
            if not country:
                country = PurchaseCountry(name=name)
                self.session.add(country)
                self.session.commit()
                self.logger.info(f"Создана новая страна приобретения: {name}")
            return country
        except Exception as e:
            self.logger.error(f"Ошибка при получении/создании страны приобретения {name}: {e}")
            self.session.rollback()
            return None
    
    # ===== БЭКАП =====
    
    def create_backup(self, backup_path):
        try:
            shutil.copy2(self.db_path, backup_path)
            self.logger.info(f"Резервная копия создана: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка создания резервной копии: {e}")
            raise
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ИСТОРИЕЙ РЫНОЧНЫХ ЦЕН =====
    
    def add_market_price_history(self, coin_id, market_price, price_date, source_file=None):
        try:
            existing = self.session.query(MarketPriceHistory).filter(
                MarketPriceHistory.coin_id == coin_id,
                MarketPriceHistory.price_date == price_date
            ).first()
            
            if existing:
                existing.market_price = market_price
                existing.source_file = source_file
                existing.created_at = datetime.now()
                self.logger.info(f"Обновлена история цены для монеты {coin_id}: {market_price} на {price_date}")
            else:
                coin = self.get_coin(coin_id)
                history = MarketPriceHistory(
                    coin_id=coin_id,
                    country_name=coin.country.name if coin.country else None,
                    denomination=coin.denomination_value,
                    year=coin.year,
                    mint_mark=coin.mint_mark,
                    market_price=market_price,
                    price_date=price_date,
                    source_file=source_file
                )
                self.session.add(history)
                self.logger.info(f"Добавлена история цены для монеты {coin_id}: {market_price} на {price_date}")
            
            self.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка добавления истории цены: {e}")
            self.session.rollback()
            return False
    
    def add_market_price_history_batch(self, coins_data, price_date, source_file=None):
        try:
            added_count = 0
            for coin, price in coins_data:
                history = MarketPriceHistory(
                    coin_id=coin.id,
                    country_name=coin.country.name if coin.country else None,
                    denomination=coin.denomination_value,
                    year=coin.year,
                    mint_mark=coin.mint_mark,
                    market_price=price,
                    price_date=price_date,
                    source_file=source_file
                )
                self.session.add(history)
                added_count += 1
            
            self.session.commit()
            self.logger.info(f"Добавлено {added_count} записей в историю цен")
            return added_count
        except Exception as e:
            self.logger.error(f"Ошибка добавления истории цен: {e}")
            self.session.rollback()
            return 0
    
    def get_market_price_history(self, coin_id=None, start_date=None, end_date=None, limit=100):
        try:
            query = self.session.query(MarketPriceHistory)
            
            if coin_id:
                query = query.filter(MarketPriceHistory.coin_id == coin_id)
            
            if start_date:
                query = query.filter(MarketPriceHistory.price_date >= start_date)
            
            if end_date:
                query = query.filter(MarketPriceHistory.price_date <= end_date)
            
            query = query.order_by(MarketPriceHistory.price_date.desc()).limit(limit)
            
            return query.all()
        except Exception as e:
            self.logger.error(f"Ошибка получения истории цен: {e}")
            return []
    
    def get_latest_market_price(self, coin_id):
        try:
            latest = self.session.query(MarketPriceHistory).filter(
                MarketPriceHistory.coin_id == coin_id
            ).order_by(MarketPriceHistory.price_date.desc()).first()
            
            return latest
        except Exception as e:
            self.logger.error(f"Ошибка получения последней цены: {e}")
            return None
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ ПОЛЕЙ =====
    

# ===== database/db_manager.py =====
# В МЕТОДЕ init_standard_fields, ДОБАВИТЬ НОВЫЕ ПОЛЯ ДЛЯ ВСЕХ СТАНДАРТНЫХ ПОЛЕЙ

    def init_standard_fields(self):
        """Инициализирует настройки для стандартных полей"""
        try:
            # Проверяем, есть ли уже записи
            existing_count = self.session.query(FieldSettings).count()
            if existing_count > 0:
                # Обновляем существующие записи, добавляем новые поля
                for field in self.session.query(FieldSettings).all():
                    if not hasattr(field, 'show_in_view'):
                        field.show_in_view = True
                    if not hasattr(field, 'show_in_edit'):
                        field.show_in_edit = True
                self.session.commit()
                return
            
            standard_fields = [
                # Специальные
                {"field_key": "select", "name": "☑", "category": "Специальные", "field_type": "checkbox", "show_in_table": True, "show_in_form": False, "show_in_view": False, "show_in_edit": False, "sort_order": 0, "is_standard": True},
                {"field_key": "id", "name": "ID", "category": "Специальные", "field_type": "number", "show_in_table": False, "show_in_form": False, "show_in_view": False, "show_in_edit": False, "sort_order": 1, "is_standard": True},
                
                # Основные
                {"field_key": "country", "name": "Страна", "category": "Основные", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 10, "is_standard": True},
                {"field_key": "catalog_number", "name": "№ каталога", "category": "Основные", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 11, "is_standard": True},
                {"field_key": "denomination_value", "name": "Номинал", "category": "Основные", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 12, "is_standard": True},
                {"field_key": "currency", "name": "Валюта", "category": "Основные", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 13, "is_standard": True},
                {"field_key": "year", "name": "Год", "category": "Основные", "field_type": "number", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 14, "is_standard": True},
                {"field_key": "period", "name": "Период", "category": "Основные", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 15, "is_standard": True},
                {"field_key": "century", "name": "Век", "category": "Основные", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 16, "is_standard": True},
                
                # Монетный двор
                {"field_key": "mint", "name": "Монетный двор", "category": "Монетный двор", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 20, "is_standard": True},
                {"field_key": "mint_mark", "name": "Знак МД", "category": "Монетный двор", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 21, "is_standard": True},
                
                # Характеристики
                {"field_key": "metal", "name": "Металл", "category": "Характеристики", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 30, "is_standard": True},
                {"field_key": "weight", "name": "Вес (г)", "category": "Характеристики", "field_type": "number", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 31, "is_standard": True},
                {"field_key": "diameter", "name": "Размер (мм)", "category": "Характеристики", "field_type": "number", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 32, "is_standard": True},
                {"field_key": "shape", "name": "Форма", "category": "Характеристики", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 33, "is_standard": True},
                
                # Гурт
                {"field_key": "edge", "name": "Гурт", "category": "Гурт", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 40, "is_standard": True},
                {"field_key": "edge_description", "name": "Описание гурта", "category": "Гурт", "field_type": "textarea", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 41, "is_standard": True},
                
                # Состояние
                {"field_key": "condition", "name": "Сохранность", "category": "Состояние", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 50, "is_standard": True},
                {"field_key": "rarity", "name": "Редкость", "category": "Состояние", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 51, "is_standard": True},
                {"field_key": "storage_location", "name": "Альбом", "category": "Состояние", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 52, "is_standard": True},
                {"field_key": "issue_type", "name": "Тип выпуска", "category": "Состояние", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 53, "is_standard": True},
                {"field_key": "avrev", "name": "АВ/РЕВ", "category": "Состояние", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 54, "is_standard": True},
                {"field_key": "status", "name": "Статус", "category": "Состояние", "field_type": "text", "show_in_table": True, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 55, "is_standard": True},
                
                # Покупка
                {"field_key": "purchase_date", "name": "Дата покупки", "category": "Покупка", "field_type": "date", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 60, "is_standard": True},
                {"field_key": "purchase_price", "name": "Цена покупки", "category": "Покупка", "field_type": "number", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 61, "is_standard": True},
                {"field_key": "purchase_where", "name": "Где куплена", "category": "Покупка", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 62, "is_standard": True},
                {"field_key": "purchase_country", "name": "Страна покупки", "category": "Покупка", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 63, "is_standard": True},
                {"field_key": "acquisition_type", "name": "Тип приобретения", "category": "Покупка", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 64, "is_standard": True},
                {"field_key": "purchase_info", "name": "Информация о покупке", "category": "Покупка", "field_type": "textarea", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 65, "is_standard": True},
                
                # Рыночная цена
                {"field_key": "market_price", "name": "Рыночная цена", "category": "Рыночная цена", "field_type": "number", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 70, "is_standard": True},
                {"field_key": "market_price_date", "name": "Дата цены", "category": "Рыночная цена", "field_type": "date", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 71, "is_standard": True},
                
                # Ссылки
                {"field_key": "ucoin_url", "name": "UCOIN ссылка", "category": "Ссылки", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 80, "is_standard": True},
                {"field_key": "meshok_url", "name": "Meshok ссылка", "category": "Ссылки", "field_type": "text", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 81, "is_standard": True},
                
                # Информация
                {"field_key": "coin_info", "name": "Информация о монете", "category": "Информация", "field_type": "textarea", "show_in_table": False, "show_in_form": True, "show_in_view": True, "show_in_edit": True, "sort_order": 90, "is_standard": True},
            ]
            
            for field_data in standard_fields:
                field = FieldSettings(**field_data, is_active=True)
                self.session.add(field)
            
            self.session.commit()
            self.logger.info("✅ Настройки стандартных полей инициализированы")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации стандартных полей: {e}")
            self.session.rollback()

    def get_all_field_settings(self):
        """Возвращает настройки всех полей"""
        try:
            return self.session.query(FieldSettings).order_by(FieldSettings.sort_order).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения настроек полей: {e}")
            return []
    
    def get_active_custom_fields(self):
        """Возвращает список активных пользовательских полей"""
        try:
            # Пока нет поля is_active, возвращаем все пользовательские поля
            return self.session.query(FieldSettings).filter(
                FieldSettings.is_standard == False
            ).order_by(FieldSettings.sort_order).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения активных полей: {e}")
            return []
    
    def get_field_settings(self, field_key):
        """Возвращает настройки поля по ключу"""
        try:
            return self.session.query(FieldSettings).filter_by(field_key=field_key).first()
        except Exception as e:
            self.logger.error(f"Ошибка получения настроек поля {field_key}: {e}")
            return None
    
    def update_field_settings(self, field_key, settings):
        """Обновляет настройки поля"""
        try:
            field = self.session.query(FieldSettings).filter_by(field_key=field_key).first()
            if field:
                for key, value in settings.items():
                    if hasattr(field, key):
                        setattr(field, key, value)
                field.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления настроек поля {field_key}: {e}")
            self.session.rollback()
            return False
    
# ===== database/db_manager.py =====
# ИСПРАВИТЬ МЕТОД add_custom_field (убрать дублирование is_active)

    def add_custom_field(self, field_data):
        """Добавляет новое пользовательское поле"""
        try:
            # Проверяем, не существует ли уже поле с таким ключом
            existing = self.session.query(FieldSettings).filter_by(field_key=field_data["field_key"]).first()
            if existing:
                raise Exception(f"Поле с ключом '{field_data['field_key']}' уже существует")
            
            # Убираем is_active из field_data если он там есть
            if 'is_active' in field_data:
                del field_data['is_active']
            
            field = FieldSettings(**field_data, is_standard=False)
            self.session.add(field)
            self.session.commit()
            
            # Добавляем колонку в таблицу coins для хранения данных
            column_name = f"custom_{field_data['field_key']}"
            try:
                with self.engine.connect() as conn:
                    # Проверяем, существует ли колонка
                    result = conn.execute(text(f"PRAGMA table_info(coins)")).fetchall()
                    columns = [r[1] for r in result]
                    if column_name not in columns:
                        conn.execute(text(f"ALTER TABLE coins ADD COLUMN {column_name} TEXT"))
                        conn.commit()
                        self.logger.info(f"✅ Добавлена колонка {column_name} в таблицу coins")
            except Exception as e:
                self.logger.warning(f"Не удалось добавить колонку {column_name}: {e}")
            
            return field.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления поля: {e}")
            self.session.rollback()
            raise
    
    def delete_custom_field_by_key(self, field_key):
        """Удаляет пользовательское поле по ключу"""
        try:
            field = self.session.query(FieldSettings).filter_by(field_key=field_key, is_standard=False).first()
            if field:
                self.session.delete(field)
                self.session.commit()
                return True, "Поле удалено"
            return False, "Поле не найдено"
        except Exception as e:
            self.logger.error(f"Ошибка удаления поля {field_key}: {e}")
            self.session.rollback()
            return False, str(e)
    
    def reset_standard_fields(self):
        """Сбрасывает настройки стандартных полей к значениям по умолчанию"""
        try:
            # Удаляем все существующие настройки стандартных полей
            self.session.query(FieldSettings).filter(FieldSettings.is_standard == True).delete()
            self.session.commit()
            
            # Инициализируем заново
            self.init_standard_fields()
            self.logger.info("✅ Настройки стандартных полей сброшены")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сброса настроек полей: {e}")
            self.session.rollback()
            return False
            
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ НЕДОСТАЮЩИЕ МЕТОДЫ (в конец класса)

    def get_all_custom_fields(self):
        """Возвращает список всех пользовательских полей"""
        try:
            return self.session.query(FieldSettings).filter(
                FieldSettings.is_standard == False
            ).order_by(FieldSettings.sort_order).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения списка полей: {e}")
            return []
    
    def get_custom_field(self, field_id):
        """Возвращает пользовательское поле по ID"""
        try:
            return self.session.query(FieldSettings).filter(
                FieldSettings.id == field_id,
                FieldSettings.is_standard == False
            ).first()
        except Exception as e:
            self.logger.error(f"Ошибка получения поля {field_id}: {e}")
            return None
            
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ МЕТОД get_field_settings_by_id

    def get_field_settings_by_id(self, field_id):
        """Возвращает настройки поля по ID"""
        try:
            from database.models import FieldSettings
            return self.session.get(FieldSettings, field_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения поля {field_id}: {e}")
            return None
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ МЕТОД update_field_settings (если нет) или ОБНОВИТЬ

    def update_field_settings(self, field_key, settings):
        """Обновляет настройки поля"""
        try:
            field = self.session.query(FieldSettings).filter_by(field_key=field_key).first()
            if field:
                for key, value in settings.items():
                    if hasattr(field, key):
                        setattr(field, key, value)
                field.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления настроек поля {field_key}: {e}")
            self.session.rollback()
            return False            
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЬСКИМИ СПРАВОЧНИКАМИ

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЬСКИМИ СПРАВОЧНИКАМИ =====
    
    def get_custom_references(self, field_key):
        """Возвращает список значений для пользовательского справочника"""
        try:
            from database.models import CustomReference
            return self.session.query(CustomReference).filter(
                CustomReference.field_key == field_key,
                CustomReference.is_active == True
            ).order_by(CustomReference.sort_order).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения справочника {field_key}: {e}")
            return []
    
    def add_custom_reference(self, field_key, name, value):
        """Добавляет значение в пользовательский справочник"""
        try:
            from database.models import CustomReference
            ref = CustomReference(field_key=field_key, name=name, value=value)
            self.session.add(ref)
            self.session.commit()
            return ref.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления значения: {e}")
            self.session.rollback()
            return None
    
    def delete_custom_reference(self, ref_id):
        """Удаляет значение из пользовательского справочника"""
        try:
            from database.models import CustomReference
            ref = self.session.get(CustomReference, ref_id)
            if ref:
                self.session.delete(ref)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка удаления: {e}")
            self.session.rollback()
            return False
            
            
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ МЕТОДЫ ДЛЯ РАБОТЫ СО СТАНДАРТНЫМИ СПРАВОЧНИКАМИ

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ СО СТАНДАРТНЫМИ СПРАВОЧНИКАМИ =====
    
    def init_standard_references(self):
        """Инициализирует стандартные справочники значениями по умолчанию"""
        try:
            from database.models import StandardReference
            
            # Проверяем, есть ли уже данные
            if self.session.query(StandardReference).count() > 0:
                return
            
            standard_refs = {
                'rarity': [
                    ('A', 'A (обычная)'),
                    ('B', 'B (редкая)'),
                    ('C', 'C (очень редкая)'),
                    ('R', 'R (редкая)'),
                    ('RR', 'RR (очень редкая)'),
                    ('RRR', 'RRR (исключительно редкая)'),
                ],
                'condition': [
                    ('UNC', 'UNC (Uncirculated) - идеальное состояние'),
                    ('AU', 'AU (About Uncirculated) - почти идеальное'),
                    ('XF', 'XF (Extremely Fine) - отличное'),
                    ('VF', 'VF (Very Fine) - очень хорошее'),
                    ('F', 'F (Fine) - хорошее'),
                    ('VG', 'VG (Very Good) - удовлетворительное'),
                    ('G', 'G (Good) - слабое'),
                    ('PR', 'PR (Poor) - плохое'),
                    ('Proof', 'Proof - пруф'),
                ],
                'shape': [
                    ('Круг', 'Круг'),
                    ('Многоугольник', 'Многоугольник'),
                    ('Овал', 'Овал'),
                    ('Квадрат', 'Квадрат'),
                    ('Прямоугольник', 'Прямоугольник'),
                ],
                'issue_type': [
                    ('Регулярный чекан', 'Регулярный чекан'),
                    ('Юбилейные монеты', 'Юбилейные монеты'),
                    ('Коллекционные монеты', 'Коллекционные монеты'),
                    ('Нотгельды', 'Нотгельды'),
                    ('Пробный', 'Пробный'),
                ],
                'avrev': [
                    ('Медальное (0°)', 'Медальное (0°)'),
                    ('Монетное (180°)', 'Монетное (180°)'),
                ],
                'status': [
                    ('in_collection', 'В коллекции'),
                    ('want', 'Хочу'),
                    ('sold', 'Продано'),
                    ('lost', 'Утеряна'),
                    ('for_sale', 'На продажу'),
                ],
                'acquisition_type': [
                    ('Покупка', 'Покупка'),
                    ('Подарок', 'Подарок'),
                    ('Обмен', 'Обмен'),
                    ('Наследство', 'Наследство'),
                    ('Находка', 'Находка'),
                    ('Закупка', 'Закупка'),
                    ('Оборот', 'Оборот'),
                ],
                'storage_location': [
                    ('Синий альбом', 'Синий альбом'),
                    ('Зелёный альбом', 'Зелёный альбом'),
                    ('Капсула', 'Капсула'),
                    ('Планшет', 'Планшет'),
                    ('Витрина', 'Витрина'),
                    ('Сейф', 'Сейф'),
                ],
            }
            
            for field_key, values in standard_refs.items():
                for sort_order, (value, name) in enumerate(values):
                    ref = StandardReference(
                        field_key=field_key,
                        value=value,
                        name=name,
                        sort_order=sort_order
                    )
                    self.session.add(ref)
            
            self.session.commit()
            self.logger.info("✅ Стандартные справочники инициализированы")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации стандартных справочников: {e}")
            self.session.rollback()
    
    def get_standard_references(self, field_key):
        """Возвращает список значений для стандартного справочника"""
        try:
            from database.models import StandardReference
            return self.session.query(StandardReference).filter(
                StandardReference.field_key == field_key,
                StandardReference.is_active == True
            ).order_by(StandardReference.sort_order).all()
        except Exception as e:
            self.logger.error(f"Ошибка получения справочника {field_key}: {e}")
            return []
    
    def add_standard_reference(self, field_key, value, name):
        """Добавляет значение в стандартный справочник"""
        try:
            from database.models import StandardReference
            ref = StandardReference(
                field_key=field_key,
                value=value,
                name=name,
                sort_order=self.session.query(StandardReference).filter_by(field_key=field_key).count()
            )
            self.session.add(ref)
            self.session.commit()
            return ref.id
        except Exception as e:
            self.logger.error(f"Ошибка добавления значения: {e}")
            self.session.rollback()
            return None
    
    def update_standard_reference(self, ref_id, value, name):
        """Обновляет значение в стандартном справочнике"""
        try:
            from database.models import StandardReference
            ref = self.session.get(StandardReference, ref_id)
            if ref:
                ref.value = value
                ref.name = name
                ref.updated_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления: {e}")
            self.session.rollback()
            return False
    
    def delete_standard_reference(self, ref_id):
        """Удаляет значение из стандартного справочника"""
        try:
            from database.models import StandardReference
            ref = self.session.get(StandardReference, ref_id)
            if ref:
                self.session.delete(ref)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка удаления: {e}")
            self.session.rollback()
            return False
      
      
# ===== database/db_manager.py =====
# ЗАМЕНИТЬ МЕТОД archive_purchases_by_batch

    def archive_purchases_by_batch(self, purchase_batch):
        """Переносит все закупки с указанным purchase_batch в архив и удаляет из основной таблицы"""
        try:
            from database.models import Purchase, PurchaseArchive
            
            # Находим все закупки с указанным номером партии
            purchases = self.session.query(Purchase).filter(
                Purchase.purchase_batch == str(purchase_batch)
            ).all()
            
            if not purchases:
                return 0, f"Закупки с №Пок {purchase_batch} не найдены"
            
            archived_count = 0
            for purchase in purchases:
                # Создаём архивную запись
                archive = PurchaseArchive()
                
                # Копируем ВСЕ поля (включая суммы)
                archive.in_collection = purchase.in_collection
                archive.collection_price = purchase.collection_price
                archive.purchase_number = purchase.purchase_number
                archive.purchase_batch = purchase.purchase_batch
                archive.import_country_id = purchase.import_country_id
                archive.continent = purchase.continent
                archive.denomination_value = purchase.denomination_value
                archive.currency = purchase.currency
                archive.year = purchase.year
                archive.location_found = purchase.location_found
                archive.quantity = purchase.quantity
                archive.comments = purchase.comments
                archive.ucoin_exchange = purchase.ucoin_exchange
                archive.ucoin_exchange_count = purchase.ucoin_exchange_count
                archive.sold_count = purchase.sold_count
                archive.sold_sum = purchase.sold_sum      # <-- ВАЖНО: сумма продажи
                archive.total = purchase.total            # <-- ВАЖНО: итоговая сумма
                archive.manual_costs = purchase.manual_costs
                archive.archived_at = datetime.now()
                archive.created_at = purchase.created_at
                archive.updated_at = purchase.updated_at
                
                self.session.add(archive)
                
                # Удаляем оригинал
                self.session.delete(purchase)
                archived_count += 1
            
            self.session.commit()
            return archived_count, f"Перенесено в архив: {archived_count} закупок"
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка архивации: {e}")
            import traceback
            traceback.print_exc()
            return 0, str(e)

    def get_archive_purchases_by_batch(self, purchase_batch):
        """Получает архивные закупки по номеру партии"""
        return self.session.query(PurchaseArchive).filter(
            PurchaseArchive.purchase_batch == str(purchase_batch)
        ).all()
        
# ===== ФАЙЛ: database/db_manager.py =====
# ПРОСТАЯ МИГРАЦИЯ (если данные не важны)

    def _migrate_delivery_column_simple(self):
        """Простая миграция: удаляем и создаём колонку заново (данные потеряются)"""
        try:
            with self.engine.connect() as conn:
                # Удаляем старую колонку
                conn.execute(text("ALTER TABLE deals DROP COLUMN delivery"))
                conn.commit()
                
                # Создаём новую колонку с правильным типом
                conn.execute(text("ALTER TABLE deals ADD COLUMN delivery VARCHAR(50)"))
                conn.commit()
                
                self.logger.info("✅ Миграция колонки delivery завершена (данные удалены)")
        except Exception as e:
            self.logger.error(f"Ошибка миграции delivery: {e}")
            
# ===== database/db_manager.py =====
# ДОБАВИТЬ МЕТОД _add_manual_costs_column

    def _add_manual_costs_column(self):
        """Добавляет колонку manual_costs в таблицы purchases и purchases_archive"""
        try:
            inspector = inspect(self.engine)
            
            # Проверяем таблицу purchases
            if 'purchases' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('purchases')]
                if 'manual_costs' not in columns:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE purchases ADD COLUMN manual_costs FLOAT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка manual_costs в таблицу purchases")
            
            # Проверяем таблицу purchases_archive
            if 'purchases_archive' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('purchases_archive')]
                if 'manual_costs' not in columns:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE purchases_archive ADD COLUMN manual_costs FLOAT"))
                        conn.commit()
                        self.logger.info("✅ Добавлена колонка manual_costs в таблицу purchases_archive")
                        
        except Exception as e:
            self.logger.error(f"Ошибка добавления колонки manual_costs: {e}")
            
            
    def force_wal_checkpoint(self, mode="TRUNCATE"):
        """
        Принудительно синхронизирует WAL-журнал с основным файлом БД.
        
        Режимы:
        - "PASSIVE": минимальное влияние, не блокирует чтение/запись
        - "FULL": полная синхронизация, блокирует запись
        - "TRUNCATE": полная синхронизация + удаляет WAL-файл
        - "RESTART": как FULL, но перезапускает WAL
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"PRAGMA wal_checkpoint({mode})"))
                conn.commit()
                
                row = result.fetchone()
                if row:
                    # Формат: (busy_pages, log_pages, checkpointed_pages)
                    busy = row[0] if len(row) > 0 else 0
                    log = row[1] if len(row) > 1 else 0
                    checkpointed = row[2] if len(row) > 2 else 0
                    
                    self.logger.info(f"✅ WAL checkpoint: busy={busy}, log={log}, checkpointed={checkpointed}")
                    return {'busy': busy, 'log': log, 'checkpointed': checkpointed}
                
                return {'busy': 0, 'log': 0, 'checkpointed': 0}
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка WAL checkpoint: {e}")
            raise
            
    def close_connection(self, checkpoint=True):
        """
        Полностью закрывает соединение с БД.
        При checkpoint=True сначала синхронизирует WAL.
        """
        try:
            if checkpoint:
                self.force_wal_checkpoint("TRUNCATE")
            
            # Закрываем сессию
            if hasattr(self, 'session') and self.session:
                self.session.close()
            
            # Закрываем engine
            if hasattr(self, 'engine') and self.engine:
                self.engine.dispose()
                
            self.logger.info("✅ Соединение с БД закрыто, WAL синхронизирован")
            
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии БД: {e}")
            raise
            
    def generate_catalog_number(self, metal_name=None):
        """Генерирует каталожный номер по металлу монеты:
        драгоценные (золото/серебро/платина/палладий) -> AG00001, AG00002...
        остальные -> NN00001, NN00002...
        Номер всегда следующий по порядку для своего префикса."""
        import re
        from database.models import Coin
        name = (metal_name or '').lower()
        precious = any(k in name for k in (
            'золот', 'gold', 'серебр', 'silver',
            'платин', 'platinum', 'паллад', 'pallad'
        ))
        prefix = 'AG' if precious else 'NN'
        try:
            rows = (self.session.query(Coin.catalog_number)
                    .filter(Coin.catalog_number.like(f'{prefix}%')).all())
            max_n = 0
            for (c,) in rows:
                if not c:
                    continue
                m = re.search(r'(\d+)\s*$', c.strip())
                if m:
                    max_n = max(max_n, int(m.group(1)))
            return f"{prefix}{max_n + 1:05d}"
        except Exception as e:
            self.logger.error(f"Ошибка генерации номера: {e}")
            return f"{prefix}00001"
            
    def _ensure_successor_links_table(self):
        """Создаёт лёгкую таблицу связей-преемников ПО НАЗВАНИЯМ.
        Страны при этом НЕ создаются — дерево стран и комбобоксы не засоряются."""
        from sqlalchemy import text
        try:
            with self.engine.connect() as conn:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS country_successor_links ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "extinct_id INTEGER NOT NULL, "
                    "successor_name TEXT NOT NULL, "
                    "UNIQUE(extinct_id, successor_name))"
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Ошибка создания таблицы country_successor_links: {e}")

    def get_successor_names(self, country_id):
        """Список названий стран-преемников из таблицы связей."""
        from sqlalchemy import text
        try:
            self._ensure_successor_links_table()
            with self.engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT successor_name FROM country_successor_links "
                    "WHERE extinct_id = :cid ORDER BY id"),
                    {'cid': country_id}).fetchall()
            return [r[0] for r in rows]
        except Exception as e:
            self.logger.error(f"Ошибка чтения связей преемников: {e}")
            return []

    def set_successor_names(self, country_id, names):
        """ЗАМЕНЯЕТ список преемников (по названиям, без создания стран)."""
        from sqlalchemy import text
        try:
            self._ensure_successor_links_table()
            with self.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM country_successor_links WHERE extinct_id = :cid"),
                    {'cid': country_id})
                for n in (names or []):
                    conn.execute(text(
                        "INSERT OR IGNORE INTO country_successor_links "
                        "(extinct_id, successor_name) VALUES (:cid, :n)"),
                        {'cid': country_id, 'n': n})
            return True, f"Установлено преемников: {len(names or [])}"
        except Exception as e:
            self.logger.error(f"Ошибка установки связей преемников: {e}")
            return False, str(e)

    def add_successor_names(self, country_id, names):
        """ДОБАВЛЯЕТ несколько преемников к имеющимся (без создания стран)."""
        from sqlalchemy import text
        try:
            self._ensure_successor_links_table()
            added = 0
            with self.engine.begin() as conn:
                for n in (names or []):
                    res = conn.execute(text(
                        "INSERT OR IGNORE INTO country_successor_links "
                        "(extinct_id, successor_name) VALUES (:cid, :n)"),
                        {'cid': country_id, 'n': n})
                    added += res.rowcount
            return True, f"Добавлено преемников: {added}"
        except Exception as e:
            self.logger.error(f"Ошибка добавления связей преемников: {e}")
            return False, str(e)

    def remove_successor_name(self, country_id, name):
        """Убирает одного преемника из таблицы связей."""
        from sqlalchemy import text
        try:
            self._ensure_successor_links_table()
            with self.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM country_successor_links "
                    "WHERE extinct_id = :cid AND successor_name = :n"),
                    {'cid': country_id, 'n': name})
            return True, "Преемник удалён"
        except Exception as e:
            self.logger.error(f"Ошибка удаления связи преемника: {e}")
            return False, str(e)