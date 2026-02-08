import pygame
import sys
import os
import numpy as np
import time
from evdev import InputDevice, ecodes, list_devices
from multiprocessing import Process, Pipe
from select import select

# ────────────────────────────────────────────────
# LOGIC PROCESS (input + timing)
# ────────────────────────────────────────────────

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
        return

    try:
        touch_dev.grab()
        print("Device grabbed exclusively")
    except Exception as e:
        print(f"Grab failed: {e}")

    is_down = False
    tx = ty = 0
    last_scan_attempt = time.time()

    while True:
        if touch_dev is None:
            conn.send([-1.0, False, 0, 0])
            if time.time() - last_scan_attempt >= 2.0:
                last_scan_attempt = time.time()
                if try_open_touch():
                    try:
                        touch_dev.grab()
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
                        if event.code == ecodes.ABS_MT_POSITION_X:
                            tx = int(event.value * 1024 / 4095)
                        elif event.code == ecodes.ABS_MT_POSITION_Y:
                            ty = int(event.value * 600 / 4095)
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

# ────────────────────────────────────────────────
# MAIN / RENDER
# ────────────────────────────────────────────────

def main():
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    parent_conn, child_conn = Pipe(duplex=False)
    p = Process(target=logic_process, args=(child_conn,), daemon=True)
    p.start()
    pygame.init()
    pygame.display.init()
    try:
        screen = pygame.display.set_mode((1024, 600), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
        print("Display initialized successfully - driver:", pygame.display.get_driver())
    except pygame.error as e:
        print(f"Display init failed: {e}")
        p.terminate()
        sys.exit(1)
    pygame.mouse.set_visible(False)
    font = pygame.font.SysFont("monospace", 18, bold=True)
    small_font = pygame.font.SysFont("monospace", 16)
    def create_gradient_bg(w, h, c1, c2):
        x = np.linspace(0, 1, w, dtype=np.float32)
        y = np.linspace(0, 1, h, dtype=np.float32)
        xv, yv = np.meshgrid(x, y)
        ratio = np.power((xv + yv) / 2, 1.15)
        r = (c1[0] + (c2[0] - c1[0]) * ratio).astype(np.uint8)
        g = (c1[1] + (c2[1] - c1[1]) * ratio).astype(np.uint8)
        b = (c1[2] + (c2[2] - c1[2]) * ratio).astype(np.uint8)
        arr = np.dstack((r, g, b)).swapaxes(0, 1)
        return pygame.surfarray.make_surface(arr).convert()
    bg = create_gradient_bg(1024, 600, (38, 39, 42), (14, 15, 18))
    btn_rect = pygame.Rect(934, 10, 80, 80)
    settings_rect = pygame.Rect(1024, 0, 190, 600)
    settings_visible = False
    settings_target_x = 1024 - 190
    settings_speed = 30
    gear_last_release_time = 0.0
    gear_debounce = 0.5
    close_last_release_time = 0.0
    close_debounce = 0.5
    prev_gear_pressed = False
    prev_close_pressed = False
    last_flight_read = time.time()
    flight_latency_ms = 0.0
    flight_rate_hz = 0
    lx = ly = rx = ry = l2 = r2 = 0
    clock = pygame.time.Clock()
    running = True
    while running:
        latest = [0.1, False, 0, 0]
        while parent_conn.poll():
            latest = parent_conn.recv()
        touch_latency_ms, touch_down, touch_x, touch_y = latest
        # Read flight data + controller inputs
        now = time.time()
        if now - last_flight_read >= 0.05:
            last_flight_read = now
            try:
                with open('/tmp/flight_status.txt', 'r') as f:
                    line = f.read().strip()
                    if line:
                        parts = line.split()
                        for part in parts:
                            if part.startswith("latency_ms:"):
                                flight_latency_ms = float(part.split(':')[1])
                            elif part.startswith("rate_hz:"):
                                flight_rate_hz = int(float(part.split(':')[1]))
                            elif part.startswith("lx:"):
                                lx = int(part.split(':')[1])
                            elif part.startswith("ly:"):
                                ly = int(part.split(':')[1])
                            elif part.startswith("rx:"):
                                rx = int(part.split(':')[1])
                            elif part.startswith("ry:"):
                                ry = int(part.split(':')[1])
                            elif part.startswith("l2:"):
                                l2 = int(part.split(':')[1])
                            elif part.startswith("r2:"):
                                r2 = int(part.split(':')[1])
            except:
                pass
        screen.blit(bg, (0, 0))
        txt_touch = f"Touch: {touch_latency_ms:5.2f} ms"
        surf_touch = font.render(txt_touch, True, (180, 185, 190))
        screen.blit(surf_touch, (16, 14))
        txt_flight = f"Flight: {flight_latency_ms:5.2f} ms Rate: {flight_rate_hz} Hz"
        surf_flight = font.render(txt_flight, True, (200, 200, 255))
        screen.blit(surf_flight, (16, 50))
        # Controller raw inputs (bottom center)
        ctrl_text = f"Left Stick: X {lx:6d} Y {ly:6d} Right Stick: X {rx:6d} Y {ry:6d}"
        surf_ctrl = small_font.render(ctrl_text, True, (180, 255, 180))
        screen.blit(surf_ctrl, (screen.get_width() // 2 - surf_ctrl.get_width() // 2, screen.get_height() - 80))
        trigger_text = f"L2 Trigger: {l2:6d} R2 Trigger: {r2:6d}"
        surf_trigger = small_font.render(trigger_text, True, (180, 255, 180))
        screen.blit(surf_trigger, (screen.get_width() // 2 - surf_trigger.get_width() // 2, screen.get_height() - 50))
        # Controller icon - bottom left - rectangle with two thumbstick circles in lower third
        icon_color = (40, 255, 80) if flight_latency_ms >= 0 else (255, 80, 80)
        icon_x, icon_y = 20, screen.get_height() - 70
        pygame.draw.rect(screen, icon_color, (icon_x, icon_y, 80, 50), width=4)
        stick_radius = 8
        left_center = (icon_x + 20, icon_y + 35)
        right_center = (icon_x + 60, icon_y + 35)
        pygame.draw.circle(screen, icon_color, left_center, stick_radius, 2)
        pygame.draw.circle(screen, icon_color, right_center, stick_radius, 2)
        # Settings gear button (top-right)
        gear_pressed = touch_down and btn_rect.collidepoint(touch_x, touch_y)
        btn_color = (50, 180, 120) if gear_pressed else (70, 75, 82)
        border_color = (100, 255, 160) if gear_pressed else (95, 100, 110)
        inner = btn_rect.inflate(-10, -10)
        inner.center = btn_rect.center
        pygame.draw.rect(screen, btn_color, inner, border_radius=18)
        pygame.draw.rect(screen, border_color, inner, width=3, border_radius=18)
        # Gear icon
        gear_center = btn_rect.center
        pygame.draw.circle(screen, (200, 200, 200), gear_center, 30, 4)
        for angle in range(0, 360, 45):
            x1 = gear_center[0] + 25 * np.cos(np.radians(angle))
            y1 = gear_center[1] + 25 * np.sin(np.radians(angle))
            x2 = gear_center[0] + 35 * np.cos(np.radians(angle))
            y2 = gear_center[1] + 35 * np.sin(np.radians(angle))
            pygame.draw.line(screen, (200, 200, 200), (x1, y1), (x2, y2), 4)
        pygame.draw.circle(screen, (200, 200, 200), gear_center, 10)
        # Detect gear button release (tap)
        gear_tapped = False
        if not gear_pressed and prev_gear_pressed and time.time() - gear_last_release_time >= gear_debounce:
            gear_tapped = True
            gear_last_release_time = time.time()
        prev_gear_pressed = gear_pressed
        # Settings panel slide animation
        if gear_tapped:
            settings_visible = not settings_visible
        if settings_visible:
            settings_rect.x = max(settings_rect.x - settings_speed, settings_target_x)
        else:
            settings_rect.x = min(settings_rect.x + settings_speed, 1024)
        # Draw settings panel
        if settings_rect.x < 1024:
            pygame.draw.rect(screen, (30, 30, 35), settings_rect)
            pygame.draw.rect(screen, (80, 80, 90), settings_rect, width=3)
            # Close button (right arrow)
            close_rect = pygame.Rect(settings_rect.right - 90, 10, 80, 80)
            close_pressed = touch_down and close_rect.collidepoint(touch_x, touch_y)
            close_color = (100, 100, 100) if close_pressed else (60, 60, 60)
            pygame.draw.rect(screen, close_color, close_rect, border_radius=18)
            pygame.draw.rect(screen, (150, 150, 150), close_rect, width=3, border_radius=18)
            # Right arrow
            arrow_points = [
                (close_rect.centerx - 20, close_rect.centery - 20),
                (close_rect.centerx + 20, close_rect.centery),
                (close_rect.centerx - 20, close_rect.centery + 20)
            ]
            pygame.draw.polygon(screen, (200, 200, 200), arrow_points)
            # Detect close button release (tap)
            close_tapped = False
            if not close_pressed and prev_close_pressed and time.time() - close_last_release_time >= close_debounce:
                close_tapped = True
                close_last_release_time = time.time()
            prev_close_pressed = close_pressed
            if close_tapped:
                settings_visible = False
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
        clock.tick(60)
    p.terminate()
    p.join(timeout=0.6)
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
