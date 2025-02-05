import psutil
import pygetwindow as gw
import win32gui, win32process
import time
import keyboard
from threading import Thread, Lock

app_times = {}
lock = Lock()
stop_tracking = False
pause_tracking = False  # New flag for pausing/resuming tracking

def get_pid_from_active_window():
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid

def get_app_name_from_pid(pid):
    try:
        return psutil.Process(pid).name()
    except psutil.NoSuchProcess:
        return "Process not found"
    except Exception as e:
        return f"Error: {e}"

def is_private_browsing(window_title):
    # List of common private browsing indicators
    private_indicators = [
        "InPrivate",  # Edge
        "Incognito",  # Chrome
        "Private Browsing",  # Firefox
        "Private Window"  # Safari
    ]
    return any(indicator.lower() in window_title.lower() for indicator in private_indicators)

def listen_for_shortcuts():
    global stop_tracking, pause_tracking
    
    def on_stop_shortcut():
        global stop_tracking
        stop_tracking = True
        print("\nShortcut detected: Stopping tracking completely...\n")
    
    def on_pause_shortcut():
        global pause_tracking
        pause_tracking = not pause_tracking
        status = "Paused" if pause_tracking else "Resumed"
        print(f"\nTracking {status}!\n")
    
    # Register shortcuts
    keyboard.add_hotkey('ctrl+shift+q', on_stop_shortcut)
    keyboard.add_hotkey('ctrl+shift+p', on_pause_shortcut)  # New shortcut for pause/resume
    
    # Keep the listener running
    keyboard.wait('esc')  # Using 'esc' as a failsafe to end the listener thread

def track_active_window():
    global stop_tracking, pause_tracking
    print("Tracking active window.")
    print("Controls:")
    print("- Press 'Ctrl + Shift + Q' to stop tracking completely")
    print("- Press 'Ctrl + Shift + P' to pause/resume tracking")
    print("- Private browsing windows are automatically excluded\n")

    last_process = None
    last_time = time.time()
    last_tracking_state = True  # To handle state changes

    try:
        while not stop_tracking:
            current_time = time.time()
            
            # Handle tracking state changes
            if last_tracking_state != (not pause_tracking):
                last_time = current_time
                last_tracking_state = not pause_tracking
            
            if not pause_tracking:
                active_window = gw.getActiveWindow()
                if active_window:
                    active_window_title = active_window.title
                    
                    # Check for private browsing
                    if is_private_browsing(active_window_title):
                        if last_process:
                            elapsed_time = current_time - last_time
                            with lock:
                                if last_process not in app_times:
                                    app_times[last_process] = 0
                                app_times[last_process] += elapsed_time
                            
                        last_process = None
                        last_time = current_time
                        time.sleep(1)
                        continue
                else:
                    active_window_title = "Unknown Window"

                pid = get_pid_from_active_window()
                process_name = get_app_name_from_pid(pid)
                current_process = process_name

                if current_process != last_process:
                    if last_process:
                        elapsed_time = current_time - last_time
                        with lock:
                            if last_process not in app_times:
                                app_times[last_process] = 0
                            app_times[last_process] += elapsed_time
                        
                        # Convert seconds to a more readable format
                        hours, remainder = divmod(app_times[last_process], 3600)
                        minutes, seconds = divmod(remainder, 60)
                        time_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                        
                        print(f"Active Window Title: {active_window_title}")
                        print(f"Active Process ID: {pid}")
                        print(f"Active Application Name: {process_name}")
                        print(f"Application: {last_process}")
                        print(f"Time spent: {time_str}")
                        print("-----------------------------------------------------------")

                    print(f"Now tracking: {active_window_title}")
                    print(f"Process: {process_name}")
                    print("-----------------------------------------------------------")

                    last_process = current_process
                    last_time = current_time

            time.sleep(1)
            
    except KeyboardInterrupt:
        pass

    # Print final summary
    print("\nFinal Application Usage Summary:")
    for app, time_spent in app_times.items():
        hours, remainder = divmod(time_spent, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"{app}: {int(hours)}h {int(minutes)}m {int(seconds)}s")

if __name__ == "__main__":
    print("Starting Screen Time Tracker...")
    
    # Start keyboard listener in a separate thread
    shortcut_thread = Thread(target=listen_for_shortcuts, daemon=True)
    shortcut_thread.start()

    # Start active window tracking
    track_active_window()