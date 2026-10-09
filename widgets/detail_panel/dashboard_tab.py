# ===== gui/widgets/detail_panel/dashboard_tab.py =====
# -*- coding: utf-8 -*-
"""
Вкладка с дашбордом для главной страницы коллекции
"""
import logging
from datetime import datetime
from collections import defaultdict
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGridLayout, QFrame, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from database.models import Coin, Country, Metal, MetalPriceHistory, MarketPriceHistory


class DashboardTab(QWidget):
    """Вкладка с дашбордом для главной страницы коллекции"""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.DashboardTab')
        self.init_ui()
        self.load_data()
        
    def _get_theme(self):
        """Возвращает словарь текущей темы (поднимаясь к главному окну)"""
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                return tm.current_theme
            w = w.parent()
        return {}

    def init_ui(self):
        """Инициализация интерфейса (тёмная тема)"""
        t = self._get_theme()
        base = t.get('base', '#1a1a2e')
        border = t.get('border', '#2a2a4a')
        muted = t.get('tab_text', '#8888aa')
        accent = t.get('accent', '#6c63ff')

        layout = QVBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(4)
        self.setLayout(layout)

        # Заголовок — тёмный, не слепит
        title = QLabel("📊 Панель управления коллекцией")
        title.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14px;
            padding: 6px;
            background-color: {t.get('surface', '#16213e')};
            color: {accent};
            border: 1px solid {border};
            border-radius: 6px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Строка с общей информацией
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {base};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 5px;
            }}
        """)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(5, 3, 5, 3)
        info_layout.setSpacing(3)
        info_frame.setLayout(info_layout)

        self.total_coins_label = QLabel("🪙 Всего монет: 0")
        self.total_coins_label.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {accent};")
        self.total_coins_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.total_coins_label)

        self.total_value_label = QLabel("💰 Рыночная стоимость: 0 ₽")
        self.total_value_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #28a745;")
        self.total_value_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.total_value_label)

        layout.addWidget(info_frame)

        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator1)

        # Агрегаты по металлам
        metals_title = QLabel("💰 Стоимость по металлам")
        metals_title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        layout.addWidget(metals_title)

        metals_frame = QFrame()
        metals_frame.setFrameShape(QFrame.NoFrame)
        metals_frame.setStyleSheet("QFrame { background-color: transparent; border: none; padding: 2px; }")
        metals_layout = QVBoxLayout()
        metals_layout.setContentsMargins(0, 2, 0, 2)
        metals_layout.setSpacing(2)
        metals_frame.setLayout(metals_layout)

        # Золото
        gold_widget = QWidget()
        gold_grid = QGridLayout()
        gold_grid.setContentsMargins(0, 0, 0, 0)
        gold_grid.setHorizontalSpacing(8)
        gold_grid.setVerticalSpacing(0)
        gold_widget.setLayout(gold_grid)
        gold_label = QLabel("🥇 Золото:")
        gold_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #FFD700;")
        gold_label.setFixedWidth(70)
        gold_grid.addWidget(gold_label, 0, 0)
        self.gold_count_label = QLabel("0")
        self.gold_count_label.setStyleSheet(f"color: {muted}; font-size: 11px;")
        self.gold_count_label.setFixedWidth(35)
        self.gold_count_label.setAlignment(Qt.AlignRight)
        gold_grid.addWidget(self.gold_count_label, 0, 1)
        gold_count_unit = QLabel("монет")
        gold_count_unit.setStyleSheet(f"color: {muted}; font-size: 10px;")
        gold_count_unit.setFixedWidth(32)
        gold_grid.addWidget(gold_count_unit, 0, 2)
        self.gold_value_label = QLabel("0 ₽")
        self.gold_value_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #28a745;")
        self.gold_value_label.setFixedWidth(80)
        self.gold_value_label.setAlignment(Qt.AlignRight)
        gold_grid.addWidget(self.gold_value_label, 0, 3)
        self.gold_weight_label = QLabel("0.00 г")
        self.gold_weight_label.setStyleSheet("color: #9b59b6; font-size: 11px;")
        self.gold_weight_label.setFixedWidth(55)
        self.gold_weight_label.setAlignment(Qt.AlignRight)
        gold_grid.addWidget(self.gold_weight_label, 0, 4)
        metals_layout.addWidget(gold_widget)

        # Серебро
        silver_widget = QWidget()
        silver_grid = QGridLayout()
        silver_grid.setContentsMargins(0, 0, 0, 0)
        silver_grid.setHorizontalSpacing(8)
        silver_grid.setVerticalSpacing(0)
        silver_widget.setLayout(silver_grid)
        silver_label = QLabel("🥈 Серебро:")
        silver_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #C0C0C0;")
        silver_label.setFixedWidth(70)
        silver_grid.addWidget(silver_label, 0, 0)
        self.silver_count_label = QLabel("0")
        self.silver_count_label.setStyleSheet(f"color: {muted}; font-size: 11px;")
        self.silver_count_label.setFixedWidth(35)
        self.silver_count_label.setAlignment(Qt.AlignRight)
        silver_grid.addWidget(self.silver_count_label, 0, 1)
        silver_count_unit = QLabel("монет")
        silver_count_unit.setStyleSheet(f"color: {muted}; font-size: 10px;")
        silver_count_unit.setFixedWidth(32)
        silver_grid.addWidget(silver_count_unit, 0, 2)
        self.silver_value_label = QLabel("0 ₽")
        self.silver_value_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #28a745;")
        self.silver_value_label.setFixedWidth(80)
        self.silver_value_label.setAlignment(Qt.AlignRight)
        silver_grid.addWidget(self.silver_value_label, 0, 3)
        self.silver_weight_label = QLabel("0.00 г")
        self.silver_weight_label.setStyleSheet("color: #9b59b6; font-size: 11px;")
        self.silver_weight_label.setFixedWidth(55)
        self.silver_weight_label.setAlignment(Qt.AlignRight)
        silver_grid.addWidget(self.silver_weight_label, 0, 4)
        metals_layout.addWidget(silver_widget)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        metals_layout.addWidget(line)

        # Итого
        total_widget = QWidget()
        total_grid = QGridLayout()
        total_grid.setContentsMargins(0, 0, 0, 0)
        total_grid.setHorizontalSpacing(8)
        total_grid.setVerticalSpacing(0)
        total_widget.setLayout(total_grid)
        total_label = QLabel("💰 Итого:")
        total_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        total_label.setFixedWidth(70)
        total_grid.addWidget(total_label, 0, 0)
        total_grid.addWidget(QLabel(""), 0, 1)
        total_grid.addWidget(QLabel(""), 0, 2)
        self.total_metals_value_label = QLabel("0 ₽")
        self.total_metals_value_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #28a745;")
        self.total_metals_value_label.setFixedWidth(80)
        self.total_metals_value_label.setAlignment(Qt.AlignRight)
        total_grid.addWidget(self.total_metals_value_label, 0, 3)
        self.total_metals_weight_label = QLabel("0.00 г")
        self.total_metals_weight_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #9b59b6;")
        self.total_metals_weight_label.setFixedWidth(75)
        self.total_metals_weight_label.setAlignment(Qt.AlignRight)
        total_grid.addWidget(self.total_metals_weight_label, 0, 4)
        metals_layout.addWidget(total_widget)
        layout.addWidget(metals_frame)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)

        # Топ-5 стран
        top_label = QLabel("📊 Топ-5 стран по количеству монет")
        top_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        layout.addWidget(top_label)
        self.top_countries_container = QWidget()
        self.top_countries_layout = QVBoxLayout()
        self.top_countries_layout.setContentsMargins(0, 0, 0, 0)
        self.top_countries_layout.setSpacing(3)
        self.top_countries_container.setLayout(self.top_countries_layout)
        layout.addWidget(self.top_countries_container)

        separator3 = QFrame()
        separator3.setFrameShape(QFrame.HLine)
        separator3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator3)

        # Распределение по векам
        centuries_label = QLabel("📅 Распределение по векам")
        centuries_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        layout.addWidget(centuries_label)
        self.centuries_container = QWidget()
        self.centuries_layout = QVBoxLayout()
        self.centuries_layout.setContentsMargins(0, 0, 0, 0)
        self.centuries_layout.setSpacing(3)
        self.centuries_container.setLayout(self.centuries_layout)
        layout.addWidget(self.centuries_container)

        separator4 = QFrame()
        separator4.setFrameShape(QFrame.HLine)
        separator4.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator4)

        # Распределение по континентам
        continents_label = QLabel("🌍 Распределение по континентам")
        continents_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        layout.addWidget(continents_label)
        self.continents_container = QWidget()
        self.continents_layout = QVBoxLayout()
        self.continents_layout.setContentsMargins(0, 0, 0, 0)
        self.continents_layout.setSpacing(3)
        self.continents_container.setLayout(self.continents_layout)
        layout.addWidget(self.continents_container)

        layout.addStretch()

    def _create_bar_chart_row(self, name, count, total, color, max_width=140):
        """Создает строку с гистограммой (тёмная тема)"""
        t = self._get_theme()
        row = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row.setLayout(row_layout)

        # Название
        label = QLabel(name)
        label.setFixedWidth(90)
        label.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
        row_layout.addWidget(label)

        # Бар (фон контейнера тёмный, чтобы полоса была видна)
        percent = (count / total * 100) if total > 0 else 0
        bar_width = int(percent * max_width / 100)
        bar_container = QWidget()
        bar_container.setStyleSheet(f"""
            background-color: {t.get('surface_active', '#253352')};
            border-radius: 2px;
        """)
        bar_container.setFixedHeight(16)
        bar_layout = QHBoxLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_container.setLayout(bar_layout)

        bar = QWidget()
        bar.setStyleSheet(f"""
            background-color: {color};
            border-radius: 2px;
        """)
        bar.setFixedWidth(max(2, bar_width))
        bar.setFixedHeight(14)
        bar_layout.addWidget(bar)
        bar_layout.addStretch()
        row_layout.addWidget(bar_container, 1)

        # Процент и количество
        info_label = QLabel(f"{count} ({percent:.1f}%)")
        info_label.setFixedWidth(65)
        info_label.setStyleSheet(f"font-size: 10px; color: {t.get('tab_text', '#8888aa')};")
        info_label.setAlignment(Qt.AlignRight)
        row_layout.addWidget(info_label)

        return row

    def load_data(self):
        """Загружает все данные для дашборда"""
        # Проверяем флаг подавления сообщений (при копировании монеты)
        try:
            main_window = None
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            if main_window and getattr(main_window, '_suppress_messages', False):
                return
        except:
            pass

        try:
            # Получаем все монеты (БЕЗ фильтра по статусу)
            all_coins = self.db_manager.session.query(Coin).filter(
                Coin.weight.isnot(None),
                Coin.weight > 0,
                Coin.metal_id.isnot(None),
                Coin.purchase_date.isnot(None)
            ).all()
            total_coins = len(all_coins)

            # Получаем последнюю дату с ценами металлов для расчета стоимости металлов
            last_price_date = self.db_manager.session.query(
                MetalPriceHistory.date
            ).order_by(MetalPriceHistory.date.desc()).first()

            # Получаем РЫНОЧНУЮ СТОИМОСТЬ (сумму market_price всех монет)
            market_value = 0
            all_coins_for_market = self.db_manager.session.query(Coin).all()
            for coin in all_coins_for_market:
                if coin.market_price:
                    market_value += coin.market_price

            total_metal_value = 0
            gold_count = 0
            silver_count = 0
            gold_value = 0
            silver_value = 0
            gold_weight = 0.0
            silver_weight = 0.0

            if last_price_date:
                target_date = last_price_date[0]
                for coin in all_coins:
                    metal = self.db_manager.session.query(Metal).get(coin.metal_id)
                    if not metal:
                        continue
                    price_entry = self.db_manager.session.query(MetalPriceHistory).filter_by(
                        metal_id=metal.id,
                        date=target_date
                    ).first()
                    if not price_entry:
                        continue
                    metal_purity = metal.get_purity_decimal()
                    metal_weight = coin.weight * metal_purity
                    coin_value = metal_weight * price_entry.close_price

                    metal_name_lower = metal.name.lower()
                    if 'золото' in metal_name_lower:
                        gold_count += 1
                        gold_value += coin_value
                        gold_weight += metal_weight
                    elif 'серебро' in metal_name_lower:
                        silver_count += 1
                        silver_value += coin_value
                        silver_weight += metal_weight

                    total_metal_value += coin_value

            # Обновляем строки с общей информацией
            self.total_coins_label.setText(f"🪙 Всего монет: {total_coins}")
            self.total_value_label.setText(f"💰 Рыночная стоимость: {market_value:,.0f} ₽")

            # Обновляем агрегаты по металлам
            self.gold_count_label.setText(f"{gold_count}")
            self.gold_value_label.setText(f"{gold_value:,.0f} ₽")
            self.gold_weight_label.setText(f"{gold_weight:.2f} г")
            self.silver_count_label.setText(f"{silver_count}")
            self.silver_value_label.setText(f"{silver_value:,.0f} ₽")
            self.silver_weight_label.setText(f"{silver_weight:.2f} г")

            total_metals_value = gold_value + silver_value
            total_metals_weight = gold_weight + silver_weight
            self.total_metals_value_label.setText(f"{total_metals_value:,.0f} ₽")
            self.total_metals_weight_label.setText(f"{total_metals_weight:.2f} г")

            # Загружаем топ-5 стран по количеству
            self._load_top_countries_chart(total_coins)

            # Загружаем распределение по векам
            self._load_centuries_distribution(all_coins)

            # Загружаем распределение по континентам
            self._load_continents_distribution()

        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных дашборда: {e}")

    def _load_top_countries_chart(self, total_coins):
        """Загружает топ-5 стран по количеству (графиком)"""
        try:
            # Очищаем контейнер
            while self.top_countries_layout.count():
                child = self.top_countries_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            countries = self.db_manager.get_all_countries()
            country_counts = []
            for country in countries:
                count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                if count > 0:
                    country_counts.append((country.name, count))

            # Сортируем и берем топ-5
            country_counts.sort(key=lambda x: x[1], reverse=True)
            top_countries = country_counts[:5]

            if not top_countries:
                label = QLabel("Нет данных о странах")
                label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
                label.setAlignment(Qt.AlignCenter)
                self.top_countries_layout.addWidget(label)
                return

            # Цвета для топ-стран
            colors = ["#4a6fa5", "#e67e22", "#27ae60", "#f1c40f", "#9b59b6"]
            for i, (name, count) in enumerate(top_countries):
                color = colors[i % len(colors)]
                row = self._create_bar_chart_row(name, count, total_coins, color, 140)
                self.top_countries_layout.addWidget(row)

        except Exception as e:
            self.logger.error(f"Ошибка при загрузке топ-стран: {e}")

    def _load_centuries_distribution(self, all_coins):
        """Загружает распределение по векам"""
        try:
            # Очищаем контейнер
            while self.centuries_layout.count():
                child = self.centuries_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Считаем монеты по векам
            centuries = {}
            for coin in all_coins:
                if coin.year:
                    century = ((coin.year - 1) // 100) + 1
                    if century < 0:
                        century_name = "до н.э."
                    else:
                        century_name = f"{century} в."
                    centuries[century_name] = centuries.get(century_name, 0) + 1

            if not centuries:
                label = QLabel("Нет данных о годах выпуска")
                label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
                label.setAlignment(Qt.AlignCenter)
                self.centuries_layout.addWidget(label)
                return

            total = sum(centuries.values())

            # Сортируем по убыванию века
            sorted_centuries = sorted(centuries.items(), key=lambda x: self._century_sort_key(x[0]), reverse=True)
            for century, count in sorted_centuries[:8]:
                row = self._create_bar_chart_row(century, count, total, "#4a6fa5", 140)
                self.centuries_layout.addWidget(row)

        except Exception as e:
            self.logger.error(f"Ошибка при загрузке распределения по векам: {e}")

    def _load_continents_distribution(self):
        """Загружает распределение по континентам"""
        try:
            # Очищаем контейнер
            while self.continents_layout.count():
                child = self.continents_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            countries = self.db_manager.get_all_countries()
            continent_counts = defaultdict(int)
            total = 0
            for country in countries:
                continent = country.continent or "Не указан"
                count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                if count > 0:
                    continent_counts[continent] += count
                    total += count

            if not continent_counts:
                label = QLabel("Нет данных по континентам")
                label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
                label.setAlignment(Qt.AlignCenter)
                self.continents_layout.addWidget(label)
                return

            # Сортируем по убыванию
            sorted_continents = sorted(continent_counts.items(), key=lambda x: x[1], reverse=True)
            for continent, count in sorted_continents:
                color = self._get_continent_color(continent)
                row = self._create_bar_chart_row(continent, count, total, color, 140)
                self.continents_layout.addWidget(row)

        except Exception as e:
            self.logger.error(f"Ошибка при загрузке распределения по континентам: {e}")

    def _century_sort_key(self, century):
        """Ключ для сортировки веков"""
        if century == "до н.э.":
            return -100
        try:
            return int(century.replace(" в.", ""))
        except:
            return 0

    def _get_continent_color(self, continent):
        """Возвращает цвет для континента"""
        colors = {
            "Европа": "#4a6fa5",
            "Азия": "#e67e22",
            "Америка": "#27ae60",
            "Африка": "#f1c40f",
            "Океания": "#9b59b6",
            "Не указан": "#95a5a6"
        }
        return colors.get(continent, "#4a6fa5")

    def refresh(self):
        """Обновляет данные дашборда"""
        self.load_data()