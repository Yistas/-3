# -*- coding: utf-8 -*-
"""
Скрипт для скачивания GeoJSON файла с границами стран
"""

import os
import sys
import requests
from pathlib import Path

def download_geojson():
    """Скачивает GeoJSON файл с границами стран"""
    data_dir = Path(__file__).parent
    output_path = data_dir / "world-countries.json"
    
    # URL с данными (используем репозиторий Folium)
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
    
    print(f"📥 Скачивание GeoJSON из {url}...")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Файл сохранён: {output_path}")
        print(f"   Размер: {len(response.content)} байт")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при скачивании: {e}")
        return False

if __name__ == "__main__":
    download_geojson()