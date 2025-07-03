import sys
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QProgressBar, QScrollArea,
    QGridLayout, QSizePolicy, QSystemTrayIcon, QMenu, QSplitter,
    QStackedWidget, QSpacerItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget
)
from PyQt6.QtCore import (
    QTimer, QThread, pyqtSignal, Qt, QSize, QPropertyAnimation,
    QEasingCurve, QRect, QSettings, QPoint, QObject
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QPalette, QAction,
    QLinearGradient, QPen, QBrush, QFontDatabase
)

# Import the backend tracking functionality
import psutil
import pygetwindow as gw
import win32gui, win32process
import keyboard
from threading import Thread, Lock


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
    """Backend tracking functionality with signals"""
    activity_changed = pyqtSignal(str, str)  # app_name, window_title
    time_updated = pyqtSignal(dict)  # app_times dict
    status_changed = pyqtSignal(str)  # status string

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


class StatusDot(QWidget):
    """Simple status dot indicator"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.status = "active"
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)
        self.blink_state = True

    def set_status(self, status):
        self.status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.status == "active":
            color = QColor(34, 197, 94)
            if self.blink_state:
                painter.setBrush(QBrush(color))
            else:
                painter.setBrush(QBrush(color.lighter(150)))
            self.blink_state = not self.blink_state
        elif self.status == "paused":
            color = QColor(251, 191, 36)
            painter.setBrush(QBrush(color))
        else:
            color = QColor(239, 68, 68)
            painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 10, 10)


class CleanButton(QPushButton):
    """Clean, minimal button"""

    def __init__(self, text="", variant="primary", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.setMinimumHeight(40)
        self.setFont(QFont("Inter", 14, QFont.Weight.Medium))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

    def update_style(self):
        if self.variant == "primary":
            self.setStyleSheet("""
                QPushButton {
                    background: #000000; color: white; border: none;
                    border-radius: 8px; padding: 12px 24px; font-weight: 500;
                }
                QPushButton:hover { background: #1a1a1a; }
                QPushButton:pressed { background: #333333; }
            """)
        elif self.variant == "secondary":
            self.setStyleSheet("""
                QPushButton {
                    background: white; color: #000000; border: 2px solid #e5e5e5;
                    border-radius: 8px; padding: 12px 24px; font-weight: 500;
                }
                QPushButton:hover { background: #f9f9f9; border-color: #d4d4d4; }
                QPushButton:pressed { background: #f0f0f0; }
            """)


class CurrentActivityCard(QFrame):
    """Clean current activity display"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_app = ""
        self.current_window = ""
        self.start_time = time.time()
        self.is_tracking = True
        self.pause_start_time = 0
        self.total_paused_duration = 0
        self.setup_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_duration)
        self.timer.start(1000)

    def setup_ui(self):
        self.setStyleSheet("""
            QFrame { background: white; border: 2px solid #f0f0f0; border-radius: 12px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        header_layout = QHBoxLayout()
        title = QLabel("CURRENTLY ACTIVE")
        title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #6b7280; letter-spacing: 1px;")
        self.status_dot = StatusDot()
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.status_dot)
        layout.addLayout(header_layout)
        self.app_label = QLabel("No application detected")
        self.app_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        self.app_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.app_label)
        self.window_label = QLabel("")
        self.window_label.setFont(QFont("Inter", 14))
        self.window_label.setStyleSheet("color: #6b7280;")
        self.window_label.setWordWrap(True)
        layout.addWidget(self.window_label)
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("JetBrains Mono", 28, QFont.Weight.Bold))
        self.duration_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.duration_label)

    def update_activity(self, app_name: str, window_title: str):
        if app_name != self.current_app:
            self.current_app = app_name
            self.current_window = window_title
            self.start_time = time.time()
            self.total_paused_duration = 0
            display_name = self.get_display_name(app_name)
            self.app_label.setText(display_name)
            if len(window_title) > 45:
                window_title = window_title[:42] + "..."
            self.window_label.setText(window_title)

    def update_duration(self):
        if self.is_tracking and self.current_app:
            duration = (time.time() - self.start_time) - self.total_paused_duration
            self.duration_label.setText(self.format_time(duration))

    def set_tracking_status(self, status: str):
        self.is_tracking = status in ["active", "resumed"]
        self.status_dot.set_status("active" if self.is_tracking else "paused")
        if status == "paused":
            self.pause_start_time = time.time()
        elif status == "resumed":
            if self.pause_start_time > 0:
                paused_duration = time.time() - self.pause_start_time
                self.total_paused_duration += paused_duration
                self.pause_start_time = 0

    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Google Chrome', 'firefox.exe': 'Mozilla Firefox',
            'msedge.exe': 'Microsoft Edge', 'code.exe': 'Visual Studio Code',
            'notepad.exe': 'Notepad', 'explorer.exe': 'File Explorer',
            'discord.exe': 'Discord', 'spotify.exe': 'Spotify',
            'slack.exe': 'Slack', 'teams.exe': 'Microsoft Teams',
            'zoom.exe': 'Zoom', 'photoshop.exe': 'Adobe Photoshop',
            'illustrator.exe': 'Adobe Illustrator', 'figma.exe': 'Figma',
            'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())

    def format_time(self, seconds: float) -> str:
        seconds = max(0, seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class AppUsageTable(QTableWidget):
    """Clean table for app usage"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_times = {}
        self.setup_ui()

    def setup_ui(self):
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Application", "Time", "Percentage"])
        # Style the table
        self.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
                gridline-color: #f0f0f0; /* Use a single color for grid */
                font-family: 'Inter';
                font-size: 14px;
                selection-background-color: #f1f5f9; /* Lighter selection */
            }
            QTableWidget::item {
                /* [FIX START]: Remove border and set color */
                border: none; /* Remove individual item borders */
                padding: 16px 20px;
                color: #212529; /* Set default text color to be visible */
                /* [FIX END] */
            }
            QTableWidget::item:selected {
                background: #f1f5f9;
                color: #000000;
            }
            QHeaderView::section {
                background: #f8fafc; /* Slightly different header bg */
                color: #475569;   /* Softer header text color */
                font-weight: 600; /* semi-bold */
                font-size: 13px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                padding: 16px 20px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
            QScrollBar:vertical {
                background: #f8fafc; width: 12px;
                border-radius: 6px; margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db; border-radius: 6px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #9ca3af; }
        """)
        # Configure headers
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(1, 140)
            header.resizeSection(2, 120)
        vertical_header = self.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.setShowGrid(True) # Use the table's grid lines for separation

    def update_app_times(self, app_times: Dict[str, float]):
        self.app_times = app_times
        self.refresh_display()

    def refresh_display(self):
        if not self.app_times:
            self.setRowCount(0)
            return
        total_time = sum(self.app_times.values())
        sorted_apps = sorted(self.app_times.items(), key=lambda x: x[1], reverse=True)
        filtered_apps = [(app, time_spent) for app, time_spent in sorted_apps if time_spent >= 0.5]
        self.setRowCount(len(filtered_apps))
        for row, (app_name, time_spent) in enumerate(filtered_apps):
            app_item = QTableWidgetItem(self.get_display_name(app_name))
            app_item.setFont(QFont("Inter", 14, QFont.Weight.Medium))
            app_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(row, 0, app_item)
            time_item = QTableWidgetItem(self.format_time(time_spent))
            time_item.setFont(QFont("JetBrains Mono", 14, QFont.Weight.Bold))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 1, time_item)
            percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setFont(QFont("Inter", 14, QFont.Weight.Medium))
            percent_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 2, percent_item)

    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Google Chrome', 'firefox.exe': 'Mozilla Firefox',
            'msedge.exe': 'Microsoft Edge', 'code.exe': 'Visual Studio Code',
            'notepad.exe': 'Notepad', 'explorer.exe': 'File Explorer',
            'discord.exe': 'Discord', 'spotify.exe': 'Spotify',
            'slack.exe': 'Slack', 'teams.exe': 'Microsoft Teams',
            'zoom.exe': 'Zoom', 'photoshop.exe': 'Adobe Photoshop',
            'illustrator.exe': 'Adobe Illustrator', 'figma.exe': 'Figma',
            'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())

    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


class StatsCard(QFrame):
    """Statistics card for summary info"""

    def __init__(self, title, value, subtitle="", parent=None):
        super().__init__(parent)
        self.setup_ui(title, value, subtitle)

    def setup_ui(self, title, value, subtitle):
        self.setStyleSheet("""
            QFrame { background: white; border: 2px solid #f0f0f0; border-radius: 12px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        title_label = QLabel(title.upper())
        title_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #6b7280; letter-spacing: 0.5px;")
        layout.addWidget(title_label)
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("JetBrains Mono", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.value_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont("Inter", 12))
            subtitle_label.setStyleSheet("color: #6b7280;")
            layout.addWidget(subtitle_label)

    def update_value(self, value):
        self.value_label.setText(value)


class TimeTrackerMainWindow(QMainWindow):
    """Clean, minimal main window"""

    def __init__(self):
        super().__init__()
        self.backend_tracker = BackendTracker()
        self.data_manager = DataManager()
        self.setup_backend_callbacks()
        self.setup_ui()
        self.setup_system_tray()
        self.start_tracking()
        self.settings = QSettings('TimeTracker', 'TimeTrackerMinimal')
        self.load_settings()

    def setup_backend_callbacks(self):
        self.backend_tracker.activity_changed.connect(self.on_activity_changed)
        self.backend_tracker.time_updated.connect(self.on_time_updated)
        self.backend_tracker.status_changed.connect(self.on_status_changed)

    def on_activity_changed(self, app_name: str, window_title: str):
        self.current_activity.update_activity(app_name, window_title)

    def on_time_updated(self, app_times: Dict[str, float]):
        self.app_usage_table.update_app_times(app_times)
        self.update_stats(app_times)

    def update_stats(self, app_times: Dict[str, float]):
        if not app_times:
            return
        total_time = sum(app_times.values())
        app_count = len([t for t in app_times.values() if t >= 1])
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        if hours > 0:
            total_time_str = f"{hours:02d}:{minutes:02d}"
        else:
            total_time_str = f"{minutes:02d}:{int(total_time % 60):02d}"
        self.total_time_card.update_value(total_time_str)
        self.apps_count_card.update_value(str(app_count))
        if app_times:
            most_used = max(app_times.items(), key=lambda x: x[1])
            most_used_name = self.get_display_name(most_used[0])
            self.most_used_card.update_value(most_used_name)

    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Chrome', 'firefox.exe': 'Firefox', 'msedge.exe': 'Edge',
            'code.exe': 'VS Code', 'notepad.exe': 'Notepad', 'explorer.exe': 'Explorer',
            'discord.exe': 'Discord', 'spotify.exe': 'Spotify', 'slack.exe': 'Slack',
            'teams.exe': 'Teams', 'zoom.exe': 'Zoom', 'photoshop.exe': 'Photoshop',
            'illustrator.exe': 'Illustrator', 'figma.exe': 'Figma', 'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())

    def on_status_changed(self, status: str):
        self.current_activity.set_tracking_status(status)
        if status == "paused":
            self.control_button.setText("Resume")
            self.control_button.variant = "primary"
        elif status == "resumed":
            self.control_button.setText("Pause")
            self.control_button.variant = "secondary"
        elif status == "stopped":
            self.quit_application()
        elif status == "private_browsing_detected":
            self.show_notification("Privacy Mode", "Tracking paused - Private browsing detected")
        elif status == "private_browsing_ended":
            self.show_notification("Privacy Mode", "Tracking resumed - Private browsing ended")
        self.control_button.update_style()

    def setup_ui(self):
        self.setWindowTitle("TimeTracker")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setStyleSheet("""
            QMainWindow { background: #fafbfc; }
            QWidget { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; }
        """)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(32)
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        content = self.create_content_area()
        main_layout.addWidget(content, 1)

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(350)
        sidebar.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        title = QLabel("TimeTracker")
        title.setFont(QFont("Inter", 32, QFont.Weight.Black))
        title.setStyleSheet("color: #000000;")
        subtitle = QLabel("Activity Monitor")
        subtitle.setFont(QFont("Inter", 16))
        subtitle.setStyleSheet("color: #6b7280;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)
        self.current_activity = CurrentActivityCard()
        layout.addWidget(self.current_activity)
        self.control_button = CleanButton("Pause", variant="secondary")
        self.control_button.clicked.connect(self.toggle_tracking)
        layout.addWidget(self.control_button)
        shortcuts_frame = QFrame()
        shortcuts_frame.setStyleSheet("""
            QFrame { background: white; border: 2px solid #f0f0f0; border-radius: 12px; }
        """)
        shortcuts_layout = QVBoxLayout(shortcuts_frame)
        shortcuts_layout.setContentsMargins(20, 16, 20, 16)
        shortcuts_layout.setSpacing(12)
        shortcuts_title = QLabel("KEYBOARD SHORTCUTS")
        shortcuts_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        shortcuts_title.setStyleSheet("color: #6b7280; letter-spacing: 0.5px;")
        shortcuts_text = QLabel("Ctrl+P: Pause/Resume\nCtrl+Shift+Q: Quit")
        shortcuts_text.setFont(QFont("JetBrains Mono", 13))
        shortcuts_text.setStyleSheet("color: #374151; line-height: 1.6;")
        shortcuts_layout.addWidget(shortcuts_title)
        shortcuts_layout.addWidget(shortcuts_text)
        layout.addWidget(shortcuts_frame)
        layout.addStretch()
        return sidebar

    def create_content_area(self):
        content = QFrame()
        content.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        title = QLabel("Today's Activity")
        title.setFont(QFont("Inter", 36, QFont.Weight.Black))
        title.setStyleSheet("color: #000000;")
        date_label = QLabel(datetime.now().strftime("%A, %B %d, %Y"))
        date_label.setFont(QFont("Inter", 18))
        date_label.setStyleSheet("color: #6b7280;")
        header_layout.addWidget(title)
        header_layout.addWidget(date_label)
        layout.addLayout(header_layout)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        self.total_time_card = StatsCard("Total Time", "00:00", "Today")
        self.apps_count_card = StatsCard("Applications", "0", "Used today")
        self.most_used_card = StatsCard("Most Used", "None", "Application")
        stats_layout.addWidget(self.total_time_card)
        stats_layout.addWidget(self.apps_count_card)
        stats_layout.addWidget(self.most_used_card)
        layout.addLayout(stats_layout)
        self.app_usage_table = AppUsageTable()
        layout.addWidget(self.app_usage_table, 1)
        return content

    def setup_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("#000000"))
        self.tray_icon.setIcon(QIcon(pixmap))
        tray_menu = QMenu()
        show_action = QAction("Show TimeTracker", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        pause_action = QAction("Toggle Tracking", self)
        pause_action.triggered.connect(self.toggle_tracking)
        tray_menu.addAction(pause_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def start_tracking(self):
        self.backend_tracker.start_tracking()

    def toggle_tracking(self):
        self.backend_tracker.toggle_pause()

    def show_notification(self, title: str, message: str):
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def closeEvent(self, event):
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_application()

    def quit_application(self):
        self.backend_tracker.stop()
        self.save_settings()
        QApplication.quit()

    def save_settings(self):
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('windowState', self.saveState())

    def load_settings(self):
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        window_state = self.settings.value('windowState')
        if window_state:
            self.restoreState(window_state)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("TimeTracker")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("TimeTracker")
    window = TimeTrackerMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
