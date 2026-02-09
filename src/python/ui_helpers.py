# ui_helpers.py - shared UI helpers (numeric stepper only)

import pygame

def draw_numeric_stepper(screen, x, y, value, label, touch_down, touch_x, touch_y):
    # Label
    label_surf = pygame.font.SysFont("monospace", 20).render(label, True, (200, 200, 200))
    screen.blit(label_surf, (x, y - 30))

    # Box for number
    box_rect = pygame.Rect(x, y, 120, 40)
    pygame.draw.rect(screen, (60, 60, 60), box_rect, border_radius=8)
    pygame.draw.rect(screen, (120, 120, 120), box_rect, width=2, border_radius=8)

    # Number centered
    num_surf = pygame.font.SysFont("monospace", 24, bold=True).render(str(value), True, (255, 255, 255))
    screen.blit(num_surf, (box_rect.centerx - num_surf.get_width() // 2, box_rect.centery - num_surf.get_height() // 2))

    # Left arrow
    left_rect = pygame.Rect(x - 40, y, 30, 40)
    left_pressed = touch_down and left_rect.collidepoint(touch_x, touch_y)
    left_color = (100, 100, 100) if left_pressed else (80, 80, 80)
    pygame.draw.rect(screen, left_color, left_rect, border_radius=8)
    pygame.draw.polygon(screen, (200, 200, 200), [
        (left_rect.centerx + 10, left_rect.top + 10),
        (left_rect.centerx - 10, left_rect.centery),
        (left_rect.centerx + 10, left_rect.bottom - 10)
    ])

    # Right arrow
    right_rect = pygame.Rect(x + 130, y, 30, 40)
    right_pressed = touch_down and right_rect.collidepoint(touch_x, touch_y)
    right_color = (100, 100, 100) if right_pressed else (80, 80, 80)
    pygame.draw.rect(screen, right_color, right_rect, border_radius=8)
    pygame.draw.polygon(screen, (200, 200, 200), [
        (right_rect.centerx - 10, right_rect.top + 10),
        (right_rect.centerx + 10, right_rect.centery),
        (right_rect.centerx - 10, right_rect.bottom - 10)
    ])

    return left_rect, left_pressed, right_rect, right_pressed