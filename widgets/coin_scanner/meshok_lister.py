# -*- coding: utf-8 -*-
"""Публикация лота на Meshok.ru через API продавца (sAPIv1).
Категории — из кэша (meshok_categories), путь: Монеты → Континент → Страна → лист.
Обязательные поля listItem по документации и ответам API:
name, category, saleType, curencyId, city, condition, quantity, longevity,
цена (startPrice для Auction / price для Sale), localDelivery(+Price),
delivery(+country/worldPrice), payment."""
import logging
import shutil
from pathlib import Path
from utils.meshok_api import MeshokSellerAPI, MeshokAPIError

LOGGER = logging.getLogger('CoinCollector.Meshok')

CREATE_URL = 'https://meshok.net/create'
EDIT_URL_TPL = 'https://meshok.net/item/edit/{item_id}'
VIEW_URL_TPL = 'https://meshok.net/item/{item_id}'
FALLBACK_CATEGORY = 1798   # «Монеты → Другие» (лист)

# Значения по умолчанию для обязательных полей доставки/оплаты
DEFAULT_PAYMENT = 'CARD,SBP,DESC'          # хотя бы один способ оплаты
DEFAULT_LOCAL_DELIVERY = 'CHARGE'          # SELF | FREE | CHARGE
DEFAULT_LOCAL_DELIVERY_PRICE = '0.00'
DEFAULT_DELIVERY = 'COUNTRY'               # NO | COUNTRY | WORLD
DEFAULT_COUNTRY_DELIVERY_PRICE = '-1.00'   # -1.00 = бесплатно
DEFAULT_WORLD_DELIVERY_PRICE = '0.00'
DEFAULT_LONGEVITY_AUCTION = 7              # 3,5,7,10,14,21
DEFAULT_LONGEVITY_SALE = 30                # 30 или 100


class MeshokLister:
    def __init__(self, main_window):
        self.logger = logging.getLogger('CoinCollector.MeshokLister')
        self.main_window = main_window
        self.out_dir = Path(__file__).resolve().parents[2] / 'data' / 'meshok_listing'
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_internal_id(self, lot):
        """Артикул лота = №Зак + МЕСТО (МЕСТО может быть пустым).
        Берётся из lot['internal_id']; если пусто — достаём из БД по purchase_id
        (таблицы purchases / purchases_archive)."""
        internal = str(lot.get('internal_id') or '').strip()
        if internal:
            return internal
        purchase_id = lot.get('purchase_id')
        if not purchase_id:
            return ''
        db = getattr(self.main_window, 'db_manager', None)
        if db is None:
            return ''
        try:
            from database.models import Purchase, PurchaseArchive
            p = db.session.query(Purchase).get(purchase_id)
            if p is None:
                p = db.session.query(PurchaseArchive).get(purchase_id)
            if p is None:
                self.logger.warning(f"⚠️ Закупка {purchase_id} не найдена в БД")
                return ''
            num = str(getattr(p, 'purchase_number', None) or '').strip()
            place = str(getattr(p, 'location_found', None) or '').strip()
            internal = f"{num}_{place}" if num and place else (num or place)
            self.logger.info(f"🏷️ Артикул из БД: №Зак={num!r} + МЕСТО={place!r} → {internal!r}")
            return internal
        except Exception as e:
            self.logger.warning(f"Не удалось получить №Зак/МЕСТО из БД: {e}")
            return ''

    def prepare_lot(self, coin, title, price, description, obverse, reverse,
                    source=None):
        """Сохраняет фото (без перекодирования) и собирает словарь лота,
        включая internal_id (№Зак + МЕСТО)."""
        source = source or {}
        if coin is not None:
            prefix = f'coin_{getattr(coin, "id", 0) or 0}'
            country = getattr(getattr(coin, 'country', None), 'name', '') or ''
        else:
            pid = source.get('purchase_id')
            prefix = f'purchase_{pid}' if pid else 'lot'
            country = source.get('country', '') or ''
        ob_ext = Path(obverse).suffix or '.png'
        rv_ext = Path(reverse).suffix or '.png'
        ob = self.out_dir / f'{prefix}_obverse{ob_ext}'
        rv = self.out_dir / f'{prefix}_reverse{rv_ext}'
        shutil.copyfile(obverse, ob)
        shutil.copyfile(reverse, rv)
        lot = {
            'coin_id': getattr(coin, 'id', None),
            'purchase_id': source.get('purchase_id'),
            'internal_id': str(source.get('internal_id') or '').strip(),
            'title': title,
            'price': price,
            'description': description,
            'country': country,
            'continent': source.get('continent', ''),
            'obverse': str(ob),
            'reverse': str(rv),
        }
        # Страховка: если source не донёс артикул — достаём из БД
        if not lot['internal_id']:
            lot['internal_id'] = self._resolve_internal_id(lot)
        self.logger.info(f"🏷️ internal_id лота: {lot['internal_id']!r}")
        return lot
     
    def publish_via_api(self, lot, category_id=None, sale_type='auction',
                        city_id=None, currency='RUB', country_name=''):
        """Выставляет лот через API Meshok (listItem).
        internalId (Артикул) = №Зак + МЕСТО — отправляется всегда, если непустой."""
        from utils.meshok_api import MeshokAPIError
        from gui.widgets.coin_scanner.meshok_categories import MeshokCategoryCache
        api = MeshokSellerAPI()

        # --- категория из кэша ---
        if category_id is None:
            try:
                cache = MeshokCategoryCache(api)
                category_id = cache.resolve(
                    lot.get('continent', ''),
                    country_name or lot.get('country', ''))
            except Exception as e:
                self.logger.error(f"Ошибка разрешения категории: {e}")
                category_id = None
        if category_id is None:
            category_id = FALLBACK_CATEGORY

        # --- город из аккаунта ---
        if city_id is None:
            try:
                acc = api.get_account_info() or {}
                city_id = (acc.get('result') or {}).get('cityId')
            except Exception:
                city_id = None

        # --- фото: публичные ссылки Google Drive ---
        photo_urls = lot.get('picture_urls') or []
        photos_note = ''
        if not photo_urls:
            try:
                from utils.meshok_photo_host import upload_lot_photos
                photo_urls = upload_lot_photos(
                    lot.get('obverse'), lot.get('reverse'),
                    coin_id=lot.get('coin_id') or lot.get('purchase_id'))
                if photo_urls:
                    photos_note = (f"\n📤 Фото загружены на Google Drive "
                                   f"({len(photo_urls)} шт.) и прикреплены к лоту.")
                else:
                    photos_note = ("\n⚠️ Не удалось загрузить фото на Google Drive — "
                                   "лот создан без фото.")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки фото: {e}")
                photos_note = f"\n⚠️ Ошибка загрузки фото: {e}"

        is_auction = str(sale_type).lower() not in (
            'fixed', 'sale', 'offer', 'фиксированная цена')
        sale_val = 'Auction' if is_auction else 'Sale'
        cur_id = self._currency_id(api, currency)

        price_val = max(float(lot.get('price') or 0), 0.01)
        params = {
            'name': (lot.get('title') or '')[:100],
            'description': lot.get('description') or '',
            'category': int(category_id),
            'saleType': sale_val,
            'condition': 'used',
            'quantity': 1,
            'longevity': DEFAULT_LONGEVITY_AUCTION if is_auction
                         else DEFAULT_LONGEVITY_SALE,
            'localDelivery': DEFAULT_LOCAL_DELIVERY,
            'localDeliveryPrice': DEFAULT_LOCAL_DELIVERY_PRICE,
            'delivery': DEFAULT_DELIVERY,
            'countryDeliveryPrice': DEFAULT_COUNTRY_DELIVERY_PRICE,
            'worldDeliveryPrice': DEFAULT_WORLD_DELIVERY_PRICE,
            'payment': DEFAULT_PAYMENT,
        }
        if cur_id is not None:
            params['curencyId'] = cur_id
        if city_id:
            params['city'] = int(city_id)
        if photo_urls:
            params['pictures'] = ','.join(photo_urls[:10])

        # === АРТИКУЛ (internalId) = №Зак + МЕСТО ===
        internal_id = self._resolve_internal_id(lot)
        if internal_id:
            params['internalId'] = internal_id
            self.logger.info(f"🏷️ internalId отправлен в listItem: {internal_id!r}")
        else:
            self.logger.warning("⚠️ internalId пуст — поле «Артикул» не заполнится")

        if is_auction:
            params['startPrice'] = price_val
            params['notify'] = 'N'
            params['antisniper'] = 'N'
        else:
            params['price'] = price_val

        try:
            result = api.list_item(params)
        except MeshokAPIError as e:
            payload = getattr(e, 'payload', None) or {}
            return (False, f"Ошибка API Meshok: {e}\nОтвет: {payload}", None, None)
        except Exception as e:
            return (False, f"Сетевая ошибка: {e}", None, None)

        item_id = None
        if isinstance(result, dict):
            res = result.get('result') or {}
            item_id = (res.get('id') if isinstance(res, dict) else None) \
                or result.get('id') or result.get('item_id')
        success = isinstance(result, dict) and result.get('success') == 1

        if success and item_id:
            edit_url = EDIT_URL_TPL.format(item_id=item_id)
            view_url = VIEW_URL_TPL.format(item_id=item_id)
            return (True,
                    f"✅ Лот опубликован!\nID: {item_id}\nСсылка: {view_url}"
                    f"{photos_note}",
                    item_id, edit_url)
        err = ''
        if isinstance(result, dict):
            err = (result.get('error') or result.get('errorText')
                   or result.get('errText') or str(result))
        return (False, f"API вернул ошибку:\n{err}{photos_note}", None, None)

    @staticmethod
    def _currency_id(api, code='RUB'):
        """ID валюты по ISO-символу (RUB -> 2)."""
        try:
            resp = api.get_currency_list() or {}
            result = resp.get('result') if isinstance(resp, dict) else None
            items = result.values() if isinstance(result, dict) else (result or [])
            fallback = None
            for it in items:
                if not isinstance(it, dict):
                    continue
                if fallback is None:
                    fallback = it.get('id')
                if (it.get('symbol') or '').strip().upper() == code.upper():
                    return it.get('id')
            return fallback
        except Exception as e:
            LOGGER.warning(f"Не удалось получить ID валюты: {e}")
        return None

    def open_edit_page(self, item_id):
        self._open_url(EDIT_URL_TPL.format(item_id=item_id))

    def open_create_page(self, lot=None):
        self._open_url(CREATE_URL)

    def _open_url(self, url):
        opened = False
        try:
            bw = getattr(self.main_window, 'browser_tab', None)
            if bw is None:
                bw = getattr(self.main_window, 'embedded_browser', None)
            if bw is not None and hasattr(bw, 'add_new_tab'):
                bw.add_new_tab(url)
                opened = True
        except Exception as e:
            LOGGER.error(f"Не удалось открыть встроенный браузер: {e}")
        if not opened:
            import webbrowser
            webbrowser.open(url)