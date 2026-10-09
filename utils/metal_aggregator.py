# utils/metal_aggregator.py
# -*- coding: utf-8 -*-

"""
Агрегатор данных по металлам для оптимизации расчетов стоимости коллекции.
Обеспечивает O(металлы + даты) вместо O(металлы × даты × монеты).
"""

import logging
from sqlalchemy import func
from database.models import Coin, Metal


class MetalAggregator:
    """Класс для агрегации весов металлов по типам через SQL GROUP BY."""
    
    @staticmethod
    def get_aggregated_weights(db_manager, country_ids=None, status=None):
        """
        Получает агрегированный вес по металлам через SQL GROUP BY.
        
        Args:
            db_manager: менеджер базы данных
            country_ids: список ID стран для фильтрации (None = все)
            status: статус монет для фильтрации (опционально)
        
        Returns:
            dict: {metal_id: {'weight': float, 'purity': float, 'name': str, 'group': str, 'coin_count': int}}
        """
        logger = logging.getLogger('CoinCollector.MetalAggregator')
        logger.info("Агрегация весов металлов (SQL GROUP BY)...")
        
        try:
            # Базовый запрос с GROUP BY - БЕЗ ФИЛЬТРА ПО СТАТУСУ
            query = db_manager.session.query(
                Coin.metal_id,
                func.sum(Coin.weight).label('total_weight'),
                func.count(Coin.id).label('coin_count'),
                Metal.purity,
                Metal.name,
                Metal.ticker_moex
            ).outerjoin(Metal, Coin.metal_id == Metal.id).filter(
                Coin.metal_id.isnot(None),
                Coin.weight.isnot(None),
                Coin.weight > 0
            )
            
            # Фильтр по статусу (если указан и не 'all')
            if status and status != 'all':
                query = query.filter(Coin.status == status)
            
            # Фильтр по странам (если указаны)
            if country_ids:
                query = query.filter(Coin.country_id.in_(country_ids))
            
            # Группировка по металлу
            query = query.group_by(Coin.metal_id, Metal.purity, Metal.name, Metal.ticker_moex)
            
            results = query.all()
            
            # Если результатов нет и статус не указан, пробуем без фильтра
            if not results and not status:
                logger.info("  Нет данных, пробуем без фильтра...")
                query = db_manager.session.query(
                    Coin.metal_id,
                    func.sum(Coin.weight).label('total_weight'),
                    func.count(Coin.id).label('coin_count'),
                    Metal.purity,
                    Metal.name,
                    Metal.ticker_moex
                ).outerjoin(Metal, Coin.metal_id == Metal.id).filter(
                    Coin.metal_id.isnot(None),
                    Coin.weight.isnot(None),
                    Coin.weight > 0
                )
                
                if country_ids:
                    query = query.filter(Coin.country_id.in_(country_ids))
                
                query = query.group_by(Coin.metal_id, Metal.purity, Metal.name, Metal.ticker_moex)
                results = query.all()
            
            logger.info(f"  Найдено уникальных металлов: {len(results)}")
            
            aggregated = {}
            for row in results:
                if row.metal_id and row.total_weight:
                    # Рассчитываем чистый вес с учетом пробы
                    purity = 1.0
                    if row.purity:
                        try:
                            purity = float(row.purity) / 1000
                        except (ValueError, TypeError):
                            pass
                    
                    # Определяем группу металла
                    group = 'other'
                    if row.name:
                        name_lower = row.name.lower()
                        if any(kw in name_lower for kw in ['золото', 'gold', 'aurum']):
                            group = 'gold'
                        elif any(kw in name_lower for kw in ['серебро', 'silver', 'argentum']):
                            group = 'silver'
                        elif any(kw in name_lower for kw in ['платина', 'platinum']):
                            group = 'platinum'
                        elif any(kw in name_lower for kw in ['медь', 'copper']):
                            group = 'copper'
                    
                    aggregated[row.metal_id] = {
                        'weight': row.total_weight * purity,
                        'purity': row.purity,
                        'name': row.name or f"Металл {row.metal_id}",
                        'group': group,
                        'coin_count': row.coin_count or 0,
                        'ticker_moex': row.ticker_moex
                    }
            
            return aggregated
            
        except Exception as e:
            logger.error(f"Ошибка в агрегаторе: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}