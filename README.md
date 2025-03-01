# App-Time-Tracker

## Overview
App-Time-Tracker is a lightweight Windows application that helps you monitor how much time you spend on different applications and windows. The tracker runs in the background and keeps a record of your active windows, providing insights into your computer usage habits.

## Features
- Real-time tracking of active windows and applications
- Automatic detection and pausing during private browsing sessions
- Convenient keyboard shortcuts for controlling the tracker
- Summary report of time spent on each application
- Privacy-focused design that respects your sensitive browsing sessions

## Requirements
- Windows OS
- Python 3.6 or higher
- Required Python packages:
  - psutil
  - pygetwindow
  - pywin32
  - keyboard

## Installation

### 1. Install Python Dependencies
```
pip install psutil pygetwindow pywin32 keyboard
```

### 2. Download the Script
Download the App-Time-Tracker script from our repository or copy the provided code into a `.py` file.

## Usage

### Starting the Tracker
Run the script using Python:
```
python app_time_tracker.py
```

### Keyboard Controls
- **Ctrl + Shift + Q**: Stop tracking and display summary
- **P**: Pause tracking
- **R**: Resume tracking

### Privacy Features
- Automatically detects and pauses tracking during private browsing sessions
- Recognizes InPrivate (Edge), Incognito (Chrome), Private Browsing (Firefox), and Private Window (Safari) modes
- Resumes tracking when you exit private browsing

## How It Works
1. The application monitors the currently active window using Windows API calls
2. It records the time spent on each application based on process name
3. When you switch applications, it updates the tracking information
4. Private browsing detection prevents tracking during sensitive sessions

## Output
The tracker provides real-time updates in the console:
- Displays the title of the current active window
- Shows the process name of the active application
- Maintains a running total of time spent on each application
- Provides a complete summary when tracking is stopped

Example output:
```
Now tracking: Document - Microsoft Word
Process: WINWORD.EXE
-----------------------------------------------------------
Application: WINWORD.EXE
Time spent: 0h 15m 22s
-----------------------------------------------------------
```

## Future Development
- GUI interface for easier interaction
- Data visualization of application usage patterns
- Daily/weekly/monthly reports
- Application categorization
- Time management goals and alerts

## Contributing
App-Time-Tracker is completely free and open source. Contributions are welcome!

## License
Open source - feel free to modify and distribute while maintaining attribution to the original project.
