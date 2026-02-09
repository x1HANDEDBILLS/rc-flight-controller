# input_tuning_panel.py - Paginated Input Tuning with High-Speed Streaming
import pygame
import time
import json
import os
import socket
from config import *
from ui_helpers import draw_numeric_stepper

# Match the file path used by the C++ engine
TUNING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "inputtuning.json")

# Global cache to prevent race conditions during rapid clicking
cached_config = {}

# --- UDP Socket Setup for Instant Tuning ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def stream_to_cpp(key, value_percent):
    """Sends value to C++ instantly via UDP."""
    try:
        # Convert percent (5) to decimal (0.05) for C++
        message = f"{key}:{value_percent / 100.0}"
        sock.sendto(message.encode(), (UDP_IP, UDP_PORT))
    except:
        pass 

# Internal Pagination State
current_page = 0
last_interaction_time = 0

# Track button states for the stepper logic
prev_states = {
    "l_dec": False, "l_inc": False,
    "r_dec": False, "r_inc": False
}
last_release = {
    "l_dec": 0.0, "l_inc": 0.0,
    "r_dec": 0.0, "r_inc": 0.0
}

def draw_input_tuning_panel(screen, rect, touch_down, touch_x, touch_y, panel_visible=None):
    global LEFT_STICK_DEADZONE, RIGHT_STICK_DEADZONE
    global current_page, last_interaction_time
    global prev_states, last_release

    # Title based on page
    title_font = pygame.font.SysFont("monospace", 28, bold=True)
    page_titles = ["Deadzone Tuning", "Sensitivity & Rates", "Expo Curves"]
    title = title_font.render(f"Input: {page_titles[current_page]}", True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 30))

    # --- PAGE RENDERING ---
    if current_page == 0:
        # Page 1: Deadzones
        l_x, l_y = rect.left + 50, rect.y + 120
        r_x, r_y = rect.left + 50, l_y + 100

        l_dec_r, l_dec_p, l_inc_r, l_inc_p = draw_numeric_stepper(
            screen, l_x, l_y, LEFT_STICK_DEADZONE, "Left Deadzone", touch_down, touch_x, touch_y
        )
        r_dec_r, r_dec_p, r_inc_r, r_inc_p = draw_numeric_stepper(
            screen, r_x, r_y, RIGHT_STICK_DEADZONE, "Right Deadzone", touch_down, touch_x, touch_y
        )

        # Logic for Deadzone adjustments
        now = time.time()
        
        # Left Stick Logic
        if not l_dec_p and prev_states["l_dec"] and (now - last_release["l_dec"]) >= 0.05:
            LEFT_STICK_DEADZONE = max(0, LEFT_STICK_DEADZONE - 1)
            stream_to_cpp("L_DZ", LEFT_STICK_DEADZONE) 
            save_settings()                            
            last_release["l_dec"] = now
        if not l_inc_p and prev_states["l_inc"] and (now - last_release["l_inc"]) >= 0.05:
            LEFT_STICK_DEADZONE = min(100, LEFT_STICK_DEADZONE + 1)
            stream_to_cpp("L_DZ", LEFT_STICK_DEADZONE)
            save_settings()
            last_release["l_inc"] = now
            
        # Right Stick Logic
        if not r_dec_p and prev_states["r_dec"] and (now - last_release["r_dec"]) >= 0.05:
            RIGHT_STICK_DEADZONE = max(0, RIGHT_STICK_DEADZONE - 1)
            stream_to_cpp("R_DZ", RIGHT_STICK_DEADZONE)
            save_settings()
            last_release["r_dec"] = now
        if not r_inc_p and prev_states["r_inc"] and (now - last_release["r_inc"]) >= 0.05:
            RIGHT_STICK_DEADZONE = min(100, RIGHT_STICK_DEADZONE + 1)
            stream_to_cpp("R_DZ", RIGHT_STICK_DEADZONE)
            save_settings()
            last_release["r_inc"] = now
        
        prev_states["l_dec"], prev_states["l_inc"] = l_dec_p, l_inc_p
        prev_states["r_dec"], prev_states["r_inc"] = r_dec_p, r_inc_p

    else:
        font = pygame.font.SysFont("monospace", 20, bold=True)
        txt = font.render("Advanced Tuning Coming Soon", True, (100, 100, 100))
        screen.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery))

    # --- NAVIGATION ARROWS & DOTS ---
    arrow_w, arrow_h = 60, 45
    prev_rect = pygame.Rect(rect.centerx - 70, rect.bottom - 70, arrow_w, arrow_h)
    next_rect = pygame.Rect(rect.centerx + 10, rect.bottom - 70, arrow_w, arrow_h)

    p_pres = touch_down and prev_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if p_pres else (40, 40, 50), prev_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(prev_rect.centerx+10, prev_rect.centery-10), (prev_rect.centerx-10, prev_rect.centery), (prev_rect.centerx+10, prev_rect.centery+10)])
    
    n_pres = touch_down and next_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if n_pres else (40, 40, 50), next_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(next_rect.centerx-10, next_rect.centery-10), (next_rect.centerx+10, next_rect.centery), (next_rect.centerx-10, next_rect.centery+10)])

    for i in range(3):
        dot_x = rect.centerx - 20 + (i * 20)
        dot_y = rect.bottom - 85
        color = (255, 255, 255) if i == current_page else (100, 100, 100)
        pygame.draw.circle(screen, color, (dot_x, dot_y), 4)

    if (p_pres or n_pres) and (time.time() - last_interaction_time) > 0.25:
        if p_pres: current_page = (current_page - 1) % 3
        if n_pres: current_page = (current_page + 1) % 3
        last_interaction_time = time.time()

def save_settings():
    """Saves to inputtuning.json safely using a memory cache and atomic replace."""
    global cached_config
    
    # Update the tuning block in our memory cache
    cached_config["tuning"] = {
        "left_deadzone": LEFT_STICK_DEADZONE / 100.0,
        "right_deadzone": RIGHT_STICK_DEADZONE / 100.0,
        "sensitivity": 1.0,
        "lowpass_alpha": 0.2
    }

    os.makedirs(os.path.dirname(TUNING_FILE), exist_ok=True)
    
    # Write to a temporary file first to prevent corruption during rapid clicking
    tmp_file = TUNING_FILE + ".tmp"
    try:
        with open(tmp_file, 'w') as f:
            json.dump(cached_config, f, indent=4)
        # Atomic swap: this prevents the file from ever being "empty" or "0.01"
        os.replace(tmp_file, TUNING_FILE)
    except Exception as e:
        print(f"Failed to save settings: {e}")

def load_settings():
    """Initial load from disk into the memory cache."""
    global LEFT_STICK_DEADZONE, RIGHT_STICK_DEADZONE, cached_config
    if os.path.exists(TUNING_FILE):
        try:
            with open(TUNING_FILE, 'r') as f:
                cached_config = json.load(f)
                t = cached_config.get("tuning", {})
                LEFT_STICK_DEADZONE = int(t.get("left_deadzone", 0.05) * 100)
                RIGHT_STICK_DEADZONE = int(t.get("right_deadzone", 0.05) * 100)
        except:
            cached_config = {}
            LEFT_STICK_DEADZONE = 5
            RIGHT_STICK_DEADZONE = 5

# --- HELPER FUNCTIONS FOR MAIN.PY ---

def get_tuned_left_stick(raw_lx, raw_ly):
    dead = LEFT_STICK_DEADZONE / 100.0
    return apply_deadzone(raw_lx, dead), apply_deadzone(raw_ly, dead)

def get_tuned_right_stick(raw_rx, raw_ry):
    dead = RIGHT_STICK_DEADZONE / 100.0
    return apply_deadzone(raw_rx, dead), apply_deadzone(raw_ry, dead)

def apply_deadzone(value, deadzone):
    normalized = value / 32768.0
    abs_val = abs(normalized)
    if abs_val < deadzone: return 0
    scaled = (abs_val - deadzone) / (1.0 - deadzone)
    return int(scaled * 32768.0 * (1 if normalized >= 0 else -1))