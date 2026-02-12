# /home/pi4/rc-flight-controller/src/python/ui_components.py
import pygame
import numpy as np
import time
from config import *
import input_tuning_panel, mapper_panel, wifi_panel, pid_panel, logs_panel, system_panel, profiles_panel, camera_panel, battery_panel, motors_panel, sensors_panel

# --- RECONFIGURED LAYOUTS ---
LAYOUT_LOWER = [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    ['shft', 'z', 'x', 'c', 'v', 'b', 'n', 'm'],
    ['123', '.', '_', 'space', 'Enter', ' ', '<-']
]

LAYOUT_UPPER = [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
    ['SHFT', 'Z', 'X', 'C', 'V', 'B', 'N', 'M'],
    ['abc', '!', '?', 'space', 'Enter', ' ', '<-']
]

LAYOUT_SPECIAL = [
    ['[', ']', '{', '}', '#', '%', '^', '*', '+', '='],
    ['-', '/', ':', ';', '(', ')', '$', '&', '@', '"'],
    ['.', ',', '?', '!', "'", '`', '~', '\\', '|'],
    ['abc', '<', '>', '(', ')', '{', '}', '[', ']'],
    ['abc', ' ', ' ', 'space', 'Enter', ' ', '<-']
]

LAYOUT_KEYPAD = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['<-', '0', 'Enter']
]

class VirtualKeyboard:
    def __init__(self):
        self.active = False
        self.text = ""
        self.title = ""
        self.callback = None
        self.last_press_time = 0
        self.open_time = 0 
        self.mode = "lower"

    def open(self, title, initial_text, callback):
        self.title = title
        self.text = str(initial_text)
        self.callback = callback
        self.active = True
        self.mode = "lower"
        self.open_time = time.time() 

    def draw(self, screen, rect, touch_down, touch_x, touch_y):
        if not self.active: return

        overlay = pygame.Surface((rect.width, rect.height))
        overlay.fill((10, 10, 15))
        screen.blit(overlay, (rect.x, rect.y))

        font = pygame.font.SysFont("monospace", 18, bold=True)
        now = time.time()
        input_allowed = (now - self.open_time) > 0.5
        debounce_rate = 0.25 # Slightly increased for Pi touchscreens

        title_txt = font.render(self.title, True, (0, 200, 255))
        screen.blit(title_txt, (rect.x + (rect.width // 2) - (title_txt.get_width() // 2), rect.y + 15))
        
        edge_buffer = 10
        kb_width = rect.width - (edge_buffer * 2)
        kb_x = rect.x + edge_buffer
        
        input_rect = pygame.Rect(kb_x, rect.y + 45, kb_width, 40)
        pygame.draw.rect(screen, (30, 30, 40), input_rect, border_radius=8)
        pygame.draw.rect(screen, (0, 150, 255), input_rect, width=2, border_radius=8)
        screen.blit(font.render(self.text + "|", True, (255, 255, 255)), (input_rect.x + 15, input_rect.y + 10))

        close_rect = pygame.Rect(rect.x + (rect.width // 2) - 70, rect.bottom - 60, 140, 45)
        is_close_pressed = touch_down and close_rect.collidepoint(touch_x, touch_y) and input_allowed
        
        if is_close_pressed and (now - self.last_press_time) > debounce_rate:
            self.active = False
            self.last_press_time = now
            return # Exit immediately

        c_color = (180, 50, 50) if is_close_pressed else (120, 35, 35)
        pygame.draw.rect(screen, c_color, close_rect, border_radius=10)
        screen.blit(font.render("CLOSE", True, (255,255,255)), (close_rect.centerx - 28, close_rect.centery - 10))

        current_layout = LAYOUT_UPPER if self.mode == "upper" else (LAYOUT_SPECIAL if self.mode == "special" else LAYOUT_LOWER)
        key_w = (kb_width // 10) - 4
        key_h = 52 
        y_start = rect.y + 100

        for r_idx, row in enumerate(current_layout):
            x_offset = kb_x
            for key in row:
                if key == ' ': 
                    x_offset += key_w + 4
                    continue
                
                k_w_scaled = key_w
                if key == "space": k_w_scaled = key_w * 2
                elif key == "Enter": k_w_scaled = key_w * 1.5
                elif key in ["123", "abc", "shft", "SHFT", "<-"]: k_w_scaled = key_w * 1.2

                k_rect = pygame.Rect(x_offset, y_start + (r_idx * (key_h + 6)), k_w_scaled, key_h)
                is_pressed = touch_down and k_rect.collidepoint(touch_x, touch_y) and input_allowed
                
                if is_pressed and (now - self.last_press_time) > debounce_rate:
                    self.last_press_time = now
                    if key == "<-": 
                        self.text = self.text[:-1]
                    elif key in ["shft", "SHFT"]: 
                        self.mode = "upper" if self.mode == "lower" else "lower"
                    elif key == "123": 
                        self.mode = "special"
                    elif key == "abc": 
                        self.mode = "lower"
                    elif key == "space": 
                        self.text += " "
                    elif key == "Enter":
                        # CRITICAL: Close state first, then fire callback
                        self.active = False
                        if self.callback: 
                            self.callback(self.text)
                        return # Kill drawing loop for this frame
                    else:
                        self.text += key

                k_color = (90, 95, 120) if is_pressed else (45, 47, 55)
                if key == "Enter": k_color = (35, 130, 65)
                if key == "<-": k_color = (140, 45, 45)
                
                pygame.draw.rect(screen, k_color, k_rect, border_radius=6)
                pygame.draw.rect(screen, (85, 85, 95), k_rect, width=1, border_radius=6)
                
                label_str = "SPACE" if key == "space" else key
                txt_surf = font.render(label_str, True, (255, 255, 255))
                screen.blit(txt_surf, (k_rect.centerx - txt_surf.get_width()//2, k_rect.centery - txt_surf.get_height()//2))
                x_offset += k_w_scaled + 4

class VirtualKeypad:
    def __init__(self):
        self.active = False
        self.text = ""
        self.title = ""
        self.callback = None
        self.last_press_time = 0
        self.open_time = 0

    def open(self, title, initial_text, callback):
        self.title = title
        self.text = str(initial_text)
        self.callback = callback
        self.active = True
        self.open_time = time.time()

    def draw(self, screen, rect, touch_down, touch_x, touch_y):
        if not self.active: return
        overlay = pygame.Surface((rect.width, rect.height))
        overlay.fill((10, 10, 15))
        screen.blit(overlay, (rect.x, rect.y))

        now = time.time()
        input_allowed = (now - self.open_time) > 0.5 
        debounce_rate = 0.25

        kp_w, kp_h = 240, 400
        kp_x = rect.x + (rect.width // 2) - (kp_w // 2)
        kp_y = rect.y + (rect.height // 2) - (kp_h // 2) - 20
        font = pygame.font.SysFont("monospace", 22, bold=True)

        title_txt = font.render(self.title, True, (0, 200, 255))
        screen.blit(title_txt, (rect.x + (rect.width // 2) - (title_txt.get_width() // 2), kp_y - 35))
        
        disp_rect = pygame.Rect(kp_x, kp_y, kp_w, 50)
        pygame.draw.rect(screen, (40, 40, 50), disp_rect, border_radius=10)
        pygame.draw.rect(screen, (0, 150, 255), disp_rect, width=2, border_radius=10)
        screen.blit(font.render(self.text + "|", True, (255, 255, 255)), (disp_rect.x + 15, disp_rect.y + 12))

        close_rect = pygame.Rect(rect.x + (rect.width // 2) - 70, rect.bottom - 60, 140, 45)
        is_close_pressed = touch_down and close_rect.collidepoint(touch_x, touch_y) and input_allowed
        
        if is_close_pressed and (now - self.last_press_time) > debounce_rate:
            self.active = False
            self.last_press_time = now
            return

        pygame.draw.rect(screen, (110, 35, 35), close_rect, border_radius=10)
        screen.blit(font.render("CANCEL", True, (255,255,255)), (close_rect.centerx - 35, close_rect.centery - 10))

        btn_w, btn_h = 65, 55
        gap, start_y = 10, kp_y + 65
        for r_idx, row in enumerate(LAYOUT_KEYPAD):
            for c_idx, key in enumerate(row):
                bx = kp_x + (c_idx * (btn_w + gap))
                by = start_y + (r_idx * (btn_h + gap))
                brect = pygame.Rect(bx, by, btn_w, btn_h)
                
                is_hit = touch_down and brect.collidepoint(touch_x, touch_y) and input_allowed
                
                if is_hit and (now - self.last_press_time) > debounce_rate:
                    self.last_press_time = now
                    if key == "<-": 
                        self.text = self.text[:-1]
                    elif key == "Enter":
                        self.active = False
                        if self.callback: 
                            self.callback(self.text)
                        return
                    else: 
                        self.text += key

                bcolor = (35, 135, 65) if key == "Enter" else ((140, 45, 45) if key == "<-" else (55, 57, 70))
                pygame.draw.rect(screen, bcolor, brect, border_radius=12)
                label = font.render(key, True, (255, 255, 255))
                screen.blit(label, (brect.centerx - label.get_width()//2, brect.centery - label.get_height()//2))

# --- PANEL & ICON UTILS ---
PANEL_MAP = [
    ("WiFi", wifi_panel.draw_wifi_panel), ("Back", None),
    ("PID", pid_panel.draw_pid_panel), ("Input", input_tuning_panel.draw_input_tuning_panel),
    ("Logs", logs_panel.draw_logs_panel), ("Mapper", mapper_panel.draw_mapper_panel),
    ("System", system_panel.draw_system_panel), ("Stats", battery_panel.draw_battery_panel),
    ("Profiles", profiles_panel.draw_profiles_panel), ("Motors", motors_panel.draw_motors_panel),
    ("Camera", camera_panel.draw_camera_panel), ("Sensors", sensors_panel.draw_sensors_panel)
]

def draw_controller_icon(screen, x, y, connected):
    color = (40, 255, 100) if connected else (255, 60, 60)
    pygame.draw.rect(screen, color, (x + 10, y + 22, 60, 32), width=3, border_radius=10)
    pygame.draw.circle(screen, color, (x + 28, y + 38), 5, width=2)
    pygame.draw.circle(screen, color, (x + 52, y + 38), 5, width=2)
    pygame.draw.circle(screen, color if connected else (80, 0, 0), (x + 40, y + 30), 4)

def draw_gear_button(screen, rect, pressed):
    bg_color = (40, 100, 200) if pressed else (50, 52, 60)
    pygame.draw.rect(screen, bg_color, rect.inflate(-6, -6), border_radius=15)
    center = rect.center
    for ang in range(0, 360, 45):
        rad = np.radians(ang)
        pts = [(center[0] + 14 * np.cos(rad-0.2), center[1] + 14 * np.sin(rad-0.2)),
               (center[0] + 24 * np.cos(rad-0.15), center[1] + 24 * np.sin(rad-0.15)),
               (center[0] + 24 * np.cos(rad+0.15), center[1] + 24 * np.sin(rad+0.15)),
               (center[0] + 14 * np.cos(rad+0.2), center[1] + 14 * np.sin(rad+0.2))]
        pygame.draw.polygon(screen, (255,255,255), pts)
    pygame.draw.circle(screen, (255,255,255), center, 16, 4)

def draw_settings_panel(screen, rect, touch_down, touch_x, touch_y, active_index, raw_signals, tuned_signals=None):
    pygame.draw.rect(screen, (30, 30, 35), rect)
    pygame.draw.rect(screen, (80, 80, 90), rect, width=3)
    button_size, spacing = 80, 10
    start_x, start_y = rect.left + 10, rect.y + 60
    clicked_index, change_detected = -1, False
    
    for i, (name, func) in enumerate(PANEL_MAP):
        row, col = i // 2, i % 2
        bx, by = start_x + col * (button_size + spacing), start_y + row * (button_size + spacing)
        brect = pygame.Rect(bx, by, button_size, button_size)
        is_pressed = touch_down and brect.collidepoint(touch_x, touch_y) and not (shared_keyboard.active or shared_keypad.active)
        if is_pressed: clicked_index = i
        bcolor = (40, 100, 200) if i == active_index else ((100, 100, 110) if is_pressed else (50, 52, 60))
        pygame.draw.rect(screen, bcolor, brect, border_radius=15)
        lbl = pygame.font.SysFont("monospace", 14, bold=True).render(name, True, (255,255,255))
        screen.blit(lbl, (brect.centerx - lbl.get_width()//2, brect.centery - lbl.get_height()//2))

    if active_index != -1 and active_index < len(PANEL_MAP):
        if PANEL_MAP[active_index][1] is not None:
            second_rect = pygame.Rect(0, 0, SCREEN_WIDTH - rect.width, SCREEN_HEIGHT)
            pygame.draw.rect(screen, (35, 35, 40), second_rect)
            
            # Draw the panel content
            p_touch = touch_down and not (shared_keyboard.active or shared_keypad.active)
            if PANEL_MAP[active_index][0] in ["Mapper", "Input"]:
                if PANEL_MAP[active_index][1](screen, second_rect, p_touch, touch_x, touch_y, raw_signals, tuned_signals):
                    change_detected = True
            else:
                PANEL_MAP[active_index][1](screen, second_rect, p_touch, touch_x, touch_y)
            
            # Draw the Keyboard/Keypad ON TOP
            shared_keyboard.draw(screen, second_rect, touch_down, touch_x, touch_y)
            shared_keypad.draw(screen, second_rect, touch_down, touch_x, touch_y)
            
    return clicked_index, change_detected

shared_keyboard = VirtualKeyboard()
shared_keypad = VirtualKeypad()