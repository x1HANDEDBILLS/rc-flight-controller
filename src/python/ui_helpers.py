# ui_helpers.py - shared UI helpers (numeric stepper only)
import pygame

def draw_numeric_stepper(screen, x, y, value, label, touch_down, touch_x, touch_y):
    """
    Renders a touch-friendly numeric stepper with increase/decrease buttons.
    Returns the rects and pressed states for the main loop to handle logic.
    """
    # Fonts
    font_main = pygame.font.SysFont("monospace", 20, bold=True)
    font_label = pygame.font.SysFont("monospace", 16)

    # Render Label above the stepper
    label_surf = font_label.render(label.upper(), True, (150, 150, 150))
    screen.blit(label_surf, (x - 40, y - 25))

    # 1. Box for number (The Display)
    box_rect = pygame.Rect(x, y, 120, 45)
    pygame.draw.rect(screen, (30, 32, 38), box_rect, border_radius=10)
    pygame.draw.rect(screen, (70, 75, 85), box_rect, width=2, border_radius=10)

    # --- FIXED DISPLAY LOGIC ---
    # :g automatically removes trailing zeros. 1.0 becomes "1", 0.1 stays "0.1"
    # We round to 1 decimal place to prevent floating point jitter (like 0.30000004)
    if isinstance(value, float):
        display_val = "{:g}".format(round(value, 1))
    else:
        display_val = str(value)

    num_surf = font_main.render(display_val, True, (0, 255, 120))
    screen.blit(num_surf, (box_rect.centerx - num_surf.get_width() // 2, box_rect.centery - num_surf.get_height() // 2))

    # 2. Left arrow (Decrease)
    left_rect = pygame.Rect(x - 55, y, 45, 45)
    left_pressed = touch_down and left_rect.collidepoint(touch_x, touch_y)
    left_color = (0, 180, 255) if left_pressed else (50, 55, 65)
    
    pygame.draw.rect(screen, left_color, left_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [
        (left_rect.centerx + 8, left_rect.centery - 10),
        (left_rect.centerx - 8, left_rect.centery),
        (left_rect.centerx + 8, left_rect.centery + 10)
    ])

    # 3. Right arrow (Increase)
    right_rect = pygame.Rect(x + 130, y, 45, 45)
    right_pressed = touch_down and right_rect.collidepoint(touch_x, touch_y)
    right_color = (0, 180, 255) if right_pressed else (50, 55, 65)
    
    pygame.draw.rect(screen, right_color, right_rect, border_radius=10)
    pygame.draw.polygon(screen, (255, 255, 255), [
        (right_rect.centerx - 8, right_rect.centery - 10),
        (right_rect.centerx + 8, right_rect.centery),
        (right_rect.centerx - 8, right_rect.centery + 10)
    ])

    return left_rect, left_pressed, right_rect, right_pressed