# input_tuning_panel.py - Input Tuning panel (auto-save on every change, no Save button)

import pygame
import time
import json
import os
from config import *
from ui_helpers import draw_numeric_stepper

# NEW SAVE LOCATION: inside project folder
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")

prev_left_decrease_pressed = False
left_decrease_last_release_time = 0.0
prev_left_increase_pressed = False
left_increase_last_release_time = 0.0

prev_right_decrease_pressed = False
right_decrease_last_release_time = 0.0
prev_right_increase_pressed = False
right_increase_last_release_time = 0.0

def draw_input_tuning_panel(screen, rect, touch_down, touch_x, touch_y, panel_visible=None):
    global LEFT_STICK_DEADZONE, RIGHT_STICK_DEADZONE
    global prev_left_decrease_pressed, left_decrease_last_release_time
    global prev_left_increase_pressed, left_increase_last_release_time
    global prev_right_decrease_pressed, right_decrease_last_release_time
    global prev_right_increase_pressed, right_increase_last_release_time

    title = pygame.font.SysFont("monospace", 28, bold=True).render("Input Tuning", True, (255, 255, 255))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 30))

    left_stepper_x = rect.left + 50
    left_stepper_y = rect.y + 100
    left_decrease_rect, left_decrease_pressed, left_increase_rect, left_increase_pressed = draw_numeric_stepper(
        screen, left_stepper_x, left_stepper_y, LEFT_STICK_DEADZONE, "Left Stick Deadzone", touch_down, touch_x, touch_y
    )

    right_stepper_x = rect.left + 50
    right_stepper_y = left_stepper_y + 80 + 20
    right_decrease_rect, right_decrease_pressed, right_increase_rect, right_increase_pressed = draw_numeric_stepper(
        screen, right_stepper_x, right_stepper_y, RIGHT_STICK_DEADZONE, "Right Stick Deadzone", touch_down, touch_x, touch_y
    )

    if not left_decrease_pressed and prev_left_decrease_pressed and time.time() - left_decrease_last_release_time >= 0.2:
        LEFT_STICK_DEADZONE = max(0, LEFT_STICK_DEADZONE - 1)
        left_decrease_last_release_time = time.time()
        save_settings()
    prev_left_decrease_pressed = left_decrease_pressed

    if not left_increase_pressed and prev_left_increase_pressed and time.time() - left_increase_last_release_time >= 0.2:
        LEFT_STICK_DEADZONE = min(100, LEFT_STICK_DEADZONE + 1)
        left_increase_last_release_time = time.time()
        save_settings()
    prev_left_increase_pressed = left_increase_pressed

    if not right_decrease_pressed and prev_right_decrease_pressed and time.time() - right_decrease_last_release_time >= 0.2:
        RIGHT_STICK_DEADZONE = max(0, RIGHT_STICK_DEADZONE - 1)
        right_decrease_last_release_time = time.time()
        save_settings()
    prev_right_decrease_pressed = right_decrease_pressed

    if not right_increase_pressed and prev_right_increase_pressed and time.time() - right_increase_last_release_time >= 0.2:
        RIGHT_STICK_DEADZONE = min(100, RIGHT_STICK_DEADZONE + 1)
        right_increase_last_release_time = time.time()
        save_settings()
    prev_right_increase_pressed = right_increase_pressed

    return left_decrease_rect, left_decrease_pressed, left_increase_rect, left_increase_pressed, right_decrease_rect, right_decrease_pressed, right_increase_rect, right_increase_pressed


def save_settings():
    data = {"left_stick_deadzone": LEFT_STICK_DEADZONE, "right_stick_deadzone": RIGHT_STICK_DEADZONE}
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Settings saved to {SETTINGS_FILE}")


def load_settings():
    global LEFT_STICK_DEADZONE, RIGHT_STICK_DEADZONE
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
            LEFT_STICK_DEADZONE = data.get("left_stick_deadzone", 0)
            RIGHT_STICK_DEADZONE = data.get("right_stick_deadzone", 0)
            print("Loaded left:", LEFT_STICK_DEADZONE, "right:", RIGHT_STICK_DEADZONE)
        except Exception as e:
            print("Load failed:", e)


def get_tuned_left_stick(raw_lx, raw_ly):
    dead = LEFT_STICK_DEADZONE / 100.0
    tuned_lx = apply_deadzone(raw_lx, dead)
    tuned_ly = apply_deadzone(raw_ly, dead)
    return tuned_lx, tuned_ly


def get_tuned_right_stick(raw_rx, raw_ry):
    dead = RIGHT_STICK_DEADZONE / 100.0
    tuned_rx = apply_deadzone(raw_rx, dead)
    tuned_ry = apply_deadzone(raw_ry, dead)
    return tuned_rx, tuned_ry


def apply_deadzone(value, deadzone):
    normalized = value / 32768.0
    abs_val = abs(normalized)
    if abs_val < deadzone:
        return 0
    scaled = (abs_val - deadzone) / (1.0 - deadzone)
    return int(scaled * 32768.0 * (1 if normalized >= 0 else -1))
