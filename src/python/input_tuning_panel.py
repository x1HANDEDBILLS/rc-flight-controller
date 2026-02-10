import pygame
import time
import json
import os
import socket
from config import *
from ui_helpers import draw_numeric_stepper

# --- CONFIG & PERSISTENCE ---
TUNING_FILE = "/home/pi4/rc-flight-controller/src/config/inputtuning.json"
UDP_IP, UDP_PORT = "127.0.0.1", 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Shared raw input array (updated by main loop)
RAW_INPUTS = [0.0] * 23 

TUNING_STATE = {
    "left_deadzone": 0.5, "left_h_id": 0, "left_v_id": 1,
    "right_deadzone": 0.5, "right_h_id": 2, "right_v_id": 3,
    "curve_type": 0, "expo": 0.0,
    "smoothing": 0.2, "global_rate": 1.0,
    "cine_on": False, 
    "cine_intensity": 1.0, 
    "curve_lh_id": 0, "curve_lv_id": 1, "curve_rh_id": 2, "curve_rv_id": 3
}

CURVE_NAMES = ["LINEAR", "STANDARD", "DYNAMIC", "EXTREME"]

# UI State
selector_active_for = None
curve_menu_open = False
last_overlay_toggle = 0.0 
current_page = 0
last_interaction_time = 0

# Input tracking for steppers
prev_states = {
    "l_dec": False, "l_inc": False, "r_dec": False, "r_inc": False,
    "e_dec": False, "e_inc": False, "s_dec": False, "s_inc": False,
    "g_dec": False, "g_inc": False, "ci_dec": False, "ci_inc": False
}
last_release = {k: 0.0 for k in prev_states.keys()}

def stream_to_cpp(key, value):
    """Sends tuning updates to the C++ Flight Core via UDP."""
    try:
        val = int(value) if isinstance(value, bool) else value
        message = f"{key}:{val}"
        sock.sendto(message.encode(), (UDP_IP, UDP_PORT))
    except Exception:
        pass 

def save_settings():
    """Saves current tuning state to JSON."""
    try:
        os.makedirs(os.path.dirname(TUNING_FILE), exist_ok=True)
        with open(TUNING_FILE, 'w') as f:
            json.dump({"tuning": TUNING_STATE}, f, indent=4)
    except Exception:
        pass

def load_settings():
    """Loads tuning state from JSON on startup."""
    if os.path.exists(TUNING_FILE):
        try:
            with open(TUNING_FILE, 'r') as f:
                data = json.load(f)
                if "tuning" in data: TUNING_STATE.update(data["tuning"])
        except Exception:
            pass

load_settings()

def draw_input_tuning_panel(screen, rect, touch_down, touch_x, touch_y, raw_signals=None):
    global RAW_INPUTS, current_page, last_interaction_time, selector_active_for, curve_menu_open, last_overlay_toggle
    if raw_signals: RAW_INPUTS = raw_signals
    
    was_changed = False

    # --- OVERLAY HANDLING ---
    if selector_active_for:
        if draw_id_selector_overlay(screen, rect, touch_down, touch_x, touch_y):
            was_changed = True
        return was_changed
        
    if curve_menu_open:
        if draw_curve_selector_overlay(screen, rect, touch_down, touch_x, touch_y):
            was_changed = True
        return was_changed

    # Draw Title
    title_font = pygame.font.SysFont("monospace", 26, bold=True)
    title = title_font.render("Input Signal Tuning", True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 20))

    # --- PAGE 0: ROUTING & EXPO ---
    if current_page == 0:
        l_x, l_y = rect.left + 65, rect.y + 100 
        r_x, r_y = rect.left + 65, l_y + 80  
        
        l_res = draw_numeric_stepper(screen, l_x, l_y, TUNING_STATE["left_deadzone"], "Left Deadzone", touch_down, touch_x, touch_y)
        r_res = draw_numeric_stepper(screen, r_x, r_y, TUNING_STATE["right_deadzone"], "Right Deadzone", touch_down, touch_x, touch_y)
        
        if draw_mapper_style_row(screen, l_x + 315, l_y - 8, "left_h_id", "left_v_id", touch_down, touch_x, touch_y):
            was_changed = True
        if draw_mapper_style_row(screen, r_x + 315, r_y - 8, "right_h_id", "right_v_id", touch_down, touch_x, touch_y):
            was_changed = True

        curve_btn = pygame.Rect(rect.left + 10, r_y + 110, 220, 60)
        pygame.draw.rect(screen, (40, 44, 52), curve_btn, border_radius=12)
        pygame.draw.rect(screen, (255, 215, 0), curve_btn, 2, border_radius=12)
        c_val = pygame.font.SysFont("monospace", 18, bold=True).render(CURVE_NAMES[TUNING_STATE["curve_type"]], True, (255, 255, 255))
        screen.blit(c_val, (curve_btn.centerx - c_val.get_width()//2, curve_btn.centery - c_val.get_height()//2))
        lbl_c = pygame.font.SysFont("monospace", 12, bold=True).render("RESPONSE ALGO", True, (150, 150, 150))
        screen.blit(lbl_c, (curve_btn.x + 5, curve_btn.y - 18))

        e_res = draw_numeric_stepper(screen, rect.left + 65, curve_btn.bottom + 50, TUNING_STATE["expo"], "Stick Expo (Negative=Sharp)", touch_down, touch_x, touch_y)
        
        target_x = curve_btn.right + 25
        t_keys = ["curve_lh_id", "curve_lv_id", "curve_rh_id", "curve_rv_id"]
        t_labels = ["LH", "LV", "RH", "RV"]
        for i in range(4):
            if draw_single_mapper_box(screen, pygame.Rect(target_x + (i * 125), curve_btn.y, 120, 60), t_keys[i], t_labels[i], touch_down, touch_x, touch_y):
                was_changed = True

        if handle_stepper_input(l_res, r_res, e_res, None, None, None):
            was_changed = True

        if touch_down and curve_btn.collidepoint(touch_x, touch_y) and (time.time() - last_overlay_toggle > 0.5):
            curve_menu_open = True
            last_overlay_toggle = time.time()

    # --- PAGE 1: FILTERS, RATES, CINEMATIC ---
    elif current_page == 1:
        s_x, s_y = rect.left + 65, rect.y + 110
        g_x, g_y = rect.left + 65, s_y + 90
        c_y = g_y + 100
        
        s_res = draw_numeric_stepper(screen, s_x, s_y, TUNING_STATE["smoothing"], "Input Smoothing (Filter)", touch_down, touch_x, touch_y)
        g_res = draw_numeric_stepper(screen, g_x, g_y, TUNING_STATE["global_rate"], "Global Rate (Max Speed)", touch_down, touch_x, touch_y)
        ci_res = draw_numeric_stepper(screen, s_x, c_y, TUNING_STATE["cine_intensity"], "Cinematic Intensity (1-10)", touch_down, touch_x, touch_y)
        
        if draw_cinematic_row(screen, s_x + 350, c_y - 10, touch_down, touch_x, touch_y):
            was_changed = True
        
        if handle_stepper_input(None, None, None, s_res, g_res, ci_res):
            was_changed = True

    draw_page_indicators(screen, rect)
    draw_navigation(screen, rect, touch_down, touch_x, touch_y)
    
    return was_changed

def draw_cinematic_row(screen, x, y, touch_down, tx, ty):
    global last_interaction_time
    changed = False
    box_rect = pygame.Rect(x, y + 10, 45, 45)
    pygame.draw.rect(screen, (40, 44, 52), box_rect, border_radius=8)
    pygame.draw.rect(screen, (0, 200, 255), box_rect, 2, border_radius=8)
    
    if TUNING_STATE["cine_on"]:
        pygame.draw.line(screen, (0, 200, 255), (box_rect.x+10, box_rect.y+22), (box_rect.x+20, box_rect.y+32), 4)
        pygame.draw.line(screen, (0, 200, 255), (box_rect.x+20, box_rect.y+32), (box_rect.x+35, box_rect.y+12), 4)

    if touch_down and box_rect.collidepoint(tx, ty) and (time.time() - last_interaction_time > 0.3):
        TUNING_STATE["cine_on"] = not TUNING_STATE["cine_on"]
        stream_to_cpp("CINE_ON", TUNING_STATE["cine_on"])
        save_settings()
        last_interaction_time = time.time()
        changed = True

    lbl = pygame.font.SysFont("monospace", 16, bold=True).render("CINEMATIC MODE", True, (0, 200, 255))
    screen.blit(lbl, (box_rect.right + 15, box_rect.centery - 10))
    return changed

def handle_stepper_input(l, r, e, s, g, ci):
    global prev_states, last_release
    now = time.time()
    changed = False
    checks = []
    
    # Deadzones: 0.1 increments, 0.0 to 5.0 (50% max)
    if l: checks.extend([("l_dec", l[1], "left_deadzone", -0.1, 0.0, 5.0, "L_DZ"), ("l_inc", l[3], "left_deadzone", 0.1, 0.0, 5.0, "L_DZ")])
    if r: checks.extend([("r_dec", r[1], "right_deadzone", -0.1, 0.0, 5.0, "R_DZ"), ("r_inc", r[3], "right_deadzone", 0.1, 0.0, 5.0, "R_DZ")])
    
    # UPDATED EXPO: Range -10.0 to 10.0, Increment 0.1
    if e: checks.extend([("e_dec", e[1], "expo", -0.1, -10.0, 10.0, "EXPO"), ("e_inc", e[3], "expo", 0.1, -10.0, 10.0, "EXPO")])
    
    if s: checks.extend([("s_dec", s[1], "smoothing", -0.05, 0, 1, "SMOOTH"), ("s_inc", s[3], "smoothing", 0.05, 0, 1, "SMOOTH")])
    if g: checks.extend([("g_dec", g[1], "global_rate", -0.1, 0.1, 3.0, "RATE"), ("g_inc", g[3], "global_rate", 0.1, 0.1, 3.0, "RATE")])
    if ci: checks.extend([("ci_dec", ci[1], "cine_intensity", -0.1, 1.0, 10.0, "CINE_VAL"), ("ci_inc", ci[3], "cine_intensity", 0.1, 1.0, 10.0, "CINE_VAL")])

    for key, pressed, target, delta, v_min, v_max, udp_key in checks:
        # Only trigger on the transition from pressed to released (prevents "stuck" buttons)
        if not pressed and prev_states[key] and (now - last_release[key]) >= 0.05:
            # We now use round(..., 1) for everything to keep it consistent with your "clean" UI
            new_val = round(max(v_min, min(v_max, TUNING_STATE[target] + delta)), 1)
            TUNING_STATE[target] = new_val
            
            # Special case for Deadzones: Map UI (1.0) to Flight Logic (0.10)
            if udp_key in ["L_DZ", "R_DZ"]:
                stream_to_cpp(udp_key, round(new_val / 10.0, 2))
            else:
                stream_to_cpp(udp_key, new_val)
                
            save_settings()
            last_release[key] = now
            changed = True
        prev_states[key] = pressed
    return changed

def draw_mapper_style_row(screen, x, y, h_key, v_key, touch_down, tx, ty):
    changed = False
    for i, k in enumerate([h_key, v_key]):
        if draw_single_mapper_box(screen, pygame.Rect(x + (i * 148), y, 140, 58), k, ["H-AXIS", "V-AXIS"][i], touch_down, tx, ty):
            changed = True
    return changed

def draw_single_mapper_box(screen, rect, state_key, label, touch_down, tx, ty):
    global selector_active_for, last_overlay_toggle
    pygame.draw.rect(screen, (20, 22, 28), rect, border_radius=8)
    pygame.draw.rect(screen, (0, 255, 120), rect, 2, border_radius=8)
    id_val = TUNING_STATE.get(state_key)
    lbl = pygame.font.SysFont("monospace", 14, bold=True).render(label, True, (0, 255, 120))
    screen.blit(lbl, (rect.x + 8, rect.y + 4))
    
    if id_val is not None and id_val < 23:
        v_txt = pygame.font.SysFont("monospace", 24, bold=True).render(f"ID {id_val:02}", True, (255, 255, 255))
        screen.blit(v_txt, (rect.x + 8, rect.y + 18))
        raw_v = int(RAW_INPUTS[id_val]) if id_val < len(RAW_INPUTS) else 0
        screen.blit(pygame.font.SysFont("monospace", 16, bold=True).render(str(raw_v), True, (0, 255, 100)), (rect.x + 8, rect.bottom - 22))
        
    if touch_down and rect.collidepoint(tx, ty) and (time.time() - last_overlay_toggle > 0.5):
        selector_active_for = state_key
        last_overlay_toggle = time.time()
        return True
    return False

def draw_id_selector_overlay(screen, rect, touch_down, tx, ty):
    global selector_active_for, last_overlay_toggle
    changed = False
    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    overlay.fill((10, 10, 15, 252))
    screen.blit(overlay, (rect.x, rect.y))
    
    start_x, start_y = rect.x + 30, rect.y + 60
    for i in range(23):
        btn = pygame.Rect(start_x + (i % 5 * 118), start_y + (i // 5 * 63), 110, 55)
        is_sel = TUNING_STATE.get(selector_active_for) == i
        pygame.draw.rect(screen, (0, 80, 40) if is_sel else (45, 45, 55), btn, border_radius=6)
        screen.blit(pygame.font.SysFont("monospace", 17, bold=True).render(f"ID {i:02}", True, (255, 255, 255)), (btn.x + 8, btn.y + 5))
        
        if touch_down and btn.collidepoint(tx, ty) and (time.time() - last_overlay_toggle > 0.5):
            TUNING_STATE[selector_active_for] = i
            stream_to_cpp(selector_active_for.upper(), i)
            save_settings()
            selector_active_for = None
            last_overlay_toggle = time.time()
            changed = True
    return changed

def draw_curve_selector_overlay(screen, rect, touch_down, tx, ty):
    global curve_menu_open, last_overlay_toggle
    changed = False
    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 235))
    screen.blit(overlay, (rect.x, rect.y))
    
    for i, name in enumerate(CURVE_NAMES):
        btn = pygame.Rect(rect.centerx - 120, rect.y + 80 + (i * 75), 240, 60)
        pygame.draw.rect(screen, (0, 255, 150) if TUNING_STATE["curve_type"] == i else (45, 48, 60), btn, border_radius=12)
        txt = pygame.font.SysFont("monospace", 22, bold=True).render(name, True, (255, 255, 255))
        screen.blit(txt, (btn.centerx - txt.get_width()//2, btn.centery - txt.get_height()//2))
        
        if touch_down and btn.collidepoint(tx, ty) and (time.time() - last_overlay_toggle > 0.5):
            TUNING_STATE["curve_type"] = i
            stream_to_cpp("CURVE", i)
            save_settings()
            curve_menu_open = False
            last_overlay_toggle = time.time()
            changed = True
    return changed

def draw_page_indicators(screen, rect):
    for i in range(2): 
        color = (0, 255, 120) if i == current_page else (60, 60, 70)
        pygame.draw.circle(screen, color, (rect.centerx - 15 + (i * 30), rect.bottom - 75), 6)

def draw_navigation(screen, rect, touch_down, touch_x, touch_y):
    global current_page, last_interaction_time
    for r, is_next in [(pygame.Rect(rect.centerx - 75, rect.bottom - 50, 60, 45), False), (pygame.Rect(rect.centerx + 15, rect.bottom - 50, 60, 45), True)]:
        pygame.draw.rect(screen, (35, 38, 48), r, border_radius=10)
        off = 8 if is_next else -8
        pygame.draw.polygon(screen, (255, 255, 255), [(r.centerx-off, r.centery-10), (r.centerx+off, r.centery), (r.centerx-off, r.centery+10)])
        if touch_down and r.collidepoint(touch_x, touch_y) and (time.time() - last_interaction_time > 0.3):
            current_page = (current_page + (1 if is_next else -1)) % 2
            last_interaction_time = time.time()