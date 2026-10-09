# -*- coding: utf-8 -*-

"""
Скрипт миграции: добавляет индексы в существующую базу данных
Запустите: python database/migrate_add_indexes.py
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_backup(db_path):
    """Создаёт резервную копию базы данных"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"coins_before_index_migration_{timestamp}.db"
    
    shutil.copy2(db_path, backup_path)
    print(f"✅ Резервная копия создана: {backup_path}")
    return backup_path


def get_existing_indexes(cursor):
    """Получает список существующих индексов"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cursor.fetchall()}
    return indexes


def add_indexes(db_path="coins.db"):
    """Добавляет индексы в базу данных"""
    
    # Проверяем существование файла БД
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных не найден: {db_path}")
        return False
    
    print("=" * 60)
    print("МИГРАЦИЯ: ДОБАВЛЕНИЕ ИНДЕКСОВ")
    print("=" * 60)
    print(f"📁 База данных: {db_path}")
    print()
    
    # Создаём резервную копию
    create_backup(db_path)
    print()
    
    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Включаем WAL-режим для безопасности
    cursor.execute("PRAGMA journal_mode=WAL")
    
    # Получаем существующие индексы
    existing_indexes = get_existing_indexes(cursor)
    print(f"📊 Существующих индексов: {len(existing_indexes)}")
    print()
    
    # Список индексов для создания
    indexes_to_create = [
        # Основные связи
        ("idx_coin_country", "coins", "country_id"),
        ("idx_coin_currency", "coins", "currency_id"),
        ("idx_coin_mint", "coins", "mint_id"),
        ("idx_coin_metal", "coins", "metal_id"),
        ("idx_coin_edge", "coins", "edge_id"),
        ("idx_coin_period", "coins", "period_id"),
        
        # Часто используемые поля
        ("idx_coin_catalog", "coins", "catalog_number"),
        ("idx_coin_year", "coins", "year"),
        ("idx_coin_status", "coins", "status"),
        ("idx_coin_selected", "coins", "selected"),
        ("idx_coin_purchase_date", "coins", "purchase_date"),
        
        # Справочники
        ("idx_coin_condition", "coins", "condition_id"),
        ("idx_coin_rarity", "coins", "rarity_id"),
        ("idx_coin_status_ref", "coins", "status_id"),
        
        # Дополнительные индексы для ускорения
        ("idx_coin_country_year", "coins", "country_id, year"),
        ("idx_coin_metal_status", "coins", "metal_id, status"),
        ("idx_coin_country_status", "coins", "country_id, status"),
    ]
    
    created = 0
    skipped = 0
    errors = 0
    
    for index_name, table, columns in indexes_to_create:
        if index_name in existing_indexes:
            print(f"⏭️  Пропущен (уже существует): {index_name}")
            skipped += 1
            continue
        
        try:
            # Создаём индекс
            sql = f"CREATE INDEX {index_name} ON {table} ({columns})"
            cursor.execute(sql)
            conn.commit()
            print(f"✅ Создан индекс: {index_name} ON {table}({columns})")
            created += 1
            
        except sqlite3.OperationalError as e:
            print(f"❌ Ошибка при создании {index_name}: {e}")
            errors += 1
    
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ МИГРАЦИИ:")
    print("=" * 60)
    print(f"  ✅ Создано индексов: {created}")
    print(f"  ⏭️  Пропущено (уже есть): {skipped}")
    print(f"  ❌ Ошибок: {errors}")
    print()
    
    # Анализируем базу для обновления статистики
    print("🔄 Анализ базы данных...")
    cursor.execute("ANALYZE")
    conn.commit()
    print("✅ Анализ завершён")
    print()
    
    # Показываем информацию о размере БД
    db_size = os.path.getsize(db_path)
    print(f"📊 Размер базы данных: {db_size / 1024:.1f} КБ")
    
    # Показываем все индексы
    updated_indexes = get_existing_indexes(cursor)
    print(f"📊 Всего индексов после миграции: {len(updated_indexes)}")
    print()
    
    # Закрываем соединение
    conn.close()
    
    print("=" * 60)
    print("✅ МИГРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
    print("=" * 60)
    print()
    print("📌 Рекомендации:")
    print("  1. Проверьте работу программы")
    print("  2. Если всё работает корректно, можете удалить резервную копию")
    print("  3. Резервная копия находится в папке backups/")
    print()
    
    return True


def verify_migration(db_path="coins.db"):
    """Проверяет, что все нужные индексы созданы"""
    print("=" * 60)
    print("ПРОВЕРКА ИНДЕКСОВ")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Показываем все индексы таблицы coins
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='coins'")
    indexes = cursor.fetchall()
    
    if indexes:
        print(f"\n📊 Индексы таблицы coins ({len(indexes)}):")
        for name, sql in indexes:
            print(f"  • {name}")
    else:
        print("\n⚠️ Индексы не найдены")
    
    # Показываем статистику запросов
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM coins WHERE country_id = 1")
    plan = cursor.fetchall()
    print(f"\n📊 План запроса для фильтрации по стране:")
    for row in plan:
        print(f"  {row}")
    
    conn.close()
    print()
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Миграция: добавление индексов в БД")
    parser.add_argument('--db', default='coins.db', help='Путь к файлу базы данных')
    parser.add_argument('--verify', action='store_true', help='Только проверить индексы')
    
    args = parser.parse_args()
    
    if args.verify:
        verify_migration(args.db)
    else:
        success = add_indexes(args.db)
        if success:
            verify_migration(args.db)
        else:
            print("❌ Миграция не выполнена")
            sys.exit(1)