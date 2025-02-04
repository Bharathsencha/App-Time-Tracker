import psutil  # For process management
import pygetwindow as gw  # For window management
import win32gui, win32process  # Windows API for GUI and process handling
import time  # For adding delays
from threading import Thread, Lock  # To run both functions concurrently and ensure thread safety

app_times = {}  # Dictionary to store time spent on each application (using PID)
lock = Lock()  # Lock for thread safety

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

# Tracking active window changes and printing active window details
def track_active_window():
    print("Tracking active window:")
    last_window = None  # Stores last active window info to detect changes
    last_time = time.time()  # Track time spent on the active window
    
    try:
        while True:
            active_window_title = gw.getActiveWindow().title
            pid = get_pid_from_active_window()
            process_name = get_app_name_from_pid(pid)
            
            # Time spent on current active window
            current_window = (active_window_title, pid, process_name)
            current_time = time.time()
            if current_window != last_window:
                if last_window:
                    elapsed_time = current_time - last_time
                    with lock:  # Ensure thread safety
                        if last_window[1] not in app_times:
                            app_times[last_window[1]] = 0
                        app_times[last_window[1]] += elapsed_time
                    print(f"PID {last_window[1]} (Window: {last_window[0]}) spent {app_times[last_window[1]]:.2f} seconds.")
                    print("-----------------------------------------------------------")

                # Print the new active window's details (PID and window title)
                print(f"Active Window Title: {active_window_title}")
                print(f"Active Process ID: {pid}")
                print(f"Active Application Name: {process_name}")
                print("-----------------------------------------------------------")

                last_window = current_window
                last_time = current_time

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped tracking.")

# Run the tracking function if executed directly
if __name__ == "__main__":
    print("Starting tracking...\n")
    
    # Running active window tracking in a thread
    active_window_thread = Thread(target=track_active_window)
    active_window_thread.start()
    active_window_thread.join()
