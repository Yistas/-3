# ===== utils/password_manager.py =====
# ИСПРАВИТЬ ИМПОРТЫ

# -*- coding: utf-8 -*-

"""
Менеджер для безопасного хранения паролей
"""

import os
import json
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from pathlib import Path


class PasswordManager:
    """Класс для безопасного хранения паролей"""
    
    def __init__(self, key_file="password.key", data_file="passwords.enc"):
        self.logger = logging.getLogger('CoinCollector.PasswordManager')
        self.key_file = Path(key_file)
        self.data_file = Path(data_file)
        self.cipher = None
        self._init_cipher()
    
    def _init_cipher(self):
        """Инициализирует шифр"""
        if self.key_file.exists():
            # Загружаем существующий ключ
            try:
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                self.cipher = Fernet(key)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки ключа: {e}")
                self._create_new_key()
        else:
            self._create_new_key()
    
    def _create_new_key(self):
        """Создает новый ключ шифрования"""
        try:
            # Генерируем ключ из системной информации
            import platform
            import socket
            
            system_info = f"{platform.node()}{platform.processor()}{socket.gethostname()}".encode()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'coin_collector_salt_2024',
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(system_info))
            self.cipher = Fernet(key)
            
            # Сохраняем ключ
            with open(self.key_file, 'wb') as f:
                f.write(key)
            self.logger.info("✅ Создан новый ключ шифрования")
        except Exception as e:
            self.logger.error(f"Ошибка создания ключа: {e}")
            # Запасной вариант - генерируем случайный ключ
            self.cipher = Fernet(Fernet.generate_key())
            with open(self.key_file, 'wb') as f:
                f.write(self.cipher._signing_key)
    
    def save_password(self, service, username, password):
        """Сохраняет пароль для сервиса"""
        try:
            # Загружаем существующие данные
            data = self._load_data()
            
            from datetime import datetime
            # Обновляем данные
            data[service] = {
                'username': username,
                'password': password,
                'updated_at': str(datetime.now())
            }
            
            # Сохраняем зашифрованные данные
            self._save_data(data)
            self.logger.info(f"✅ Сохранен пароль для {service}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения пароля: {e}")
            return False
    
    def get_password(self, service):
        """Получает пароль для сервиса"""
        try:
            data = self._load_data()
            if service in data:
                return data[service]['username'], data[service]['password']
            return None, None
        except Exception as e:
            self.logger.error(f"Ошибка получения пароля: {e}")
            return None, None
    
    def delete_password(self, service):
        """Удаляет пароль для сервиса"""
        try:
            data = self._load_data()
            if service in data:
                del data[service]
                self._save_data(data)
                self.logger.info(f"✅ Удален пароль для {service}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка удаления пароля: {e}")
            return False
    
    def _load_data(self):
        """Загружает зашифрованные данные"""
        if not self.data_file.exists():
            return {}
        
        try:
            with open(self.data_file, 'rb') as f:
                encrypted_data = f.read()
            decrypted = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            self.logger.error(f"Ошибка загрузки данных: {e}")
            return {}
    
    def _save_data(self, data):
        """Сохраняет зашифрованные данные"""
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            encrypted = self.cipher.encrypt(json_str.encode('utf-8'))
            with open(self.data_file, 'wb') as f:
                f.write(encrypted)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения данных: {e}")
            return False
    
    def has_password(self, service):
        """Проверяет, сохранен ли пароль для сервиса"""
        data = self._load_data()
        return service in data