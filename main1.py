import sys
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
import os
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QProgressBar, QScrollArea,
    QGridLayout, QSizePolicy, QSystemTrayIcon, QMenu, QSplitter,
    QStackedWidget, QSpacerItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QDateEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import (
    QTimer, QThread, pyqtSignal, Qt, QSize, QPropertyAnimation,
    QEasingCurve, QRect, QSettings, QPoint, QDate, QObject
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


class AppLauncher:
    """Handles launching applications"""
    
    @staticmethod
    def get_app_paths():
        """Get common application paths"""
        return {
            'chrome.exe': [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ],
            'firefox.exe': [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
            ],
            'msedge.exe': [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            ],
            'code.exe': [
                r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.getenv('USERNAME')),
                r"C:\Program Files\Microsoft VS Code\Code.exe"
            ],
            'notepad.exe': [r"C:\Windows\System32\notepad.exe"],
            'discord.exe': [
                r"C:\Users\{}\AppData\Local\Discord\Update.exe".format(os.getenv('USERNAME'))
            ],
            'spotify.exe': [
                r"C:\Users\{}\AppData\Roaming\Spotify\Spotify.exe".format(os.getenv('USERNAME'))
            ],
            'slack.exe': [
                r"C:\Users\{}\AppData\Local\slack\slack.exe".format(os.getenv('USERNAME'))
            ],
            'teams.exe': [
                r"C:\Users\{}\AppData\Local\Microsoft\Teams\current\Teams.exe".format(os.getenv('USERNAME'))
            ],
            'zoom.exe': [
                r"C:\Users\{}\AppData\Roaming\Zoom\bin\Zoom.exe".format(os.getenv('USERNAME'))
            ],
            'figma.exe': [
                r"C:\Users\{}\AppData\Local\Figma\Figma.exe".format(os.getenv('USERNAME'))
            ],
            'notion.exe': [
                r"C:\Users\{}\AppData\Local\Notion\Notion.exe".format(os.getenv('USERNAME'))
            ]
        }
    
    @staticmethod
    def launch_app(process_name):
        """Launch application by process name"""
        try:
            app_paths = AppLauncher.get_app_paths()
            
            if process_name in app_paths:
                # Try each possible path
                for path in app_paths[process_name]:
                    if os.path.exists(path):
                        subprocess.Popen([path])
                        return True
                
                # If no direct path found, try using start command
                app_name = process_name.replace('.exe', '')
                subprocess.Popen(['start', app_name], shell=True)
                return True
            else:
                # Try to start using the process name
                app_name = process_name.replace('.exe', '')
                subprocess.Popen(['start', app_name], shell=True)
                return True
                
        except Exception as e:
            print(f"Error launching {process_name}: {e}")
            return False


class BackendTracker(QObject):
    """Backend tracking functionality with signals"""
    
    activity_changed = pyqtSignal(str, str)  # app_name, window_title
    time_updated = pyqtSignal(dict)          # app_times dict
    status_changed = pyqtSignal(str)         # status string
    
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
                if self.pause_tracking:
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
                else:
                    if self.private_browsing_active:
                        self.pause_tracking = False
                        self.status_changed.emit("private_browsing_ended")
                    self.private_browsing_active = False
                
                if self.pause_tracking:
                    time.sleep(1)
                    continue
                
                pid = self.get_pid_from_active_window()
                if not pid:
                    time.sleep(1)
                    continue
                
                process_name = self.get_app_name_from_pid(pid)
                current_process = process_name
                current_time = time.time()
                
                if current_process != self.last_process:
                    if self.last_process:
                        elapsed_time = current_time - self.last_time
                        with self.lock:
                            if self.last_process not in self.app_times:
                                self.app_times[self.last_process] = 0
                            self.app_times[self.last_process] += elapsed_time
                        
                        self.time_updated.emit(self.app_times.copy())
                    
                    self.activity_changed.emit(process_name, active_window_title)
                    
                    self.current_app = process_name
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
        # Final save before stopping
        with self.lock:
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
            color = QColor(34, 197, 94)  # Green
            if self.blink_state:
                painter.setBrush(QBrush(color))
            else:
                painter.setBrush(QBrush(color.lighter(150)))
            self.blink_state = not self.blink_state
        elif self.status == "paused":
            color = QColor(251, 191, 36)  # Yellow
            painter.setBrush(QBrush(color))
        else:
            color = QColor(239, 68, 68)   # Red
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
                    background: #000000;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #1a1a1a;
                }
                QPushButton:pressed {
                    background: #333333;
                }
            """)
        elif self.variant == "secondary":
            self.setStyleSheet("""
                QPushButton {
                    background: white;
                    color: #000000;
                    border: 2px solid #e5e5e5;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #f9f9f9;
                    border-color: #d4d4d4;
                }
                QPushButton:pressed {
                    background: #f0f0f0;
                }
            """)


class CurrentActivityCard(QFrame):
    """Clean current activity display"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_app = ""
        self.current_window = ""
        self.start_time = time.time()
        self.is_tracking = True
        self.accumulated_duration = 0  # Store accumulated duration before pause
        self.setup_ui()
        
        # Timer for updating duration
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_duration)
        self.timer.start(1000)
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("CURRENTLY ACTIVE")
        title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #6b7280; letter-spacing: 1px;")
        
        self.status_dot = StatusDot()
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.status_dot)
        
        layout.addLayout(header_layout)
        
        # App name
        self.app_label = QLabel("No application detected")
        self.app_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        self.app_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.app_label)
        
        # Window title
        self.window_label = QLabel("")
        self.window_label.setFont(QFont("Inter", 14))
        self.window_label.setStyleSheet("color: #6b7280;")
        self.window_label.setWordWrap(True)
        layout.addWidget(self.window_label)
        
        # Duration
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("JetBrains Mono", 28, QFont.Weight.Bold))
        self.duration_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.duration_label)
    
    def update_activity(self, app_name: str, window_title: str):
        if app_name != self.current_app:
            self.current_app = app_name
            self.current_window = window_title
            self.start_time = time.time()
            self.accumulated_duration = 0  # Reset accumulated duration on new activity
            
            display_name = self.get_display_name(app_name)
            self.app_label.setText(display_name)
            
            # Truncate long window titles
            if len(window_title) > 45:
                window_title = window_title[:42] + "..."
            self.window_label.setText(window_title)
    
    def update_duration(self):
        if self.is_tracking and self.current_app:
            duration = self.accumulated_duration + (time.time() - self.start_time)
            self.duration_label.setText(self.format_time(duration))
    
    def set_tracking_status(self, status: str):
        was_tracking = self.is_tracking
        self.is_tracking = status in ["active", "resumed"]
        self.status_dot.set_status("active" if self.is_tracking else "paused")
        if self.is_tracking:
            if not was_tracking:
                # Resuming: set start_time to current time minus accumulated duration
                self.start_time = time.time()
        else:
            if was_tracking:
                # Pausing: accumulate elapsed duration
                self.accumulated_duration += time.time() - self.start_time
    
    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Google Chrome',
            'firefox.exe': 'Mozilla Firefox',
            'msedge.exe': 'Microsoft Edge',
            'code.exe': 'Visual Studio Code',
            'notepad.exe': 'Notepad',
            'explorer.exe': 'File Explorer',
            'discord.exe': 'Discord',
            'spotify.exe': 'Spotify',
            'slack.exe': 'Slack',
            'teams.exe': 'Microsoft Teams',
            'zoom.exe': 'Zoom',
            'photoshop.exe': 'Adobe Photoshop',
            'illustrator.exe': 'Adobe Illustrator',
            'figma.exe': 'Figma',
            'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())
    
    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class AppUsageTable(QTableWidget):
    """Clean table for app usage with clickable app icons"""
    
    app_launched = pyqtSignal(str)  # Signal when app is launched
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_times = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["", "Application", "Time", "Percentage"])
        
        # Style the table
        self.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
                gridline-color: #f8f9fa;
                font-family: 'Inter';
                font-size: 14px;
                selection-background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 16px 20px;
                border-bottom: 1px solid #f0f0f0;
                border-right: none;
            }
            QTableWidget::item:selected {
                background: #f8f9fa;
                color: #000000;
            }
            QHeaderView::section {
                background: #fafbfc;
                color: #374151;
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                padding: 16px 20px;
                border: none;
                border-bottom: 2px solid #e5e7eb;
                border-right: 1px solid #f0f0f0;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QScrollBar:vertical {
                background: #f9fafb;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }
        """)
        
        # Configure headers
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Icon column
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # App name
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)   # Time
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)   # Percentage
            header.resizeSection(0, 60)   # Icon column width
            header.resizeSection(2, 140)  # Time column width
            header.resizeSection(3, 120)  # Percentage column width
        
        vertical_header = self.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        
        # Connect cell click to launch app
        self.cellClicked.connect(self.on_cell_clicked)
    
    def on_cell_clicked(self, row, column):
        """Handle cell click to launch app"""
        if column == 0:  # Icon column clicked
            app_item = self.item(row, 1)  # Get app name from second column
            if app_item:
                display_name = app_item.text()
                process_name = self.get_process_name_from_display(display_name)
                if process_name:
                    success = AppLauncher.launch_app(process_name)
                    if success:
                        self.app_launched.emit(f"Launched {display_name}")
                    else:
                        self.app_launched.emit(f"Failed to launch {display_name}")
    
    def get_process_name_from_display(self, display_name: str) -> str:
        """Convert display name back to process name"""
        reverse_map = {
            'Google Chrome': 'chrome.exe',
            'Mozilla Firefox': 'firefox.exe',
            'Microsoft Edge': 'msedge.exe',
            'Visual Studio Code': 'code.exe',
            'Notepad': 'notepad.exe',
            'File Explorer': 'explorer.exe',
            'Discord': 'discord.exe',
            'Spotify': 'spotify.exe',
            'Slack': 'slack.exe',
            'Microsoft Teams': 'teams.exe',
            'Zoom': 'zoom.exe',
            'Adobe Photoshop': 'photoshop.exe',
            'Adobe Illustrator': 'illustrator.exe',
            'Figma': 'figma.exe',
            'Notion': 'notion.exe',
        }
        return reverse_map.get(display_name, display_name.lower() + '.exe')
    
    def update_app_times(self, app_times: Dict[str, float]):
        self.app_times = app_times
        self.refresh_display()
    
    def refresh_display(self):
        if not self.app_times:
            self.setRowCount(0)
            return
        
        total_time = sum(self.app_times.values())
        sorted_apps = sorted(self.app_times.items(), key=lambda x: x[1], reverse=True)
        
        # Filter apps with less than 1 second
        filtered_apps = [(app, time_spent) for app, time_spent in sorted_apps if time_spent >= 1]
        
        self.setRowCount(len(filtered_apps))
        
        for row, (app_name, time_spent) in enumerate(filtered_apps):
            # App icon (clickable)
            icon_item = QTableWidgetItem(self.get_app_icon(app_name))
            icon_item.setFont(QFont("Segoe UI Emoji", 20))
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setToolTip(f"Click to launch {self.get_display_name(app_name)}")
            self.setItem(row, 0, icon_item)
            
            # App name
            app_item = QTableWidgetItem(self.get_display_name(app_name))
            app_item.setFont(QFont("Inter", 14, QFont.Weight.Medium))
            self.setItem(row, 1, app_item)
            
            # Time
            time_item = QTableWidgetItem(self.format_time(time_spent))
            time_item.setFont(QFont("JetBrains Mono", 14, QFont.Weight.Bold))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 2, time_item)
            
            # Percentage
            percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setFont(QFont("Inter", 14, QFont.Weight.Medium))
            percent_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 3, percent_item)
    
    def get_app_icon(self, process_name: str) -> str:
        icon_map = {
            'chrome.exe': '🌐',
            'firefox.exe': '🦊',
            'msedge.exe': '🌐',
            'code.exe': '💻',
            'notepad.exe': '📝',
            'explorer.exe': '📁',
            'discord.exe': '💬',
            'spotify.exe': '🎵',
            'slack.exe': '💼',
            'teams.exe': '👥',
            'zoom.exe': '📹',
            'photoshop.exe': '🎨',
            'illustrator.exe': '✏️',
            'figma.exe': '🎨',
            'notion.exe': '📋',
        }
        return icon_map.get(process_name, '⚡')
    
    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Google Chrome',
            'firefox.exe': 'Mozilla Firefox',
            'msedge.exe': 'Microsoft Edge',
            'code.exe': 'Visual Studio Code',
            'notepad.exe': 'Notepad',
            'explorer.exe': 'File Explorer',
            'discord.exe': 'Discord',
            'spotify.exe': 'Spotify',
            'slack.exe': 'Slack',
            'teams.exe': 'Microsoft Teams',
            'zoom.exe': 'Zoom',
            'photoshop.exe': 'Adobe Photoshop',
            'illustrator.exe': 'Adobe Illustrator',
            'figma.exe': 'Figma',
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
            QFrame {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel(title.upper())
        title_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #6b7280; letter-spacing: 0.5px;")
        layout.addWidget(title_label)
        
        # Value
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("JetBrains Mono", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #000000;")
        layout.addWidget(self.value_label)
        
        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont("Inter", 12))
            subtitle_label.setStyleSheet("color: #6b7280;")
            layout.addWidget(subtitle_label)
    
    def update_value(self, value):
        self.value_label.setText(value)


class HistoryWidget(QWidget):
    """Widget for viewing historical data"""
    
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setup_ui()
        self.load_available_dates()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Header with date selector
        header_layout = QHBoxLayout()
        
        title = QLabel("Historical Data")
        title.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #000000;")
        
        # Date selector
        self.date_combo = QComboBox()
        self.date_combo.setFont(QFont("Inter", 14))
        self.date_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 2px solid #e5e5e5;
                border-radius: 8px;
                padding: 8px 12px;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #d4d4d4;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """)
        self.date_combo.currentTextChanged.connect(self.on_date_changed)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Select Date:"))
        header_layout.addWidget(self.date_combo)
        
        layout.addLayout(header_layout)
        
        # Stats cards for selected date
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(20)
        
        self.hist_total_time_card = StatsCard("Total Time", "00:00", "Selected date")
        self.hist_apps_count_card = StatsCard("Applications", "0", "Used that day")
        self.hist_most_used_card = StatsCard("Most Used", "None", "Application")
        
        self.stats_layout.addWidget(self.hist_total_time_card)
        self.stats_layout.addWidget(self.hist_apps_count_card)
        self.stats_layout.addWidget(self.hist_most_used_card)
        
        layout.addLayout(self.stats_layout)
        
        # Historical data table
        self.history_table = AppUsageTable()
        layout.addWidget(self.history_table, 1)
    
    def load_available_dates(self):
        """Load all available dates into combo box"""
        dates = self.data_manager.get_all_dates()
        self.date_combo.clear()
        
        if dates:
            for date_str in dates:
                # Format date nicely
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%A, %B %d, %Y")
                    self.date_combo.addItem(formatted_date, date_str)
                except:
                    self.date_combo.addItem(date_str, date_str)
        else:
            self.date_combo.addItem("No data available", "")
    
    def on_date_changed(self, formatted_date):
        """Handle date selection change"""
        if not formatted_date or formatted_date == "No data available":
            return
        
        # Get the actual date string from combo box data
        current_index = self.date_combo.currentIndex()
        date_str = self.date_combo.itemData(current_index)
        
        if date_str:
            # Load data for selected date
            app_times = self.data_manager.get_date_data(date_str)
            self.history_table.update_app_times(app_times)
            self.update_historical_stats(app_times)
    
    def update_historical_stats(self, app_times: Dict[str, float]):
        """Update statistics cards for historical data"""
        if not app_times:
            self.hist_total_time_card.update_value("00:00")
            self.hist_apps_count_card.update_value("0")
            self.hist_most_used_card.update_value("None")
            return
        
        total_time = sum(app_times.values())
        app_count = len([t for t in app_times.values() if t >= 1])
        
        # Format total time
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        
        if hours > 0:
            total_time_str = f"{hours:02d}:{minutes:02d}:00"
        else:
            total_time_str = f"{minutes:02d}:00"
        
        self.hist_total_time_card.update_value(total_time_str)
        self.hist_apps_count_card.update_value(str(app_count))
        
        # Most used app
        if app_times:
            most_used = max(app_times.items(), key=lambda x: x[1])
            most_used_name = self.get_display_name(most_used[0])
            self.hist_most_used_card.update_value(most_used_name)
    
    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Chrome',
            'firefox.exe': 'Firefox',
            'msedge.exe': 'Edge',
            'code.exe': 'VS Code',
            'notepad.exe': 'Notepad',
            'explorer.exe': 'Explorer',
            'discord.exe': 'Discord',
            'spotify.exe': 'Spotify',
            'slack.exe': 'Slack',
            'teams.exe': 'Teams',
            'zoom.exe': 'Zoom',
            'photoshop.exe': 'Photoshop',
            'illustrator.exe': 'Illustrator',
            'figma.exe': 'Figma',
            'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())
    
    def refresh_dates(self):
        """Refresh the available dates"""
        self.load_available_dates()


class TimeTrackerMainWindow(QMainWindow):
    """Clean, minimal main window with tabs"""
    
    def __init__(self):
        super().__init__()
        self.backend_tracker = BackendTracker()
        self.data_manager = DataManager()
        self.setup_backend_callbacks()
        self.setup_ui()
        self.setup_system_tray()
        self.start_tracking()
        
        # Load settings
        self.settings = QSettings('TimeTracker', 'TimeTrackerMinimal')
        self.load_settings()
    
    def setup_backend_callbacks(self):
        """Connect backend to UI"""
        self.backend_tracker.activity_changed.connect(self.on_activity_changed)
        self.backend_tracker.time_updated.connect(self.on_time_updated)
        self.backend_tracker.status_changed.connect(self.on_status_changed)
    
    def on_activity_changed(self, app_name: str, window_title: str):
        """Handle activity change from backend"""
        self.current_activity.update_activity(app_name, window_title)
    
    def on_time_updated(self, app_times: Dict[str, float]):
        """Handle time update from backend"""
        self.app_usage_table.update_app_times(app_times)
        self.update_stats(app_times)
        # Refresh history dates in case new data was added
        self.history_widget.refresh_dates()
    
    def update_stats(self, app_times: Dict[str, float]):
        """Update statistics cards"""
        if not app_times:
            return
        
        total_time = sum(app_times.values())
        app_count = len([t for t in app_times.values() if t >= 1])
        
        # Format total time
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        
        if hours > 0:
            total_time_str = f"{hours:02d}:{minutes:02d}:00"
        else:
            total_time_str = f"{minutes:02d}:00"
        
        self.total_time_card.update_value(total_time_str)
        self.apps_count_card.update_value(str(app_count))
        
        # Most used app
        if app_times:
            most_used = max(app_times.items(), key=lambda x: x[1])
            most_used_name = self.get_display_name(most_used[0])
            self.most_used_card.update_value(most_used_name)
    
    def get_display_name(self, process_name: str) -> str:
        name_map = {
            'chrome.exe': 'Chrome',
            'firefox.exe': 'Firefox',
            'msedge.exe': 'Edge',
            'code.exe': 'VS Code',
            'notepad.exe': 'Notepad',
            'explorer.exe': 'Explorer',
            'discord.exe': 'Discord',
            'spotify.exe': 'Spotify',
            'slack.exe': 'Slack',
            'teams.exe': 'Teams',
            'zoom.exe': 'Zoom',
            'photoshop.exe': 'Photoshop',
            'illustrator.exe': 'Illustrator',
            'figma.exe': 'Figma',
            'notion.exe': 'Notion',
        }
        return name_map.get(process_name, process_name.replace('.exe', '').title())
    
    def on_status_changed(self, status: str):
        """Handle status change from backend"""
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
    
    def on_app_launched(self, message):
        """Handle app launch notification"""
        self.show_notification("App Launcher", message)
    
    def setup_ui(self):
        self.setWindowTitle("TimeTracker")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Set clean styling
        self.setStyleSheet("""
            QMainWindow {
                background: #fafbfc;
            }
            QWidget {
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: white;
                color: #6b7280;
                border: 2px solid #f0f0f0;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 12px 24px;
                margin-right: 4px;
                font-weight: 500;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: #fafbfc;
                color: #000000;
                border-color: #e5e5e5;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background: #f9f9f9;
                color: #374151;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(32)
        
        # Left sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Main content with tabs
        content = self.create_content_area()
        main_layout.addWidget(content, 1)
    
    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(350)
        sidebar.setStyleSheet("""
            QFrame {
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Header
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
        
        # Current activity
        self.current_activity = CurrentActivityCard()
        layout.addWidget(self.current_activity)
        
        # Control button
        self.control_button = CleanButton("Pause", variant="secondary")
        self.control_button.clicked.connect(self.toggle_tracking)
        layout.addWidget(self.control_button)
        
        # Shortcuts info
        shortcuts_frame = QFrame()
        shortcuts_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
            }
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
        
        # App launcher info
        launcher_frame = QFrame()
        launcher_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #f0f0f0;
                border-radius: 12px;
            }
        """)
        
        launcher_layout = QVBoxLayout(launcher_frame)
        launcher_layout.setContentsMargins(20, 16, 20, 16)
        launcher_layout.setSpacing(12)
        
        launcher_title = QLabel("APP LAUNCHER")
        launcher_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        launcher_title.setStyleSheet("color: #6b7280; letter-spacing: 0.5px;")
        
        launcher_text = QLabel("Click app icons in the table\nto launch applications")
        launcher_text.setFont(QFont("Inter", 12))
        launcher_text.setStyleSheet("color: #374151; line-height: 1.6;")
        
        launcher_layout.addWidget(launcher_title)
        launcher_layout.addWidget(launcher_text)
        
        layout.addWidget(launcher_frame)
        layout.addStretch()
        
        return sidebar
    
    def create_content_area(self):
        content = QFrame()
        content.setStyleSheet("QFrame { background: transparent; }")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Today's activity tab
        today_tab = self.create_today_tab()
        self.tab_widget.addTab(today_tab, "Today")
        
        # History tab
        self.history_widget = HistoryWidget(self.data_manager)
        self.tab_widget.addTab(self.history_widget, "History")
        
        layout.addWidget(self.tab_widget)
        
        return content
    
    def create_today_tab(self):
        today_widget = QWidget()
        layout = QVBoxLayout(today_widget)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(24)
        
        # Header
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
        
        # Stats cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.total_time_card = StatsCard("Total Time", "00:00", "Today")
        self.apps_count_card = StatsCard("Applications", "0", "Used today")
        self.most_used_card = StatsCard("Most Used", "None", "Application")
        
        stats_layout.addWidget(self.total_time_card)
        stats_layout.addWidget(self.apps_count_card)
        stats_layout.addWidget(self.most_used_card)
        
        layout.addLayout(stats_layout)
        
        # App usage table
        self.app_usage_table = AppUsageTable()
        self.app_usage_table.app_launched.connect(self.on_app_launched)
        layout.addWidget(self.app_usage_table, 1)
        
        return today_widget
    
    def setup_system_tray(self):
        """Setup system tray"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create simple icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("#000000"))
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # Create menu
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
        """Start backend tracking"""
        self.backend_tracker.start_tracking()
    
    def toggle_tracking(self):
        """Toggle tracking via backend"""
        self.backend_tracker.toggle_pause()
    
    def show_notification(self, title: str, message: str):
        """Show system tray notification"""
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_application()
    
    def quit_application(self):
        """Quit application"""
        self.backend_tracker.stop()
        self.save_settings()
        QApplication.quit()
    
    def save_settings(self):
        """Save settings"""
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('windowState', self.saveState())
    
    def load_settings(self):
        """Load settings"""
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        
        window_state = self.settings.value('windowState')
        if window_state:
            self.restoreState(window_state)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set application properties
    app.setApplicationName("TimeTracker")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("TimeTracker")
    
    # Create and show main window
    window = TimeTrackerMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()