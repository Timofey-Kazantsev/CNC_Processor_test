import sys
import requests
import subprocess
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDialog, QVBoxLayout,
                             QLabel, QPushButton, QMessageBox, QProgressBar, QAction, QWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import hashlib

CURRENT_VERSION = "1.228"
GITHUB_REPO = "Timofey-Kazantsev/CNC_Processor_test"


class UpdateCheckThread(QThread):
    found_update = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=10)
            data = response.json()

            latest_version = data['tag_name'].replace('v', '')

            if latest_version > CURRENT_VERSION:
                self.found_update.emit({
                    'version': latest_version,
                    'body': data.get('body', 'Новые функции и исправления'),
                    'assets': data.get('assets', [])
                })
            else:
                self.error.emit("Установлена последняя версия")

        except Exception as e:
            self.error.emit(f"Не удалось проверить обновления: {e}")


class DownloadUpdateThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url, save_path):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=60)
            total = int(response.headers.get('content-length', 0))

            with open(self.save_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = int((downloaded / total) * 100)
                        self.progress.emit(percent)

            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(f"Ошибка скачивания: {e}")


class UpdateDialog(QDialog):
    def __init__(self, update_info):
        super().__init__()
        self.update_info = update_info
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Доступно обновление")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout()

        title = QLabel(f"🎉 Доступна версия {self.update_info['version']}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50;")
        layout.addWidget(title)

        body = QLabel(f"Что нового:\n{self.update_info['body']}")
        body.setWordWrap(True)
        layout.addWidget(body)

        info = QLabel("⚠ Будет скачан установщик. После скачивания закройте программу и запустите установщик.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()

        download_btn = QPushButton("📥 Скачать установщик")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        download_btn.clicked.connect(self.download_update)
        btn_layout.addWidget(download_btn)

        cancel_btn = QPushButton("Позже")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def download_update(self):
        if not self.update_info['assets']:
            QMessageBox.warning(self, "Ошибка", "Нет файла для скачивания")
            return

        setup_asset = None
        for asset in self.update_info['assets']:
            if 'Setup' in asset['name'] or 'setup' in asset['name']:
                setup_asset = asset
                break

        if not setup_asset:
            setup_asset = self.update_info['assets'][0]

        download_url = setup_asset['browser_download_url']
        save_path = os.path.join(os.environ['TEMP'], "CNC_Processor_Setup.exe")

        self.progress.setVisible(True)
        self.progress.setValue(0)

        self.download_thread = DownloadUpdateThread(download_url, save_path)
        self.download_thread.progress.connect(self.progress.setValue)
        self.download_thread.finished.connect(lambda path: self.on_download_finished(path))
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

    def on_download_finished(self, path):
        QMessageBox.information(
            self,
            "Готово",
            f"✅ Установщик скачан!\n\n"
            f"Расположение: {path}\n\n"
            f"1. Закройте программу\n"
            f"2. Запустите скачанный установщик\n"
            f"3. Он переустановит новую версию"
        )
        self.accept()
        subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def on_download_error(self, error):
        QMessageBox.critical(self, "Ошибка", f"❌ {error}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNC Processor")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        label = QLabel("CNC Processor v" + CURRENT_VERSION)
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label)

        QTimer.singleShot(3000, self.check_for_updates)

    def check_for_updates(self):
        self.check_thread = UpdateCheckThread()
        self.check_thread.found_update.connect(lambda data: UpdateDialog(data).exec_())
        self.check_thread.error.connect(lambda msg: print(f"Обновления: {msg}"))
        self.check_thread.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())