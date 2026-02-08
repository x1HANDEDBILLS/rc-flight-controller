# controller_monitor.py - fast monitoring for GUI (does NOT affect transmitter path)

import time

def controller_monitor(conn):
    while True:
        # REPLACE THIS WITH YOUR REAL CONTROLLER READ CODE
        # This is placeholder data to test the pipe
        # In real use, read from the same source as your C++ or Python control loop
        lx = 0
        ly = 0
        rx = 0
        ry = 0
        l2 = 0
        r2 = 0

        conn.send(('ctrl', lx, ly, rx, ry, l2, r2))
        time.sleep(0.016)  # 60 Hz updates for GUI
