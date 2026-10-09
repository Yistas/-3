# -*- coding: utf-8 -*-

"""
Обработчики синхронизации с Google Drive
"""


class CloudHandlersMixin:
    """Примесь с методами синхронизации с Google Drive"""
    
    def show_gdrive_sync_dialog(self):
        """Открывает диалог управления синхронизацией с Google Drive"""
        try:
            from gui.dialogs.gdrive_sync_dialog import GDriveSyncDialog
            dialog = GDriveSyncDialog(self.gdrive_sync, self)
            dialog.exec()
        except ImportError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить диалог:\n{e}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {e}")
    
    def show_cloud_sync_settings(self):
        """Устаревший метод, оставлен для совместимости"""
        self.show_gdrive_sync_dialog()