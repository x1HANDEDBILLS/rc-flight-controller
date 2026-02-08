# ui_components.py - controller icon, gear button, settings panels

import pygame
import numpy as np
from config import *
from input_tuning_panel import draw_input_tuning_panel

def draw_controller_icon(screen, x, y, connected):
    color = (40, 255, 80) if connected else (255, 80, 80)
    pygame.draw.rect(screen, color, (x, y, 80, 50), width=4)

    stick_r = STICK_RADIUS
    pygame.draw.circle(screen, color, (x + 20, y + 35), stick_r, 2)
    pygame.draw.circle(screen, color, (x + 60, y + 35), stick_r, 2)

def draw_gear_button(screen, rect, pressed):
    color = (50, 180, 120) if pressed else (70, 75, 82)
    border = (100, 255, 160) if pressed else (95, 100, 110)
    inner = rect.inflate(-10, -10)
    inner.center = rect.center
    pygame.draw.rect(screen, color, inner, border_radius=18)
    pygame.draw.rect(screen, border, inner, width=3, border_radius=18)

    center = rect.center
    pygame.draw.circle(screen, (200, 200, 200), center, 30, 4)
    for ang in range(0, 360, 45):
        x1 = center[0] + 25 * np.cos(np.radians(ang))
        y1 = center[1] + 25 * np.sin(np.radians(ang))
        x2 = center[0] + 35 * np.cos(np.radians(ang))
        y2 = center[1] + 35 * np.sin(np.radians(ang))
        pygame.draw.line(screen, (200, 200, 200), (x1, y1), (x2, y2), 4)
    pygame.draw.circle(screen, (200, 200, 200), center, 10)

def draw_settings_panel(screen, rect, touch_down, touch_x, touch_y, second_panel_visible):
    pygame.draw.rect(screen, (30, 30, 35), rect)
    pygame.draw.rect(screen, (80, 80, 90), rect, width=3)

    # Title
    title = pygame.font.SysFont("monospace", 24, bold=True).render("Settings", True, (255, 255, 255))
    screen.blit(title, (rect.x + 45, rect.y + 20))

    # Button grid - shifted 10px right
    button_size = 80
    spacing = 10
    start_x = rect.right - 20 - (button_size * 2 + spacing) + 10
    start_y = rect.y + 60

    back_rect = None
    back_pressed = False
    input_rect = None
    input_pressed = False

    for row in range(6):
        for col in range(2):
            bx = start_x + col * (button_size + spacing)
            by = start_y + row * (button_size + spacing)
            brect = pygame.Rect(bx, by, button_size, button_size)
            bpressed = touch_down and brect.collidepoint(touch_x, touch_y)
            bcolor = (100, 100, 100) if bpressed else (60, 60, 60)
            pygame.draw.rect(screen, bcolor, brect, border_radius=18)
            pygame.draw.rect(screen, (150, 150, 150), brect, width=3, border_radius=18)

            if row == 0 and col == 1:
                back_rect = brect
                back_pressed = bpressed
                arrow_points = [
                    (brect.centerx - 20, brect.centery - 20),
                    (brect.centerx + 20, brect.centery),
                    (brect.centerx - 20, brect.centery + 20)
                ]
                pygame.draw.polygon(screen, (200, 200, 200), arrow_points)

            if row == 1 and col == 1:
                input_rect = brect
                input_pressed = bpressed
                label = pygame.font.SysFont("monospace", 24, bold=True).render("Input", True, (255, 255, 255))
                screen.blit(label, (brect.centerx - label.get_width() // 2, brect.centery - label.get_height() // 2))

    if second_panel_visible:
        second_rect = pygame.Rect(0, 0, SCREEN_WIDTH - rect.width, SCREEN_HEIGHT)
        pygame.draw.rect(screen, (35, 35, 40), second_rect)
        pygame.draw.rect(screen, (90, 90, 100), second_rect, width=3)

        # Pass panel visibility as 6th argument
        draw_input_tuning_panel(screen, second_rect, touch_down, touch_x, touch_y, second_panel_visible)

    return back_rect, back_pressed, input_rect, input_pressed
