# mapper_panel.py - UI for input mapping and split config

import pygame
import time
import json
import os

# --- PERSISTENT PATH CONFIG ---
SETTINGS_FILE = "/home/pi4/rc-flight-controller/src/config/inputmapper.json"

# --- INTERNAL STATE ---
CHANNEL_MAPS = [i for i in range(16)]
SPLIT_CONFIG = {
    "target_ch": -1, 
    "pos_id": 22, 
    "neg_id": 22,
    "pos_center": False, 
    "pos_reverse": False,
    "neg_center": False, 
    "neg_reverse": False
}

current_page = 0 
last_interaction_time = 0
selector_active_for_ch = -1 
selector_mode = "simple" 
selector_open_time = 0 

def get_tuned_val(raw_val, is_center, is_reverse):
    """
    Transforms raw input into 16-bit space with centering and reversal.
    Clamps result between -32768 and 32767.
    """
    try:
        val = int(raw_val)
    except:
        val = 0
        
    # Apply 32768 Shift if centering is active (lifting baseline to 0)
    if is_center:
        val = val + 32768
    
    # Apply Polarity Flip
    if is_reverse:
        val *= -1
        
    # Hard Clamp to prevent overflow/underflow errors in C++ engine
    return max(-32768, min(32767, val))

def save_mapper_settings():
    """Saves current mapping state to the specified JSON path."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({
                "channel_map": CHANNEL_MAPS, 
                "split_config": SPLIT_CONFIG
            }, f, indent=4)
    except Exception as e:
        print(f"Save Error: {e}")

def load_mapper_settings():
    """Loads mapping state from disk on startup."""
    global CHANNEL_MAPS, SPLIT_CONFIG
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                d = json.load(f)
                # Use slice assignment to update the existing list object
                CHANNEL_MAPS[:] = d.get("channel_map", [i for i in range(16)])
                loaded_split = d.get("split_config", {})
                for k in SPLIT_CONFIG:
                    if k in loaded_split: 
                        SPLIT_CONFIG[k] = loaded_split[k]
        except Exception as e:
            print(f"Load Error: {e}")

# Perform initial load on module import
load_mapper_settings()

def draw_mapper_panel(screen, rect, touch_down, touch_x, touch_y, raw_axes, tuned_signals=None):
    """Main rendering loop for the Mapper UI."""
    global CHANNEL_MAPS, SPLIT_CONFIG, last_interaction_time, current_page, selector_active_for_ch, selector_mode, selector_open_time
    
    was_changed = False # Returns True to main.py to trigger a UDP sync

    # --- SELECTOR OVERLAY ---
    if selector_active_for_ch != -1:
        return draw_selector_grid(screen, rect, touch_down, touch_x, touch_y, raw_axes)

    # --- STYLES ---
    title_font = pygame.font.SysFont("monospace", 28, bold=True)
    font = pygame.font.SysFont("monospace", 20, bold=True)
    small_font = pygame.font.SysFont("monospace", 15, bold=True)

    # --- TITLE ---
    page_titles = ["Channels 1-8", "Channels 9-16", "Advanced Split Mix"]
    title = title_font.render(page_titles[current_page], True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 20))

    # --- PAGES 1 & 2: CHANNEL LIST ---
    if current_page < 2:
        start_ch = 0 if current_page == 0 else 8
        for i in range(8):
            ch_idx = start_ch + i
            y_off = rect.y + 80 + (i * 45)
            is_ovr = (SPLIT_CONFIG["target_ch"] == ch_idx)
            
            # Label
            lbl = font.render(f"CH{ch_idx+1:02}:", True, (100,100,110) if is_ovr else (200,200,200))
            screen.blit(lbl, (rect.left + 50, y_off))
            
            # Button Box
            id_box = pygame.Rect(rect.left + 130, y_off - 5, 140, 35)
            pygame.draw.rect(screen, (30,30,35) if is_ovr else (50,52,60), id_box, border_radius=8)
            
            label = "SPLIT ACTIVE" if is_ovr else (f"ID {CHANNEL_MAPS[ch_idx]:02}" if CHANNEL_MAPS[ch_idx] != 22 else "NONE")
            txt = font.render(label, True, (80,80,90) if is_ovr else (255,255,255))
            screen.blit(txt, (id_box.centerx - txt.get_width()//2, id_box.centery - txt.get_height()//2))

            if not is_ovr and touch_down and id_box.collidepoint(touch_x, touch_y) and (time.time()-last_interaction_time) > 0.4:
                selector_active_for_ch, selector_mode, selector_open_time = ch_idx, "simple", time.time()
                last_interaction_time = time.time()

    # --- PAGE 3: ADVANCED SPLIT MIXER ---
    elif current_page == 2:
        y_row = rect.y + 130
        
        # Target Channel Selector
        ch_btn = pygame.Rect(rect.left + 40, y_row, 140, 60)
        pygame.draw.rect(screen, (50, 52, 60), ch_btn, border_radius=10)
        t_label = small_font.render("TARGET CH", True, (150, 150, 150))
        screen.blit(t_label, (ch_btn.x, ch_btn.y - 20))
        ch_txt = font.render("NONE" if SPLIT_CONFIG["target_ch"] == -1 else f"CH {SPLIT_CONFIG['target_ch']+1}", True, (0, 200, 255))
        screen.blit(ch_txt, (ch_btn.centerx - ch_txt.get_width()//2, ch_btn.centery - ch_txt.get_height()//2))

        sides = [
            {"key": "pos", "x": rect.left + 210, "color": (0, 255, 100), "label": "Positive (+)"},
            {"key": "neg", "x": rect.left + 430, "color": (255, 50, 50), "label": "Negative (-)"}
        ]

        for side in sides:
            s_key = side["key"]
            btn_rect = pygame.Rect(side["x"], y_row, 190, 60)
            src_id = SPLIT_CONFIG[f"{s_key}_id"]
            
            # Pull live tuned data for visual feedback
            raw_v = tuned_signals[src_id] if tuned_signals and src_id < 23 else (raw_axes[src_id] if src_id < 23 else -32768)
            tuned_v = get_tuned_val(raw_v, SPLIT_CONFIG[f"{s_key}_center"], SPLIT_CONFIG[f"{s_key}_reverse"])
            
            pygame.draw.rect(screen, (40, 45, 50), btn_rect, border_radius=10)
            pygame.draw.rect(screen, side["color"], btn_rect, 2, border_radius=10)
            screen.blit(small_font.render(side["label"], True, (200, 200, 200)), (btn_rect.x, btn_rect.y - 20))
            
            v_txt = font.render(f"ID {src_id:02}: {tuned_v}", True, (255, 255, 255))
            screen.blit(v_txt, (btn_rect.centerx - v_txt.get_width()//2, btn_rect.centery - v_txt.get_height()//2))

            # Center/Reverse Checkboxes
            for j, opt in enumerate(["center", "reverse"]):
                cb_rect = pygame.Rect(btn_rect.x + (j*98), btn_rect.bottom + 12, 24, 24)
                full_key = f"{s_key}_{opt}"
                pygame.draw.rect(screen, (60, 60, 70), cb_rect, border_radius=4)
                if SPLIT_CONFIG[full_key]:
                    pygame.draw.line(screen, (0, 255, 100), (cb_rect.x+5, cb_rect.y+12), (cb_rect.x+20, cb_rect.bottom-5), 3)
                    pygame.draw.line(screen, (0, 255, 100), (cb_rect.x+10, cb_rect.bottom-5), (cb_rect.right-5, cb_rect.y+5), 3)
                
                lbl = small_font.render(opt.capitalize(), True, (200, 200, 200))
                screen.blit(lbl, (cb_rect.right + 6, cb_rect.y + 4))

                if touch_down and cb_rect.collidepoint(touch_x, touch_y) and (time.time()-last_interaction_time) > 0.3:
                    SPLIT_CONFIG[full_key] = not SPLIT_CONFIG[full_key]
                    save_mapper_settings(); was_changed = True; last_interaction_time = time.time()

            # Click main ID box to change source ID
            if touch_down and btn_rect.collidepoint(touch_x, touch_y) and (time.time()-last_interaction_time) > 0.5:
                selector_active_for_ch, selector_mode, selector_open_time = 99, f"split_{s_key}", time.time()
                last_interaction_time = time.time()

        # Target Channel Interaction
        if touch_down and ch_btn.collidepoint(touch_x, touch_y) and (time.time()-last_interaction_time) > 0.5:
            selector_active_for_ch, selector_mode, selector_open_time = 99, "split_ch", time.time()
            last_interaction_time = time.time()

    # --- NAVIGATION ARROWS ---
    prev_rect = pygame.Rect(rect.centerx - 80, rect.bottom - 60, 60, 45)
    next_rect = pygame.Rect(rect.centerx + 20, rect.bottom - 60, 60, 45)
    pygame.draw.rect(screen, (40, 40, 50), prev_rect, border_radius=10)
    pygame.draw.rect(screen, (40, 40, 50), next_rect, border_radius=10)
    pygame.draw.polygon(screen, (255,255,255), [(prev_rect.centerx+10, prev_rect.centery-10), (prev_rect.centerx-10, prev_rect.centery), (prev_rect.centerx+10, prev_rect.centery+10)])
    pygame.draw.polygon(screen, (255,255,255), [(next_rect.centerx-10, next_rect.centery-10), (next_rect.centerx+10, next_rect.centery), (next_rect.centerx-10, next_rect.centery+10)])
    
    if touch_down and (time.time()-last_interaction_time) > 0.3:
        if prev_rect.collidepoint(touch_x, touch_y): current_page = (current_page-1)%3; last_interaction_time=time.time()
        elif next_rect.collidepoint(touch_x, touch_y): current_page = (current_page+1)%3; last_interaction_time=time.time()
    
    return was_changed

def draw_selector_grid(screen, rect, touch_down, touch_x, touch_y, raw_data):
    """Draws the 5x5 Input/Target selection grid overlay."""
    global selector_active_for_ch, selector_mode, last_interaction_time, selector_open_time, SPLIT_CONFIG, CHANNEL_MAPS
    is_locked = (time.time() - selector_open_time) < 0.5
    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA); overlay.fill((10, 10, 15, 250)); screen.blit(overlay, (rect.x, rect.y))
    font = pygame.font.SysFont("monospace", 17, bold=True)
    title_font = pygame.font.SysFont("monospace", 26, bold=True)
    
    msg = title_font.render("Select Channel" if "ch" in selector_mode else "Select Input ID", True, (0, 200, 255))
    screen.blit(msg, (rect.centerx - msg.get_width()//2, rect.y + 15))
    
    cols, rows = 5, 5 
    btn_w, btn_h = 110, 55
    start_x = rect.x + (rect.width - (cols * 118)) // 2
    start_y = rect.y + 60

    max_range = 16 if "ch" in selector_mode else 23 
    for i in range(max_range):
        bx = start_x + (i%5 * 118)
        by = start_y + (i//5 * 63)
        btn_rect = pygame.Rect(bx, by, btn_w, btn_h)
        pygame.draw.rect(screen, (45, 45, 55), btn_rect, border_radius=6)
        
        label = f"CH {i+1}" if "ch" in selector_mode else f"ID {i:02}"
        screen.blit(font.render(label, True, (200, 200, 200)), (bx+8, by+5))
        
        # Show real-time raw values in the selector for easier ID finding
        if "ch" not in selector_mode:
            v_val = str(int(raw_data[i])) if i < len(raw_data) else "0"
            v_txt = font.render(v_val, True, (0, 255, 100))
            screen.blit(v_txt, (bx+8, by+28))

        if not is_locked and touch_down and btn_rect.collidepoint(touch_x, touch_y):
            if selector_mode == "simple": CHANNEL_MAPS[selector_active_for_ch] = i
            elif selector_mode == "split_ch": SPLIT_CONFIG["target_ch"] = i
            elif selector_mode == "split_pos": SPLIT_CONFIG["pos_id"] = i
            elif selector_mode == "split_neg": SPLIT_CONFIG["neg_id"] = i
            save_mapper_settings(); selector_active_for_ch = -1; last_interaction_time = time.time(); return True

    # "NONE" Button at the bottom
    none_rect = pygame.Rect(rect.centerx - 75, rect.bottom - 70, 150, 48)
    pygame.draw.rect(screen, (60, 30, 30), none_rect, border_radius=8)
    screen.blit(font.render("NONE (22)", True, (255, 255, 255)), (none_rect.centerx - 45, none_rect.centery - 10))
    if not is_locked and touch_down and none_rect.collidepoint(touch_x, touch_y):
        if selector_mode == "split_ch": SPLIT_CONFIG["target_ch"] = -1
        elif selector_mode == "split_pos": SPLIT_CONFIG["pos_id"] = 22
        elif selector_mode == "split_neg": SPLIT_CONFIG["neg_id"] = 22
        else: CHANNEL_MAPS[selector_active_for_ch] = 22
        save_mapper_settings(); selector_active_for_ch = -1; last_interaction_time = time.time(); return True

    return False
