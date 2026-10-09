# -*- coding: utf-8 -*-

"""Модуль для работы с закупками (ExchangeTab)"""

from .exchange_tab import ExchangeTab
from .silver.silver_sales_tab import SilverSalesTab
from .balance_chart_tab import BalanceChartTab

__all__ = ['ExchangeTab', 'SalesTab', 'BalanceChartTab']