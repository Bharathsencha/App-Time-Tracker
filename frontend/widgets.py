from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QHBoxLayout, QHeaderView, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont, QPen
import time
import subprocess
import os
from datetime import datetime
from typing import Dict

class AppLauncher:
    @staticmethod
    def get_app_paths():
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
        try:
            app_paths = AppLauncher.get_app_paths()
            if process_name in app_paths:
                for path in app_paths[process_name]:
                    if os.path.exists(path):
                        subprocess.Popen([path])
                        return True
                app_name = process_name.replace('.exe', '')
                subprocess.Popen(['start', app_name], shell=True)
                return True
            else:
                app_name = process_name.replace('.exe', '')
                subprocess.Popen(['start', app_name], shell=True)
                return True
        except Exception as e:
            print(f"Error launching {process_name}: {e}")
            return False

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
            color = QColor(239, 68, 68)  # Red
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
        self.accumulated_duration = 0
        self.setup_ui()

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
            self.accumulated_duration = 0

            display_name = self.get_display_name(app_name)
            self.app_label.setText(display_name)

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
                self.start_time = time.time()
        else:
            if was_tracking:
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

    app_launched = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_times = {}
        self.setup_ui()

    def setup_ui(self):
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["", "Application", "Time", "Percentage"])

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
        """)

        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(0, 60)
            header.resizeSection(2, 140)
            header.resizeSection(3, 120)

        vertical_header = self.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)

        self.cellClicked.connect(self.on_cell_clicked)

    def on_cell_clicked(self, row, column):
        if column == 0:
            app_item = self.item(row, 1)
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

    def update_app_times(self, app_times):
        self.app_times = app_times
        self.refresh_display()

    def refresh_display(self):
        if not self.app_times:
            self.setRowCount(0)
            return

        total_time = sum(self.app_times.values())
        sorted_apps = sorted(self.app_times.items(), key=lambda x: x[1], reverse=True)
        filtered_apps = [(app, time_spent) for app, time_spent in sorted_apps if time_spent >= 1]

        self.setRowCount(len(filtered_apps))

        for row, (app_name, time_spent) in enumerate(filtered_apps):
            icon_item = QTableWidgetItem(self.get_app_icon(app_name))
            icon_item.setFont(QFont("Segoe UI Emoji", 20))
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setToolTip(f"Click to launch {self.get_display_name(app_name)}")
            self.setItem(row, 0, icon_item)

            app_item = QTableWidgetItem(self.get_display_name(app_name))
            app_item.setFont(QFont("Inter", 14, QFont.Weight.Medium))
            self.setItem(row, 1, app_item)

            time_item = QTableWidgetItem(self.format_time(time_spent))
            time_item.setFont(QFont("JetBrains Mono", 14, QFont.Weight.Bold))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 2, time_item)

            percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setFont(QFont("Inter", 14))
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

        title_label = QLabel(title.upper())
        title_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #6b7280; letter-spacing: 0.5px;")

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("JetBrains Mono", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #000000;")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

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
