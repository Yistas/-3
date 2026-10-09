# -*- coding: utf-8 -*-

"""
Диагностика базы данных
"""

import os
import sqlite3
import sys

def debug_database():
    print("="*60)
    print("ДИАГНОСТИКА БАЗЫ ДАННЫХ")
    print("="*60)
    
    db_path = "coins.db"
    
    # Проверяем существует ли файл
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных {db_path} не найден!")
        return
    
    print(f"✅ Файл базы данных найден: {db_path}")
    print(f"   Размер: {os.path.getsize(db_path)} байт")
    
    # Подключаемся напрямую через SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Получаем список всех таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\n📊 Таблицы в базе данных: {[t[0] for t in tables]}")
    
    # Проверяем таблицу countries
    if ('countries',) in tables:
        cursor.execute("SELECT COUNT(*) FROM countries")
        countries_count = cursor.fetchone()[0]
        print(f"\n📊 Таблица 'countries': {countries_count} записей")
        
        if countries_count > 0:
            cursor.execute("SELECT id, name, code FROM countries LIMIT 5")
            print("\nСтраны (первые 5):")
            for row in cursor.fetchall():
                print(f"   ID: {row[0]}, Название: {row[1]}, Код: {row[2]}")
    else:
        print("❌ Таблица 'countries' не найдена!")
    
    # Проверяем таблицу coins
    if ('coins',) in tables:
        cursor.execute("SELECT COUNT(*) FROM coins")
        coins_count = cursor.fetchone()[0]
        print(f"\n📊 Таблица 'coins': {coins_count} записей")
        
        if coins_count > 0:
            cursor.execute("""
                SELECT c.id, c.denomination, c.year, c.country_id, c.condition 
                FROM coins c LIMIT 5
            """)
            print("\nМонеты (первые 5):")
            for row in cursor.fetchall():
                print(f"   ID: {row[0]}, Номинал: {row[1]}, Год: {row[2]}, "
                      f"Country ID: {row[3]}, Сохранность: {row[4]}")
            
            # Проверяем связи с таблицей countries
            cursor.execute("""
                SELECT COUNT(*) FROM coins 
                WHERE country_id IS NOT NULL 
                AND country_id NOT IN (SELECT id FROM countries)
            """)
            invalid_refs = cursor.fetchone()[0]
            if invalid_refs > 0:
                print(f"⚠️ Найдено {invalid_refs} монет с несуществующими country_id")
    else:
        print("❌ Таблица 'coins' не найдена!")
    
    conn.close()
    
    print("\n" + "="*60)
    print("Что делать дальше:")
    print("1. Если таблицы пустые - запустите: python database/init_db.py")
    print("2. Если таблицы есть, но монет нет - проверьте init_db.py")
    print("3. Запустите программу: python main.py")

if __name__ == "__main__":
    debug_database()