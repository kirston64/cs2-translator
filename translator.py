"""
CS2 Auto Translator
Перехватывает Ctrl+Shift+T, переводит текст из чата CS2 и отправляет перевод.
"""

import sys
import time
import threading
import pyperclip
import keyboard
import pyautogui
from deep_translator import GoogleTranslator
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QSystemTrayIcon, QMenu, QAction,
    QFrame, QTextEdit, QCheckBox, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QPainter, QBrush, QPen


# Поддерживаемые языки
LANGUAGES = {
    "English": "en",
    "Ukrainian": "uk",
    "German": "de",
    "French": "fr",
    "Spanish": "es",
    "Portuguese": "pt",
    "Italian": "it",
    "Polish": "pl",
    "Turkish": "tr",
    "Chinese": "zh-CN",
    "Japanese": "ja",
    "Korean": "ko",
    "Czech": "cs",
    "Swedish": "sv",
    "Danish": "da",
    "Finnish": "fi",
    "Norwegian": "no",
    "Dutch": "nl",
    "Romanian": "ro",
    "Hungarian": "hu",
    "Bulgarian": "bg",
    "Serbian": "sr",
    "Croatian": "hr",
    "Greek": "el",
    "Arabic": "ar",
    "Thai": "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
    "Malay": "ms",
    "Filipino": "tl",
}

SOURCE_LANG = "ru"


def create_icon_pixmap(size=64, color="#6C5CE7"):
    """Создаёт иконку программатически."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(QPen(Qt.NoPen))
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 12, 12)
    painter.setPen(QPen(QColor("white")))
    font = QFont("Segoe UI", size // 3, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    painter.end()
    return pixmap


class TranslatorSignals(QObject):
    """Сигналы для потокобезопасного обновления UI."""
    log_message = pyqtSignal(str)
    status_update = pyqtSignal(str)


class TranslatorCore:
    """Ядро переводчика — перевод + ввод в CS2."""

    def __init__(self, signals):
        self.signals = signals
        self.target_lang = "en"
        self.enabled = True
        self._translator_cache = {}
        self._lock = threading.Lock()

    def get_translator(self, target):
        if target not in self._translator_cache:
            self._translator_cache[target] = GoogleTranslator(
                source=SOURCE_LANG, target=target
            )
        return self._translator_cache[target]

    def translate_and_send(self):
        """Основной цикл: копировать текст, перевести, вставить, отправить."""
        if not self.enabled:
            return

        with self._lock:
            try:
                # Сохраняем текущий буфер обмена
                old_clipboard = ""
                try:
                    old_clipboard = pyperclip.paste()
                except Exception:
                    pass

                # Задержка чтобы модификаторы отпустились
                time.sleep(0.15)

                # Отпускаем все клавиши чтобы не мешали
                keyboard.release("ctrl")
                keyboard.release("shift")
                time.sleep(0.05)

                # Выделяем весь текст в поле ввода чата CS2
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.08)

                # Копируем
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.1)

                # Читаем скопированный текст
                text = pyperclip.paste().strip()

                if not text or text == old_clipboard.strip():
                    self.signals.log_message.emit("[!] Пустой текст или не удалось скопировать")
                    return

                self.signals.log_message.emit(f"[RU] {text}")
                self.signals.status_update.emit("Перевожу...")

                # Переводим
                translator = self.get_translator(self.target_lang)
                translated = translator.translate(text)

                if not translated:
                    self.signals.log_message.emit("[!] Ошибка перевода")
                    self.signals.status_update.emit("Готов")
                    return

                self.signals.log_message.emit(f"[{self.target_lang.upper()}] {translated}")

                # Выделяем старый текст и вставляем перевод
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
                pyperclip.copy(translated)
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.08)

                # Отправляем сообщение
                pyautogui.press("enter")

                self.signals.status_update.emit("Готов")
                self.signals.log_message.emit("--- Отправлено ---")

                # Восстанавливаем буфер обмена
                time.sleep(0.1)
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

            except Exception as e:
                self.signals.log_message.emit(f"[ERROR] {e}")
                self.signals.status_update.emit("Ошибка")


STYLESHEET = """
QMainWindow {
    background-color: #1a1a2e;
}
QWidget#central {
    background-color: #1a1a2e;
}
QLabel {
    color: #e0e0e0;
    font-family: "Segoe UI", sans-serif;
}
QLabel#title {
    color: #6C5CE7;
    font-size: 22px;
    font-weight: bold;
    font-family: "Segoe UI", sans-serif;
}
QLabel#subtitle {
    color: #888;
    font-size: 11px;
}
QLabel#status {
    color: #00b894;
    font-size: 13px;
    font-weight: bold;
    padding: 4px 12px;
    background-color: rgba(0, 184, 148, 30);
    border-radius: 8px;
}
QLabel#status[error="true"] {
    color: #ff7675;
    background-color: rgba(255, 118, 117, 30);
}
QComboBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-family: "Segoe UI", sans-serif;
    min-width: 180px;
}
QComboBox:hover {
    border: 1px solid #6C5CE7;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #6C5CE7;
    border: 1px solid #333;
    border-radius: 4px;
}
QPushButton#toggle {
    background-color: #6C5CE7;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: bold;
    font-family: "Segoe UI", sans-serif;
}
QPushButton#toggle:hover {
    background-color: #7f6ff0;
}
QPushButton#toggle[active="false"] {
    background-color: #e74c3c;
}
QPushButton#toggle[active="false"]:hover {
    background-color: #ff6b6b;
}
QTextEdit#log {
    background-color: #0f0f23;
    color: #a0a0c0;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 8px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}
QFrame#separator {
    background-color: #2a2a4a;
    max-height: 1px;
}
QCheckBox {
    color: #e0e0e0;
    font-family: "Segoe UI", sans-serif;
    font-size: 12px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #444;
    background-color: #16213e;
}
QCheckBox::indicator:checked {
    background-color: #6C5CE7;
    border: 1px solid #6C5CE7;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.signals = TranslatorSignals()
        self.core = TranslatorCore(self.signals)
        self.hotkey_registered = False

        self.setWindowTitle("CS2 Translator")
        self.setFixedSize(420, 520)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._init_ui()
        self._connect_signals()
        self._setup_tray()
        self._register_hotkey()

        # Для перетаскивания окна
        self._drag_pos = None

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Заголовок + кнопка закрытия
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("CS2 Translator")
        title.setObjectName("title")
        title_col.addWidget(title)
        subtitle = QLabel("Ctrl+Shift+T  -  перевод и отправка")
        subtitle.setObjectName("subtitle")
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()

        # Кнопка свернуть в трей
        minimize_btn = QPushButton("_")
        minimize_btn.setFixedSize(30, 30)
        minimize_btn.setStyleSheet("""
            QPushButton { background: #2a2a4a; color: #888; border: none; border-radius: 6px; font-size: 16px; }
            QPushButton:hover { background: #6C5CE7; color: white; }
        """)
        minimize_btn.clicked.connect(self._to_tray)
        header.addWidget(minimize_btn)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton { background: #2a2a4a; color: #888; border: none; border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #e74c3c; color: white; }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Разделитель
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # Выбор языка
        lang_row = QHBoxLayout()
        lang_label = QLabel("Перевод на:")
        lang_label.setStyleSheet("font-size: 13px;")
        lang_row.addWidget(lang_label)

        self.lang_combo = QComboBox()
        for name in LANGUAGES:
            self.lang_combo.addItem(name, LANGUAGES[name])
        self.lang_combo.setCurrentIndex(0)  # English по умолчанию
        self.lang_combo.currentIndexChanged.connect(self._on_lang_change)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        # Статус
        status_row = QHBoxLayout()
        status_label = QLabel("Статус:")
        status_label.setStyleSheet("font-size: 13px;")
        status_row.addWidget(status_label)
        self.status = QLabel("Готов")
        self.status.setObjectName("status")
        status_row.addWidget(self.status)
        status_row.addStretch()

        # Кнопка вкл/выкл
        self.toggle_btn = QPushButton("ВКЛ")
        self.toggle_btn.setObjectName("toggle")
        self.toggle_btn.setProperty("active", True)
        self.toggle_btn.setFixedWidth(80)
        self.toggle_btn.clicked.connect(self._toggle)
        status_row.addWidget(self.toggle_btn)
        layout.addLayout(status_row)

        # Опция: оставлять окно поверх
        self.topmost_cb = QCheckBox("Поверх всех окон")
        self.topmost_cb.setChecked(True)
        self.topmost_cb.stateChanged.connect(self._toggle_topmost)
        layout.addWidget(self.topmost_cb)

        # Лог
        log_label = QLabel("Лог переводов:")
        log_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        layout.addWidget(self.log)

        layout.addStretch()

    def _connect_signals(self):
        self.signals.log_message.connect(self._append_log)
        self.signals.status_update.connect(self._update_status)

    def _setup_tray(self):
        icon = QIcon(create_icon_pixmap())
        self.setWindowIcon(icon)

        self.tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _register_hotkey(self):
        try:
            keyboard.add_hotkey("ctrl+shift+t", self._on_hotkey, suppress=True)
            self.hotkey_registered = True
            self._append_log("[SYS] Хоткей Ctrl+Shift+T зарегистрирован")
        except Exception as e:
            self._append_log(f"[SYS] Ошибка регистрации хоткея: {e}")

    def _on_hotkey(self):
        """Вызывается при нажатии Alt+Enter — запускаем перевод в отдельном потоке."""
        thread = threading.Thread(target=self.core.translate_and_send, daemon=True)
        thread.start()

    def _on_lang_change(self, index):
        code = self.lang_combo.itemData(index)
        self.core.target_lang = code
        name = self.lang_combo.itemText(index)
        self._append_log(f"[SYS] Язык: {name} ({code})")

    def _toggle(self):
        self.core.enabled = not self.core.enabled
        if self.core.enabled:
            self.toggle_btn.setText("ВКЛ")
            self.toggle_btn.setProperty("active", True)
            self._update_status("Готов")
        else:
            self.toggle_btn.setText("ВЫКЛ")
            self.toggle_btn.setProperty("active", False)
            self._update_status("Отключён")
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    def _toggle_topmost(self, state):
        flags = self.windowFlags()
        if state == Qt.Checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _append_log(self, msg):
        self.log.append(msg)
        # Ограничиваем лог
        if self.log.document().blockCount() > 200:
            cursor = self.log.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 50)
            cursor.removeSelectedText()

    def _update_status(self, text):
        self.status.setText(text)

    def _to_tray(self):
        self.hide()
        self.tray.showMessage("CS2 Translator", "Свёрнут в трей. Ctrl+Shift+T работает.", QSystemTrayIcon.Information, 2000)

    def _show_from_tray(self):
        self.show()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _quit(self):
        if self.hotkey_registered:
            keyboard.unhook_all()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        self._quit()
        event.accept()

    # Перетаскивание безрамочного окна
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    # Отключаем паузу pyautogui для скорости
    pyautogui.PAUSE = 0.01
    pyautogui.FAILSAFE = False

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
