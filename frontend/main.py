import sys
from PyQt6.QtWidgets import QApplication
from frontend.main_window import TimeTrackerMainWindow

def main():
    app = QApplication(sys.argv)
    window = TimeTrackerMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
