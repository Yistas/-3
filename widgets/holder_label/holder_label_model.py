# -*- coding: utf-8 -*-

"""
Модель данных для печати этикеток холдеров
"""

from dataclasses import dataclass
from typing import List, Optional
from database.models import Coin


@dataclass
class HolderLabelData:
    """Данные для одной этикетки холдера"""
    catalog_number: str          # № (каталожный номер)
    country: str                 # Страна
    denomination: str            # Номинал
    year: str                    # Год
    mint_mark: str               # Знак МД (если есть)
    period: str                  # Период

    def __post_init__(self):
        """Очищает пустые значения"""
        if self.mint_mark == "" or self.mint_mark is None:
            self.mint_mark = ""
        if self.period == "" or self.period is None:
            self.period = "—"

    def get_top_line1(self) -> str:
        """Возвращает первую строку верхней части: Страна"""
        return self.country

    def get_top_line2(self) -> str:
        """Возвращает вторую строку верхней части: Номинал, год, МД"""
        parts = [self.denomination, self.year]
        if self.mint_mark and self.mint_mark.strip():
            parts.append(self.mint_mark)
        filtered = [str(p) for p in parts if p and str(p).strip()]
        return ", ".join(filtered) if filtered else ""

    def get_bottom_line1(self) -> str:
        """Первая строка нижней части: ТОЛЬКО номер.
        Слово 'ПЕРИОД:' рисует принтер отдельным ярлыком справа —
        раньше оно дублировалось (было и здесь, и отдельным ярлыком)."""
        return f"№: {self.catalog_number}"

    def get_bottom_line2(self) -> str:
        """Возвращает вторую строку нижней части: значение периода"""
        return self.period

    @classmethod
    def from_coin(cls, coin: Coin) -> 'HolderLabelData':
        """Создает данные из объекта Coin"""
        return cls(
            catalog_number=coin.catalog_number or "—",
            country=coin.country.name if coin.country else "—",
            denomination=coin.denomination_value or "—",
            year=str(coin.year) if coin.year else "—",
            mint_mark=coin.mint_mark or "",
            period=coin.period_obj.get_display_text() if coin.period_obj else "—"
        )

    @classmethod
    def from_coins(cls, coins: List[Coin]) -> List['HolderLabelData']:
        """Создает список данных из списка монет"""
        return [cls.from_coin(coin) for coin in coins if coin]