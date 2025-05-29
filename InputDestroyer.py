
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal
from pynput import mouse, keyboard
from pynput.keyboard import GlobalHotKeys
import sys
import json
import time
import threading

key_mapping = {
    'Key.enter': keyboard.Key.enter,
    'Key.ctrl_l': keyboard.Key.ctrl_l,
    'Key.alt_l': keyboard.Key.alt_l,
    'Key.delete': keyboard.Key.delete,
    'Key.space': keyboard.Key.space,
    'Key.shift_r': keyboard.Key.shift_r,
    'Key.shift_l': keyboard.Key.shift_l,
    'Key.ctrl_r': keyboard.Key.ctrl_r,
    'Key.f1': keyboard.Key.f1,
    'Key.f2': keyboard.Key.f2,
    'Key.f3': keyboard.Key.f3,
    'Key.tab': keyboard.Key.tab,
    'Key.shift': keyboard.Key.shift,
    'Key.backspace': keyboard.Key.backspace
}


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_keys=None):
        super().__init__(parent)
        self.setWindowTitle("Hotkey Settings")
        layout = QtWidgets.QFormLayout(self)

        self.start_hotkey = QtWidgets.QKeySequenceEdit(current_keys.get("start", "Ctrl+F1"))
        self.stop_hotkey = QtWidgets.QKeySequenceEdit(current_keys.get("stop", "Ctrl+F2"))
        self.play_hotkey = QtWidgets.QKeySequenceEdit(current_keys.get("play", "Ctrl+F3"))

        layout.addRow("Start Recording:", self.start_hotkey)
        layout.addRow("Stop All:", self.stop_hotkey)
        layout.addRow("Play:", self.play_hotkey)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def get_hotkeys(self):
        return {
            "start": self.start_hotkey.keySequence().toString(),
            "stop": self.stop_hotkey.keySequence().toString(),
            "play": self.play_hotkey.keySequence().toString()
        }


class InputRecorderApp(QtWidgets.QMainWindow):
    macro_loaded = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Input Macro Recorder")
        self.setGeometry(100, 100, 900, 600)

        self.actions = []
        self.start_time = None
        self.recording = False
        self.playing = False
        self.stop_playback = False
        self.last_event_time = None

        self.mouse_event_interval = 0.05
        self.last_mouse_move_time = 0

        self.hotkey_config = self.load_hotkeys()
        self.init_ui()
        self.setup_listeners()
        self.setup_hotkeys()
        self.macro_loaded.connect(self._populate_table)

    def init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        toolbar = QtWidgets.QHBoxLayout()
        layout.addLayout(toolbar)

        self.start_btn = QtWidgets.QPushButton("Start Recording")
        self.stop_btn = QtWidgets.QPushButton("Stop Recording")
        self.play_btn = QtWidgets.QPushButton("Play")
        self.stop_play_btn = QtWidgets.QPushButton("Stop")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.load_btn = QtWidgets.QPushButton("Load")

        toolbar.addWidget(self.start_btn)
        toolbar.addWidget(self.stop_btn)
        toolbar.addWidget(self.play_btn)
        toolbar.addWidget(self.stop_play_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.load_btn)
        self.settings_btn = QtWidgets.QPushButton("Settings")
        toolbar.addWidget(self.settings_btn)
        self.settings_btn.clicked.connect(self.open_settings)

        toolbar.addWidget(QtWidgets.QLabel("Repeat:"))
        self.repeat_entry = QtWidgets.QLineEdit("1")
        self.repeat_entry.setFixedWidth(40)
        toolbar.addWidget(self.repeat_entry)

        toolbar.addWidget(QtWidgets.QLabel("Speed:"))
        self.speed_entry = QtWidgets.QLineEdit("1.0")
        self.speed_entry.setFixedWidth(40)
        toolbar.addWidget(self.speed_entry)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Type", "Action", "X", "Y", "Extra", "Delay"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.start_btn.clicked.connect(self.check_start_recording)
        self.stop_btn.clicked.connect(self.stop_recording)
        self.play_btn.clicked.connect(self.start_playing)
        self.stop_play_btn.clicked.connect(self.stop_playing)
        self.save_btn.clicked.connect(self.save_macro)
        self.load_btn.clicked.connect(self.load_macro)

    def setup_listeners(self):
        self.mouse_listener = mouse.Listener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click,
            on_scroll=self.on_mouse_scroll
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()

    
    def open_settings(self):
        dialog = SettingsDialog(self, current_keys=self.hotkey_config)
        if dialog.exec_():
            self.hotkey_config = dialog.get_hotkeys()
            self.save_hotkeys(self.hotkey_config)
            self.hotkeys.stop()
            self.setup_hotkeys()

    def load_hotkeys(self):
        try:
            with open("settings.json", "r") as f:
                return json.load(f)
        except:
            return {"start": "Ctrl+F1", "stop": "Ctrl+F2", "play": "Ctrl+F3"}

    def save_hotkeys(self, keys):
        with open("settings.json", "w") as f:
            json.dump(keys, f, indent=2)


    def setup_hotkeys(self):
        hotkeys = GlobalHotKeys({
            '<ctrl>+<f1>': lambda: QtCore.QMetaObject.invokeMethod(self, "check_start_recording", QtCore.Qt.QueuedConnection),
            '<ctrl>+<f2>': lambda: QtCore.QMetaObject.invokeMethod(self, "stop_all", QtCore.Qt.QueuedConnection),
            '<ctrl>+<f3>': lambda: QtCore.QMetaObject.invokeMethod(self, "start_playing", QtCore.Qt.QueuedConnection),
        })
        hotkeys.start()

    @QtCore.pyqtSlot()
    def stop_all(self):
        self.stop_recording()
        self.stop_playing()

    def current_delay(self):
        now = time.time()
        delay = 0.0 if self.last_event_time is None else round(now - self.last_event_time, 3)
        self.last_event_time = now
        return delay

    def log_event(self, event, record_to_list=True):
        if record_to_list:
            self.actions.append(event)
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)
        for i, key in enumerate(["type", "action", "x", "y", "extra", "delay"]):
            self.table.setItem(row_pos, i, QtWidgets.QTableWidgetItem(str(event.get(key, ''))))

    @QtCore.pyqtSlot()
    def check_start_recording(self):
        if self.actions:
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Overwrite Recording?")
            msg.setText("A recording already exists. What would you like to do?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
            msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
            ret = msg.exec_()

            if ret == QtWidgets.QMessageBox.Save:
                self.save_macro()
                self.start_recording()
            elif ret == QtWidgets.QMessageBox.Discard:
                self.start_recording()
            else:
                return
        else:
            self.start_recording()

    def start_recording(self):
        self.actions.clear()
        self.table.setRowCount(0)
        self.recording = True
        self.start_time = time.time()
        self.last_event_time = None
        print("[REC] Recording started")

    def stop_recording(self):
        self.recording = False
        print("[REC] Recording stopped")

    @QtCore.pyqtSlot()
    def start_playing(self):
        if not self.actions:
            QtWidgets.QMessageBox.warning(self, "No macro", "No actions to play.")
            return
        self.playing = True
        self.stop_playback = False
        threading.Thread(target=self.play_macro, daemon=True).start()

    def stop_playing(self):
        self.stop_playback = True
        self.playing = False

    def play_macro(self):
        mctrl = mouse.Controller()
        kctrl = keyboard.Controller()
        try:
            repeat_count = max(1, int(self.repeat_entry.text()))
            speed = float(self.speed_entry.text())
        except ValueError:
            repeat_count = 1
            speed = 1.0

        for _ in range(repeat_count):
            for action in self.actions:
                if self.stop_playback:
                    break
                time.sleep(action['delay'] / speed)
                if action['type'] == 'Mouse':
                    if action['action'] == 'Move':
                        mctrl.position = (action['x'], action['y'])
                    elif action['action'] == 'Click':
                        mctrl.position = (action['x'], action['y'])
                        mctrl.click(mouse.Button.left if action['extra'] == 'left' else mouse.Button.right)
                    elif action['action'] == 'Scroll':
                        mctrl.position = (action['x'], action['y'])
                        mctrl.scroll(0, action['extra'])
                elif action['type'] == 'Key':
                    try:
                        key_lookup = f"Key.{action['action']}" if action.get('is_special') else action['action']
                        key = key_mapping.get(key_lookup, action['action'])
                        kctrl.press(key)
                        kctrl.release(key)
                    except Exception as e:
                        print(f"[ERROR] Could not playback key: {action['action']}, {e}")
            if self.stop_playback:
                break
        self.playing = False

    def save_macro(self):
        file, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Macro", "", "JSON Files (*.json)")
        if file:
            with open(file, "w") as f:
                json.dump(self.actions, f, indent=2)

    def load_macro(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Macro", "", "JSON Files (*.json)")
        if file:
            def load_worker():
                try:
                    with open(file, "r") as f:
                        loaded_actions = json.load(f)
                    self.macro_loaded.emit(loaded_actions)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load macro:\n{e}")

            threading.Thread(target=load_worker, daemon=True).start()

    def _populate_table(self, loaded_actions):
        self.actions = loaded_actions
        self.table.setRowCount(0)
        self._load_index = 0

        def load_chunk():
            CHUNK_SIZE = 20
            for _ in range(CHUNK_SIZE):
                if self._load_index >= len(self.actions):
                    self._load_timer.stop()
                    return
                self.log_event(self.actions[self._load_index], record_to_list=False)
                self._load_index += 1

        self._load_timer = QtCore.QTimer()
        self._load_timer.timeout.connect(load_chunk)
        self._load_timer.start(10)

    def on_mouse_move(self, x, y):
        if self.playing or not self.recording:
            return
        now = time.time()
        if now - self.last_mouse_move_time >= self.mouse_event_interval:
            self.last_mouse_move_time = now
            self.log_event({
                'type': 'Mouse',
                'action': 'Move',
                'x': x,
                'y': y,
                'delay': self.current_delay()
            })

    def on_mouse_click(self, x, y, button, pressed):
        if self.playing or not self.recording or not pressed:
            return
        self.log_event({
            'type': 'Mouse',
            'action': 'Click',
            'x': x,
            'y': y,
            'extra': button.name,
            'delay': self.current_delay()
        })

    def on_mouse_scroll(self, x, y, dx, dy):
        if self.playing or not self.recording:
            return
        self.log_event({
            'type': 'Mouse',
            'action': 'Scroll',
            'x': x,
            'y': y,
            'extra': dy,
            'delay': self.current_delay()
        })

    def on_key_press(self, key):
        if self.playing or not self.recording:
            return
        try:
            if hasattr(key, 'char') and key.char is not None:
                name = key.char
                is_special = False
            else:
                name = key.name
                is_special = True
            self.log_event({
                'type': 'Key',
                'action': name,
                'is_special': is_special,
                'delay': self.current_delay()
            })
        except Exception as e:
            print(f"[ERROR] on_key_press: {e}")

    def on_key_release(self, key):
        if key == keyboard.Key.esc:
            self.stop_all()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = InputRecorderApp()
    window.show()
    sys.exit(app.exec_())
