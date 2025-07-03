import sys
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
from datetime import datetime
from backend.tracker import BackendTracker
from frontend.widgets import StatusDot, CleanButton, CurrentActivityCard, AppUsageTable, StatsCard
from frontend.widgets import HistoryWidget

class TimeTrackerMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.backend_tracker = BackendTracker()
        self.data_manager = self.backend_tracker.data_manager
        self.setup_backend_callbacks()
        self.setup_ui()
        self.setup_system_tray()
        self.start_tracking()

        # Load settings
        self.settings = QSettings('TimeTracker', 'TimeTrackerMinimal')
        self.load_settings()

    def setup_backend_callbacks(self):
        self.backend_tracker.activity_changed.connect(self.on_activity_changed)
        self.backend_tracker.time_updated.connect(self.on_time_updated)
        self.backend_tracker.status_changed.connect(self.on_status_changed)

    def on_activity_changed(self, app_name: str, window_title: str):
        self.current_activity.update_activity(app_name, window_title)

    def on_time_updated(self, app_times: dict):
        self.app_usage_table.update_app_times(app_times)
        self.update_stats(app_times)
        self.history_widget.refresh_dates()

    def update_stats(self, app_times: dict):
        if not app_times:
            return

        total_time = sum(app_times.values())
        app_count = len([t for t in app_times.values() if t >= 1])

        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)

        if hours > 0:
            total_time_str = f"{hours:02d}:{minutes:02d}:00"
        else:
            total_time_str = f"{minutes:02d}:00"

        self.total_time_card.update_value(total_time_str)
        self.apps_count_card.update_value(str(app_count))

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
        self.show_notification("App Launcher", message)

    def setup_ui(self):
        self.setWindowTitle("TimeTracker")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

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
        sidebar.setStyleSheet("""
            QFrame {
                background: transparent;
            }
        """)

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

        self.tab_widget = QTabWidget()

        today_tab = self.create_today_tab()
        self.tab_widget.addTab(today_tab, "Today")

        self.history_widget = HistoryWidget(self.data_manager)
        self.tab_widget.addTab(self.history_widget, "History")

        layout.addWidget(self.tab_widget)

        return content

    def create_today_tab(self):
        today_widget = QWidget()
        layout = QVBoxLayout(today_widget)
        layout.setContentsMargins(0, 24, 0, 0)
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
        self.app_usage_table.app_launched.connect(self.on_app_launched)
        layout.addWidget(self.app_usage_table, 1)

        return today_widget

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
