# main.py - 3-row debug (RAW / TUNED / SENT) + latency tracking

import pygame
import sys
import os
import time
import numpy as np
from multiprocessing import Process, Pipe
from logic_process import logic_process
from flight_reader import read_flight_data
from render_core import create_gradient_bg
from ui_components import draw_controller_icon, draw_gear_button, draw_settings_panel
from input_tuning_panel import draw_input_tuning_panel, get_tuned_left_stick, get_tuned_right_stick, load_settings
from config import *

load_settings()

parent_conn, child_conn = Pipe(False)
p = Process(target=logic_process, args=(child_conn,), daemon=True)
p.start()

pygame.init()
pygame.display.init()

try:
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
    print("Display init OK - driver:", pygame.display.get_driver())
except pygame.error as e:
    print(f"Display failed: {e}")
    p.terminate()
    sys.exit(1)

pygame.mouse.set_visible(False)

font = pygame.font.SysFont("monospace", 18, bold=True)
small_font = pygame.font.SysFont("monospace", 16)
debug_font = pygame.font.SysFont("monospace", 17, bold=True)

bg = create_gradient_bg(SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG_DARK, COLOR_BG_LIGHT)

btn_rect = pygame.Rect(BTN_RECT)
settings_target_x = SCREEN_WIDTH - 190
settings_rect = pygame.Rect(SCREEN_WIDTH, 0, 190, 600)
settings_speed = 30

settings_visible = False
second_panel_visible = False

last_flight_read = time.time()
last_file_mtime = 0.0
flight_latency_ms = flight_rate_hz = peak_latency = 0.0
lx = ly = rx = ry = l2 = r2 = 0

# Timing for latency tracking
raw_time = tuned_time = sent_time = 0.0

history = [0.0] * 110

clock = pygame.time.Clock()
running = True

prev_gear_pressed = False
gear_last_release_time = 0.0

prev_back_pressed = False
back_last_release_time = 0.0

prev_input_pressed = False
input_last_release_time = 0.0

while running:
    latest = [0.1, False, 0, 0]
    while parent_conn.poll():
        latest = parent_conn.recv()

    t_lat, t_down, tx, ty = latest

    if t_lat >= 0:
        history.pop(0)
        history.append(t_lat)
        peak_latency = max(peak_latency, t_lat)

    now = time.time()
    if now - last_flight_read >= 0.02:
        last_flight_read = now
        try:
            mtime = os.path.getmtime('/tmp/flight_status.txt')
            if mtime > last_file_mtime:
                last_file_mtime = mtime
                with open('/tmp/flight_status.txt', 'r') as f:
                    line = f.read().strip()
                    if line:
                        parts = line.split()
                        for part in parts:
                            if part.startswith("lx:"): lx = int(part.split(':')[1])
                            elif part.startswith("ly:"): ly = int(part.split(':')[1])
                            elif part.startswith("rx:"): rx = int(part.split(':')[1])
                            elif part.startswith("ry:"): ry = int(part.split(':')[1])
                            elif part.startswith("l2:"): l2 = int(part.split(':')[1])
                            elif part.startswith("r2:"): r2 = int(part.split(':')[1])
                            elif part.startswith("latency_ms:"): flight_latency_ms = float(part.split(':')[1])
                            elif part.startswith("rate_hz:"): flight_rate_hz = int(float(part.split(':')[1]))
        except:
            pass

    screen.blit(bg, (0, 0))

    if t_lat < 0:
        touch_text = "Touch: Disconnected"
        touch_color = COLOR_DISCONNECTED
    else:
        touch_text = f"Touch: {t_lat:5.2f} ms   Peak: {peak_latency:4.1f} ms"
        touch_color = COLOR_GOOD if t_lat < 8 else COLOR_WARN if t_lat < 25 else COLOR_DANGER

    screen.blit(font.render(touch_text, True, touch_color), (16, 14))

    flight_text = f"Flight: {flight_latency_ms:5.2f} ms   Rate: {flight_rate_hz} Hz"
    screen.blit(font.render(flight_text, True, COLOR_FLIGHT), (16, 50))

    # === 3-ROW DEBUG DISPLAY - Top Middle ===
    tuned_lx, tuned_ly = get_tuned_left_stick(lx, ly)
    tuned_rx, tuned_ry = get_tuned_right_stick(rx, ry)

    # Simulate "Sent" values (final values going to transmitter)
    sent_lx = tuned_lx
    sent_ly = tuned_ly
    sent_rx = tuned_rx
    sent_ry = tuned_ry
    sent_l2 = l2
    sent_r2 = r2

    debug_y = 85
    raw_color = (255, 200, 100)
    tuned_color = (100, 255, 100)
    sent_color = (100, 180, 255)

    raw_text = debug_font.render(f"RAW   LX:{lx:6d} LY:{ly:6d}  RX:{rx:6d} RY:{ry:6d}  L2:{l2:5d} R2:{r2:5d}", True, raw_color)
    tuned_text = debug_font.render(f"TUNED LX:{tuned_lx:6d} LY:{tuned_ly:6d}  RX:{tuned_rx:6d} RY:{tuned_ry:6d}  L2:{l2:5d} R2:{r2:5d}", True, tuned_color)
    sent_text = debug_font.render(f"SENT  LX:{sent_lx:6d} LY:{sent_ly:6d}  RX:{sent_rx:6d} RY:{sent_ry:6d}  L2:{sent_l2:5d} R2:{sent_r2:5d}", True, sent_color)

    screen.blit(raw_text, (SCREEN_WIDTH//2 - raw_text.get_width()//2, debug_y))
    screen.blit(tuned_text, (SCREEN_WIDTH//2 - tuned_text.get_width()//2, debug_y + 26))
    screen.blit(sent_text, (SCREEN_WIDTH//2 - sent_text.get_width()//2, debug_y + 52))

    # Live controller visualization
    stick_radius = 60
    stick_spacing = 240
    center_x = SCREEN_WIDTH // 2
    left_stick_x = center_x - (stick_spacing // 2)
    right_stick_x = center_x + (stick_spacing // 2)
    stick_y = SCREEN_HEIGHT - 180

    left_center = (left_stick_x, stick_y)
    pygame.draw.circle(screen, (80, 80, 80), left_center, stick_radius, 4)
    left_x = left_center[0] + (tuned_lx / 32768.0) * stick_radius
    left_y = left_center[1] + (tuned_ly / 32768.0) * stick_radius
    pygame.draw.circle(screen, (0, 255, 80), (int(left_x), int(left_y)), 12)

    right_center = (right_stick_x, stick_y)
    pygame.draw.circle(screen, (80, 80, 80), right_center, stick_radius, 4)
    right_x = right_center[0] + (tuned_rx / 32768.0) * stick_radius
    right_y = right_center[1] + (tuned_ry / 32768.0) * stick_radius
    pygame.draw.circle(screen, (0, 255, 80), (int(right_x), int(right_y)), 12)

    l2_pct = int((l2 / 32768.0) * 100)
    r2_pct = int((r2 / 32768.0) * 100)

    l2_text = small_font.render(f"L2: {l2_pct}%", True, (180, 255, 180))
    r2_text = small_font.render(f"R2: {r2_pct}%", True, (180, 255, 180))

    screen.blit(l2_text, (left_center[0] - l2_text.get_width() // 2, stick_y + stick_radius + 10))
    screen.blit(r2_text, (right_center[0] - r2_text.get_width() // 2, stick_y + stick_radius + 10))

    draw_controller_icon(screen, ICON_X, SCREEN_HEIGHT - ICON_Y_OFFSET, flight_latency_ms >= 0)

    gear_pressed = t_down and btn_rect.collidepoint(tx, ty)
    draw_gear_button(screen, btn_rect, gear_pressed)

    gear_tapped = False
    if not gear_pressed and prev_gear_pressed and time.time() - gear_last_release_time >= DEBOUNCE:
        gear_tapped = True
        gear_last_release_time = time.time()
    prev_gear_pressed = gear_pressed

    if gear_tapped:
        settings_visible = not settings_visible

    if settings_visible:
        settings_rect.x = max(settings_rect.x - settings_speed, settings_target_x)
    else:
        settings_rect.x = min(settings_rect.x + settings_speed, SCREEN_WIDTH)

    if settings_rect.x < SCREEN_WIDTH:
        back_rect, back_pressed, input_rect, input_pressed = draw_settings_panel(screen, settings_rect, t_down, tx, ty, second_panel_visible)

        back_tapped = False
        if not back_pressed and prev_back_pressed and time.time() - back_last_release_time >= DEBOUNCE:
            back_tapped = True
            back_last_release_time = time.time()
        prev_back_pressed = back_pressed

        if back_tapped:
            settings_visible = False
            second_panel_visible = False

        input_tapped = False
        if not input_pressed and prev_input_pressed and time.time() - input_last_release_time >= DEBOUNCE:
            input_tapped = True
            input_last_release_time = time.time()
        prev_input_pressed = input_pressed

        if input_tapped:
            second_panel_visible = not second_panel_visible

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
