# -*- coding: utf-8 -*-
"""
Парсер страниц монет ru.ucoin.net + сборка HTML-описания лота Meshok.
Без нейросетей: только разбор HTML страницы, открытой в браузере закупок.

Формат описания (HTML, теги, разрешённые Мешком):
- заголовок <h3>: «Продаю оригинальную монету: <Страна> <Номинал> <Год> года.»
- таблица характеристик (Страна, Номинал, Валюта, Год, Период, Правитель,
  Металл, Вес, Диаметр, Толщина, Гурт, Отношение авс/рев, Тираж, Каталог)
- строка «Описание:» (вторая строка шапки страницы, если есть)
- стандартный блок условий продажи (STANDARD_DESCRIPTION_HTML)
"""
import re
import html as _html
import logging

LOGGER = logging.getLogger('CoinCollector.UcoinDescription')

LABEL_MAP = {
    'описание гурта': 'edge_description',
    'каталожные номера': 'catalog',
    'монетный двор': 'mint',
    'год': 'year',
    'страна': 'country',
    'номинал': 'denomination',
    'валюта': 'currency',
    'материал': 'metal',
    'металл': 'metal',
    'вес': 'weight',
    'диаметр': 'diameter',
    'толщина': 'thickness',
    'гурт': 'edge',
    'форма': 'shape',
    'период': 'period',
    'правитель': 'ruler',
    'отношение авс/рев': 'alignment',
    'авс/рев': 'alignment',
    'orientation': 'alignment',
    'редкость': 'rarity',
}

# Стандартный блок условий продажи (добавляется в конец описания каждого лота)
STANDARD_DESCRIPTION_HTML = """
<div style="font-size: 13px; color: #333333; line-height: 1.5;">
<p style="margin: 0 0 8px 0;"><b>Спасибо за внимание к моим лотам.</b></p>
<p style="margin: 0 0 8px 0;">Оплату можно произвести на банковские карты Сбера, ТБанка, Райфайзен, ВТБ, Озон банков.</p>
<p style="margin: 0 0 8px 0;">За работу почты ответственность не несу, при розыске помогу с заявлениями и розыском. Страхуйте отправления. При порче отправления претензии принимаю только при фиксации повреждения в отделении в присутствии работника Почты. Лоты отправляются только после предоплаты (включая почтовые расходы).</p>
<p style="margin: 0 0 8px 0;">Личные встречи возможны при покупке от 500р, лоты объединяю.</p>
<p style="margin: 0;">Есть вопросы, пишите, договоримся.</p>
</div>
"""


def _clean(fragment):
    """Убирает теги из фрагмента HTML и схлопывает пробелы."""
    text = re.sub(r'<[^>]+>', ' ', fragment or '')
    text = _html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _esc(text):
    """Экранирует текст для безопасной вставки в HTML."""
    return _html.escape(str(text), quote=False)


def _with_unit(val, unit):
    """Добавляет единицу измерения, если значение — чисто число."""
    if not val:
        return None
    return f"{val} {unit}" if re.fullmatch(r'[\d.,]+', val.strip()) else val


def parse_coin_page(page_html):
    """Парсит HTML страницы монеты UCOIN.
    Возвращает словарь: year, country, denomination, currency, metal, weight,
    diameter, thickness, edge, edge_description, mint, period, ruler,
    alignment, catalog, mintage, title, subtitle (вторая строка шапки)."""
    data = {}
    if not page_html:
        return data

    # --- таблица характеристик (th/td) ---
    for m in re.finditer(r'<tr[^>]*>\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
                         page_html, re.S | re.I):
        label = _clean(m.group(1)).lower()
        value = _clean(m.group(2))
        if not value:
            continue
        for key, field in LABEL_MAP.items():
            if label.startswith(key) and field not in data:
                data[field] = value
                break

    # --- ШАПКА монеты: 1-я строка = название, 2-я строка = описание (серия) ---
    tm = re.search(r'<div class="h"[^>]*>(.*?)</div>', page_html, re.S)
    if not tm:
        tm = re.search(r'<h1[^>]*>(.*?)</h1>', page_html, re.S)
    if tm:
        block = tm.group(1)
        raw = re.sub(r'<[^>]+>', '\n', block)
        lines = [_clean(ln) for ln in raw.split('\n')]
        lines = [ln for ln in lines if ln]
        if lines:
            data['title'] = lines[0]
            if len(lines) > 1 and lines[1] != lines[0]:
                data['subtitle'] = lines[1]

    # --- тираж из таблицы tabMintage (первая строка с числами) ---
    mm = re.search(r'<div class="tabMintage".*?</table>', page_html, re.S)
    if mm:
        for r in re.findall(r'<tr[^>]*>(.*?)</tr>', mm.group(0), re.S):
            cells = [_clean(c) for c in
                     re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', r, re.S)]
            nums = [c for c in cells if re.search(r'\d', c)]
            if nums:
                data.setdefault('mintage', nums[-1])
                break
    return data


def build_description(d, fallback_country=None, fallback_year=None,
                      fallback_denomination=None, internal_id=None):
    """Собирает HTML-описание лота Meshok из распарсенных данных UCOIN.
    internal_id (если передан) — добавляется строкой «Артикул: ...»
    сразу после заголовка. В конец всегда добавляется стандартный блок."""
    country = d.get('country') or fallback_country or ''
    denom = d.get('denomination') or fallback_denomination or ''
    year = d.get('year') or (str(fallback_year) if fallback_year else '')
    head = f"Продаю оригинальную монету: {country} {denom} {year} года."
    head = re.sub(r'\s+', ' ', head).strip()

    # === Артикул: строка сразу после заголовка ===
    article_p = ''
    internal = str(internal_id or '').strip()
    if internal:
        article_p = (
            f'<p style="margin: 8px 0; font-size: 15px;">'
            f'<b>Артикул:</b> {_esc(internal)}</p>'
        )

    rows = [
        ('Страна', country),
        ('Номинал', denom),
        ('Валюта', d.get('currency')),
        ('Год', year),
        ('Период', d.get('period')),
        ('Правитель', d.get('ruler')),
        ('Металл', d.get('metal')),
        ('Вес', _with_unit(d.get('weight'), 'г')),
        ('Диаметр', _with_unit(d.get('diameter'), 'мм')),
        ('Толщина', _with_unit(d.get('thickness'), 'мм')),
        ('Гурт', ' '.join(x for x in (d.get('edge'), d.get('edge_description'))
                          if x) or None),
        ('Отношение авс/рев', d.get('alignment')),
        ('Тираж', d.get('mintage')),
        ('Каталог', d.get('catalog')),
    ]
    html_rows = []
    for label, val in rows:
        if val:
            html_rows.append(
                '<tr>'
                f'<td style="padding: 3px 14px 3px 0; color: #666666; '
                f'white-space: nowrap; vertical-align: top;">'
                f'<b>{_esc(label)}:</b></td>'
                f'<td style="padding: 3px 0; vertical-align: top;">'
                f'{_esc(val)}</td>'
                '</tr>')

    subtitle = (d.get('subtitle') or '').strip()
    desc_p = ''
    if subtitle and subtitle != (d.get('title') or '').strip():
        desc_p = (f'<p style="margin: 10px 0 0 0; font-size: 14px;">'
                  f'<b>Описание:</b> {_esc(subtitle)}</p>')

    html = (
        '<div style="font-family: Georgia, \'Times New Roman\', serif; '
        'max-width: 720px; color: #222222;">'
        f'<h3 style="margin: 0 0 4px 0; color: #1a3c6e; font-size: 17px;">'
        f'{_esc(head)}</h3>'
        + article_p +  # <-- ВОТ ЭТА СТРОКА ДОЛЖНА БЫТЬ
        '<table style="border-collapse: collapse; width: 100%; '
        'font-size: 14px; line-height: 1.45;">'
        + ''.join(html_rows) +
        '</table>'
        + desc_p +
        '<hr style="margin: 14px 0 10px 0; border: none; '
        'background-color: #cccccc; height: 1px;">'
        + STANDARD_DESCRIPTION_HTML +
        '</div>'
    )
    return html