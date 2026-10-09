# -*- coding: utf-8 -*-
"""
Сканер монет: Canon LiDE 220 и др.
Бэкенды (по приоритету):
1) WIA через pywin32;
2) WIA через PowerShell COM (без pywin32);
3) scanimage (SANE, Linux);
4) импорт файла (вручную).

Поддержка скана ЧАСТИ планшета (rect = доли (x, y, w, h) от планшета):
четверть/половина листа сканируется быстрее и даёт меньший файл.
Автокроп первой (верхней-левой) монеты: квадрат по контуру + margin_mm.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

LOGGER = logging.getLogger('CoinCollector.Scanner')
WIA_FORMAT_BMP = '{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}'

PS_LIST_SCRIPT = r'''
$dm = New-Object -ComObject WIA.DeviceManager
$found = 0
foreach ($info in $dm.DeviceInfos) { if ($info.Type -eq 1) { $found = 1; break } }
exit $found
'''

PS_SCAN_SCRIPT = r'''
param([string]$OutPath, [int]$Dpi = 600,
      [double]$Fx = 0, [double]$Fy = 0, [double]$Fw = 1, [double]$Fh = 1)
$ErrorActionPreference = "Stop"
$dm = New-Object -ComObject WIA.DeviceManager
$device = $null
foreach ($info in $dm.DeviceInfos) {
    if ($info.Type -eq 1) { $device = $info.Connect(); break }
}
if ($device -eq $null) { Write-Error "SCANNER_NOT_FOUND"; exit 3 }
$item = $device.Items.Item(1)
try {
    $item.Properties.Item("Horizontal Resolution").Value = $Dpi
    $item.Properties.Item("Vertical Resolution").Value = $Dpi
    $bedW = $item.Properties.Item("Horizontal Bed Size").Value
    $bedH = $item.Properties.Item("Vertical Bed Size").Value
    $item.Properties.Item("Horizontal Position").Value = [int]($bedW * $Fx)
    $item.Properties.Item("Vertical Position").Value = [int]($bedH * $Fy)
    $item.Properties.Item("Horizontal Extent").Value = [int]($bedW * $Fw)
    $item.Properties.Item("Vertical Extent").Value = [int]($bedH * $Fh)
} catch { }
if (Test-Path $OutPath) { Remove-Item $OutPath -Force }
$img = $item.Transfer("%s")
$img.SaveFile($OutPath)
exit 0
''' % WIA_FORMAT_BMP


def _find_powershell():
    if os.name != 'nt':
        return None
    candidates = [
        r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
        r'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        r = subprocess.run(['where', 'powershell'], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split('\n')[0].strip()
    except Exception:
        pass
    return None


class WiaScanner:
    """Windows WIA через pywin32."""
    name = 'WIA (pywin32)'

    def available(self):
        try:
            import win32com.client  # noqa
            dm = win32com.client.Dispatch('WIA.DeviceManager')
            for i in range(1, dm.DeviceInfos.Count + 1):
                if int(dm.DeviceInfos(i).Type) == 1:
                    return True
            return False
        except ImportError:
            return False
        except Exception:
            return False

    def _connect(self):
        import win32com.client
        dm = win32com.client.Dispatch('WIA.DeviceManager')
        for i in range(1, dm.DeviceInfos.Count + 1):
            info = dm.DeviceInfos(i)
            if int(info.Type) == 1:
                return info.Connect()
        raise RuntimeError('Сканер не найден (WIA)')

    def scan_to_file(self, path, dpi=600, rect=None):
        """rect = (fx, fy, fw, fh) — доли планшета; None = весь лист."""
        device = self._connect()
        item = device.Items(1)
        try:
            props = item.Properties
            props('Horizontal Resolution').Value = float(dpi)
            props('Vertical Resolution').Value = float(dpi)
            bed_w = props('Horizontal Bed Size').Value
            bed_h = props('Vertical Bed Size').Value
            if rect:
                fx, fy, fw, fh = rect
                props('Horizontal Position').Value = int(bed_w * fx)
                props('Vertical Position').Value = int(bed_h * fy)
                props('Horizontal Extent').Value = max(1, int(bed_w * fw))
                props('Vertical Extent').Value = max(1, int(bed_h * fh))
            else:
                props('Horizontal Position').Value = 0
                props('Vertical Position').Value = 0
                props('Horizontal Extent').Value = bed_w
                props('Vertical Extent').Value = bed_h
        except Exception as e:
            LOGGER.warning(f"Не удалось задать область скана: {e}")
        img = item.Transfer(WIA_FORMAT_BMP)
        bmp = path + '.bmp'
        img.SaveFile(bmp)
        from PIL import Image
        Image.open(bmp).save(path)
        Path(bmp).unlink(missing_ok=True)
        return path


class PowerShellWiaScanner:
    """Windows WIA через PowerShell COM — НЕ требует pywin32."""
    name = 'WIA (PowerShell)'

    def __init__(self):
        self._ps_path = _find_powershell()

    def available(self):
        if os.name != 'nt' or not self._ps_path:
            return False
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.ps1', delete=False,
                                               encoding='utf-8-sig') as f:
                f.write(PS_LIST_SCRIPT)
                script = f.name
            r = subprocess.run(
                [self._ps_path, '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-File', script],
                capture_output=True, timeout=20)
            Path(script).unlink(missing_ok=True)
            return r.returncode == 1
        except Exception as e:
            LOGGER.warning(f"PowerShell WIA недоступен: {e}")
            return False

    def scan_to_file(self, path, dpi=600, rect=None):
        if not self._ps_path:
            raise RuntimeError("PowerShell не найден")
        fx, fy, fw, fh = rect if rect else (0.0, 0.0, 1.0, 1.0)
        with tempfile.NamedTemporaryFile('w', suffix='.ps1', delete=False,
                                           encoding='utf-8-sig') as f:
            f.write(PS_SCAN_SCRIPT)
            script = f.name
        try:
            r = subprocess.run(
                [self._ps_path, '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-File', script, '-OutPath', path, '-Dpi', str(int(dpi)),
                 '-Fx', str(fx), '-Fy', str(fy), '-Fw', str(fw), '-Fh', str(fh)],
                capture_output=True, timeout=180, text=True)
            if r.returncode == 3:
                raise RuntimeError('Сканер не найден (WIA). Проверьте подключение.')
            if r.returncode != 0 or not Path(path).exists():
                raise RuntimeError(f"Ошибка сканирования (код {r.returncode}): "
                                   f"{(r.stderr or '').strip()[:300]}")
            return path
        finally:
            Path(script).unlink(missing_ok=True)


class SaneScanner:
    """Linux/SANE (область задаётся в мм: планшет ~216×297 мм)."""
    name = 'SANE (scanimage)'

    def available(self):
        try:
            r = subprocess.run(['scanimage', '-V'], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def scan_to_file(self, path, dpi=600, rect=None):
        cmd = ['scanimage', '--resolution', str(dpi), '--format=png', '-o', path]
        if rect:
            fx, fy, fw, fh = rect
            bed_w, bed_h = 216.0, 297.0
            cmd += ['-l', f'{bed_w * fx:.1f}', '-t', f'{bed_h * fy:.1f}',
                    '-x', f'{bed_w * fw:.1f}', '-y', f'{bed_h * fh:.1f}']
        subprocess.run(cmd, check=True, timeout=180)
        return path


class FileImporter:
    """Ручной импорт файла (кнопка «📁 Выбрать файл…»)."""
    name = 'Импорт файла (сканер не найден)'

    def available(self):
        return True

    def scan_to_file(self, path, dpi=600, rect=None):
        from PySide6.QtWidgets import QFileDialog
        src, _ = QFileDialog.getOpenFileName(
            None, 'Выберите фото стороны монеты', '',
            'Изображения (*.png *.jpg *.jpeg *.bmp *.webp)')
        if not src:
            raise RuntimeError('Отменено пользователем')
        from PIL import Image
        Image.open(src).save(path)
        return path


def get_backend():
    for cls in (WiaScanner, PowerShellWiaScanner, SaneScanner):
        try:
            b = cls()
            if b.available():
                LOGGER.info(f"🖨️ Выбран бэкенд сканера: {b.name}")
                return b
        except Exception:
            continue
    LOGGER.warning("⚠️ Сканер не найден — включён режим импорта файла")
    return FileImporter()


def crop_coin(src_path, out_path, dpi=600, margin_mm=5.0):
    """Вырезает ПЕРВУЮ монету (верхняя-левая) из скана: компоненты связности,
    фильтр «похожести на монету», квадрат по контуру + margin_mm, без ресайза."""
    from PIL import Image
    import numpy as np
    from collections import deque

    img = Image.open(src_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    gray = np.asarray(img.convert('L'), dtype=np.float32)
    h, w = gray.shape

    edge = max(2, min(h, w) // 50)
    ring = np.concatenate([gray[:edge, :].ravel(), gray[-edge:, :].ravel(),
                           gray[:, :edge].ravel(), gray[:, -edge:].ravel()])
    bg = float(np.median(ring))
    mask = np.abs(gray - bg) > 25

    k = max(1, int(min(h, w) / 400))
    small = mask[::k, ::k]
    sh, sw = small.shape
    small_flat = small.ravel()
    visited = bytearray(sh * sw)
    comps = []
    for start in np.flatnonzero(small_flat):
        if visited[start]:
            continue
        q = deque([start])
        visited[start] = 1
        pix = [start]
        while q:
            cur = q.popleft()
            y, x = divmod(cur, sw)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < sh and 0 <= nx < sw:
                    nidx = ny * sw + nx
                    if not visited[nidx] and small_flat[nidx]:
                        visited[nidx] = 1
                        q.append(nidx)
                        pix.append(nidx)
        ys = [p // sw for p in pix]
        xs = [p % sw for p in pix]
        comps.append({'t': min(ys), 'b': max(ys),
                      'l': min(xs), 'r': max(xs), 'n': len(pix)})

    min_side_s = max(2, int(10 / 25.4 * dpi / k))
    max_side_s = max(6, int(100 / 25.4 * dpi / k))

    def looks_like_coin(c, strict):
        bw = c['r'] - c['l'] + 1
        bh = c['b'] - c['t'] + 1
        if not (min_side_s <= bw <= max_side_s and min_side_s <= bh <= max_side_s):
            return False
        if not (0.5 <= bw / bh <= 2.0):
            return False
        if c['n'] / (bw * bh) < 0.45:
            return False
        if strict:
            if c['t'] <= 0 or c['l'] <= 0 or c['b'] >= sh - 1 or c['r'] >= sw - 1:
                return False
        return True

    chosen = None
    for strict in (True, False):
        cand = [c for c in comps if looks_like_coin(c, strict)]
        if cand:
            cand.sort(key=lambda c: (c['t'], c['l']))
            chosen = cand[0]
            break
    if chosen is None:
        rows = np.where(mask.sum(axis=1) > 0)[0]
        cols = np.where(mask.sum(axis=0) > 0)[0]
        if rows.size == 0:
            img.save(out_path)
            return out_path
        t_f, b_f, l_f, r_f = rows[0], rows[-1], cols[0], cols[-1]
    else:
        t_f = chosen['t'] * k
        l_f = chosen['l'] * k
        b_f = (chosen['b'] + 1) * k - 1
        r_f = (chosen['r'] + 1) * k - 1

    margin = int(margin_mm / 25.4 * dpi)
    side = max(r_f - l_f + 1, b_f - t_f + 1) + 2 * margin
    cy = (t_f + b_f) // 2
    cx = (l_f + r_f) // 2
    y0 = cy - side // 2
    x0 = cx - side // 2
    pad_top = max(0, -y0)
    pad_left = max(0, -x0)
    pad_bottom = max(0, y0 + side - h)
    pad_right = max(0, x0 + side - w)
    y0 = max(0, y0)
    x0 = max(0, x0)
    y1 = min(h, y0 + side)
    x1 = min(w, x0 + side)
    cropped = img.crop((x0, y0, x1, y1))
    if pad_top or pad_left or pad_bottom or pad_right:
        bg_int = int(max(0, min(255, bg)))
        canvas = Image.new('RGB', (side, side), (bg_int, bg_int, bg_int))
        canvas.paste(cropped, (pad_left, pad_top))
        cropped = canvas
    if str(out_path).lower().endswith(('.jpg', '.jpeg')):
        cropped.save(out_path, quality=95, subsampling=0)
    else:
        cropped.save(out_path)
    return out_path