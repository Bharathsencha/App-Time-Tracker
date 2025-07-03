import psutil
import pygetwindow as gw
import win32gui, win32process
import time
import keyboard
from threading import Thread, Lock
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from pathlib import Path
import json
from datetime import datetime

class DataManager:
    """Handles saving and loading of time tracking data"""
    
    def __init__(self):
        self.data_dir = Path.home() / "TimeTracker"
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "tracking_data.json"
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        
    def load_data(self):
        """Load all tracking data from file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                return data
            return {}
        except Exception as e:
            print(f"Error loading data: {e}")
            return {}
    
    def save_data(self, all_data):
        """Save all tracking data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(all_data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def get_today_data(self):
        """Get today's tracking data"""
        all_data = self.load_data()
        return all_data.get(self.current_date, {})
    
    def save_today_data(self, app_times):
        """Save today's tracking data"""
        all_data = self.load_data()
        all_data[self.current_date] = app_times
        self.save_data(all_data)
    
    def get_date_data(self, date_str):
        """Get tracking data for specific date"""
        all_data = self.load_data()
        return all_data.get(date_str, {})
    
    def get_all_dates(self):
        """Get all dates with tracking data"""
        all_data = self.load_data()
        return sorted(all_data.keys(), reverse=True)


class BackendTracker(QObject):
    activity_changed = pyqtSignal(str, str)  # app_name, window_title
    time_updated = pyqtSignal(dict)           # app_times dict
    status_changed = pyqtSignal(str)          # status string

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.app_times = self.data_manager.get_today_data()  # Load today's data
        self.lock = Lock()
        self.stop_tracking = False
        self.pause_tracking = False
        self.current_app = ""
        self.current_window = ""
        self.last_process = None
        self.last_time = time.time()
        self.private_browsing_active = False

        # Auto-save timer
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.auto_save)
        self.save_timer.start(30000)  # Save every 30 seconds

    def auto_save(self):
        """Auto-save current data"""
        with self.lock:
            self.data_manager.save_today_data(self.app_times)

    def get_pid_from_active_window(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid
        except:
            return None

    def get_app_name_from_pid(self, pid):
        try:
            return psutil.Process(pid).name()
        except psutil.NoSuchProcess:
            return "Process not found"
        except Exception as e:
            return f"Error: {e}"

    def is_private_browsing(self, window_title):
        private_indicators = [
            "InPrivate", "Incognito", "Private Browsing", "Private Window"
        ]
        return any(indicator.lower() in window_title.lower() for indicator in private_indicators)

    def listen_for_shortcuts(self):
        def on_stop_shortcut():
            self.stop_tracking = True
            self.status_changed.emit("stopped")

        def on_pause_shortcut():
            self.pause_tracking = not self.pause_tracking
            status = "paused" if self.pause_tracking else "resumed"
            self.status_changed.emit(status)

        try:
            keyboard.add_hotkey('ctrl+shift+q', on_stop_shortcut)
            keyboard.add_hotkey('ctrl+p', on_pause_shortcut)
            keyboard.add_hotkey('ctrl+r', on_pause_shortcut)
            keyboard.wait()
        except:
            pass

    def track_active_window(self):
        try:
            while not self.stop_tracking:
                current_time = time.time()

                if self.pause_tracking:
                    self.last_time = current_time
                    time.sleep(1)
                    continue

                active_window = gw.getActiveWindow()
                if active_window:
                    active_window_title = active_window.title
                else:
                    active_window_title = "Unknown Window"

                if self.is_private_browsing(active_window_title):
                    if not self.private_browsing_active:
                        self.pause_tracking = True
                        self.status_changed.emit("private_browsing_detected")
                        self.private_browsing_active = True
                        continue
                else:
                    if self.private_browsing_active:
                        self.pause_tracking = False
                        self.status_changed.emit("private_browsing_ended")
                        self.private_browsing_active = False

                pid = self.get_pid_from_active_window()
                if not pid:
                    time.sleep(1)
                    continue

                current_process = self.get_app_name_from_pid(pid)

                if self.last_process:
                    elapsed_time = current_time - self.last_time
                    with self.lock:
                        if self.last_process not in self.app_times:
                            self.app_times[self.last_process] = 0
                        self.app_times[self.last_process] += elapsed_time
                        self.time_updated.emit(self.app_times.copy())

                if current_process != self.last_process:
                    self.activity_changed.emit(current_process, active_window_title)
                    self.current_app = current_process
                    self.current_window = active_window_title

                self.last_process = current_process
                self.last_time = current_time

                time.sleep(1)
        except Exception as e:
            print(f"Tracking error: {e}")

    def start_tracking(self):
        self.shortcut_thread = Thread(target=self.listen_for_shortcuts, daemon=True)
        self.shortcut_thread.start()

        self.tracking_thread = Thread(target=self.track_active_window, daemon=True)
        self.tracking_thread.start()

        # Emit initial data
        self.time_updated.emit(self.app_times.copy())

    def toggle_pause(self):
        self.pause_tracking = not self.pause_tracking
        status = "paused" if self.pause_tracking else "resumed"
        self.status_changed.emit(status)

    def stop(self):
        self.stop_tracking = True
        with self.lock:
            if self.last_process and not self.pause_tracking:
                elapsed_time = time.time() - self.last_time
                if self.last_process not in self.app_times:
                    self.app_times[self.last_process] = 0
                self.app_times[self.last_process] += elapsed_time
            self.data_manager.save_today_data(self.app_times)
