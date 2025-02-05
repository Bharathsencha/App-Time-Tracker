import psutil  # For process management
import pygetwindow as gw  # For window management
import win32gui, win32process  # Windows API for GUI and process handling
import time  # For adding delays
import keyboard  # For detecting keyboard shortcuts
from threading import Thread, Lock  # To run functions concurrently and ensure thread safety

app_times = {}  # Dictionary to store time spent on each application (using process name)
lock = Lock()  # Lock for thread safety

stop_tracking = False  # Flag to stop tracking when shortcut is pressed

# Retrieves the Process ID (PID) of the active window
def get_pid_from_active_window():
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid

# Retrieves the application name using the PID
def get_app_name_from_pid(pid):
    try:
        return psutil.Process(pid).name()
    except psutil.NoSuchProcess:
        return "Process not found"
    except Exception as e:
        return f"Error: {e}"

# Function to listen for a shortcut (Ctrl + Shift + Q) to stop tracking
def listen_for_shortcut():
    global stop_tracking
    keyboard.wait("ctrl+shift+q")  # Wait for shortcut press
    stop_tracking = True
    print("\nShortcut detected: Stopping tracking...\n")

# Tracking active window changes and printing active window details
def track_active_window():
    global stop_tracking
    print("Tracking active window. Press 'Ctrl + Shift + Q' to stop.\n")

    last_process = None  # Stores last active process info to detect changes
    last_time = time.time()  # Track time spent on the active window

    try:
        while not stop_tracking:
            active_window = gw.getActiveWindow()
            if active_window:
                active_window_title = active_window.title
            else:
                active_window_title = "Unknown Window"

            pid = get_pid_from_active_window()
            process_name = get_app_name_from_pid(pid)

            # Time spent on the current active application
            current_process = process_name
            current_time = time.time()

            if current_process != last_process:
                if last_process:
                    elapsed_time = current_time - last_time
                    with lock:  # Ensure thread safety
                        if last_process not in app_times:
                            app_times[last_process] = 0
                        app_times[last_process] += elapsed_time
                    print(f"Application: {last_process} spent {app_times[last_process]:.2f} seconds.")
                    print("-----------------------------------------------------------")

                # Print the new active application's details
                print(f"Active Window Title: {active_window_title}")
                print(f"Active Process ID: {pid}")
                print(f"Active Application Name: {process_name}")
                print("-----------------------------------------------------------")

                last_process = current_process
                last_time = current_time

            time.sleep(1)
    except KeyboardInterrupt:
        pass  # Avoids error when stopping with a shortcut

    print("\nFinal Application Usage Time:")
    for app, time_spent in app_times.items():
        print(f"{app}: {time_spent:.2f} seconds")

# Run the tracking function if executed directly
if __name__ == "__main__":
    print("Starting tracking...\nPress 'Ctrl + Shift + Q' to stop.\n")

    # Start keyboard listener in a separate thread
    shortcut_thread = Thread(target=listen_for_shortcut, daemon=True)
    shortcut_thread.start()

    # Start active window tracking
    track_active_window()
