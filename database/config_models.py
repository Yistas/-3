# -*- coding: utf-8 -*-

"""
Модели для конфигурационной базы данных
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

ConfigBase = declarative_base()


class ConfigKey(ConfigBase):
    """Модель для хранения ключей настроек"""
    __tablename__ = 'config_keys'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, unique=True)  # Ключ настройки
    category = Column(String(100), nullable=True)            # Категория (например, 'window', 'backup', 'gdrive')
    description = Column(Text, nullable=True)               # Описание настройки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связь со значениями
    values = relationship("ConfigValue", back_populates="config_key", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ConfigKey(key='{self.key}')>"


class ConfigValue(ConfigBase):
    """Модель для хранения значений настроек"""
    __tablename__ = 'config_values'

    id = Column(Integer, primary_key=True)
    config_key_id = Column(Integer, ForeignKey('config_keys.id'), nullable=False)
    
    # Значение в разных форматах
    value_text = Column(Text, nullable=True)        # Для строк
    value_int = Column(Integer, nullable=True)      # Для чисел
    value_float = Column(Float, nullable=True)      # Для чисел с плавающей точкой
    value_bool = Column(Boolean, nullable=True)     # Для булевых значений
    value_json = Column(Text, nullable=True)        # Для JSON (сложные структуры)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связь с ключом
    config_key = relationship("ConfigKey", back_populates="values")

    def __repr__(self):
        return f"<ConfigValue(key_id={self.config_key_id})>"

    def get_value(self):
        """Возвращает значение в правильном формате"""
        if self.value_json is not None:
            import json
            try:
                return json.loads(self.value_json)
            except:
                return self.value_json
        if self.value_bool is not None:
            return self.value_bool
        if self.value_float is not None:
            return self.value_float
        if self.value_int is not None:
            return self.value_int
        return self.value_text

    def set_value(self, value):
        """Устанавливает значение в правильный формат"""
        import json
        
        if isinstance(value, dict) or isinstance(value, list):
            self.value_json = json.dumps(value, ensure_ascii=False)
            self.value_text = None
            self.value_int = None
            self.value_float = None
            self.value_bool = None
        elif isinstance(value, bool):
            self.value_bool = value
            self.value_text = None
            self.value_int = None
            self.value_float = None
            self.value_json = None
        elif isinstance(value, int):
            self.value_int = value
            self.value_text = None
            self.value_float = None
            self.value_bool = None
            self.value_json = None
        elif isinstance(value, float):
            self.value_float = value
            self.value_text = None
            self.value_int = None
            self.value_bool = None
            self.value_json = None
        else:
            self.value_text = str(value) if value is not None else None
            self.value_int = None
            self.value_float = None
            self.value_bool = None
            self.value_json = None


class ConfigFile(ConfigBase):
    """Модель для хранения целых файлов настроек (как резерв)"""
    __tablename__ = 'config_files'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False, unique=True)  # Имя файла
    content = Column(Text, nullable=True)                        # Содержимое файла
    file_type = Column(String(50), default='json')               # Тип файла
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<ConfigFile(filename='{self.filename}')>"


def init_config_db(db_path="system_data/data/config.db"):
    """Инициализирует конфигурационную базу данных"""
    engine = create_engine(f'sqlite:///{db_path}')
    ConfigBase.metadata.create_all(engine)
    return engine