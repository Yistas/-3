# -*- coding: utf-8 -*-

"""
Кэш для справочных данных (валюты, страны, металлы и т.д.)
"""

import time
from typing import Any, Callable, Dict, Optional


class ReferenceCache:
    """
    Кэш справочников в памяти с TTL.
    
    Использование:
        currencies = ReferenceCache.get('currencies', db_manager.get_all_currencies)
    
    Для сброса:
        ReferenceCache.invalidate('currencies')
    """
    
    _cache: Dict[str, Any] = {}
    _timestamps: Dict[str, float] = {}
    TTL: int = 300  # 5 минут
    
    @classmethod
    def get(cls, key: str, loader: Callable, ttl: Optional[int] = None) -> Any:
        """
        Возвращает данные из кэша или загружает через loader.
        
        Args:
            key: Ключ кэша (например, 'currencies')
            loader: Функция для загрузки данных
            ttl: Время жизни в секундах (по умолчанию 300)
        
        Returns:
            Загруженные данные
        """
        ttl = ttl or cls.TTL
        now = time.time()
        
        if key in cls._cache and (now - cls._timestamps.get(key, 0)) < ttl:
            return cls._cache[key]
        
        data = loader()
        cls._cache[key] = data
        cls._timestamps[key] = now
        return data
    
    @classmethod
    def invalidate(cls, key: Optional[str] = None) -> None:
        """Инвалидирует кэш для ключа или полностью"""
        if key:
            cls._cache.pop(key, None)
            cls._timestamps.pop(key, None)
        else:
            cls._cache.clear()
            cls._timestamps.clear()
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        return {
            'size': len(cls._cache),
            'keys': list(cls._cache.keys()),
            'ttl': cls.TTL,
        }