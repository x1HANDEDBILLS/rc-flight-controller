import pygame
import numpy as np
from config import *
import input_tuning_panel, mapper_panel, wifi_panel, pid_panel, logs_panel, system_panel, profiles_panel, camera_panel, battery_panel, motors_panel, sensors_panel

# --- NAVIGATION CONFIG ---
# This maps the UI Button Label to the draw function in each module
PANEL_MAP = [
    ("WiFi", wifi_panel.draw_wifi_panel), ("Back", None),
    ("PID", pid_panel.draw_pid_panel), ("Input", input_tuning_panel.draw_input_tuning_panel),
    ("Logs", logs_panel.draw_logs_panel), ("Mapper", mapper_panel.draw_mapper_panel),
    ("System", system_panel.draw_system_panel), ("Stats", battery_panel.draw_battery_panel),
    ("Profiles", profiles_panel.draw_profiles_panel), ("Motors", motors_panel.draw_motors_panel),
    ("Camera", camera_panel.draw_camera_panel), ("Sensors", sensors_panel.draw_sensors_panel)
]

def draw_controller_icon(screen, x, y, connected):
    """Renders the status icon for the physical RC link."""
    color = (40, 255, 100) if connected else (255, 60, 60)
    
    # Modern Controller Body
    pygame.draw.rect(screen, color, (x + 10, y + 22, 60, 32), width=3, border_radius=10)
    
    # Joystick Pads
    pygame.draw.circle(screen, color, (x + 28, y + 38), 5, width=2)
    pygame.draw.circle(screen, color, (x + 52, y + 38), 5, width=2)
    
    # Status LED
    led_color = color if connected else (80, 0, 0)
    pygame.draw.circle(screen, led_color, (x + 40, y + 30), 4)

def draw_gear_button(screen, rect, pressed):
    """Renders the animated settings gear."""
    bg_color = (40, 100, 200) if pressed else (50, 52, 60)
    border_color = (100, 180, 255) if pressed else (95, 100, 110)
    icon_color = (255, 255, 255) if pressed else (200, 200, 200)
    
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(screen, bg_color, inner, border_radius=15)
    pygame.draw.rect(screen, border_color, inner, width=3, border_radius=15)
    
    center = rect.center
    outer_r, inner_r, hub_r = 24, 16, 7
    for ang in range(0, 360, 45):
        rad = np.radians(ang)
        pts = [
            (center[0] + (inner_r-2) * np.cos(rad-0.2), center[1] + (inner_r-2) * np.sin(rad-0.2)),
            (center[0] + outer_r * np.cos(rad-0.15), center[1] + outer_r * np.sin(rad-0.15)),
            (center[0] + outer_r * np.cos(rad+0.15), center[1] + outer_r * np.sin(rad+0.15)),
            (center[0] + (inner_r-2) * np.cos(rad+0.2), center[1] + (inner_r-2) * np.sin(rad+0.2))
        ]
        pygame.draw.polygon(screen, icon_color, pts)
    pygame.draw.circle(screen, icon_color, center, inner_r, 4)
    pygame.draw.circle(screen, icon_color, center, hub_r, 3)

def draw_settings_panel(screen, rect, touch_down, touch_x, touch_y, active_index, raw_signals):
    """Renders the sidebar navigation and calls the active sub-panel."""
    # Render Sidebar Background
    pygame.draw.rect(screen, (30, 30, 35), rect)
    pygame.draw.rect(screen, (80, 80, 90), rect, width=3)
    
    button_size, spacing = 80, 10
    start_x, start_y = rect.left + 10, rect.y + 60
    clicked_index = -1
    
    # Draw Grid of Buttons
    for i, (name, func) in enumerate(PANEL_MAP):
        row, col = i // 2, i % 2
        bx, by = start_x + col * (button_size + spacing), start_y + row * (button_size + spacing)
        brect = pygame.Rect(bx, by, button_size, button_size)
        
        is_pressed = touch_down and brect.collidepoint(touch_x, touch_y)
        if is_pressed: clicked_index = i
        
        # Color Logic
        if name == "Back": 
            bcolor = (120, 60, 60) if is_pressed else (80, 40, 40)
        elif i == active_index: 
            bcolor = (40, 100, 200) # Active Highlight
        else: 
            bcolor = (100, 100, 110) if is_pressed else (50, 52, 60)
        
        pygame.draw.rect(screen, bcolor, brect, border_radius=15)
        pygame.draw.rect(screen, (150, 150, 150), brect, width=2, border_radius=15)
        
        lbl = pygame.font.SysFont("monospace", 14, bold=True).render(name, True, (255,255,255))
        screen.blit(lbl, (brect.centerx - lbl.get_width()//2, brect.centery - lbl.get_height()//2))

    # --- SUB-PANEL RENDERING ---
    # If a tab is selected, draw its specific UI over the main screen area
    if active_index != -1 and PANEL_MAP[active_index][1] is not None:
        # Define the content area (Screen minus the sidebar width)
        second_rect = pygame.Rect(0, 0, SCREEN_WIDTH - rect.width, SCREEN_HEIGHT)
        
        # Panel Background
        pygame.draw.rect(screen, (35, 35, 40), second_rect)
        pygame.draw.rect(screen, (90, 90, 100), second_rect, width=3)
        
        panel_name = PANEL_MAP[active_index][0]
        panel_func = PANEL_MAP[active_index][1]

        # Context-Aware Parameter Passing
        # Mapper and Input (Tuning) need to see the live raw_signals for visualization
        if panel_name in ["Mapper", "Input"]:
            panel_func(screen, second_rect, touch_down, touch_x, touch_y, raw_signals)
        else:
            # Other panels (WiFi, System, etc) use the standard signature
            panel_func(screen, second_rect, touch_down, touch_x, touch_y)
            
    return clicked_index