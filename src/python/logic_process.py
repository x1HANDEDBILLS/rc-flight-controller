# logic_process.py - touchscreen input with resolution-aware scaling
from evdev import InputDevice, ecodes, list_devices
from select import select
import time
from config import SCREEN_WIDTH, SCREEN_HEIGHT # Added this for proper scaling

def logic_process(conn):
    touch_dev = None
    device_path = None
    high_priority_keywords = ["biqu", "btt", "hdmi7", "hdmi5", "bi-qu", "bigtreetech", "usb touchscreen", "generic touch", "usb touch", "hid-compliant", "hid compliant"]
    exclude_keywords = ["sony", "controller", "wireless", "ps", "dual", "gamepad", "xbox", "joy", "mouse", "keyboard"]

    def try_open_touch():
        nonlocal touch_dev, device_path
        if touch_dev:
            try:
                touch_dev.close()
            except:
                pass
        touch_dev = None
        device_path = None
        candidates = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
                name_lower = dev.name.lower()
                if any(kw in name_lower for kw in exclude_keywords):
                    continue
                caps = dev.capabilities()
                has_mt = ecodes.ABS_MT_POSITION_X in caps.get(ecodes.EV_ABS, [])
                has_touch = ecodes.BTN_TOUCH in caps.get(ecodes.EV_KEY, [])
                if has_mt or has_touch:
                    candidates.append((path, dev.name, has_mt, has_touch))
                    if any(kw in name_lower for kw in high_priority_keywords):
                        touch_dev = dev
                        device_path = path
                        return True
            except:
                pass
        if touch_dev is None and candidates:
            candidates.sort(key=lambda x: (not x[2], not x[3]), reverse=True)
            touch_dev = InputDevice(candidates[0][0])
            device_path = candidates[0][0]
            return True
        return False

    print("Initial scan for touchscreen...")
    if not try_open_touch():
        print("No touchscreen found initially.")
        conn.send([999.0, False, 0, 0])
        # We don't return here so it can keep re-scanning in the loop
    else:
        try:
            touch_dev.grab()
            print(f"Device {touch_dev.name} grabbed exclusively")
        except Exception as e:
            print(f"Grab failed: {e}")

    is_down = False
    tx = ty = 0
    last_scan_attempt = time.time()

    # Get max values of the digitizer for accurate scaling
    abs_info_x = touch_dev.absinfo(ecodes.ABS_MT_POSITION_X) if touch_dev else None
    max_x = abs_info_x.max if abs_info_x else 4095
    abs_info_y = touch_dev.absinfo(ecodes.ABS_MT_POSITION_Y) if touch_dev else None
    max_y = abs_info_y.max if abs_info_y else 4095

    while True:
        if touch_dev is None:
            conn.send([-1.0, False, 0, 0])
            if time.time() - last_scan_attempt >= 2.0:
                last_scan_attempt = time.time()
                if try_open_touch():
                    try:
                        touch_dev.grab()
                        # Refresh digitizer max values on reconnect
                        max_x = touch_dev.absinfo(ecodes.ABS_MT_POSITION_X).max
                        max_y = touch_dev.absinfo(ecodes.ABS_MT_POSITION_Y).max
                    except:
                        pass
            time.sleep(0.5)
            continue

        try:
            t_start = time.perf_counter_ns()
            r, _, _ = select([touch_dev.fd], [], [], 0.012)

            if r:
                for event in touch_dev.read():
                    if event.type == ecodes.EV_ABS:
                        # Scaled to actual SCREEN size defined in config.py
                        if event.code == ecodes.ABS_MT_POSITION_X:
                            tx = int(event.value * SCREEN_WIDTH / max_x)
                        elif event.code == ecodes.ABS_MT_POSITION_Y:
                            ty = int(event.value * SCREEN_HEIGHT / max_y)
                    elif event.type == ecodes.EV_KEY:
                        if event.code == ecodes.BTN_TOUCH:
                            is_down = bool(event.value)
                    elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                        latency_ms = (time.perf_counter_ns() - t_start) / 1_000_000
                        conn.send([latency_ms, is_down, tx, ty])
            else:
                latency_ms = (time.perf_counter_ns() - t_start) / 1_000_000
                conn.send([latency_ms, is_down, tx, ty])

        except OSError as e:
            if e.errno == 19:
                print("Touch device lost - re-scanning...")
                touch_dev = None
                conn.send([-1.0, False, 0, 0])
            else:
                raise

        time.sleep(0.0005)