# -*- coding: utf-8 -*-

"""
Менеджер резервного копирования для Coin Collector
"""

import os
import sys
import shutil
import json
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .backup_settings import BackupSettings
from utils.paths import paths


class BackupManager:
    """Класс для управления резервным копированием"""
    
    def __init__(self, settings: Optional[BackupSettings] = None):
        self.logger = logging.getLogger('CoinCollector.Backup')
        self.settings = settings or BackupSettings()
        
        # ===== ИСПРАВЛЕНО: используем paths для получения папки бекапов =====
        self.backup_dir = paths.get_backups_dir()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Папка для бекапов: {self.backup_dir.absolute()}")
        
        # ===== ИСПРАВЛЕНО: корневая папка проекта =====
        self.root_dir = paths.get_root_dir()
        self.logger.info(f"Корневая папка проекта: {self.root_dir}")
        
        # Загружаем настройки из менеджера
        self.config_files = self.settings.get_config_files()
        self.normal_backup_folders = self.settings.get_normal_folders()
        self.full_backup_folders = self.settings.get_full_folders()
        self.exclude_patterns = self.settings.get_exclude_patterns()
    
    def create_backup(self, backup_name=None, backup_type='normal'):
        """
        Создает резервную копию всех важных файлов
        
        Args:
            backup_name: имя бекапа (если None, генерируется автоматически)
            backup_type: тип бекапа ('normal' или 'full')
        
        Returns:
            str: путь к созданному бекапу или None в случае ошибки
        """
        try:
            # Генерируем имя бекапа
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{backup_type}_{timestamp}"
            else:
                # Очищаем имя от недопустимых символов
                backup_name = "".join(c for c in backup_name if c.isalnum() or c in "._- ")
                # Добавляем префикс типа, если его нет
                if not backup_name.startswith(('normal_', 'full_', 'auto_')):
                    backup_name = f"{backup_type}_{backup_name}"
            
            backup_path = self.backup_dir / f"{backup_name}.zip"
            
            self.logger.info(f"Создание {backup_type} резервной копии: {backup_path}")
            
            # Создаем ZIP архив
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Добавляем конфигурационные файлы из корня
                for file in self.config_files:
                    file_path = self.root_dir / file
                    if file_path.exists():
                        zipf.write(file_path, file)
                        self.logger.debug(f"Добавлен файл: {file}")
                    else:
                        self.logger.debug(f"Файл не найден (пропускаем): {file}")
                
                # Выбираем папки для бекапа в зависимости от типа
                if backup_type == 'full':
                    folders_to_backup = self.full_backup_folders
                else:
                    folders_to_backup = self.normal_backup_folders
                
                # Добавляем папки
                for folder in folders_to_backup:
                    folder_path = self.root_dir / folder
                    if folder_path.exists() and folder_path.is_dir():
                        self.logger.info(f"Добавление папки: {folder}")
                        self._add_folder_to_zip(zipf, folder_path, folder, backup_type)
                    else:
                        self.logger.debug(f"Папка не найдена (пропускаем): {folder}")
                
                # Сохраняем информацию о бекапе
                backup_info = {
                    'name': backup_name,
                    'type': backup_type,
                    'created': datetime.now().isoformat(),
                    'root_dir': str(self.root_dir),
                    'files': self.config_files,
                    'folders': folders_to_backup,
                    'version': '1.0',
                    'python_version': sys.version,
                    'settings': {
                        'auto_backup_enabled': self.settings.get('auto_backup_enabled'),
                        'max_backups': {
                            'auto': self.settings.get('max_auto_backups'),
                            'normal': self.settings.get('max_normal_backups'),
                            'full': self.settings.get('max_full_backups')
                        }
                    }
                }
                zipf.writestr('backup_info.json', json.dumps(backup_info, indent=2, ensure_ascii=False))
            
            # Проверяем размер бекапа
            if backup_path.exists():
                backup_size = backup_path.stat().st_size
                self.logger.info(f"✅ Резервная копия создана: {backup_path} ({self._format_size(backup_size)})")
                
                # Обновляем время последнего авто-бекапа
                if backup_type == 'auto' or backup_name.startswith('auto_'):
                    self.settings.update_last_auto_backup()
                
                return str(backup_path)
            else:
                self.logger.error("❌ Файл бекапа не создан")
                return None
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при создании бекапа: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def _add_folder_to_zip(self, zipf, folder_path, arc_prefix, backup_type):
        """Добавляет папку в ZIP архив с исключениями"""
        try:
            added_count = 0
            skipped_count = 0
            
            for root, dirs, files in os.walk(folder_path):
                root_path = Path(root)
                
                # Исключаем ненужные папки
                dirs[:] = [d for d in dirs if not self._should_exclude(d, root_path, backup_type)]
                
                for file in files:
                    file_path = root_path / file
                    
                    # Проверяем, нужно ли исключить файл
                    if self._should_exclude(file, root_path, backup_type):
                        skipped_count += 1
                        continue
                    
                    try:
                        # Получаем путь относительно корня проекта
                        rel_path = file_path.relative_to(self.root_dir)
                        arc_name = str(rel_path)
                        
                        if added_count % 100 == 0:
                            self.logger.debug(f"Добавление файла {added_count}: {arc_name}")
                        
                        zipf.write(file_path, arc_name)
                        added_count += 1
                        
                    except ValueError:
                        # Ошибка возникает, если файл не находится в корневой папке
                        try:
                            arc_name = str(file_path.absolute()).replace(':', '').replace('\\', '/')
                            zipf.write(file_path, arc_name)
                            added_count += 1
                        except:
                            skipped_count += 1
                            
                    except PermissionError:
                        self.logger.debug(f"Файл занят, пропускаем: {file_path}")
                        skipped_count += 1
                    except Exception as e:
                        self.logger.debug(f"Ошибка при добавлении {file_path}: {e}")
                        skipped_count += 1
            
            self.logger.info(f"Папка {arc_prefix}: добавлено {added_count} файлов, пропущено {skipped_count}")
                        
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении папки {folder_path}: {e}")
    
    def _should_exclude(self, name, path, backup_type):
        """Проверяет, нужно ли исключить файл/папку"""
        path_str = str(path)
        
        # Всегда исключаем папку с бекапами
        if 'backups' in path_str.split(os.sep):
            return True
        
        # Всегда исключаем эти паттерны
        for pattern in self.exclude_patterns:
            if pattern.endswith('*'):
                if name.endswith(pattern[:-1]):
                    return True
            elif name == pattern:
                return True
        
        # Для обычного бекапа исключаем логи и venv
        if backup_type == 'normal':
            if 'logs' in path_str.split(os.sep) or 'venv' in path_str.split(os.sep):
                return True
            if name.endswith('.log'):
                return True
        
        return False
    
    def restore_backup(self, backup_path, restore_type='normal'):
        """Восстанавливает данные из резервной копии"""
        try:
            backup_path = Path(backup_path)
            if not backup_path.exists():
                self.logger.error(f"Файл бекапа не найден: {backup_path}")
                return False
            
            self.logger.info(f"Восстановление из бекапа: {backup_path}")
            
            # Создаем временную папку для распаковки
            temp_dir = self.backup_dir / "temp_restore"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            try:
                # Распаковываем архив
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # Восстанавливаем корневые файлы
                for file in self.config_files:
                    src = temp_dir / file
                    if src.exists():
                        dst = self.root_dir / file
                        if dst.exists():
                            backup_file = dst.with_suffix('.bak')
                            shutil.copy2(dst, backup_file)
                            self.logger.debug(f"Создана резервная копия: {backup_file}")
                        shutil.copy2(src, dst)
                        self.logger.info(f"Восстановлен файл: {file}")
                
                # Восстанавливаем папки
                folders_to_restore = self.normal_backup_folders
                if restore_type == 'full':
                    folders_to_restore = self.full_backup_folders
                
                for folder in folders_to_restore:
                    src = temp_dir / folder
                    if src.exists() and src.is_dir():
                        dst = self.root_dir / folder
                        
                        # Создаем резервную копию текущей папки
                        if dst.exists():
                            backup_folder = dst.parent / f"{folder}_bak"
                            if backup_folder.exists():
                                shutil.rmtree(backup_folder)
                            shutil.copytree(dst, backup_folder)
                            self.logger.debug(f"Создана резервная копия папки: {backup_folder}")
                            
                            # Удаляем текущую папку
                            shutil.rmtree(dst)
                        
                        # Восстанавливаем из бекапа
                        shutil.copytree(src, dst)
                        self.logger.info(f"Восстановлена папка: {folder}")
                
                self.logger.info("✅ Восстановление успешно завершено")
                
                # Показываем уведомление, если включено
                if self.settings.should_notify('restore'):
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(None, "Успех", "Данные успешно восстановлены.")
                
                return True
                
            finally:
                # Удаляем временную папку
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка при восстановлении из бекапа: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def list_backups(self):
        """Возвращает список доступных бекапов"""
        backups = []
        try:
            for file in sorted(self.backup_dir.glob("*.zip"), reverse=True):
                try:
                    stat = file.stat()
                    size = stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Определяем тип бекапа по имени
                    backup_type = 'normal'
                    if file.stem.startswith('full_'):
                        backup_type = 'full'
                    elif file.stem.startswith('auto_'):
                        backup_type = 'auto'
                    
                    info = {
                        'path': str(file),
                        'name': file.stem,
                        'type': backup_type,
                        'size': size,
                        'size_str': self._format_size(size),
                        'modified': modified,
                        'modified_str': modified.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Пробуем прочитать backup_info.json из архива
                    try:
                        with zipfile.ZipFile(file, 'r') as zipf:
                            if 'backup_info.json' in zipf.namelist():
                                with zipf.open('backup_info.json') as f:
                                    backup_info = json.load(f)
                                    info['created'] = backup_info.get('created', '')
                                    info['version'] = backup_info.get('version', '1.0')
                                    info['type'] = backup_info.get('type', backup_type)
                    except:
                        pass
                    
                    backups.append(info)
                    
                except Exception as e:
                    self.logger.error(f"Ошибка при чтении бекапа {file}: {e}")
            
            self.logger.debug(f"Найдено {len(backups)} бекапов")
            return backups
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении списка бекапов: {e}")
            return []
    
    def create_auto_backup(self):
        """Создает автоматический бекап при запуске программы"""
        try:
            # Проверяем, нужно ли создавать авто-бекап
            if not self.settings.should_create_auto_backup():
                self.logger.info("Автоматический бекап не требуется (интервал еще не прошел)")
                return False
            
            self.logger.info("Создание автоматического бекапа...")
            backup_path = self.create_backup(backup_type='auto')
            
            if backup_path:
                self.logger.info("✅ Автоматический бекап создан")
                
                # Удаляем старые бекапы
                self._cleanup_old_backups('auto', self.settings.get_max_backups('auto'))
                self._cleanup_old_backups('normal', self.settings.get_max_backups('normal'))
                self._cleanup_old_backups('full', self.settings.get_max_backups('full'))
                
                # Показываем уведомление, если включено
                if self.settings.should_notify('backup'):
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(None, "Бекап создан", 
                        f"Автоматический бекап успешно создан:\n{backup_path}")
                
                return True
            else:
                self.logger.warning("Не удалось создать автоматический бекап")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка при создании автоматического бекапа: {e}")
            return False
    
    def _cleanup_old_backups(self, prefix='auto', keep=5):
        """Удаляет старые бекапы с указанным префиксом"""
        try:
            backups = sorted(
                [f for f in self.backup_dir.glob(f"{prefix}_*.zip")],
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            deleted = 0
            for old_backup in backups[keep:]:
                old_backup.unlink()
                self.logger.info(f"Удален старый бекап: {old_backup.name}")
                deleted += 1
            
            if deleted > 0:
                self.logger.info(f"Очистка завершена: удалено {deleted} старых бекапов")
                
        except Exception as e:
            self.logger.error(f"Ошибка при очистке старых бекапов: {e}")
    
    def _format_size(self, size):
        """Форматирует размер файла в читаемый вид"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"