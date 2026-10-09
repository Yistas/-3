# -*- coding: utf-8 -*-

"""
Вспомогательные методы для получения значений полей монет
"""

import json


class ValueHelpersMixin:
    """Примесь с методами получения значений монет"""
    
    def get_coin_value(self, coin, key):
        """Получает значение поля монеты по ключу"""
        if coin is None:
            return ""
        
        # Специальные поля
        if key == "select":
            return ""
        elif key == "id":
            return str(coin.id) if coin.id else ""
        elif key == "flag":
            return ""
        
        # Основные поля
        elif key == "country":
            return coin.country.name if coin.country else ""
        elif key == "catalog_number":
            return coin.catalog_number or ""
        elif key == "denomination_value":
            return coin.denomination_value or ""
        elif key == "currency":
            if coin.currency_obj:
                return coin.currency_obj.get_display_text()
            return coin.currency or ""
        elif key == "year":
            return str(coin.year) if coin.year else ""
        elif key == "period":
            if hasattr(coin, 'period_obj') and coin.period_obj:
                return coin.period_obj.get_display_text()
            return ""
        elif key == "century":
            return getattr(coin, 'century', '') or ""
        
        # Монетный двор
        elif key == "mint":
            if coin.mint_obj:
                return coin.mint_obj.get_display_text()
            return coin.mint or ""
        elif key == "mint_mark":
            return coin.mint_mark or ""
        
        # Характеристики
        elif key == "metal":
            if coin.metal_obj:
                return coin.metal_obj.get_display_text()
            return ""
        elif key == "fineness":
            return getattr(coin, 'fineness', '') or ""
        elif key == "weight":
            return f"{coin.weight:.2f}" if coin.weight else ""
        elif key == "diameter":
            return f"{coin.diameter:.2f}" if coin.diameter else ""
        elif key == "thickness":
            return f"{coin.thickness:.2f}" if hasattr(coin, 'thickness') and coin.thickness else ""
        elif key == "shape":
            if hasattr(coin, 'shape_id') and coin.shape_id and hasattr(coin, 'shape_ref') and coin.shape_ref:
                return coin.shape_ref.name
            return getattr(coin, 'shape', '') or ""
        elif key == "mintage":
            return f"{coin.mintage:,}" if coin.mintage else ""
        elif key == "quality":
            return getattr(coin, 'quality', '') or ""
        
        # Гурт
        elif key == "edge":
            if hasattr(coin, 'edge_obj') and coin.edge_obj:
                return coin.edge_obj.name
            return getattr(coin, 'edge_description', '') or ""
        elif key == "edge_description":
            return getattr(coin, 'edge_description', '') or ""
        
        # Состояние
        elif key == "condition":
            if hasattr(coin, 'condition_id') and coin.condition_id and hasattr(coin, 'condition_ref') and coin.condition_ref:
                return coin.condition_ref.name
            return coin.condition or ""
        elif key == "rarity":
            if hasattr(coin, 'rarity_id') and coin.rarity_id and hasattr(coin, 'rarity_ref') and coin.rarity_ref:
                return coin.rarity_ref.name
            return getattr(coin, 'rarity', '') or ""
        elif key == "storage_location":
            if hasattr(coin, 'storage_location_id') and coin.storage_location_id and hasattr(coin, 'storage_location_ref') and coin.storage_location_ref:
                return coin.storage_location_ref.name
            return getattr(coin, 'storage_location', '') or ""
        elif key == "issue_type":
            if hasattr(coin, 'issue_type_id') and coin.issue_type_id and hasattr(coin, 'issue_type_ref') and coin.issue_type_ref:
                return coin.issue_type_ref.name
            return getattr(coin, 'issue_type', '') or ""
        elif key == "avrev":
            if hasattr(coin, 'avrev_id') and coin.avrev_id and hasattr(coin, 'avrev_ref') and coin.avrev_ref:
                return coin.avrev_ref.name
            return getattr(coin, 'avrev', '') or ""
        elif key == "status":
            if hasattr(coin, 'status_id') and coin.status_id and hasattr(coin, 'status_ref') and coin.status_ref:
                return coin.status_ref.name
            if coin.status:
                status_map = {
                    'in_collection': 'В коллекции',
                    'want': 'Хочу',
                    'sold': 'Продано',
                    'lost': 'Утеряна',
                    'for_sale': 'На продажу'
                }
                return status_map.get(coin.status, coin.status)
            return ""
        
        # Покупка
        elif key == "purchase_price":
            return f"{coin.purchase_price:.2f} ₽" if coin.purchase_price else ""
        elif key == "purchase_date":
            if hasattr(coin, 'purchase_date') and coin.purchase_date:
                return coin.purchase_date.strftime("%d.%m.%Y")
            return ""
        elif key == "purchase_place":
            return getattr(coin, 'purchase_place', '') or ""
        elif key == "purchase_where":
            return getattr(coin, 'purchase_where', '') or ""
        elif key == "purchase_info":
            return getattr(coin, 'purchase_info', '') or ""
        elif key == "purchase_country":
            if hasattr(coin, 'purchase_country_obj') and coin.purchase_country_obj:
                return coin.purchase_country_obj.name
            return ""
        elif key == "acquisition_type":
            if hasattr(coin, 'acquisition_type_id') and coin.acquisition_type_id and hasattr(coin, 'acquisition_type_ref') and coin.acquisition_type_ref:
                return coin.acquisition_type_ref.name
            return getattr(coin, 'acquisition_type', '') or ""
        
        # Продажа
        elif key == "sale_price":
            return f"{coin.sale_price:.2f} ₽" if coin.sale_price else ""
        elif key == "sale_date":
            if hasattr(coin, 'sale_date') and coin.sale_date:
                return coin.sale_date.strftime("%d.%m.%Y")
            return ""
        
        # Рыночная цена
        elif key == "market_price":
            return f"{coin.market_price:,.2f} ₽" if coin.market_price else ""
        elif key == "market_price_date":
            if hasattr(coin, 'market_price_date') and coin.market_price_date:
                return coin.market_price_date.strftime("%d.%m.%Y")
            return ""
        
        # Информация
        elif key == "coin_info":
            info = getattr(coin, 'coin_info', '')
            if not info:
                info = getattr(coin, 'notes', '')
            return info or ""
        elif key == "obverse":
            return getattr(coin, 'obverse_description', '') or ""
        elif key == "reverse":
            return getattr(coin, 'reverse_description', '') or ""
        
        # Изображения
        elif key == "obverse_image":
            return getattr(coin, 'obverse_image', '') or ""
        elif key == "reverse_image":
            return getattr(coin, 'reverse_image', '') or ""
        
        # Ссылки
        elif key == "ucoin_url":
            return getattr(coin, 'ucoin_url', '') or ""
        elif key == "meshok_url":
            return getattr(coin, 'meshok_url', '') or ""
        
        # Количество
        elif key == "quantity":
            return str(coin.quantity) if coin.quantity else "1"
        
        # Временные метки
        elif key == "created_at":
            if hasattr(coin, 'created_at') and coin.created_at:
                return coin.created_at.strftime("%d.%m.%Y %H:%M")
            return ""
        elif key == "updated_at":
            if hasattr(coin, 'updated_at') and coin.updated_at:
                return coin.updated_at.strftime("%d.%m.%Y %H:%M")
            return ""
        
        # Заметки
        elif key == "notes":
            return getattr(coin, 'notes', '') or ""
        
        # Пользовательские поля
        elif key.startswith("custom_"):
            field_key = key.replace("custom_", "")
            if hasattr(coin, 'custom_data') and coin.custom_data:
                try:
                    custom_data = json.loads(coin.custom_data)
                    value = custom_data.get(field_key)
                    if value is not None:
                        return str(value)
                except:
                    pass
            return ""
        
        # Если ничего не подошло
        return ""