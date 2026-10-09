# -*- coding: utf-8 -*-

"""
Скрипт для проверки содержимого базы данных
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import Country, Coin

def check_database():
    """Проверяет содержимое базы данных"""
    print("="*60)
    print("ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("="*60)
    
    db_manager = DatabaseManager("coins.db")
    
    # Получаем все страны
    countries = db_manager.get_all_countries()
    print(f"\n📊 СТРАНЫ ({len(countries)}):")
    print("-" * 40)
    for country in countries:
        coin_count = db_manager.session.query(Coin).filter_by(country_id=country.id).count()
        print(f"ID: {country.id:2} | {country.name:30} | Монет: {coin_count}")
    
    # Получаем все монеты
    coins = db_manager.get_all_coins()
    print(f"\n📊 МОНЕТЫ ({len(coins)}):")
    print("-" * 80)
    print(f"{'ID':3} {'Страна':20} {'Номинал':15} {'Год':6} {'Металл':15} {'Сохранность':10}")
    print("-" * 80)
    
    for coin in coins:
        country_name = coin.country.name if coin.country else "Неизвестно"
        print(f"{coin.id:3} {country_name:20} {coin.denomination or '':15} "
              f"{coin.year or '':6} {coin.metal or '':15} {coin.condition or '':10}")
    
    print("="*60)

if __name__ == "__main__":
    check_database()