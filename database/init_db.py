# -*- coding: utf-8 -*-

"""
Скрипт для инициализации базы данных и добавления тестовых данных
Запустите этот скрипт один раз для создания базы данных
"""

import os
import sys
# Добавляем путь к корневой папке проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import Base, Country, Coin
from sqlalchemy import create_engine
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Инициализирует базу данных и добавляет тестовые данные"""
    logger.info("="*50)
    logger.info("ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
    logger.info("="*50)
    
    # Создаем менеджер базы данных
    db_path = "coins.db"
    logger.info(f"Создание базы данных: {db_path}")
    
    # Удаляем старую базу если нужно (раскомментируйте если хотите начать с чистого листа)
    # if os.path.exists(db_path):
    #     os.remove(db_path)
    #     logger.info("Старая база данных удалена")
    
    db_manager = DatabaseManager(db_path)
    
    # Проверяем, есть ли уже данные
    countries = db_manager.get_all_countries()
    if len(countries) > 10:  # Больше чем стран по умолчанию
        logger.info(f"База данных уже содержит {len(countries)} стран и {len(db_manager.get_all_coins())} монет")
        print(f"\n✅ База данных уже инициализирована")
        print(f"   Стран: {len(countries)}")
        print(f"   Монет: {len(db_manager.get_all_coins())}")
        return db_manager
    
    logger.info("Добавление тестовых данных...")
    
    # Добавляем тестовые монеты
    test_coins = [
        {
            'country_name': 'Россия',
            'denomination': '10 рублей',
            'period': 'Российская Федерация',
            'year': 2023,
            'metal': 'Сталь с никелевым покрытием',
            'fineness': 'никелированная',
            'weight': 5.63,
            'diameter': 22.0,
            'mint': 'Московский монетный двор',
            'mint_mark': 'ММД',
            'mintage': 5000000,
            'condition': 'UNC',
            'rarity': 'Обычная',
            'status': 'in_collection',
            'quantity': 1,
            'purchase_price': 100,
            'purchase_place': 'Интернет-магазин',
            'acquisition_type': 'Покупка',
            'obverse_description': 'В центре - номинал "10 РУБЛЕЙ", под ним - год "2023"',
            'reverse_description': 'В центре - герб России, надпись "РОССИЙСКАЯ ФЕДЕРАЦИЯ"',
            'edge_description': 'Рубчатый с надписью'
        },
        {
            'country_name': 'СССР',
            'denomination': '1 рубль',
            'period': 'СССР',
            'year': 1985,
            'metal': 'Медно-никелевый сплав',
            'fineness': 'нейзильбер',
            'weight': 7.5,
            'diameter': 27.0,
            'mint': 'Ленинградский монетный двор',
            'mint_mark': 'ЛМД',
            'mintage': 1000000,
            'condition': 'XF',
            'rarity': 'Обычная',
            'status': 'in_collection',
            'quantity': 1,
            'purchase_price': 50,
            'purchase_place': 'Барахолка',
            'acquisition_type': 'Покупка',
            'obverse_description': 'Герб СССР, 15 витков ленты',
            'reverse_description': 'Номинал "1 РУБЛЬ", год "1985"',
            'edge_description': 'Рубчатый'
        },
        {
            'country_name': 'США',
            'denomination': '1 доллар',
            'period': 'США',
            'year': 2022,
            'metal': 'Медь с латунным покрытием',
            'fineness': 'латунь',
            'weight': 8.1,
            'diameter': 26.5,
            'mint': 'Денвер',
            'mint_mark': 'D',
            'mintage': 2000000,
            'condition': 'UNC',
            'rarity': 'Обычная',
            'status': 'in_collection',
            'quantity': 1,
            'purchase_price': 75,
            'purchase_place': 'Поездка в США',
            'acquisition_type': 'Покупка',
            'obverse_description': 'Портрет Джорджа Вашингтона',
            'reverse_description': 'Орел с расправленными крыльями',
            'edge_description': 'Гладкий'
        },
        {
            'country_name': 'Германия',
            'denomination': '2 евро',
            'period': 'Еврозона',
            'year': 2020,
            'metal': 'Биметалл',
            'fineness': 'медно-никель/латунь',
            'weight': 8.5,
            'diameter': 25.75,
            'mint': 'Монетный двор Мюнхена',
            'mint_mark': 'D',
            'mintage': 3000000,
            'condition': 'UNC',
            'rarity': 'Обычная',
            'status': 'in_collection',
            'quantity': 1,
            'purchase_price': 150,
            'purchase_place': 'Поездка в Германию',
            'acquisition_type': 'Покупка',
            'obverse_description': 'Карта Европы на фоне звезд',
            'reverse_description': 'Номинал "2 EURO"',
            'edge_description': 'Рубчатый с надписью'
        },
        {
            'country_name': 'Великобритания',
            'denomination': '1 фунт',
            'period': 'Великобритания',
            'year': 2021,
            'metal': 'Биметалл',
            'fineness': 'никель-латунь',
            'weight': 8.75,
            'diameter': 23.43,
            'mint': 'Королевский монетный двор',
            'mint_mark': 'RM',
            'mintage': 1500000,
            'condition': 'UNC',
            'rarity': 'Обычная',
            'status': 'in_collection',
            'quantity': 1,
            'purchase_price': 120,
            'purchase_place': 'Поездка в Англию',
            'acquisition_type': 'Покупка',
            'obverse_description': 'Портрет Королевы Елизаветы II',
            'reverse_description': 'Символы Великобритании',
            'edge_description': 'Рубчатый с надписью'
        }
    ]
    
    try:
        added_count = 0
        for coin_data in test_coins:
            # Получаем или создаем страну
            country_name = coin_data.pop('country_name')
            country = db_manager.get_or_create_country(country_name)
            if country:
                coin_data['country_id'] = country.id
                coin_id = db_manager.add_coin(coin_data)
                logger.info(f"Добавлена монета: {country_name} {coin_data['denomination']} {coin_data['year']} (ID: {coin_id})")
                added_count += 1
        
        logger.info(f"✅ Добавлено {added_count} тестовых монет")
        
        # Показываем статистику
        countries = db_manager.get_all_countries()
        coins = db_manager.get_all_coins()
        
        print(f"\n{'='*50}")
        print(f"✅ БАЗА ДАННЫХ УСПЕШНО ИНИЦИАЛИЗИРОВАНА!")
        print(f"{'='*50}")
        print(f"\n📊 Статистика:")
        print(f"   - Стран в базе: {len(countries)}")
        print(f"   - Монет в базе: {len(coins)}")
        print(f"   - Файл базы: {db_path}")
        
        print(f"\n📋 Список стран:")
        for country in countries[:10]:  # Показываем первые 10
            coin_count = db_manager.session.query(Coin).filter_by(country_id=country.id).count()
            print(f"   • {country.name}: {coin_count} монет")
        
        print(f"\n📋 Последние добавленные монеты:")
        for coin in coins[-5:]:  # Показываем последние 5
            country_name = coin.country.name if coin.country else "Неизвестно"
            print(f"   • {country_name}: {coin.denomination} {coin.year} ({coin.condition})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении тестовых данных: {e}")
        import traceback
        traceback.print_exc()
    
    return db_manager

if __name__ == "__main__":
    init_database()