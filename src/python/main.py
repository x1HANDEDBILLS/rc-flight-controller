import pygame
import sys
import os
import time
import numpy as np
from multiprocessing import Process, Pipe
from logic_process import logic_process
from render_core import create_gradient_bg
from ui_components import draw_gear_button, draw_settings_panel, draw_controller_icon
from input_tuning_panel import get_tuned_left_stick, get_tuned_right_stick, load_settings
from mapper_panel import load_mapper_settings
from config import *

load_settings()
load_mapper_settings()

parent_conn, child_conn = Pipe(False)
p = Process(target=logic_process, args=(child_conn,), daemon=True)
p.start()

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
pygame.mouse.set_visible(False)

font = pygame.font.SysFont("monospace", 18, bold=True)
debug_font = pygame.font.SysFont("monospace", 17, bold=True)
bg = create_gradient_bg(SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG_DARK, COLOR_BG_LIGHT)
settings_rect = pygame.Rect(SCREEN_WIDTH, 0, 190, SCREEN_HEIGHT)

settings_visible = False
active_panel_index = -1
last_nav_time = 0
peak_latency = 0.0

# Persistent State
lx = ly = rx = ry = connected = 0
flight_latency_ms = flight_rate_hz = 0.0

# Protocol State (The "Sent" values from C++)
ch1 = ch2 = ch3 = ch4 = "0"

clock = pygame.time.Clock()
running = True

while running:
    latest = [0.1, False, 0, 0]
    while parent_conn.poll(): latest = parent_conn.recv()
    t_lat, t_down, tx, ty = latest
    peak_latency = max(peak_latency, t_lat)

    # LIVE REAL-TIME PARSER
    if os.path.exists('/tmp/flight_status.txt'):
        try:
            with open('/tmp/flight_status.txt', 'r') as f:
                f.seek(0)
                content = f.read().strip()
                if content:
                    parts = content.split()
                    data = {}
                    for p_item in parts:
                        if ':' in p_item:
                            k, v = p_item.split(':', 1)
                            data[k] = v
                    
                    # RAW Hardware Values (Big Numbers)
                    if 'raw_lx' in data: lx = int(float(data['raw_lx']))
                    if 'raw_ly' in data: ly = int(float(data['raw_ly']))
                    if 'raw_rx' in data: rx = int(float(data['raw_rx']))
                    if 'raw_ry' in data: ry = int(float(data['raw_ry']))
                    
                    # Protocol Values (Small Numbers 172-1811)
                    if 'ch1' in data: ch1 = data['ch1']
                    if 'ch2' in data: ch2 = data['ch2']
                    if 'ch3' in data: ch3 = data['ch3']
                    if 'ch4' in data: ch4 = data['ch4']
                    
                    if 'connected' in data: connected = int(float(data['connected']))
                    if 'latency_ms' in data: flight_latency_ms = float(data['latency_ms'])
                    if 'rate_hz' in data: flight_rate_hz = float(data['rate_hz'])
        except Exception:
            pass

    screen.blit(bg, (0, 0))
    t_color = (0, 255, 100) if t_lat < 10 else (255, 50, 50)
    screen.blit(font.render(f"Touch: {t_lat:5.2f}ms  Peak: {peak_latency:4.1f}ms", True, t_color), (16, 14))
    screen.blit(font.render(f"Flight: {flight_latency_ms:5.2f}ms  Rate: {int(flight_rate_hz)}Hz", True, (100, 180, 255)), (16, 45))

    # TUNED values calculated locally in Python for the "Tuned" row
    tlx, tly = get_tuned_left_stick(lx, ly)
    trx, try_ = get_tuned_right_stick(rx, ry)
    
    # Update UI Text
    debug_y = 85
    r_txt = debug_font.render(f"RAW   LX:{lx:6d} LY:{ly:6d} RX:{rx:6d} RY:{ry:6d}", True, (255, 200, 100))
    t_txt = debug_font.render(f"TUNED LX:{tlx:6d} LY:{tly:6d} RX:{trx:6d} RY:{try_:6d}", True, (100, 255, 100))
    
    # FIX: "SENT" now displays the strings ch1-ch4 directly from the file
    s_txt = debug_font.render(f"SENT   LX:{ch1:>4} LY:{ch2:>4} RX:{ch3:>4} RY:{ch4:>4}", True, (100, 180, 255))
    
    screen.blit(r_txt, (SCREEN_WIDTH//2 - r_txt.get_width()//2, debug_y))
    screen.blit(t_txt, (SCREEN_WIDTH//2 - t_txt.get_width()//2, debug_y + 25))
    screen.blit(s_txt, (SCREEN_WIDTH//2 - s_txt.get_width()//2, debug_y + 50))

    # Sticks visualizer
    for sx, val_x, val_y in [(SCREEN_WIDTH//2 - 120, lx, ly), (SCREEN_WIDTH//2 + 120, rx, ry)]:
        pygame.draw.circle(screen, (60, 60, 65), (sx, 350), 60, 3)
        jx = sx + (val_x / 32768.0) * 60
        jy = 350 + (val_y / 32768.0) * 60
        pygame.draw.circle(screen, (0, 255, 100), (int(jx), int(jy)), 10)

    draw_controller_icon(screen, 20, SCREEN_HEIGHT - 75, connected == 1)
    
    gear_rect = pygame.Rect(BTN_RECT)
    gear_pressed = t_down and gear_rect.collidepoint(tx, ty)
    draw_gear_button(screen, gear_rect, gear_pressed)
    
    now = time.time()
    if gear_pressed and (now - last_nav_time) > 0.4:
        settings_visible = not settings_visible
        last_nav_time = now

    if settings_visible:
        settings_rect.x = max(settings_rect.x - 30, SCREEN_WIDTH - 190)
        clicked = draw_settings_panel(screen, settings_rect, t_down, tx, ty, active_panel_index)
        if clicked != -1 and (now - last_nav_time) > 0.3:
            if clicked == 1:
                settings_visible = False
                active_panel_index = -1
            else: active_panel_index = clicked
            last_nav_time = now
    else:
        settings_rect.x = min(settings_rect.x + 30, SCREEN_WIDTH)
        active_panel_index = -1

    pygame.display.flip()
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
    clock.tick(60)

p.terminate()
pygame.quit()