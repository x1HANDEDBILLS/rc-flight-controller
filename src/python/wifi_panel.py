# wifi_panel.py - Generated Paginated UI Panel
import pygame
import time
from config import *

# Local State
current_page = 0
last_interaction_time = 0

def draw_wifi_panel(screen, rect, touch_down, touch_x, touch_y):
    global current_page, last_interaction_time
    
    # Title Rendering
    title_font = pygame.font.SysFont("monospace", 28, bold=True)
    title = title_font.render(f"WiFi: Page {current_page + 1}", True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 30))

    # Placeholder Content
    font = pygame.font.SysFont("monospace", 20, bold=True)
    msg = font.render(f"WiFi settings coming soon...", True, (100, 100, 100))
    screen.blit(msg, (rect.centerx - msg.get_width()//2, rect.centery))

    # --- NAVIGATION ARROWS ---
    arrow_w, arrow_h = 60, 45
    prev_rect = pygame.Rect(rect.centerx - 70, rect.bottom - 70, arrow_w, arrow_h)
    next_rect = pygame.Rect(rect.centerx + 10, rect.bottom - 70, arrow_w, arrow_h)

    # Draw Back Arrow
    p_pres = touch_down and prev_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if p_pres else (40, 40, 50), prev_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(prev_rect.centerx+10, prev_rect.centery-10), (prev_rect.centerx-10, prev_rect.centery), (prev_rect.centerx+10, prev_rect.centery+10)])
    
    # Draw Next Arrow
    n_pres = touch_down and next_rect.collidepoint(touch_x, touch_y)
    pygame.draw.rect(screen, (70, 70, 80) if n_pres else (40, 40, 50), next_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [(next_rect.centerx-10, next_rect.centery-10), (next_rect.centerx+10, next_rect.centery), (next_rect.centerx-10, next_rect.centery+10)])

    # --- PAGE INDICATOR DOTS ---
    for i in range(3):
        dot_x = rect.centerx - 20 + (i * 20)
        dot_y = rect.bottom - 85
        color = (255, 255, 255) if i == current_page else (100, 100, 100)
        pygame.draw.circle(screen, color, (dot_x, dot_y), 4)

    # Switching Logic (Debounced)
    if (p_pres or n_pres) and (time.time() - last_interaction_time) > 0.25:
        if p_pres: current_page = (current_page - 1) % 3
        if n_pres: current_page = (current_page + 1) % 3
        last_interaction_time = time.time()
