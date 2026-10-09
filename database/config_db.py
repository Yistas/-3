# -*- coding: utf-8 -*-

"""
Менеджер конфигурационной базы данных
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.config_models import ConfigKey, ConfigValue, ConfigFile, init_config_db
from utils.paths import paths


class ConfigDB:
    """Класс для работы с конфигурационной БД"""
    
    _instance = None
    
    # Максимальное количество записей истории для одного ключа
    MAX_HISTORY_PER_KEY = 5
    
    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path=None):
        if self._initialized:
            return
        
        self.logger = logging.getLogger('CoinCollector.ConfigDB')
        
        # ===== ИСПРАВЛЕНО: используем правильный путь через paths =====
        if db_path is None:
            # Используем папку data/ через paths
            data_dir = paths.get_data_dir()
            db_path = str(data_dir / "config.db")
        else:
            # Если передан относительный путь, помещаем в data/
            if not os.path.isabs(db_path) and not os.path.dirname(db_path):
                data_dir = paths.get_data_dir()
                data_dir.mkdir(parents=True, exist_ok=True)
                db_path = str(data_dir / db_path)
        
        self.db_path = db_path
        
        # Создаём папку если её нет
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Инициализируем БД
        self.engine = init_config_db(db_path)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        
        self._initialized = True
        self.logger.info(f"Конфигурационная БД инициализирована: {db_path}")
    
    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПУТЯМИ =====
    
    def _normalize_path_for_db(self, path):
        """
        Преобразует абсолютный путь в относительный для хранения в БД.
        """
        if not path:
            return path
        
        path_obj = Path(path)
        
        # Если путь уже относительный, возвращаем как есть
        if not path_obj.is_absolute():
            return str(path_obj)
        
        try:
            # Пытаемся сделать путь относительным от корня программы
            root_dir = paths.get_root_dir()
            rel_path = path_obj.relative_to(root_dir)
            return str(rel_path)
        except ValueError:
            # Если не удалось сделать относительным, пробуем от system_data
            try:
                system_data = paths.get_system_data_dir()
                rel_path = path_obj.relative_to(system_data)
                return f"system_data/{rel_path}"
            except ValueError:
                # Если и это не удалось, возвращаем как есть
                return str(path_obj)
    
    def _denormalize_path_from_db(self, path):
        """
        Преобразует относительный путь из БД в абсолютный.
        """
        if not path:
            return path
        
        path_obj = Path(path)
        
        # Если путь уже абсолютный, возвращаем как есть
        if path_obj.is_absolute():
            return str(path_obj)
        
        # Проверяем, начинается ли путь с system_data/
        path_str = str(path_obj).replace('\\', '/')
        if path_str.startswith('system_data/'):
            # Путь относительно system_data
            rel_part = path_str[12:]  # убираем 'system_data/'
            return str(paths.get_system_data_dir() / rel_part)
        
        # Путь относительно корня программы
        return str(paths.get_root_dir() / path_obj)
    
    def _is_path_string(self, value):
        """Проверяет, является ли строка путём."""
        if not isinstance(value, str):
            return False
        if len(value) < 3:
            return False
        # Проверяем наличие разделителей пути
        if '/' not in value and '\\' not in value:
            return False
        # Проверяем, не является ли это обычным текстом
        common_words = ['data', 'settings', 'config', 'backup', 'window', 'color']
        if any(word in value.lower() for word in common_words):
            return True
        return False
    
    def _normalize_paths_in_dict(self, data):
        """Рекурсивно нормализует пути в словаре."""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._normalize_paths_in_dict(value)
            elif isinstance(value, list):
                result[key] = self._normalize_paths_in_list(value)
            elif isinstance(value, str) and self._is_path_string(value):
                result[key] = self._normalize_path_for_db(value)
            else:
                result[key] = value
        return result
    
    def _normalize_paths_in_list(self, data):
        """Рекурсивно нормализует пути в списке."""
        if not isinstance(data, list):
            return data
        
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self._normalize_paths_in_dict(item))
            elif isinstance(item, list):
                result.append(self._normalize_paths_in_list(item))
            elif isinstance(item, str) and self._is_path_string(item):
                result.append(self._normalize_path_for_db(item))
            else:
                result.append(item)
        return result
    
    def _denormalize_paths_in_dict(self, data):
        """Рекурсивно денормализует пути в словаре."""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._denormalize_paths_in_dict(value)
            elif isinstance(value, list):
                result[key] = self._denormalize_paths_in_list(value)
            elif isinstance(value, str) and self._is_path_string(value):
                result[key] = self._denormalize_path_from_db(value)
            else:
                result[key] = value
        return result
    
    def _denormalize_paths_in_list(self, data):
        """Рекурсивно денормализует пути в списке."""
        if not isinstance(data, list):
            return data
        
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self._denormalize_paths_in_dict(item))
            elif isinstance(item, list):
                result.append(self._denormalize_paths_in_list(item))
            elif isinstance(item, str) and self._is_path_string(item):
                result.append(self._denormalize_path_from_db(item))
            else:
                result.append(item)
        return result
    
    # ===== ОСНОВНЫЕ МЕТОДЫ =====
    
    def get(self, key, default=None):
        """Получает значение настройки по ключу (последнее значение)"""
        try:
            config_key = self.session.query(ConfigKey).filter_by(key=key).first()
            if not config_key:
                return default
            
            # Берём последнее значение
            value = self.session.query(ConfigValue).filter_by(
                config_key_id=config_key.id
            ).order_by(ConfigValue.created_at.desc()).first()
            
            if not value:
                return default
            
            result = value.get_value()
            
            # Если значение содержит пути, денормализуем их
            if isinstance(result, dict):
                result = self._denormalize_paths_in_dict(result)
            elif isinstance(result, list):
                result = self._denormalize_paths_in_list(result)
            elif isinstance(result, str) and self._is_path_string(result):
                result = self._denormalize_path_from_db(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения настройки {key}: {e}")
            return default
    
    def get_history(self, key, limit=None):
        """
        Возвращает историю изменений для ключа.
        
        Args:
            key: ключ настройки
            limit: максимальное количество записей (по умолчанию None - все)
        
        Returns:
            list: список словарей с полями id, value, created_at
        """
        try:
            config_key = self.session.query(ConfigKey).filter_by(key=key).first()
            if not config_key:
                return []
            
            query = self.session.query(ConfigValue).filter_by(
                config_key_id=config_key.id
            ).order_by(ConfigValue.created_at.desc())
            
            if limit is not None:
                query = query.limit(limit)
            
            values = query.all()
            
            result = []
            for val in values:
                result.append({
                    'id': val.id,
                    'value': val.get_value(),
                    'created_at': val.created_at.isoformat() if val.created_at else None
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения истории для {key}: {e}")
            return []
    
    def set(self, key, value, category=None, description=None):
        """
        Устанавливает значение настройки.
        Сохраняет историю изменений, оставляя не более MAX_HISTORY_PER_KEY записей.
        """
        try:
            # Нормализуем пути перед сохранением
            if isinstance(value, dict):
                value = self._normalize_paths_in_dict(value)
            elif isinstance(value, list):
                value = self._normalize_paths_in_list(value)
            elif isinstance(value, str) and self._is_path_string(value):
                value = self._normalize_path_for_db(value)
            
            # Ищем или создаём ключ
            config_key = self.session.query(ConfigKey).filter_by(key=key).first()
            if not config_key:
                config_key = ConfigKey(
                    key=key,
                    category=category,
                    description=description
                )
                self.session.add(config_key)
                self.session.flush()
            else:
                if category is not None:
                    config_key.category = category
                if description is not None:
                    config_key.description = description
            
            # Создаём новое значение
            config_value = ConfigValue(config_key_id=config_key.id)
            config_value.set_value(value)
            
            self.session.add(config_value)
            self.session.commit()
            
            # === ОГРАНИЧИВАЕМ ИСТОРИЮ ===
            self._trim_history(config_key.id)
            
            self.logger.debug(f"Настройка {key} сохранена")
            return True
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка сохранения настройки {key}: {e}")
            return False
    
    def _trim_history(self, config_key_id):
        """
        Оставляет только последние MAX_HISTORY_PER_KEY записей для ключа.
        """
        try:
            # Считаем количество записей для этого ключа
            count = self.session.query(ConfigValue).filter_by(
                config_key_id=config_key_id
            ).count()
            
            if count <= self.MAX_HISTORY_PER_KEY:
                return
            
            # Находим ID записей, которые нужно удалить (старые)
            ids_to_delete = self.session.query(ConfigValue.id).filter_by(
                config_key_id=config_key_id
            ).order_by(
                ConfigValue.created_at.desc()
            ).offset(
                self.MAX_HISTORY_PER_KEY
            ).all()
            
            if ids_to_delete:
                ids_list = [id_[0] for id_ in ids_to_delete]
                self.session.query(ConfigValue).filter(
                    ConfigValue.id.in_(ids_list)
                ).delete(synchronize_session=False)
                self.session.commit()
                
                self.logger.debug(
                    f"Удалено {len(ids_list)} старых записей истории для ключа {config_key_id}"
                )
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка обрезки истории: {e}")
    
    def get_history_for_key(self, key, limit=5):
        """
        Возвращает историю изменений для ключа с ограничением по умолчанию 5.
        
        Args:
            key: ключ настройки
            limit: максимальное количество записей (по умолчанию 5)
        
        Returns:
            list: список словарей с полями id, value, created_at
        """
        return self.get_history(key, limit)
    
    def delete(self, key):
        """Удаляет настройку и всю её историю"""
        try:
            config_key = self.session.query(ConfigKey).filter_by(key=key).first()
            if config_key:
                self.session.delete(config_key)
                self.session.commit()
                self.logger.debug(f"Настройка {key} удалена")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка удаления настройки {key}: {e}")
            return False
    
    def get_all(self, category=None):
        """Возвращает все настройки (опционально по категории) с последними значениями"""
        try:
            query = self.session.query(ConfigKey)
            if category:
                query = query.filter_by(category=category)
            
            result = {}
            for config_key in query.all():
                value = self.session.query(ConfigValue).filter_by(
                    config_key_id=config_key.id
                ).order_by(ConfigValue.created_at.desc()).first()
                
                if value:
                    val = value.get_value()
                    # Денормализуем пути
                    if isinstance(val, dict):
                        val = self._denormalize_paths_in_dict(val)
                    elif isinstance(val, list):
                        val = self._denormalize_paths_in_list(val)
                    elif isinstance(val, str) and self._is_path_string(val):
                        val = self._denormalize_path_from_db(val)
                    result[config_key.key] = val
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения настроек: {e}")
            return {}
    
    def get_category(self, category):
        """Возвращает все настройки из категории"""
        return self.get_all(category)
    
    def save_file(self, filename, content, file_type='json'):
        """Сохраняет содержимое файла в БД"""
        try:
            config_file = self.session.query(ConfigFile).filter_by(filename=filename).first()
            if not config_file:
                config_file = ConfigFile(filename=filename)
            
            config_file.content = content
            config_file.file_type = file_type
            config_file.updated_at = datetime.now()
            
            self.session.add(config_file)
            self.session.commit()
            
            self.logger.debug(f"Файл {filename} сохранён в БД")
            return True
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка сохранения файла {filename}: {e}")
            return False
    
    def load_file(self, filename):
        """Загружает содержимое файла из БД"""
        try:
            config_file = self.session.query(ConfigFile).filter_by(filename=filename).first()
            if config_file:
                return config_file.content
            return None
        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла {filename}: {e}")
            return None
    
    def delete_file(self, filename):
        """Удаляет файл из БД"""
        try:
            config_file = self.session.query(ConfigFile).filter_by(filename=filename).first()
            if config_file:
                self.session.delete(config_file)
                self.session.commit()
                self.logger.debug(f"Файл {filename} удалён из БД")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка удаления файла {filename}: {e}")
            return False
    
    def import_from_json_files(self, json_dir=None):
        """Импортирует все JSON файлы из папки в БД"""
        if json_dir is None:
            json_dir = paths.get_data_dir()
        else:
            json_dir = Path(json_dir)
        
        if not json_dir.exists():
            return 0
        
        imported = 0
        for file_path in json_dir.glob("*.json"):
            # Пропускаем файлы, которые не нужно импортировать
            if file_path.name in ['credentials.json', 'service_account.json', 'gdrive_token.pickle']:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if self.save_file(file_path.name, content):
                    imported += 1
                    
            except Exception as e:
                self.logger.error(f"Ошибка импорта {file_path.name}: {e}")
        
        return imported
    
    def export_to_json_files(self, json_dir=None):
        """Экспортирует все файлы из БД в папку"""
        if json_dir is None:
            json_dir = paths.get_data_dir()
        else:
            json_dir = Path(json_dir)
        
        json_dir.mkdir(parents=True, exist_ok=True)
        
        exported = 0
        config_files = self.session.query(ConfigFile).all()
        
        for config_file in config_files:
            try:
                file_path = json_dir / config_file.filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(config_file.content)
                exported += 1
            except Exception as e:
                self.logger.error(f"Ошибка экспорта {config_file.filename}: {e}")
        
        return exported
    
    def close(self):
        """Закрывает соединение с БД"""
        try:
            self.session.close()
            self.engine.dispose()
            self.logger.info("Соединение с конфигурационной БД закрыто")
        except Exception as e:
            self.logger.error(f"Ошибка закрытия БД: {e}")


# Глобальный экземпляр
_config_db = None


def get_config_db(db_path=None):
    """Возвращает глобальный экземпляр ConfigDB"""
    global _config_db
    if _config_db is None:
        _config_db = ConfigDB(db_path)
    return _config_db