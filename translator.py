"""
CS2 Auto Translator
Записывает нажатия клавиш в буфер, по Ctrl+Shift+T переводит и отправляет.
"""

import sys
import time
import threading
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

# Клавиши-модификаторы которые НЕ записываем в буфер
MODIFIER_KEYS = {
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "alt", "left alt", "right alt",
    "left windows", "right windows",
    "caps lock", "tab", "escape",
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
    "insert", "delete", "home", "end",
    "page up", "page down",
    "up", "down", "left", "right",
    "print screen", "scroll lock", "pause",
    "num lock",
}


def create_icon_pixmap(size=64, color="#6C5CE7"):
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
    log_message = pyqtSignal(str)
    status_update = pyqtSignal(str)


class KeyBuffer:
    """Записывает нажатия клавиш только когда чат CS2 открыт."""

    # Клавиши которые открывают чат в CS2
    CHAT_OPEN_KEYS = {"enter", "y", "u"}

    def __init__(self):
        self._buffer = []
        self._lock = threading.Lock()
        self._enabled = True       # общий вкл/выкл
        self._chat_open = False     # чат CS2 открыт?

    def set_enabled(self, val):
        with self._lock:
            self._enabled = val
            if not val:
                self._chat_open = False
                self._buffer.clear()

    def on_key(self, event):
        """Обработчик нажатия клавиши."""
        if not self._enabled or event.event_type != "down":
            return

        name = event.name
        lower = name.lower()

        # Пропускаем модификаторы
        if lower in MODIFIER_KEYS:
            return

        with self._lock:
            if not self._chat_open:
                # Чат закрыт — ждём клавишу открытия чата
                if lower in self.CHAT_OPEN_KEYS:
                    self._chat_open = True
                    self._buffer.clear()
                return

            # Чат открыт — записываем
            if lower == "escape":
                # Закрыл чат без отправки
                self._chat_open = False
                self._buffer.clear()
            elif lower == "backspace":
                if self._buffer:
                    self._buffer.pop()
            elif lower == "space":
                self._buffer.append(" ")
            elif lower == "enter":
                # Отправил сообщение (без перевода)
                self._chat_open = False
                self._buffer.clear()
            elif len(name) == 1:
                self._buffer.append(name)

    @property
    def chat_open(self):
        with self._lock:
            return self._chat_open

    def get_text(self):
        with self._lock:
            return "".join(self._buffer)

    def clear_and_close(self):
        with self._lock:
            self._buffer.clear()
            self._chat_open = False

    def reopen(self):
        """Снова начать запись (после перевода)."""
        with self._lock:
            self._buffer.clear()
            self._chat_open = False


class TranslatorCore:
    """Ядро переводчика."""

    def __init__(self, signals, key_buffer):
        self.signals = signals
        self.key_buffer = key_buffer
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
        """Берёт текст из буфера, переводит, стирает оригинал и печатает перевод."""
        if not self.enabled:
            return

        with self._lock:
            try:
                text = self.key_buffer.get_text().strip()

                if not text:
                    self.signals.log_message.emit("[!] Буфер пуст — нечего переводить")
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

                # Ждём отпускания модификаторов
                time.sleep(0.15)
                keyboard.release("ctrl")
                keyboard.release("shift")
                time.sleep(0.05)

                # Стираем оригинальный текст из чата (backspace по количеству символов)
                for _ in range(len(text) + 5):  # +5 на всякий случай
                    pyautogui.press("backspace")
                    time.sleep(0.005)

                time.sleep(0.05)

                # Печатаем перевод посимвольно через keyboard (поддерживает любую раскладку)
                keyboard.write(translated, delay=0.01)
                time.sleep(0.05)

                # Отправляем
                pyautogui.press("enter")

                self.signals.status_update.emit("Готов")
                self.signals.log_message.emit("--- Отправлено ---")

                self.key_buffer.reopen()

            except Exception as e:
                self.signals.log_message.emit(f"[ERROR] {e}")
                self.signals.status_update.emit("Ошибка")
                self.key_buffer.reopen()


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
        self.key_buffer = KeyBuffer()
        self.core = TranslatorCore(self.signals, self.key_buffer)
        self.hotkey_registered = False

        self.setWindowTitle("CS2 Translator")
        self.setFixedSize(420, 520)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._init_ui()
        self._connect_signals()
        self._setup_tray()
        self._register_hooks()

        self._drag_pos = None

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Заголовок
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
        self.lang_combo.setCurrentIndex(0)
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

        self.toggle_btn = QPushButton("ВКЛ")
        self.toggle_btn.setObjectName("toggle")
        self.toggle_btn.setProperty("active", True)
        self.toggle_btn.setFixedWidth(80)
        self.toggle_btn.clicked.connect(self._toggle)
        status_row.addWidget(self.toggle_btn)
        layout.addLayout(status_row)

        # Буфер (показываем что записано)
        buf_row = QHBoxLayout()
        buf_label = QLabel("Буфер:")
        buf_label.setStyleSheet("font-size: 12px; color: #888;")
        buf_row.addWidget(buf_label)
        self.buf_display = QLabel("")
        self.buf_display.setStyleSheet("font-size: 12px; color: #6C5CE7;")
        buf_row.addWidget(self.buf_display)
        buf_row.addStretch()
        layout.addLayout(buf_row)

        # Таймер обновления буфера
        self.buf_timer = QTimer()
        self.buf_timer.timeout.connect(self._update_buf_display)
        self.buf_timer.start(200)

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
        self.log.setMaximumHeight(180)
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

    def _register_hooks(self):
        try:
            # Хук на все клавиши для записи в буфер
            keyboard.hook(self.key_buffer.on_key)
            # Хоткей для перевода
            keyboard.add_hotkey("ctrl+shift+t", self._on_hotkey, suppress=True)
            self.hotkey_registered = True
            self._append_log("[SYS] Хоткей Ctrl+Shift+T зарегистрирован")
            self._append_log("[SYS] Запись включается только когда чат открыт (Enter/Y/U)")
            self._append_log("[SYS] Напиши в чате на русском, жми Ctrl+Shift+T")
        except Exception as e:
            self._append_log(f"[SYS] Ошибка: {e}")

    def _on_hotkey(self):
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
            self.key_buffer.set_enabled(True)
        else:
            self.toggle_btn.setText("ВЫКЛ")
            self.toggle_btn.setProperty("active", False)
            self._update_status("Отключён")
            self.key_buffer.set_enabled(False)
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    def _toggle_topmost(self, state):
        flags = self.windowFlags()
        if state == Qt.Checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _update_buf_display(self):
        if not self.key_buffer.chat_open:
            self.buf_display.setText("(чат закрыт)")
            return
        text = self.key_buffer.get_text()
        display = text[-40:] if len(text) > 40 else text
        self.buf_display.setText(display if display else "(печатай...)")

    def _append_log(self, msg):
        self.log.append(msg)
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    pyautogui.PAUSE = 0.01
    pyautogui.FAILSAFE = False

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
