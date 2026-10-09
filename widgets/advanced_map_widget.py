# -*- coding: utf-8 -*-
"""
Улучшенная статистическая карта мира:
тёмная тема (OSM-инверсия), тепловая шкала, метрики (кол-во / рынок / вес / металл),
легенды, учёт исчезнувших стран через преемников (без перекрывания).
"""
import os
import logging
import tempfile
import json
from pathlib import Path
from collections import defaultdict
from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                               QLabel, QPushButton, QFrame,
                               QRadioButton, QButtonGroup, QCheckBox,
                               QApplication)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
import folium

from utils.map_settings import (
    COUNTRY_NAME_ALTERNATIVES,
    RUSSIAN_TO_ENGLISH,
    ENGLISH_TO_RUSSIAN,
    HISTORICAL_MAPPING,
    COUNTRY_COORDINATES,
    COUNTRY_CODES
)

COUNTRIES_GEOJSON = Path(__file__).parent.parent / "data" / "world-countries.json"


class AdvancedMapWidget(QWidget):
    """Улучшенная статистическая карта с историческими данными и тёмной темой"""
    MODE_COUNTRIES = 0
    MODE_CONTINENTS = 1
    MODE_HISTORICAL = 2

    CONTINENT_COLORS = {
        "Европа": "#4a6fa5",
        "Азия": "#e67e22",
        "Америка": "#27ae60",
        "Африка": "#f1c40f",
        "Океания": "#9b59b6",
        "Другие": "#95a5a6"
    }
    CENTURIES = [21, 20, 19, 18, 17, 16, 15]
    HEAT_STOPS = [
        (0.00, (255, 255, 204)),
        (0.25, (254, 217, 118)),
        (0.50, (254, 153, 41)),
        (0.75, (222, 45, 38)),
        (1.00, (128, 0, 38)),
    ]

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.AdvancedMapWidget')
        self.db_manager = db_manager
        self.display_mode = self.MODE_COUNTRIES
        self.selected_centuries = set()
        self.metal_filter = 'all'
        self.show_extinct = True
        self.map_metric = 'count'
        self.last_map_file = None
        self.gdf = None
        self.geojson_data = None
        self._geo_names = None
        self._ru_en_cache_obj = None
        self._web_view_ready = False
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.geojson_path = COUNTRIES_GEOJSON
        if not self.geojson_path.exists():
            self.download_geojson()
        self.init_ui()
        QTimer.singleShot(200, self.load_geodata)

    # ================= ТЕМА =================
    def _is_dark_theme(self):
        try:
            w = self.parent()
            while w is not None:
                tm = getattr(w, 'theme_manager', None)
                if tm is not None:
                    return tm.current_theme.get('type', 'dark') == 'dark'
                w = w.parent()
        except Exception:
            pass
        return True

    def _palette(self):
        if self._is_dark_theme():
            return {
                'bg': '#1a1a2e', 'panel': '#16213e', 'text': '#e4e4ef',
                'muted': '#8888aa', 'border': '#2a2a4a', 'accent': '#6c63ff',
                'box': '#1f2b47', 'popup_bg': '#16213e', 'popup_fg': '#e4e4ef',
            }
        return {
            'bg': '#f5f5f5', 'panel': '#ffffff', 'text': '#333333',
            'muted': '#666666', 'border': '#cccccc', 'accent': '#4a6fa5',
            'box': '#f5f5f5', 'popup_bg': '#ffffff', 'popup_fg': '#333333',
        }

    def _heat_color(self, value, max_value):
        """Цвет тепловой шкалы. None если значение нулевое."""
        if not value or value <= 0:
            return None
        t = min(1.0, value / max(1, max_value))
        stops = self.HEAT_STOPS
        for i in range(1, len(stops)):
            t0, c0 = stops[i - 1]
            t1, c1 = stops[i]
            if t <= t1:
                k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                rgb = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                return '#%02x%02x%02x' % rgb
        return '#800026'

    def download_geojson(self):
        try:
            import requests
            url = ("https://raw.githubusercontent.com/python-visualization/"
                   "folium/master/examples/data/world-countries.json")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(self.geojson_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info("GeoJSON файл скачан")
        except Exception as e:
            self.logger.error(f"Ошибка скачивания GeoJSON: {e}")

    # ================= UI =================
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        layout.addWidget(self.create_control_panel())
        self.info_label = QLabel("Загрузка данных...")
        self.info_label.setMinimumHeight(18)
        p = self._palette()
        self.info_label.setStyleSheet(
            f"color: {p['muted']}; padding: 2px; font-size: 11px;")
        layout.addWidget(self.info_label)
        try:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(500)
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(
                QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            layout.addWidget(self.web_view)
            self._web_view_ready = True
        except Exception as e:
            self.logger.error(f"Ошибка создания WebView: {e}")
            error_label = QLabel(f"❌ Ошибка: {str(e)[:100]}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(error_label)
            self.web_view = None

    def create_control_panel(self):
        """Компактная панель: 3 строки фильтров."""
        p = self._palette()
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet(
            f"QFrame {{ background-color: {p['panel']}; border-radius: 3px; padding: 2px; }}"
            f"QLabel {{ font-size: 11px; color: {p['text']}; }}"
            f"QRadioButton, QCheckBox {{ font-size: 11px; color: {p['text']}; }}"
            f"QComboBox {{ font-size: 11px; background-color: {p['box']}; "
            f"color: {p['text']}; border: 1px solid {p['border']}; "
            f"border-radius: 3px; padding: 1px; }}")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        panel.setLayout(layout)
        # --- Строка 1: область + режим + обновить ---
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(QLabel("Область:"))
        self.area_combo = QComboBox()
        self.area_combo.addItems(
            ["Весь мир", "Европа", "Азия", "Америка", "Африка", "Океания"])
        self.area_combo.currentTextChanged.connect(self.on_area_changed)
        self.area_combo.setMaximumWidth(110)
        row1.addWidget(self.area_combo)
        row1.addSpacing(10)
        row1.addWidget(QLabel("Режим:"))
        self.mode_group = QButtonGroup(self)
        self.country_mode = QRadioButton("🗺️ Страны")
        self.country_mode.setChecked(True)
        self.country_mode.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.country_mode, self.MODE_COUNTRIES)
        row1.addWidget(self.country_mode)
        self.continent_mode = QRadioButton("🌍 Континенты")
        self.continent_mode.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.continent_mode, self.MODE_CONTINENTS)
        row1.addWidget(self.continent_mode)
        self.historical_mode = QRadioButton("🏛️ Исторические")
        self.historical_mode.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.historical_mode, self.MODE_HISTORICAL)
        row1.addWidget(self.historical_mode)
        row1.addStretch()
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setToolTip("Обновить карту")
        self.refresh_btn.setFixedSize(26, 22)
        self.refresh_btn.clicked.connect(self.update_map)
        row1.addWidget(self.refresh_btn)
        layout.addLayout(row1)
        # --- Строка 2: века + металл + исчезнувшие ---
        row2 = QHBoxLayout()
        row2.setSpacing(2)
        row2.addWidget(QLabel("Века:"))
        self.all_centuries_check = QCheckBox("Все")
        self.all_centuries_check.setChecked(True)
        self.all_centuries_check.toggled.connect(self.on_all_centuries_toggled)
        row2.addWidget(self.all_centuries_check)
        self.century_checks = {}
        for century in self.CENTURIES:
            check = QCheckBox(f"{century}в.")
            check.toggled.connect(self.on_century_toggled)
            self.century_checks[century] = check
            row2.addWidget(check)
        row2.addSpacing(10)
        row2.addWidget(QLabel("Металл:"))
        self.metal_group = QButtonGroup(self)
        self.metal_all_radio = QRadioButton("Все")
        self.metal_all_radio.setChecked(True)
        self.metal_group.addButton(self.metal_all_radio, 0)
        row2.addWidget(self.metal_all_radio)
        self.metal_precious_radio = QRadioButton("Драг. (золото, серебро)")
        self.metal_group.addButton(self.metal_precious_radio, 1)
        row2.addWidget(self.metal_precious_radio)
        self.metal_other_radio = QRadioButton("Прочие")
        self.metal_group.addButton(self.metal_other_radio, 2)
        row2.addWidget(self.metal_other_radio)
        for rb in (self.metal_all_radio, self.metal_precious_radio,
                   self.metal_other_radio):
            rb.toggled.connect(self.on_metal_filter_changed)
        row2.addSpacing(10)
        self.extinct_toggle = QCheckBox("🏚️ Исчезнувшие")
        self.extinct_toggle.setChecked(self.show_extinct)
        self.extinct_toggle.toggled.connect(self.on_extinct_toggle_changed)
        row2.addWidget(self.extinct_toggle)
        row2.addStretch()
        layout.addLayout(row2)
        # --- Строка 3: метрика ---
        row3 = QHBoxLayout()
        row3.setSpacing(2)
        row3.addWidget(QLabel("Метрика:"))
        self.metric_group = QButtonGroup(self)
        self.metric_count_radio = QRadioButton("📊 Количество")
        self.metric_count_radio.setChecked(True)
        self.metric_group.addButton(self.metric_count_radio, 0)
        row3.addWidget(self.metric_count_radio)
        self.metric_market_radio = QRadioButton("💰 Рыночная стоимость, ₽")
        self.metric_group.addButton(self.metric_market_radio, 1)
        row3.addWidget(self.metric_market_radio)
        self.metric_weight_radio = QRadioButton("⚖️ Общий вес, г")
        self.metric_group.addButton(self.metric_weight_radio, 2)
        row3.addWidget(self.metric_weight_radio)
        self.metric_metal_radio = QRadioButton("🥇 Стоимость чистого металла, ₽")
        self.metric_group.addButton(self.metric_metal_radio, 3)
        row3.addWidget(self.metric_metal_radio)
        for rb in (self.metric_count_radio, self.metric_market_radio,
                   self.metric_weight_radio, self.metric_metal_radio):
            rb.toggled.connect(self.on_metric_changed)
        row3.addStretch()
        layout.addLayout(row3)
        return panel

    # ================= ОБРАБОТЧИКИ =================
    def on_area_changed(self):
        self.update_map()

    def on_mode_changed(self):
        if self.country_mode.isChecked():
            self.display_mode = self.MODE_COUNTRIES
        elif self.continent_mode.isChecked():
            self.display_mode = self.MODE_CONTINENTS
        else:
            self.display_mode = self.MODE_HISTORICAL
        self.update_map()

    def on_all_centuries_toggled(self, checked):
        if checked:
            for check in self.century_checks.values():
                check.setChecked(False)
            self.selected_centuries = set()
        self.update_map()

    def on_century_toggled(self):
        self.selected_centuries = set()
        for century, check in self.century_checks.items():
            if check.isChecked():
                self.selected_centuries.add(century)
        if self.selected_centuries:
            self.all_centuries_check.setChecked(False)
        else:
            self.all_centuries_check.setChecked(True)
        self.update_map()

    def on_metal_filter_changed(self, checked=True):
        if not checked:
            return
        if self.metal_precious_radio.isChecked():
            self.metal_filter = 'precious'
        elif self.metal_other_radio.isChecked():
            self.metal_filter = 'other'
        else:
            self.metal_filter = 'all'
        self.update_map()

    def on_extinct_toggle_changed(self, checked):
        self.show_extinct = bool(checked)
        self.update_map()

    def on_metric_changed(self, checked=True):
        if not checked:
            return
        if self.metric_market_radio.isChecked():
            self.map_metric = 'market_value'
        elif self.metric_weight_radio.isChecked():
            self.map_metric = 'weight'
        elif self.metric_metal_radio.isChecked():
            self.map_metric = 'metal_value'
        else:
            self.map_metric = 'count'
        self.update_map()

    # ================= ОПИСАНИЯ ФИЛЬТРОВ =================
    def get_century_filter_description(self):
        if not self.selected_centuries:
            return "все века"
        centuries_list = sorted(list(self.selected_centuries), reverse=True)
        if len(centuries_list) == 1:
            return f"{centuries_list[0]} век"
        return (f"{', '.join(str(c) for c in centuries_list[:-1])}"
                f" и {centuries_list[-1]} века")

    def get_metal_filter_description(self):
        return {
            'all': 'все металлы',
            'precious': 'драгоценные (золото, серебро)',
            'other': 'прочие металлы',
        }.get(self.metal_filter, 'все металлы')

    def get_full_filter_description(self):
        parts = [self.get_century_filter_description()]
        metal = self.get_metal_filter_description()
        if metal != 'все металлы':
            parts.append(metal)
        return ' | '.join(parts)

    def _metric_meta(self):
        return {
            'count': ('Количество монет', ''),
            'market_value': ('Рыночная стоимость, ₽', '₽'),
            'weight': ('Общий вес, г', 'г'),
            'metal_value': ('Стоимость чистого металла, ₽', '₽'),
        }.get(getattr(self, 'map_metric', 'count'), ('Количество монет', ''))

    def _fmt_metric(self, v):
        m = getattr(self, 'map_metric', 'count')
        if m == 'count':
            return f"{int(round(v))}"
        if m == 'weight':
            return f"{v:,.1f}".replace(',', ' ')
        return f"{v:,.0f}".replace(',', ' ')

    def _metric_value(self, stats):
        return float((stats or {}).get(
            getattr(self, 'map_metric', 'count'), 0) or 0)

    # ================= ДАННЫЕ =================
    def load_geodata(self):
        try:
            if self.geojson_path.exists():
                with open(self.geojson_path, 'r', encoding='utf-8') as f:
                    self.geojson_data = json.load(f)
                self.logger.info(
                    f"✅ Загружены геоданные "
                    f"{len(self.geojson_data.get('features', []))} стран")
            else:
                self.logger.warning("GeoJSON файл не найден")
            self.update_map()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки геоданных: {e}")
            self.update_map()

    def _ru_en_cache(self):
        """Нормализованный кэш РУС->АНГЛ (ключи/значения без лишних пробелов)."""
        if self._ru_en_cache_obj is None:
            cache = {}
            for k, v in RUSSIAN_TO_ENGLISH.items():
                if k and v:
                    cache.setdefault(k.strip(), []).append(v.strip())
            for k, v in COUNTRY_NAME_ALTERNATIVES.items():
                if k and v:
                    vals = v if isinstance(v, (list, tuple)) else [v]
                    for a in vals:
                        if a:
                            cache.setdefault(k.strip(), []).append(a.strip())
            for k in cache:
                seen = set()
                out = []
                for a in cache[k]:
                    if a not in seen:
                        seen.add(a)
                        out.append(a)
                cache[k] = out
            self._ru_en_cache_obj = cache
        return self._ru_en_cache_obj

    def _english_candidates(self, name):
        return list(self._ru_en_cache().get((name or '').strip(), []))

    def _geo_name_set(self):
        if self._geo_names is None:
            self._geo_names = set()
            if self.geojson_data:
                for f in self.geojson_data.get('features', []):
                    n = (f.get('properties') or {}).get('name', '')
                    if n:
                        self._geo_names.add(n)
        return self._geo_names

    def _country_coords(self, name):
        key = (name or '').strip()
        coords = COUNTRY_COORDINATES.get(key)
        if coords is None:
            for k, v in COUNTRY_COORDINATES.items():
                if (k or '').strip() == key:
                    coords = v
                    break
        return coords

    def _precious_metal_ids(self):
        from database.models import Metal
        keywords = ('золот', 'gold', 'серебр', 'silver',
                    'платин', 'platinum', 'паллад', 'palladium')
        ids = []
        try:
            for m in self.db_manager.session.query(Metal).all():
                nm = (m.name or '').lower()
                if any(k in nm for k in keywords):
                    ids.append(m.id)
        except Exception as e:
            self.logger.error(f"Ошибка чтения драгоценных металлов: {e}")
        return ids

    def _metal_filter_condition(self):
        from database.models import Coin
        from sqlalchemy import not_, or_, false, true
        if self.metal_filter == 'all':
            return None
        ids = self._precious_metal_ids()
        if self.metal_filter == 'precious':
            if not ids:
                return false()
            return Coin.metal_id.in_(ids)
        if not ids:
            return true()
        return or_(not_(Coin.metal_id.in_(ids)), Coin.metal_id.is_(None))

    def _get_metal_prices(self):
        """Цены металлов и пробы из БД (последняя дата MetalPriceHistory)."""
        from database.models import Metal, MetalPriceHistory
        prices = {}
        purity = {}
        try:
            last = self.db_manager.session.query(MetalPriceHistory.date)\
                .order_by(MetalPriceHistory.date.desc()).first()
            target_date = last[0] if last else None
            for metal in self.db_manager.session.query(Metal).all():
                try:
                    purity[metal.id] = metal.get_purity_decimal()
                except Exception:
                    purity[metal.id] = None
                if target_date is not None:
                    entry = self.db_manager.session.query(MetalPriceHistory)\
                        .filter_by(metal_id=metal.id, date=target_date).first()
                    if entry:
                        prices[metal.id] = entry.close_price
        except Exception as e:
            self.logger.error(f"Ошибка загрузки цен металлов: {e}")
        return prices, purity

    def _get_country_stats(self, country_id, metal_prices, purity_map):
        """Агрегаты по стране с учётом фильтров: count, market_value,
        weight, pure_weight, metal_value."""
        from database.models import Coin
        from sqlalchemy import or_
        q = self.db_manager.session.query(Coin).filter_by(country_id=country_id)
        if self.selected_centuries:
            conds = []
            for c in self.selected_centuries:
                conds.append((Coin.year >= (c - 1) * 100 + 1) & (Coin.year <= c * 100))
            q = q.filter(or_(*conds))
        if getattr(self, 'metal_filter', 'all') != 'all':
            cond = self._metal_filter_condition()
            if cond is not None:
                q = q.filter(cond)
        st = {'count': 0, 'market_value': 0.0, 'weight': 0.0,
              'pure_weight': 0.0, 'metal_value': 0.0}
        for coin in q.all():
            st['count'] += 1
            mp = getattr(coin, 'market_price', None)
            if mp:
                try:
                    st['market_value'] += float(mp)
                except Exception:
                    pass
            w = getattr(coin, 'weight', None)
            if w:
                try:
                    wf = float(w)
                    st['weight'] += wf
                    price = metal_prices.get(coin.metal_id)
                    pur = purity_map.get(coin.metal_id)
                    if price and pur:
                        pw = wf * pur
                        st['pure_weight'] += pw
                        st['metal_value'] += pw * price
                except Exception:
                    pass
        return st

    def _historical_mapping(self):
        try:
            return HISTORICAL_MAPPING or {}
        except Exception:
            return {}

    def _successors_names(self, hist_name, data):
        """Русские названия преемников: БД → HISTORICAL_MAPPING."""
        succ = []
        country = data.get('country') if isinstance(data, dict) else None
        try:
            if country is not None:
                objs = self.db_manager.get_country_successors(country.id) or []
                succ = [getattr(s, 'name', None) or str(s) for s in objs]
        except Exception:
            succ = []
        if not succ:
            key = (hist_name or '').strip()
            for k, v in self._historical_mapping().items():
                if (k or '').strip() == key:
                    succ = [(x or '').strip() for x in (v or [])]
                    break
        return [s for s in succ if s]

    def get_country_data(self):
        """Данные по странам: stats (count/market/weight/metal) + наследование."""
        metal_prices, purity_map = self._get_metal_prices()
        countries = self.db_manager.get_all_countries()
        all_data = {}
        for country in countries:
            st = self._get_country_stats(country.id, metal_prices, purity_map)
            if st['count'] > 0:
                all_data[country.id] = {
                    'country': country,
                    'coins': st['count'],
                    'stats': st,
                    'original_countries': set(),
                }
        if self.display_mode == self.MODE_COUNTRIES:
            total = sum(d['coins'] for d in all_data.values())
            return all_data, total
        if self.display_mode == self.MODE_CONTINENTS:
            if getattr(self, 'show_extinct', True):
                result = dict(all_data)
            else:
                result = {cid: d for cid, d in all_data.items()
                          if not getattr(d['country'], 'is_extinct', False)}
            total = sum(d['coins'] for d in result.values())
            return result, total
        # MODE_HISTORICAL
        result = {}
        for country_id, data in all_data.items():
            country = data['country']
            if getattr(country, 'is_extinct', False):
                if country.id not in result:
                    result[country.id] = {
                        'country': country, 'coins': 0, 'stats': dict(data['stats']),
                        'original_countries': set([country.name])}
                else:
                    result[country.id]['coins'] += data['coins']
                    for k in result[country.id]['stats']:
                        result[country.id]['stats'][k] += data['stats'].get(k, 0)
        from database.models import Country
        zero = {'count': 0, 'market_value': 0.0, 'weight': 0.0,
                'pure_weight': 0.0, 'metal_value': 0.0}
        for hist_name, successors in self._historical_mapping().items():
            if any(d['country'].name == hist_name for d in result.values()):
                continue
            agg = dict(zero)
            for succ in successors:
                sc = self.db_manager.session.query(Country)\
                    .filter_by(name=succ).first()
                if sc and sc.id in all_data:
                    for k in agg:
                        agg[k] += all_data[sc.id]['stats'].get(k, 0)
            if agg['count'] > 0:
                class TempCountry:
                    pass
                tc = TempCountry()
                tc.name = hist_name
                tc.is_extinct = True
                tc.id = -abs(hash(hist_name))
                result[tc.id] = {'country': tc, 'coins': agg['count'],
                                 'stats': agg,
                                 'original_countries': set(successors)}
        total = sum(d['coins'] for d in result.values())
        return result, total

    def merge_country_geometries(self, country_names, alternatives=None):
        if not self.geojson_data:
            return None
        if alternatives is None:
            alternatives = {}
        merged_coords = []
        for feature in self.geojson_data['features']:
            name = feature['properties'].get('name', '')
            hit = name in country_names
            if not hit:
                for target_name in country_names:
                    if target_name in alternatives:
                        if name in alternatives[target_name]:
                            hit = True
                            break
            if hit:
                geom = feature['geometry']
                if geom['type'] == 'Polygon':
                    merged_coords.append(geom['coordinates'])
                elif geom['type'] == 'MultiPolygon':
                    merged_coords.extend(geom['coordinates'])
        if merged_coords:
            return {'type': 'MultiPolygon', 'coordinates': merged_coords}
        return None

    def get_continent_for_country(self, country):
        if country.continent and country.continent in self.CONTINENT_COLORS:
            return country.continent
        name_to_continent = {
            "Россия": "Европа", "Великобритания": "Европа", "Германия": "Европа",
            "Франция": "Европа", "Италия": "Европа", "Испания": "Европа",
            "Португалия": "Европа", "Нидерланды": "Европа", "Бельгия": "Европа",
            "Швейцария": "Европа", "Австрия": "Европа", "Швеция": "Европа",
            "Норвегия": "Европа", "Финляндия": "Европа", "Дания": "Европа",
            "Польша": "Европа", "Чехия": "Европа", "Словакия": "Европа",
            "Венгрия": "Европа", "Греция": "Европа", "Ирландия": "Европа",
            "Украина": "Европа", "Беларусь": "Европа", "Литва": "Европа",
            "Латвия": "Европа", "Эстония": "Европа", "Румыния": "Европа",
            "Болгария": "Европа", "Сербия": "Европа", "Хорватия": "Европа",
            "Словения": "Европа", "Босния и Герцеговина": "Европа",
            "Албания": "Европа", "Северная Македония": "Европа",
            "Косово": "Европа", "Молдова": "Европа", "Исландия": "Европа",
            "Мальта": "Европа", "Кипр": "Азия", "Турция": "Азия",
            "США": "Америка", "Канада": "Америка", "Мексика": "Америка",
            "Бразилия": "Америка", "Аргентина": "Америка", "Чили": "Америка",
            "Колумбия": "Америка", "Венесуэла": "Америка", "Перу": "Америка",
            "Эквадор": "Америка", "Боливия": "Америка", "Парагвай": "Америка",
            "Уругвай": "Америка", "Гайана": "Америка", "Суринам": "Америка",
            "Куба": "Америка", "Ямайка": "Америка", "Гаити": "Америка",
            "Доминикана": "Америка", "Пуэрто-Рико": "Америка",
            "Китай": "Азия", "Япония": "Азия", "Индия": "Азия",
            "Корея": "Азия", "Вьетнам": "Азия", "Таиланд": "Азия",
            "Малайзия": "Азия", "Индонезия": "Азия", "Филиппины": "Азия",
            "Пакистан": "Азия", "Бангладеш": "Азия", "Мьянма": "Азия",
            "Непал": "Азия", "Бутан": "Азия", "Шри-Ланка": "Азия",
            "Монголия": "Азия", "Казахстан": "Азия", "Киргизия": "Азия",
            "Таджикистан": "Азия", "Туркменистан": "Азия",
            "Узбекистан": "Азия", "Афганистан": "Азия", "Иран": "Азия",
            "Ирак": "Азия", "Сирия": "Азия", "Ливан": "Азия",
            "Иордания": "Азия", "Израиль": "Азия",
            "Саудовская Аравия": "Азия", "Йемен": "Азия", "Оман": "Азия",
            "ОАЭ": "Азия", "Катар": "Азия", "Кувейт": "Азия",
            "Бахрейн": "Азия",
            "Египет": "Африка", "ЮАР": "Африка", "Нигерия": "Африка",
            "Кения": "Африка", "Танзания": "Африка", "Уганда": "Африка",
            "Эфиопия": "Африка", "Сомали": "Африка", "Судан": "Африка",
            "Алжир": "Африка", "Марокко": "Африка", "Тунис": "Африка",
            "Ливия": "Африка", "Мавритания": "Африка", "Сенегал": "Африка",
            "Мали": "Африка", "Буркина-Фасо": "Африка", "Нигер": "Африка",
            "Чад": "Африка", "Камерун": "Африка", "Габон": "Африка",
            "ДР Конго": "Африка", "Ангола": "Африка", "Намибия": "Африка",
            "Ботсвана": "Африка", "Зимбабве": "Африка", "Замбия": "Африка",
            "Мозамбик": "Африка", "Мадагаскар": "Африка",
            "Австралия": "Океания", "Новая Зеландия": "Океания",
            "Папуа - Новая Гвинея": "Океания", "Фиджи": "Океания",
            "Соломоновы Острова": "Океания", "Вануату": "Океания",
            "Самоа": "Океания", "Тонга": "Океания", "Кирибати": "Океания",
            "Микронезия": "Океания", "Маршалловы Острова": "Океания",
            "Палау": "Океания", "Науру": "Океания", "Тувалу": "Океания",
        }
        return name_to_continent.get(country.name, "Другие")

    def get_country_code(self, country):
        if country.iso3 and len(country.iso3) == 3:
            return country.iso3
        return COUNTRY_CODES.get(country.name)

    # ================= КАРТА =================
    def create_map(self):
        """Базовая карта на тайлах OpenStreetMap — без API-ключа и водяных знаков.
        Тёмный вид достигается CSS-инверсией слоя плиток в _postprocess_html."""
        area = self.area_combo.currentText()
        centers = {
            "Весь мир": [20, 0], "Европа": [50, 10], "Азия": [30, 100],
            "Америка": [20, -80], "Африка": [0, 20], "Океания": [-20, 140]
        }
        zooms = {
            "Весь мир": 2, "Европа": 4, "Азия": 3,
            "Америка": 3, "Африка": 3, "Океания": 3
        }
        m = folium.Map(
            location=centers.get(area, [20, 0]),
            zoom_start=zooms.get(area, 2),
            tiles='OpenStreetMap',
            attr='© OpenStreetMap contributors'
        )
        return m

    def add_country_data_to_map(self, m, country_data, total_coins):
        """Хороплет по выбранной метрике. Исчезнувшие страны (при вкл. галочке)
        ОБЪЕДИНЯЮТСЯ со странами-преемниками (без перекрывания слоем)."""
        zero = {'count': 0, 'market_value': 0.0, 'weight': 0.0,
                'pure_weight': 0.0, 'metal_value': 0.0}
        if not (self.geojson_path.exists() and self.geojson_data):
            self.add_markers_to_map(m, country_data)
            return m
        try:
            dark = self._is_dark_theme()
            names_set = self._geo_name_set()
            stats_by_en = {}
            inherited_info = {}
            unmatched = []
            for data in country_data.values():
                country = data['country']
                st = data.get('stats') or dict(zero)
                if getattr(country, 'is_extinct', False):
                    if not getattr(self, 'show_extinct', True):
                        continue
                    targets = []
                    for s in self._successors_names(country.name, data):
                        for cand in self._english_candidates(s):
                            if cand in names_set:
                                targets.append(cand)
                                break
                    if targets:
                        for en in targets:
                            agg = stats_by_en.setdefault(en, dict(zero))
                            for k in agg:
                                agg[k] += st.get(k, 0)
                            inherited_info.setdefault(en, []).append(
                                (country.name, st['count']))
                    else:
                        unmatched.append((country, st))
                    continue
                en = None
                for cand in self._english_candidates(country.name):
                    if cand in names_set:
                        en = cand
                        break
                if en:
                    agg = stats_by_en.setdefault(en, dict(zero))
                    for k in agg:
                        agg[k] += st.get(k, 0)
                else:
                    unmatched.append((country, st))
            max_val = max(
                [self._metric_value(st) for st in stats_by_en.values()] +
                [self._metric_value(st) for _, st in unmatched] or [1]) or 1
            geo = {'type': 'FeatureCollection', 'features': []}
            for f in self.geojson_data['features']:
                nm = (f.get('properties') or {}).get('name', '')
                st = stats_by_en.get(nm, zero)
                props = dict(f.get('properties') or {})
                props['cnt'] = int(st['count'])
                props['own'] = int(st['count'] - sum(
                    c for _, c in inherited_info.get(nm, [])))
                props['inh'] = '; '.join(
                    f"{h}: {c}" for h, c in inherited_info.get(nm, [])) or '—'
                props['mval'] = round(st['market_value'], 2)
                props['wt'] = round(st['weight'], 1)
                props['mtval'] = round(st['metal_value'], 2)
                props['mv'] = round(self._metric_value(st), 2)
                geo['features'].append(
                    {'type': 'Feature', 'properties': props,
                     'geometry': f['geometry']})

            def style_function(feature):
                mv = (feature.get('properties') or {}).get('mv', 0) or 0
                color = self._heat_color(mv, max_val)
                if color is None:
                    return {'fillColor': '#26263a' if dark else '#f0f0f0',
                            'fillOpacity': 0.25 if dark else 0.3,
                            'color': '#8888aa' if dark else '#444444',
                            'weight': 0.6}
                return {'fillColor': color, 'fillOpacity': 0.8,
                        'color': '#0f0f1a' if dark else '#333333',
                        'weight': 0.8}

            folium.GeoJson(
                geo,
                name='countries_fill',
                style_function=style_function,
                tooltip=folium.GeoJsonTooltip(
                    fields=['name', 'cnt', 'own', 'inh', 'mval', 'wt', 'mtval'],
                    aliases=['Страна:', 'Монет:', 'Своих монет:',
                             'Унаследовано:', 'Рын. стоимость, ₽:',
                             'Вес, г:', 'Ст-ть металла, ₽:'],
                    localize=True, sticky=False, labels=True)
            ).add_to(m)
            if unmatched:
                marker_layer = folium.FeatureGroup(name='countries_markers')
                shown = 0
                for country, st in unmatched:
                    coords = self._country_coords(country.name)
                    if not coords or coords[0] is None:
                        continue
                    color = self._heat_color(
                        self._metric_value(st), max_val) or '#800026'
                    folium.CircleMarker(
                        [coords[0], coords[1]], radius=8,
                        popup=f"<b>{country.name}</b><br>"
                              f"Монет: {int(st['count'])}",
                        tooltip=f"{country.name}: "
                                f"{self._fmt_metric(self._metric_value(st))}",
                        color='#000000' if dark else '#333333',
                        weight=1.5,
                        fill=True, fillColor=color, fillOpacity=0.9
                    ).add_to(marker_layer)
                    shown += 1
                if shown:
                    marker_layer.add_to(m)
            title, _ = self._metric_meta()
            self._add_quantity_legend(m, max_val, title=title)
            self.info_label.setText(
                f"✅ По странам | {title} | "
                f"{self.get_full_filter_description()} | "
                f"Монет: {int(total_coins)} | "
                f"Область: {self.area_combo.currentText()}")
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.add_markers_to_map(m, country_data)
        return m

    def add_continent_data_to_map(self, m, continent_data, total_coins):
        """Режим континентов: заливка по континентам + маркеры с метрикой."""
        p = self._palette()
        if not (self.geojson_path.exists() and self.geojson_data):
            self.add_markers_to_map(m, {})
            return m
        try:
            dark = self._is_dark_theme()
            countries = self.db_manager.get_all_countries()
            country_to_continent = {}
            for country in countries:
                country_to_continent[country.name] = \
                    self.get_continent_for_country(country)
            total_metric = sum(
                self._metric_value(v) if isinstance(v, dict) else float(v or 0)
                for v in continent_data.values()) or 1

            def style_function(feature):
                geo_name = feature['properties'].get('name', '')
                country_name = ENGLISH_TO_RUSSIAN.get(geo_name, geo_name)
                continent = country_to_continent.get(country_name, "Другие")
                color = self.CONTINENT_COLORS.get(continent, "#95a5a6")
                st = continent_data.get(continent) or {}
                if isinstance(st, dict):
                    cont_val = self._metric_value(st)
                else:
                    cont_val = float(st or 0)
                if cont_val > 0:
                    opacity = 0.3 + min(cont_val / total_metric, 0.5)
                else:
                    opacity = 0.1
                return {
                    'fillColor': color,
                    'color': '#000000',
                    'weight': 0.5,
                    'fillOpacity': opacity,
                }

            folium.GeoJson(
                self.geojson_data,
                name='continents',
                style_function=style_function,
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'], aliases=['Страна:'],
                    localize=True, sticky=False, labels=True)
            ).add_to(m)
            for continent, st in continent_data.items():
                continent_center = {
                    "Европа": [50, 10], "Азия": [40, 100],
                    "Америка": [20, -80], "Африка": [0, 20],
                    "Океания": [-20, 140], "Другие": [0, 0]
                }.get(continent, [0, 0])
                color = self.CONTINENT_COLORS.get(continent, "#95a5a6")
                if isinstance(st, dict):
                    cont_val = self._metric_value(st)
                    cont_count = int(st.get('count', 0))
                else:
                    cont_val = float(st or 0)
                    cont_count = int(st or 0)
                countries_list = []
                for data in self.get_country_data()[0].values():
                    country = data['country']
                    if self.get_continent_for_country(country) == continent:
                        countries_list.append(
                            f"{country.name}: {int(data['coins'])}")
                countries_text = "<br>".join(countries_list[:8])
                if len(countries_list) > 8:
                    countries_text += f"<br>... и ещё {len(countries_list) - 8}"
                popup_html = f"""
                <div style="font-family: Arial; min-width: 250px; max-width: 300px;
                            max-height: 400px; overflow-y: auto; padding: 8px;
                            background-color: {p['popup_bg']};
                            color: {p['popup_fg']};">
                    <h3 style="margin: 0 0 5px 0; color: {color}; font-size: 18px;
                               text-align: center;">{continent}</h3>
                    <hr style="margin: 5px 0; border: 1px solid {color};">
                    <table style="width: 100%; font-size: 13px;
                                  border-collapse: collapse;">
                        <tr>
                            <td style="padding: 3px; font-weight: bold;">
                                💰 Всего монет:</td>
                            <td style="padding: 3px; text-align: right;
                                       font-weight: bold; color: {color};">
                                {cont_count}</td>
                        </tr>
                        <tr>
                            <td style="padding: 3px; font-weight: bold;">
                                📊 {self._metric_meta()[0]}:</td>
                            <td style="padding: 3px; text-align: right;
                                       font-weight: bold; color: {color};">
                                {self._fmt_metric(cont_val)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 3px; font-weight: bold;">
                                🗺️ Стран:</td>
                            <td style="padding: 3px; text-align: right;">
                                {len(countries_list)}</td>
                        </tr>
                    </table>
                    <hr style="margin: 5px 0;">
                    <p style="font-weight: bold; margin: 3px 0; font-size: 13px;">
                        📋 Страны:</p>
                    <div style="background-color: {p['box']}; padding: 5px;
                                border-radius: 3px; font-size: 12px;
                                max-height: 200px; overflow-y: auto;">
                        {countries_text if countries_text else "Нет монет"}
                    </div>
                </div>
                """
                folium.Marker(
                    continent_center,
                    popup=folium.Popup(popup_html, max_width=350, max_height=450),
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="background-color: {color}; color: white;
                            font-weight: bold; padding: 6px 12px;
                            border-radius: 20px; border: 2px solid white;
                            box-shadow: 0 0 10px rgba(0,0,0,0.4); opacity: 0.95;
                            font-size: 14px; text-align: center;
                            min-width: 120px; cursor: pointer;">
                            {continent}<br>
                            <span style="font-size: 12px;">{cont_count} монет<br>
                            {self._fmt_metric(cont_val)}</span>
                        </div>
                        """
                    ),
                    tooltip=f"{continent}: {cont_count} монет | "
                            f"{self._fmt_metric(cont_val)}"
                ).add_to(m)
            self.info_label.setText(
                f"✅ По континентам | {self.get_full_filter_description()} | "
                f"Монет: {int(total_coins)} | "
                f"Континентов: {len(continent_data)} | "
                f"Область: {self.area_combo.currentText()}")
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            self.add_markers_to_map(m, {})
        return m

    def add_markers_to_map(self, m, country_data):
        pairs = []
        for key, val in (country_data or {}).items():
            if isinstance(val, dict):
                country = val.get('country')
                st = val.get('stats') or {'count': val.get('coins', 0)}
            else:
                country = key
                st = {'count': int(val or 0)}
            if country is not None:
                pairs.append((country, st))
        max_val = max([self._metric_value(st) for _, st in pairs] or [1]) or 1
        dark = self._is_dark_theme()
        for country, st in pairs:
            coords = self._country_coords(country.name)
            if coords and coords[0] is not None:
                color = self._heat_color(
                    self._metric_value(st), max_val) or '#800026'
                folium.CircleMarker(
                    [coords[0], coords[1]], radius=8,
                    popup=f"<b>{country.name}</b><br>"
                          f"Монет: {int(st.get('count', 0))}",
                    tooltip=f"{country.name}: "
                            f"{self._fmt_metric(self._metric_value(st))}",
                    color='#000000' if dark else '#333333',
                    weight=1.5,
                    fill=True, fillColor=color, fillOpacity=0.9
                ).add_to(m)
        self._add_quantity_legend(m, max_val, title=self._metric_meta()[0])
        return m

    def create_historical_map(self, m, country_data, total_coins):
        self.logger.info("=== СОЗДАНИЕ ИСТОРИЧЕСКОЙ КАРТЫ ===")
        dark = self._is_dark_theme()
        if self.geojson_data:
            folium.GeoJson(
                self.geojson_data,
                name='background',
                style_function=lambda x: {
                    'fillColor': '#20203a' if dark else '#f5f5f5',
                    'color': '#333355' if dark else '#dddddd',
                    'weight': 0.3,
                    'fillOpacity': 0.3,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'], aliases=['Страна:'])
            ).add_to(m)
        names_set = self._geo_name_set()
        historical = {}
        for data in country_data.values():
            country = data['country']
            if getattr(country, 'is_extinct', False) or \
                    country.name in self._historical_mapping():
                if data.get('original_countries'):
                    historical[country.name] = {
                        'coins': data['coins'],
                        'stats': data.get('stats') or {},
                        'successors': list(data['original_countries'])}
        if not historical:
            self.logger.warning("Нет исторических стран для отображения")
            self.info_label.setText(
                "📭 Нет исчезнувших стран с заданными преемниками. "
                "Откройте диалог «Историческая преемственность стран» "
                "и установите связи.")
            return m
        max_val = max(
            [self._metric_value(d.get('stats')) for d in historical.values()]
            or [1]) or 1
        layer = folium.FeatureGroup(name='historical_territories')
        added = 0
        for hist_name, hd in historical.items():
            coins = int(hd['coins'])
            val = self._metric_value(hd.get('stats')) or coins
            cands = set()
            for s in hd['successors']:
                for cand in self._english_candidates(s):
                    if cand in names_set:
                        cands.add(cand)
            if not cands:
                self.logger.warning(
                    f"Нет геометрий преемников для {hist_name}")
                continue
            geom = self.merge_country_geometries(cands)
            if not geom:
                continue
            color = self._heat_color(val, max_val) or '#800026'
            succ_text = ', '.join(hd['successors'][:6])
            if len(hd['successors']) > 6:
                succ_text += '…'
            folium.GeoJson(
                geom,
                name=hist_name,
                style_function=lambda x, c=color: {
                    'fillColor': c, 'color': '#000000',
                    'weight': 1.5, 'fillOpacity': 0.7},
                highlight_function=lambda x: {
                    'weight': 3, 'color': '#000000', 'fillOpacity': 0.9},
                tooltip=(f"{hist_name}\n💰 Монет: {coins}\n"
                         f"{self._metric_meta()[0]}: {self._fmt_metric(val)}\n"
                         f"🔄 Преемники: {succ_text}")
            ).add_to(layer)
            added += 1
        if added:
            layer.add_to(m)
        self._add_quantity_legend(m, max_val,
                                  title=f"🏛️ {self._metric_meta()[0]}")
        self.info_label.setText(
            f"✅ Историческая карта | {self.get_full_filter_description()} | "
            f"Монет: {int(total_coins)} | Исторических стран: {added} | "
            f"Область: {self.area_combo.currentText()}")
        return m

    def _add_quantity_legend(self, m, max_val, title="Количество монет"):
        bounds = [(0, max_val * 0.25), (max_val * 0.25, max_val * 0.5),
                  (max_val * 0.5, max_val * 0.75), (max_val * 0.75, max_val)]
        zero = '#3a3a4a' if self._is_dark_theme() else '#eeeeee'
        items = ('<div style="display: flex; align-items: center; '
                 'margin-bottom: 4px;">'
                 f'<div style="width: 22px; height: 14px; background: {zero}; '
                 'border: 1px solid #888; border-radius: 2px;"></div>'
                 '<span style="margin-left: 8px;">0</span></div>')
        for a, b in bounds:
            color = self._heat_color(b if b > 0 else 1, max_val) or zero
            items += ('<div style="display: flex; align-items: center; '
                      'margin-bottom: 4px;">'
                      f'<div style="width: 22px; height: 14px; '
                      f'background: {color}; '
                      'border: 1px solid #888; border-radius: 2px;"></div>'
                      f'<span style="margin-left: 8px;">'
                      f'{self._fmt_metric(a)} – {self._fmt_metric(b)}'
                      '</span></div>')
        html = ('<div style="position: fixed; bottom: 30px; left: 30px; '
                'z-index: 1000; background: rgba(22,33,62,.94); '
                'color: #e4e4ef; padding: 10px 12px; border-radius: 8px; '
                'border: 1px solid #2a2a4a; '
                'box-shadow: 0 2px 10px rgba(0,0,0,.5); '
                "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; "
                'min-width: 150px;">'
                '<div style="font-weight: bold; margin-bottom: 6px; '
                f'text-align: center;">{title}</div>{items}</div>')
        from branca.element import Element
        m.get_root().html.add_child(Element(html))

    # ================= ОБНОВЛЕНИЕ =================
    def update_map(self):
        if not self._web_view_ready or self.web_view is None:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.info_label.setText("🔄 Создание карты...")
            country_data, total_coins = self.get_country_data()
            if not country_data:
                self.show_empty_message("Нет данных для отображения")
                self.info_label.setText("📭 Нет данных")
                return
            m = self.create_map()
            if self.display_mode == self.MODE_COUNTRIES:
                m = self.add_country_data_to_map(m, country_data, total_coins)
            elif self.display_mode == self.MODE_CONTINENTS:
                zero = {'count': 0, 'market_value': 0.0, 'weight': 0.0,
                        'pure_weight': 0.0, 'metal_value': 0.0}
                continent_dict = {}
                for data in country_data.values():
                    cont = self.get_continent_for_country(data['country'])
                    agg = continent_dict.setdefault(cont, dict(zero))
                    st = data.get('stats') or zero
                    for k in agg:
                        agg[k] += st.get(k, 0)
                m = self.add_continent_data_to_map(m, continent_dict, total_coins)
            else:
                m = self.create_historical_map(m, country_data, total_coins)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html',
                                              delete=False,
                                              encoding='utf-8') as f:
                m.save(f.name)
                self.last_map_file = f.name
            self._postprocess_html(self.last_map_file)
            if self.web_view:
                self.web_view.setUrl(QUrl.fromLocalFile(self.last_map_file))
        except Exception as e:
            self.logger.error(f"Ошибка создания карты: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.show_empty_message(f"Ошибка: {str(e)[:50]}")
        finally:
            QApplication.restoreOverrideCursor()

    def _postprocess_html(self, file_path):
        """Постобработка HTML карты:
        1) скрывает логотипы/атрибуцию;
        2) тёмная тема: инверсия OSM-плиток (без водяных знаков), тёмные тултипы;
        3) тултипы БЕЗ переносов строк (шире) и с уменьшенным межстрочным интервалом."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            css = """
            <style>
                /* скрыть логотипы и атрибуцию */
                .leaflet-control-attribution,
                .leaflet-control-attribution a,
                a[href*="leafletjs.com"],
                a[href*="openstreetmap.org"] {
                    display: none !important;
                }
                /* Тултип: контейнер хранит переносы строк (pre-line),
                   но ячейки таблицы НЕ переносятся (nowrap) → тултип шире */
                .leaflet-tooltip {
                    white-space: pre-line !important;
                    line-height: 1.15 !important;
                    max-width: none !important;
                }
                .leaflet-tooltip table {
                    border-collapse: collapse !important;
                }
                .leaflet-tooltip th,
                .leaflet-tooltip td {
                    white-space: nowrap !important;
                    line-height: 1.15 !important;
                    padding: 1px 10px 1px 0 !important;
                    font-size: 12px !important;
                }
            """
            if self._is_dark_theme():
                css += """
                html, body { background: #1a1a2e !important; }
                .leaflet-container {
                    background: #1a1a2e !important;
                    font-family: 'Segoe UI', Arial, sans-serif !important;
                }
                /* ТЁМНАЯ КАРТА из OSM-плиток без водяных знаков */
                .leaflet-tile-pane {
                    filter: invert(1) hue-rotate(180deg)
                            brightness(0.85) contrast(0.9) saturate(0.75);
                }
                .leaflet-tooltip {
                    background: #16213e !important;
                    color: #e4e4ef !important;
                    border: 1px solid #6c63ff !important;
                    box-shadow: 0 0 8px rgba(108,99,255,.45) !important;
                }
                .leaflet-popup-content-wrapper {
                    background: #16213e !important;
                    color: #e4e4ef !important;
                    border: 1px solid #2a2a4a !important;
                    border-radius: 8px !important;
                }
                .leaflet-popup-tip { background: #16213e !important; }
                .leaflet-popup-content a { color: #8f88ff !important; }
                .leaflet-popup-close-button { color: #8888aa !important; }
                .leaflet-control-zoom a {
                    background: #16213e !important;
                    color: #e4e4ef !important;
                    border-color: #2a2a4a !important;
                }
                .leaflet-bar { border: 1px solid #2a2a4a !important; }
                """
            css += "</style>"
            if '</head>' in content:
                content = content.replace('</head>', css + '</head>')
            else:
                content = css + content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Ошибка постобработки карты: {e}")

    _remove_logos = _postprocess_html

    def show_empty_message(self, message):
        p = self._palette()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><style>
            body {{
                display: flex; justify-content: center; align-items: center;
                height: 100vh; margin: 0;
                font-family: Arial, sans-serif;
                background-color: {p['bg']};
            }}
            .message {{
                text-align: center; padding: 30px;
                background-color: {p['panel']}; color: {p['text']};
                border: 1px solid {p['border']}; border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }}
            h2 {{ color: {p['accent']}; }}
            p {{ color: {p['muted']}; }}
        </style></head>
        <body>
            <div class="message">
                <h2>📭 {message}</h2>
                <p>Попробуйте выбрать другой фильтр или добавить монеты
                в коллекцию.</p>
            </div>
        </body>
        </html>
        """
        if self.web_view:
            self.web_view.setHtml(html)
        self.info_label.setText(f"📭 {message}")

    def closeEvent(self, event):
        if self.last_map_file and os.path.exists(self.last_map_file):
            try:
                os.unlink(self.last_map_file)
            except Exception:
                pass
        super().closeEvent(event)