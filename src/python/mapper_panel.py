# mapper_panel.py - Paginated Channel Mapping UI with Dots
import pygame
import time
import json
import os
from config import *

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")

# Internal State
CHANNEL_MAPS = [i for i in range(16)]
current_page = 0 
last_interaction_time = 0

def draw_mapper_panel(screen, rect, touch_down, touch_x, touch_y):
    global CHANNEL_MAPS, last_interaction_time, current_page
    
    # Title
    title_font = pygame.font.SysFont("monospace", 28, bold=True)
    page_titles = ["Channels 1-8", "Channels 9-16", "Advanced Mapping"]
    title = title_font.render(f"Mapper: {page_titles[current_page]}", True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 30))

    font = pygame.font.SysFont("monospace", 20, bold=True)
    
    # --- PAGE RENDERING ---
    if current_page < 2:  # Pages 0 and 1
        start_ch = 0 if current_page == 0 else 8
        for i in range(8):
            ch_idx = start_ch + i
            y_off = rect.y + 100 + (i * 50)
            x_left = rect.left + 50
            
            lbl = font.render(f"CH{ch_idx+1:02}: Source ID {CHANNEL_MAPS[ch_idx]:02}", True, (200, 200, 200))
            screen.blit(lbl, (x_left, y_off))
            
            minus_rect = pygame.Rect(rect.right - 140, y_off - 5, 45, 35)
            plus_rect = pygame.Rect(rect.right - 80, y_off - 5, 45, 35)
            
            for r, txt in [(minus_rect, "-"), (plus_rect, "+")]:
                is_pressed = touch_down and r.collidepoint(touch_x, touch_y)
                color = (100, 100, 110) if is_pressed else (50, 52, 60)
                pygame.draw.rect(screen, color, r, border_radius=8)
                pygame.draw.rect(screen, (150, 150, 150), r, width=2, border_radius=8)
                btn_txt = font.render(txt, True, (255, 255, 255))
                screen.blit(btn_txt, (r.centerx - btn_txt.get_width()//2, r.centery - btn_txt.get_height()//2))

                if is_pressed and (time.time() - last_interaction_time) > 0.15:
                    if txt == "+": CHANNEL_MAPS[ch_idx] = (CHANNEL_MAPS[ch_idx] + 1) % 23
                    else: CHANNEL_MAPS[ch_idx] = (CHANNEL_MAPS[ch_idx] - 1) % 23
                    last_interaction_time = time.time()
                    save_mapper_settings()
    else:
        # Page 2: Advanced
        adv_txt = font.render("Custom Logic Config Coming Soon", True, (100, 100, 100))
        screen.blit(adv_txt, (rect.centerx - adv_txt.get_width()//2, rect.centery))

    # --- NAVIGATION ARROWS & DOTS ---
    arrow_w, arrow_h = 60, 45
    prev_rect = pygame.Rect(rect.centerx - 70, rect.bottom - 70, arrow_w, arrow_h)
    next_rect = pygame.Rect(rect.centerx + 10, rect.bottom - 70, arrow_w, arrow_h)

    # Prev Arrow
    p_pres = touch_down and prev_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if p_pres else (40, 40, 50), prev_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(prev_rect.centerx+10, prev_rect.centery-10), (prev_rect.centerx-10, prev_rect.centery), (prev_rect.centerx+10, prev_rect.centery+10)])
    
    # Next Arrow
    n_pres = touch_down and next_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if n_pres else (40, 40, 50), next_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(next_rect.centerx-10, next_rect.centery-10), (next_rect.centerx+10, next_rect.centery), (next_rect.centerx-10, next_rect.centery+10)])

    # Page Indicator Dots (The "Pretty Dots")
    for i in range(3):
        dot_x = rect.centerx - 20 + (i * 20)
        dot_y = rect.bottom - 85
        color = (255, 255, 255) if i == current_page else (100, 100, 100)
        pygame.draw.circle(screen, color, (dot_x, dot_y), 4)

    # Page Switching Logic
    if (p_pres or n_pres) and (time.time() - last_interaction_time) > 0.25:
        if p_pres: current_page = (current_page - 1) % 3
        if n_pres: current_page = (current_page + 1) % 3
        last_interaction_time = time.time()

def save_mapper_settings():
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
        data["channel_map"] = CHANNEL_MAPS
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Mapper Save Error: {e}")

def load_mapper_settings():
    global CHANNEL_MAPS
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
            CHANNEL_MAPS = data.get("channel_map", [i for i in range(16)])
        except: pass
