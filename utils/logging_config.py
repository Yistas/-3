# -*- coding: utf-8 -*-

"""
Улучшенная настройка логирования для приложения
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

def setup_logging(log_level=logging.DEBUG):
    """
    Настраивает систему логирования
    
    Args:
        log_level: Уровень логирования (по умолчанию DEBUG)
    
    Returns:
        logger: Настроенный логгер
    """
    # Создаем папку для логов, если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Имя файла лога с датой
    log_file = log_dir / f"coin_collector_{datetime.now().strftime('%Y%m%d')}.log"
    error_log = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настройка форматтера
    formatter = logging.Formatter(log_format, date_format)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Файловый обработчик для всех сообщений (с ротацией по дням)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Файловый обработчик только для ошибок
    error_handler = logging.handlers.TimedRotatingFileHandler(
        error_log, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Консольный обработчик (для отладки)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # В консоль только INFO и выше
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Создаем основной логгер приложения
    logger = logging.getLogger('CoinCollector')
    logger.setLevel(log_level)
    
    # Логируем запуск
    logger.info("="*60)
    logger.info("ЗАПУСК ПРИЛОЖЕНИЯ Coin Collector")
    logger.info("="*60)
    logger.info(f"Версия Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    logger.info(f"Уровень логирования: {logging.getLevelName(log_level)}")
    logger.info(f"Файл лога: {log_file}")
    
    return logger

def log_function_call(logger):
    """
    Декоратор для логирования вызовов функций
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"→ Вызов: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"← Завершено: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"✗ Ошибка в {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator

class LoggerMixin:
    """
    Миксин для добавления логирования в классы
    """
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger