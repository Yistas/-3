# -*- coding: utf-8 -*-
"""
Клиент API продавца Meshok.ru (sAPIv1).

Справка:
- URL: https://api.meshok.net/sAPIv1/<method>
- Авторизация: заголовок Authorization: Bearer <api_key>
- Запрос: POST, параметры x-www-form-urlencoded, UTF-8
- Ответ: JSON
"""
import logging
import requests

API_BASE = "https://api.meshok.net/sAPIv1/"
DEFAULT_API_KEY = "0595b5066eaa9d76a21de434b3f7518c"


class MeshokAPIError(Exception):
    """Ошибка ответа API Meshok"""

    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload


class MeshokSellerAPI:
    """Клиент API продавца Мешок"""

    def __init__(self, api_key=DEFAULT_API_KEY, timeout=30):
        self.logger = logging.getLogger('CoinCollector.MeshokAPI')
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers['Authorization'] = f'Bearer {api_key}'

    # ---------- базовый вызов ----------
    def _call(self, method, params=None):
        params = dict(params or {})
        url = API_BASE + method
        self.logger.info(f"➡️ POST {url} | параметры: {sorted(params.keys())}")
        try:
            resp = self._session.post(url, data=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise MeshokAPIError(f"Сеть: {e}")
        text = resp.text
        self.logger.info(f"⬅️ {resp.status_code} {text[:500]}")
        try:
            data = resp.json()
        except Exception:
            raise MeshokAPIError(f"Не-JSON ответ ({resp.status_code}): {text[:300]}")
        if isinstance(data, dict):
            err = (data.get('error') or data.get('errorText')
                   or data.get('errText'))
            if err and data.get('success') not in (1, None):
                raise MeshokAPIError(str(err), data)
        return data

    # ---------- информация ----------
    def get_account_info(self):
        """Информация об аккаунте продавца."""
        return self._call('getAccountInfo')

    def get_item_list(self):
        """Список активных лотов."""
        return self._call('getItemList')

    def get_finished_item_list(self):
        return self._call('getFinishedItemList')

    def get_unsold_finished_item_list(self):
        return self._call('getUnsoldFinishedItemList')

    def get_sold_finished_item_list(self):
        return self._call('getSoldFinishedItemList')

    def get_item_info(self, item_id):
        return self._call('getItemInfo', {'id': item_id})

    def get_common_description_list(self):
        return self._call('getCommonDescriptionList')

    def get_category_info(self, category_id):
        return self._call('getCategoryInfo', {'id': category_id})

    def get_sub_category(self, category_id):
        return self._call('getSubCategory', {'id': category_id})

    def get_currency_list(self):
        return self._call('getCurencyList')

    def get_country_list(self):
        return self._call('getCountryList')

    def get_cities_list(self, country_id):
        return self._call('getCitiesList', {'id': country_id})

    # ---------- категории (дерево и поиск) ----------
    def get_categories_tree(self, parent_id=0):
        """Возвращает подкатегории для указанного parent_id.
        parent_id=0 — корневые категории, parent_id=252 — подкатегории «Монет»."""
        return self._call('getSubCategory', {'id': str(parent_id)})

    def search_category_by_name(self, name_fragment, root_id=0, max_depth=4):
        """Ищет категории по фрагменту названия.
        Возвращает список [{'id': ..., 'name': ..., 'path': ...}, ...].
        При ошибке API возвращает пустой список (не падает)."""
        matches = []
        try:
            root = self.get_categories_tree(root_id)
            self._walk_categories(root, (name_fragment or '').lower(),
                                  matches, 0, max_depth, path='')
        except MeshokAPIError as e:
            self.logger.warning(f"Поиск категорий недоступен: {e}")
        except Exception as e:
            self.logger.warning(f"Ошибка поиска категорий: {e}")
        return matches

    def _walk_categories(self, node, needle, matches, depth, max_depth, path):
        """Рекурсивный обход дерева категорий (словари и списки)."""
        if depth > max_depth:
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                self._walk_categories(child, needle, matches,
                                      depth, max_depth, path)
            return
        if not isinstance(node, dict):
            return
        name = str(node.get('name') or node.get('title') or '').strip()
        cid = (node.get('id') or node.get('catId')
               or node.get('category_id'))
        cur_path = f"{path} > {name}" if path else name
        if name and cid is not None and needle in name.lower():
            matches.append({'id': cid, 'name': name, 'path': cur_path})
        for key in ('children', 'subcategories', 'sub',
                    'items', 'result', 'list'):
            if key in node:
                self._walk_categories(node[key], needle, matches,
                                      depth + 1, max_depth, cur_path)

    # ---------- управление лотами ----------
    def list_item(self, params):
        """Выставить лот на продажу. params — словарь параметров listItem."""
        return self._call('listItem', params)

    def update_item(self, params):
        return self._call('updateItem', params)

    def stop_sale(self, item_id):
        return self._call('stopSale', {'id': item_id})

    def relist_item(self, item_id):
        return self._call('relistItem', {'id': item_id})

    def delete_item(self, item_id):
        return self._call('deleteItem', {'id': item_id})

    # ---------- удобная обёртка для лота монеты ----------
    def list_coin_lot(self, name, category_id, description, price,
                      photo_urls=None, sale_type='auction', **extra):
        """Собрать и отправить лот монеты.
        photo_urls — список ПУБЛИЧНЫХ URL фото (photo1..photo10)."""
        params = {
            'name': (name or '')[:100],
            'category': category_id,
            'description': description or '',
            'price': price,
            'saleType': sale_type,
        }
        for i, url in enumerate((photo_urls or [])[:10], start=1):
            params[f'photo{i}'] = url
        params.update(extra)
        return self.list_item(params)


def test_connection(api_key=DEFAULT_API_KEY):
    """Быстрая проверка ключа: вернуть информацию об аккаунте."""
    api = MeshokSellerAPI(api_key)
    return api.get_account_info()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print(test_connection())