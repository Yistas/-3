# -*- coding: utf-8 -*-
"""Кэш категорий Meshok: дерево скачивается ОДИН раз и хранится в
data/meshok_categories.json; недостающие ветки докачиваются по требованию
(с задержкой 1.1 c — лимит Мешка «не более 1 запроса в секунду»)."""
import json
import logging
import time
from pathlib import Path

LOGGER = logging.getLogger('CoinCollector.MeshokCategories')

CACHE_PATH = Path(__file__).resolve().parents[2] / 'data' / 'meshok_categories.json'
COINS_ROOT_ID = 252
OTHER_NAMES = ('другое', 'другие', 'разное', 'прочее', 'прочие')
CONTINENT_FRAGMENTS = (('океан', 'океан'), ('европ', 'европ'),
                       ('ази', 'ази'), ('амер', 'амер'), ('африк', 'африк'))


class MeshokCategoryCache:
    def __init__(self, api):
        self.api = api
        self.nodes = {}
        self._load()

    # ---------- кэш ----------
    def _load(self):
        try:
            if CACHE_PATH.exists():
                self.nodes = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
                LOGGER.info(f"📂 Кэш категорий загружен: {len(self.nodes)} узлов")
        except Exception as e:
            LOGGER.warning(f"Не удалось загрузить кэш категорий: {e}")
            self.nodes = {}

    def _save(self):
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(
                json.dumps(self.nodes, ensure_ascii=False, indent=1),
                encoding='utf-8')
        except Exception as e:
            LOGGER.warning(f"Не удалось сохранить кэш категорий: {e}")

    @staticmethod
    def _rate_limit():
        time.sleep(1.1)   # лимит Мешка: 1 запрос/сек

    def children_of(self, cat_id):
        """Дочерние разделы из кэша; при отсутствии — скачивает и кеширует."""
        key = str(cat_id)
        node = self.nodes.get(key)
        if node is not None and 'children' in node:
            return node['children']
        self._rate_limit()
        resp = self.api.get_sub_category(cat_id) or {}
        result = resp.get('result') if isinstance(resp, dict) else None
        items = []
        if isinstance(result, dict):
            items = [v for v in result.values() if isinstance(v, dict)]
        elif isinstance(result, list):
            items = [v for v in result if isinstance(v, dict)]
        children = []
        for it in items:
            cid = str(it.get('id'))
            child = {'id': cid,
                     'name': it.get('name') or '',
                     'subCategories': bool(it.get('subCategories'))}
            self.nodes.setdefault(cid, child)
            children.append(child)
        if node is None:
            node = {'id': key, 'name': '', 'subCategories': True}
            self.nodes[key] = node
        node['children'] = children
        self._save()
        return children

    # ---------- поиск ----------
    @staticmethod
    def _find(children, needle):
        needle = (needle or '').strip().lower()
        if not needle:
            return None
        for ch in children:
            if needle in (ch.get('name') or '').lower():
                return ch
        return None

    @staticmethod
    def _find_other(children):
        for ch in children:
            nm = (ch.get('name') or '').lower()
            if any(o in nm for o in OTHER_NAMES):
                return ch
        return None

    @staticmethod
    def _first_leaf(children):
        for ch in children:
            if not ch.get('subCategories'):
                return ch
        return children[0] if children else None

    def resolve(self, continent='', country=''):
        """Путь: Монеты(252) → Континент → Страна → лист.
        Если страны нет — ветка «Другое». Возвращает int(id) или None."""
        try:
            root_children = self.children_of(COINS_ROOT_ID)
        except Exception as e:
            LOGGER.error(f"Не удалось загрузить корень 'Монеты': {e}")
            return None
        # --- континент ---
        cont = (continent or '').strip().lower()
        frag = ''
        for c, f in CONTINENT_FRAGMENTS:
            if c in cont:
                frag = f
                break
        cont_node = self._find(root_children, frag) if frag else None
        if cont_node is None:
            cont_node = self._find_other(root_children) or \
                (root_children[0] if root_children else None)
        if cont_node is None:
            return None
        # --- страна ---
        try:
            cont_children = self.children_of(int(cont_node['id']))
        except Exception as e:
            LOGGER.error(f"Не удалось загрузить подразделы континента: {e}")
            cont_children = []
        country_node = self._find(cont_children, country) if country else None
        if country_node is None:
            country_node = self._find_other(cont_children) or cont_node
        # --- лист ---
        if country_node.get('subCategories'):
            try:
                leaves = self.children_of(int(country_node['id']))
            except Exception:
                leaves = []
            leaf = self._find_other(leaves) or self._first_leaf(leaves)
            if leaf is not None:
                return int(leaf['id'])
        return int(country_node['id'])