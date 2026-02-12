import pygame
import sys
import os
import time
import socket
import numpy as np
from multiprocessing import Process, Pipe
from logic_process import logic_process
from render_core import create_gradient_bg
from ui_components import (
    draw_gear_button, draw_settings_panel, draw_controller_icon, 
    PANEL_MAP, shared_keyboard, shared_keypad
)
from input_tuning_panel import load_settings, TUNING_STATE
from mapper_panel import load_mapper_settings, get_tuned_val, CHANNEL_MAPS, SPLIT_CONFIG
from config import *

# --- UDP SETUP FOR C++ ENGINE ---
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ENGINE_ADDR = ("127.0.0.1", 5005)

def sync_to_engine(retries=3, delay=1.0):
    """
    Sends the current mapping and tuning rules to the C++ engine.
    """
    print("Syncing configs to C++ engine...")
    for attempt in range(retries):
        try:
            # 1. SYNC CHANNEL MAPS
            m_str = ",".join(map(str, CHANNEL_MAPS))
            s = SPLIT_CONFIG
            split_data = f"{s['target_ch']},{s['pos_id']},{s['neg_id']},{int(s['pos_center'])},{int(s['pos_reverse'])},{int(s['neg_center'])},{int(s['neg_reverse'])}"
            packet = f"SET_MAP|{m_str}|{split_data}"
            udp_sock.sendto(packet.encode(), ENGINE_ADDR)

            # 2. SYNC TUNING PARAMS (Smoothing, Rates, Cinematic, Deadzones)
            t = TUNING_STATE
            params = [
                f"SMOOTH:{t['smoothing']}",
                f"RATE:{t['global_rate']}",
                f"EXPO:{t['expo']}",
                f"CINE_ON:{int(t['cine_on'])}",
                f"CINE_SPD:{t['cine_speed']}", 
                f"CINE_ACC:{t['cine_accel']}",
                f"L_DZ:{round(t['left_deadzone'] / 10.0, 2)}",
                f"R_DZ:{round(t['right_deadzone'] / 10.0, 2)}"
            ]
            for p_msg in params:
                udp_sock.sendto(p_msg.encode(), ENGINE_ADDR)
            print("Sync complete.")
            return True 

        except Exception as e:
            print(f"UDP Sync Attempt {attempt+1} Error: {e}. Retrying in {delay}s...")
            time.sleep(delay)
    print("Sync failed after retries.")
    return False

# Initialize configs and sync
load_settings()
load_mapper_settings()
sync_to_engine()

# Setup communication for touch/logic
parent_conn, child_conn = Pipe(False)
p = Process(target=logic_process, args=(child_conn,), daemon=True)
p.start()

pygame.display.init()
pygame.font.init()

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
pygame.mouse.set_visible(False)

font = pygame.font.SysFont("monospace", 18, bold=True)
small_font = pygame.font.SysFont("monospace", 14, bold=True)
debug_font = pygame.font.SysFont("monospace", 17, bold=True)
bg = create_gradient_bg(SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG_DARK, COLOR_BG_LIGHT)
settings_rect = pygame.Rect(SCREEN_WIDTH, 0, 190, SCREEN_HEIGHT)

# UI State
settings_visible = False
active_panel_index = -1
last_nav_time = 0
ui_lock_time = 0   # <--- GLOBAL TOUCH SHIELD TIMER
peak_latency = 0.0

# Persistent Flight Data
connected = 0
flight_latency_ms = flight_rate_hz = 0.0
raw_signals = [0] * 23 
tuned_signals = [0] * 23 
ch_sent = ["0"] * 16

clock = pygame.time.Clock()
running = True

try:
    while running:
        # 1. Handle Touch Pipe
        latest = [0.1, False, 0, 0]
        while parent_conn.poll(): 
            latest = parent_conn.recv()
        t_lat, t_down, tx, ty = latest
        peak_latency = max(peak_latency, t_lat)

        now = time.time()
        
        # --- TOUCH SHIELD LOGIC ---
        # Detect if an overlay was open in the PREVIOUS frame
        prev_overlay_active = shared_keyboard.active or shared_keypad.active
        
        # Check if touch is currently locked (Grace period after UI changes)
        is_locked = (now - ui_lock_time) < 0.3
        
        # This is the filtered signal we pass to UI elements
        safe_t_down = t_down and not is_locked

        # 2. Parse Telemetry from C++ Engine
        if os.path.exists('/tmp/flight_status.txt'):
            try:
                with open('/tmp/flight_status.txt', 'r') as f:
                    content = f.read().strip()
                    if content:
                        parts = content.split()
                        data = {p_item.split(':', 1)[0]: p_item.split(':', 1)[1] for p_item in parts if ':' in p_item}
                        for key, val in data.items():
                            if key.startswith('rawid'):
                                idx = int(key.replace('rawid', ''))
                                if idx < 23: raw_signals[idx] = int(float(val))
                            elif key.startswith('tunedid'):
                                idx = int(key.replace('tunedid', ''))
                                if idx < 23: tuned_signals[idx] = int(float(val))
                            elif key.startswith('ch'):
                                idx = int(key.replace('ch', '')) - 1
                                if idx < 16: ch_sent[idx] = val
                        if 'connected' in data: connected = int(float(data['connected']))
                        if 'latency_ms' in data: flight_latency_ms = float(data['latency_ms'])
                        if 'rate_hz' in data: flight_rate_hz = float(data['rate_hz'])
            except Exception: 
                pass

        # 3. Stick Preview Logic
        mapped_preview = [0] * 16
        for i in range(16):
            if i == SPLIT_CONFIG["target_ch"]:
                s = SPLIT_CONFIG
                p_raw = tuned_signals[s["pos_id"]] if s["pos_id"] < 23 else -32768
                n_raw = tuned_signals[s["neg_id"]] if s["neg_id"] < 23 else -32768
                p_tuned = get_tuned_val(p_raw, s["pos_center"], s["pos_reverse"])
                n_tuned = get_tuned_val(n_raw, s["neg_center"], s["neg_reverse"])
                mapped_preview[i] = max(-32768, min(32767, p_tuned + n_tuned))
            else:
                src_id = CHANNEL_MAPS[i]
                mapped_preview[i] = tuned_signals[src_id] if src_id < 23 else -32768

        # 4. Rendering
        screen.blit(bg, (0, 0))
        
        # Header Status
        t_color = (0, 255, 100) if t_lat < 10 else (255, 50, 50)
        screen.blit(font.render(f"Touch: {t_lat:5.2f}ms  Peak: {peak_latency:4.1f}ms", True, t_color), (16, 14))
        screen.blit(font.render(f"Flight: {flight_latency_ms:5.2f}ms  Rate: {int(flight_rate_hz)}Hz", True, (100, 180, 255)), (16, 45))

        # Debug Data Table
        debug_y = 85
        r_txt = debug_font.render(f"RAW ID  00:{raw_signals[0]:6d} 01:{raw_signals[1]:6d} 02:{raw_signals[2]:6d} 03:{raw_signals[3]:6d}", True, (255, 200, 100))
        t_txt = debug_font.render(f"TUNED  CH1:{mapped_preview[0]:6d} CH2:{mapped_preview[1]:6d} CH3:{mapped_preview[2]:6d} CH4:{mapped_preview[3]:6d}", True, (100, 255, 100))
        s_txt = debug_font.render(f"SENT   CH1:{str(ch_sent[0]):>6} CH2:{str(ch_sent[1]):>6} CH3:{str(ch_sent[2]):>6} CH4:{str(ch_sent[3]):>6}", True, (100, 180, 255))
        screen.blit(r_txt, (SCREEN_WIDTH//2 - r_txt.get_width()//2, debug_y))
        screen.blit(t_txt, (SCREEN_WIDTH//2 - t_txt.get_width()//2, debug_y + 25))
        screen.blit(s_txt, (SCREEN_WIDTH//2 - s_txt.get_width()//2, debug_y + 50))

        # Stick Visualizers
        stick_centers = [(SCREEN_WIDTH//2 - 120, 350, 0, 1, "CH 1/2"), (SCREEN_WIDTH//2 + 120, 350, 2, 3, "CH 3/4")]
        for sx, sy, x_idx, y_idx, label in stick_centers:
            pygame.draw.circle(screen, (60, 60, 65), (sx, sy), 60, 3)
            jx = sx + (mapped_preview[x_idx] / 32768.0) * 60
            jy = sy + (mapped_preview[y_idx] / 32768.0) * 60
            pygame.draw.circle(screen, (0, 255, 100), (int(jx), int(jy)), 10)
            lbl = small_font.render(label, True, (120, 120, 130))
            screen.blit(lbl, (sx - lbl.get_width()//2, sy + 70))

        # Bottom Icons
        draw_controller_icon(screen, 20, SCREEN_HEIGHT - 75, connected == 1)
        
        # Gear Button (Uses safe_t_down)
        gear_rect = pygame.Rect(BTN_RECT)
        gear_pressed = safe_t_down and gear_rect.collidepoint(tx, ty)
        draw_gear_button(screen, gear_rect, gear_pressed)
        
        if gear_pressed and (now - last_nav_time) > 0.4:
            settings_visible = not settings_visible
            last_nav_time = now
            ui_lock_time = now # Shield background when toggling sidebar

        # 5. Settings Sidebar & Sub-Panel Logic
        if settings_visible:
            settings_rect.x = max(settings_rect.x - 30, SCREEN_WIDTH - 190)
            
            # Pass safe_t_down to the UI logic
            new_clicked, settings_changed = draw_settings_panel(
                screen, settings_rect, safe_t_down, tx, ty, active_panel_index, raw_signals, tuned_signals
            )
            
            # Check if an overlay (keyboard/keypad) JUST closed
            curr_overlay_active = shared_keyboard.active or shared_keypad.active
            if prev_overlay_active and not curr_overlay_active:
                ui_lock_time = now # Lock touch for 300ms so background doesn't click

            if settings_changed:
                sync_to_engine()

            if new_clicked != -1 and (now - last_nav_time) > 0.3:
                if PANEL_MAP[new_clicked][0] == "Back":
                    settings_visible = False
                    active_panel_index = -1
                else:
                    active_panel_index = new_clicked
                last_nav_time = now
                ui_lock_time = now # Shield touch during tab switches
        else:
            settings_rect.x = min(settings_rect.x + 30, SCREEN_WIDTH)
            active_panel_index = -1

        pygame.display.flip()
        
        # 6. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: 
                running = False
            elif event.type == pygame.QUIT:
                running = False

        clock.tick(60)

except KeyboardInterrupt:
    print("\nShutting down gracefully...")

finally:
    if p.is_alive():
        p.terminate()
        p.join(timeout=2.0)
    pygame.quit()
    udp_sock.close()
    sys.exit(0)