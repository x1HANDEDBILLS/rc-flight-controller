import pygame
import time
import os
from multiprocessing import Process, Pipe
from logic_process import logic_process
from config import *

# --- INITIALIZE ACTUAL TOUCH HARDWARE ---
parent_conn, child_conn = Pipe(False)
p = Process(target=logic_process, args=(child_conn,), daemon=True)
p.start()

pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
pygame.mouse.set_visible(False)
font = pygame.font.SysFont("monospace", 20, bold=True)

class TestState:
    def __init__(self):
        self.slider_val = 200
        self.is_dragging = False
        self.kb_active = False
        self.kb_open_time = 0   # Safety for opening
        self.ui_lock_time = 0    # Safety for closing
        self.last_action = "System Ready"

state = TestState()

def run_test():
    running = True
    clock = pygame.time.Clock()

    while running:
        # 1. GET RAW TOUCH DATA
        latest = [0.1, False, 0, 0]
        while parent_conn.poll():
            latest = parent_conn.recv()
        t_lat, t_down, tx, ty = latest

        now = time.time()

        # 2. THE GLOBAL SHIELD (FOR THE BACKGROUND)
        # Prevents clicking the wifi list the moment the keyboard closes
        safe_t_down = t_down
        if (now - state.ui_lock_time) < 0.3:
            safe_t_down = False

        # --- RENDERING ---
        screen.fill((15, 15, 20))
        
        # DRAW SLIDER
        slider_rect = pygame.Rect(100, 150, 400, 60)
        pygame.draw.rect(screen, (40, 40, 50), slider_rect, border_radius=10)
        
        # DRAG LOGIC (Uses safe_t_down so it doesn't jump when keyboard closes)
        if safe_t_down and slider_rect.collidepoint(tx, ty) and not state.kb_active:
            state.is_dragging = True
        
        if not t_down: # Use RAW t_down so it releases the moment you let go
            state.is_dragging = False
            
        if state.is_dragging:
            state.slider_val = max(0, min(tx - slider_rect.x, slider_rect.width))
            state.last_action = f"Dragging: {int(state.slider_val)}"

        pygame.draw.rect(screen, (0, 150, 255), (slider_rect.x, slider_rect.y, state.slider_val, 60), border_radius=10)
        screen.blit(font.render("DRAG SLIDER TEST", True, (255,255,255)), (100, 110))

        # DRAW WIFI BUTTON
        wifi_rect = pygame.Rect(100, 300, 400, 60)
        # Check safe_t_down to prevent ghost clicks
        if safe_t_down and wifi_rect.collidepoint(tx, ty) and not state.kb_active:
            state.kb_active = True
            state.kb_open_time = now # MARK WHEN WE OPENED IT
            state.last_action = "Keyboard Opened"

        pygame.draw.rect(screen, (60, 40, 40), wifi_rect, border_radius=10)
        screen.blit(font.render("CLICK ME (KEYBOARD POPUP)", True, (255,255,255)), (115, 315))

        # DRAW KEYBOARD OVERLAY
        if state.kb_active:
            kb_overlay = pygame.Rect(50, 50, 700, 380)
            pygame.draw.rect(screen, (30, 30, 35), kb_overlay, border_radius=20)
            pygame.draw.rect(screen, (0, 255, 100), kb_overlay, width=3, border_radius=20)
            
            # THE SAFETY CHECK: Keyboard ignores touch for first 0.4 seconds
            kb_input_allowed = (now - state.kb_open_time) > 0.4
            
            enter_btn = pygame.Rect(300, 300, 200, 80)
            
            # Check for "Enter" click ONLY if allowed
            if kb_input_allowed and t_down and enter_btn.collidepoint(tx, ty):
                state.kb_active = False
                state.ui_lock_time = now # LOCK TOUCH FOR BACKGROUND
                state.last_action = "ENTER HIT - TOUCH SHIELDED"

            btn_color = (0, 180, 80) if kb_input_allowed else (40, 60, 50)
            pygame.draw.rect(screen, btn_color, enter_btn, border_radius=10)
            screen.blit(font.render("ENTER", True, (255,255,255)), (360, 325))
            
            if not kb_input_allowed:
                screen.blit(font.render("WAIT...", True, (255, 100, 100)), (365, 270))

        # DEBUG INFO
        screen.blit(font.render(f"Action: {state.last_action}", True, (0, 255, 0)), (20, 20))
        
        pygame.display.flip()
        clock.tick(60)

    p.terminate()
    pygame.quit()

if __name__ == "__main__":
    run_test()