import pygame
import sys
import os
import time
import socket
import numpy as np
from multiprocessing import Process, Pipe
from logic_process import logic_process
from render_core import create_gradient_bg
from ui_components import draw_gear_button, draw_settings_panel, draw_controller_icon
# Import both tuning state and the draw function
from input_tuning_panel import load_settings, draw_input_tuning_panel, TUNING_STATE
from mapper_panel import load_mapper_settings, draw_mapper_panel, get_tuned_val, CHANNEL_MAPS, SPLIT_CONFIG
from config import *

# --- UDP SETUP FOR C++ ENGINE ---
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ENGINE_ADDR = ("127.0.0.1", 5005)

def sync_to_engine():
    """
    Sends the current mapping and split-mixer rules to the C++ engine.
    This bridges the gap between 'TUNED' (Python) and 'SENT' (C++).
    """
    try:
        # 1. SYNC CHANNEL MAPS
        # Format: MAP|ch0,ch1...ch15|target_ch,pos_id,neg_id,pos_c,pos_r,neg_c,neg_r
        m_str = ",".join(map(str, CHANNEL_MAPS))
        s = SPLIT_CONFIG
        split_data = f"{s['target_ch']},{s['pos_id']},{s['neg_id']},{int(s['pos_center'])},{int(s['pos_reverse'])},{int(s['neg_center'])},{int(s['neg_reverse'])}"
        packet = f"SET_MAP|{m_str}|{split_data}"
        udp_sock.sendto(packet.encode(), ENGINE_ADDR)

        # 2. SYNC TUNING PARAMS (Smoothing, Rates, Cinematic)
        # This ensures C++ starts with the same values saved in your JSON
        t = TUNING_STATE
        params = [
            f"SMOOTH:{t['smoothing']}",
            f"RATE:{t['global_rate']}",
            f"EXPO:{t['expo']}",
            f"CINE_ON:{int(t['cine_on'])}",
            f"CINE_VAL:{t['cine_intensity']}",
            f"L_DZ:{t['left_deadzone']}",
            f"R_DZ:{t['right_deadzone']}"
        ]
        for p_msg in params:
            udp_sock.sendto(p_msg.encode(), ENGINE_ADDR)

    except Exception as e:
        print(f"UDP Sync Error: {e}")

# Initialize configs
load_settings()
load_mapper_settings()
sync_to_engine() # Sync everything on startup

# Setup communication for touch/logic
parent_conn, child_conn = Pipe(False)
p = Process(target=logic_process, args=(child_conn,), daemon=True)
p.start()

pygame.init()
# Use DOUBLEBUF and HWSURFACE for smooth rendering of live numbers
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
peak_latency = 0.0

# Persistent State
connected = 0
flight_latency_ms = flight_rate_hz = 0.0
raw_signals = [0] * 23 

# Protocol State (The "Sent" values from C++)
ch_sent = ["0"] * 16

clock = pygame.time.Clock()
running = True

while running:
    # Handle Touch Pipe
    latest = [0.1, False, 0, 0]
    while parent_conn.poll(): 
        latest = parent_conn.recv()
    t_lat, t_down, tx, ty = latest
    peak_latency = max(peak_latency, t_lat)

    # --- LIVE REAL-TIME PARSER ---
    # Captures current status from the C++ flight controller
    if os.path.exists('/tmp/flight_status.txt'):
        try:
            with open('/tmp/flight_status.txt', 'r') as f:
                content = f.read().strip()
                if content:
                    parts = content.split()
                    data = {p_item.split(':', 1)[0]: p_item.split(':', 1)[1] for p_item in parts if ':' in p_item}
                    
                    # 1. DYNAMIC RAW INPUT PARSER
                    for key, val in data.items():
                        if key.startswith('rawid'):
                            try:
                                idx = int(key.replace('rawid', ''))
                                if idx < len(raw_signals):
                                    raw_signals[idx] = int(float(val))
                            except: pass

                    # 2. Protocol Values (CH1-CH16)
                    for i in range(16):
                        key = f'ch{i+1}'
                        if key in data:
                            ch_sent[i] = data[key]
                    
                    if 'connected' in data: connected = int(float(data['connected']))
                    if 'latency_ms' in data: flight_latency_ms = float(data['latency_ms'])
                    if 'rate_hz' in data: flight_rate_hz = float(data['rate_hz'])
        except Exception: pass

    # --- LIVE TUNING CALCULATION (FOR UI FEEDBACK) ---
    tuned_channels = [0] * 16
    for ch_idx in range(16):
        if ch_idx == SPLIT_CONFIG["target_ch"]:
            s = SPLIT_CONFIG
            p_raw = raw_signals[s["pos_id"]] if s["pos_id"] < 23 else -32768
            n_raw = raw_signals[s["neg_id"]] if s["neg_id"] < 23 else -32768
            
            p_tuned = get_tuned_val(p_raw, s["pos_center"], s["pos_reverse"])
            n_tuned = get_tuned_val(n_raw, s["neg_center"], s["neg_reverse"])
            
            tuned_channels[ch_idx] = max(-32768, min(32767, p_tuned + n_tuned))
        else:
            src_id = CHANNEL_MAPS[ch_idx]
            tuned_channels[ch_idx] = raw_signals[src_id] if src_id < 23 else -32768

    # Render Background
    screen.blit(bg, (0, 0))
    t_color = (0, 255, 100) if t_lat < 10 else (255, 50, 50)
    screen.blit(font.render(f"Touch: {t_lat:5.2f}ms  Peak: {peak_latency:4.1f}ms", True, t_color), (16, 14))
    screen.blit(font.render(f"Flight: {flight_latency_ms:5.2f}ms  Rate: {int(flight_rate_hz)}Hz", True, (100, 180, 255)), (16, 45))

    # --- RENDER DEBUG TEXT ---
    debug_y = 85
    r_txt = debug_font.render(f"RAW ID  00:{raw_signals[0]:6d} 01:{raw_signals[1]:6d} 02:{raw_signals[2]:6d} 03:{raw_signals[3]:6d}", True, (255, 200, 100))
    t_txt = debug_font.render(f"TUNED  CH1:{tuned_channels[0]:6d} CH2:{tuned_channels[1]:6d} CH3:{tuned_channels[2]:6d} CH4:{tuned_channels[3]:6d}", True, (100, 255, 100))
    s_txt = debug_font.render(f"SENT   CH1:{str(ch_sent[0]):>6} CH2:{str(ch_sent[1]):>6} CH3:{str(ch_sent[2]):>6} CH4:{str(ch_sent[3]):>6}", True, (100, 180, 255))
    
    screen.blit(r_txt, (SCREEN_WIDTH//2 - r_txt.get_width()//2, debug_y))
    screen.blit(t_txt, (SCREEN_WIDTH//2 - t_txt.get_width()//2, debug_y + 25))
    screen.blit(s_txt, (SCREEN_WIDTH//2 - s_txt.get_width()//2, debug_y + 50))

    # --- DYNAMIC STICK VISUALIZER ---
    stick_centers = [(SCREEN_WIDTH//2 - 120, 0, 1, "CH 1/2"), (SCREEN_WIDTH//2 + 120, 2, 3, "CH 3/4")]
    for sx, x_idx, y_idx, label in stick_centers:
        pygame.draw.circle(screen, (60, 60, 65), (sx, 350), 60, 3)
        pygame.draw.line(screen, (45, 45, 50), (sx-60, 350), (sx+60, 350), 1)
        pygame.draw.line(screen, (45, 45, 50), (sx, 350-60), (sx, 350+60), 1)
        
        jx = sx + (tuned_channels[x_idx] / 32768.0) * 60
        jy = 350 + (tuned_channels[y_idx] / 32768.0) * 60
        
        pygame.draw.circle(screen, (0, 255, 100), (int(jx), int(jy)), 10)
        lbl = small_font.render(label, True, (120, 120, 130))
        screen.blit(lbl, (sx - lbl.get_width()//2, 420))

    draw_controller_icon(screen, 20, SCREEN_HEIGHT - 75, connected == 1)
    
    gear_rect = pygame.Rect(BTN_RECT)
    gear_pressed = t_down and gear_rect.collidepoint(tx, ty)
    draw_gear_button(screen, gear_rect, gear_pressed)
    
    now = time.time()
    if gear_pressed and (now - last_nav_time) > 0.4:
        settings_visible = not settings_visible
        last_nav_time = now

    # --- SETTINGS SIDEBAR & PANEL LOGIC ---
    if settings_visible:
        settings_rect.x = max(settings_rect.x - 30, SCREEN_WIDTH - 190)
        
        # Draw the sidebar and detect if a tab was clicked
        clicked = draw_settings_panel(screen, settings_rect, t_down, tx, ty, active_panel_index, raw_signals)
        
        panel_rect = pygame.Rect(0, 0, SCREEN_WIDTH - 190, SCREEN_HEIGHT)

        if active_panel_index == 0:  # Input Tuning (Expo/Smooth/Cine)
            # This function internaly sends UDP packets via its stream_to_cpp calls
            draw_input_tuning_panel(screen, panel_rect, t_down, tx, ty, raw_signals)

        elif active_panel_index == 2:  # Input Mapper Panel
            was_changed = draw_mapper_panel(screen, panel_rect, t_down, tx, ty, raw_signals)
            if was_changed:
                sync_to_engine() 

        # Handle Sidebar Navigation
        if clicked != -1 and (now - last_nav_time) > 0.3:
            if clicked == 1: # Close sidebar button index
                settings_visible = False
                active_panel_index = -1
            else: 
                active_panel_index = clicked
            last_nav_time = now
    else:
        # Slide sidebar out
        settings_rect.x = min(settings_rect.x + 30, SCREEN_WIDTH)
        active_panel_index = -1

    pygame.display.flip()
    
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: 
            running = False
    
    clock.tick(60)

# Cleanup
p.terminate()
pygame.quit()
sys.exit()