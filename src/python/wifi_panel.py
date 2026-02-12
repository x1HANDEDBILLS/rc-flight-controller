# wifi_panel.py - FULL PRODUCTION BUILD V3 (FIXED PERMISSIONS + ORIGINAL ANIMATION)
import pygame
import time
import subprocess
import threading
import math
import re
from config import *

# --- Global State ---
current_page = 0
last_page = -1
last_interaction_time = 0
wifi_ssids = []
bt_devices = []
loading = False
loading_start = 0
selected_ssid = ""
wifi_status = {}
bt_status = {}
remembered_ssids = []
autoconnect_dict = {}

# Scrolling State
scroll_y = 0
scroll_dragging = False
last_touch_y = 0
start_scroll_y = 0

# --- Font Initialization ---
pygame.font.init()
FONT_TITLE = pygame.font.SysFont("monospace", 26, bold=True)
FONT_MED = pygame.font.SysFont("monospace", 18, bold=True)
FONT_SMALL = pygame.font.SysFont("monospace", 14, bold=True)
FONT_TINY = pygame.font.SysFont("monospace", 11, bold=True)
FONT_ARROW = pygame.font.SysFont("monospace", 20, bold=True)

def debug_print(section, message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{section.upper()}] {message}")

# --- WiFi Logic ---
def fetch_remembered():
    global remembered_ssids, autoconnect_dict
    try:
        # Use sudo to ensure we can read all connection details
        output = subprocess.getoutput("""
        for uuid in $(sudo nmcli -t -f UUID,TYPE con show | grep ':802-11-wireless$' | cut -d: -f1); do
            ssid=$(sudo nmcli -t -f 802-11-wireless.ssid con show "$uuid" | cut -d: -f2)
            auto=$(sudo nmcli -t -f connection.autoconnect con show "$uuid" | cut -d: -f2)
            echo "$ssid:$auto"
        done
        """).splitlines()
        
        remembered_ssids = []
        autoconnect_dict = {}
        for line in output:
            if ':' in line:
                s, a = line.split(':', 1)
                if s:
                    remembered_ssids.append(s)
                    autoconnect_dict[s] = (a.strip() == 'yes')
    except Exception as e:
        debug_print("wifi-err", f"Fetch Fail: {e}")

def get_profiles_for_ssid(ssid):
    uuids = subprocess.getoutput("sudo nmcli -t -f UUID,TYPE con show | grep ':802-11-wireless$' | cut -d: -f1").splitlines()
    matches = []
    for u in uuids:
        s_val = subprocess.getoutput(f"sudo nmcli -t -f 802-11-wireless.ssid con show {u} | cut -d: -f2").strip()
        if s_val == ssid:
            matches.append(u)
    return matches

def scan_wifi():
    global wifi_ssids, loading, wifi_status
    debug_print("wifi", "Scanning...")
    # Clean break: reset status unless connecting
    wifi_status = {k: v for k, v in wifi_status.items() if v in ["linking...", "clearing..."]}
    fetch_remembered()
    try:
        raw_active = subprocess.getoutput("sudo nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes'").strip()
        active_ssid = raw_active.split(':')[-1] if raw_active else None

        subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'rescan'], timeout=8, capture_output=True)
        output = subprocess.check_output(['sudo', 'nmcli', '-f', 'SSID,ACTIVE,SECURITY,BARS', '--terse', 'dev', 'wifi']).decode('utf-8')
        
        found, seen = [], set()
        for line in output.splitlines():
            parts = line.split(':')
            if len(parts) < 4: continue
            name, active_str = parts[0], parts[1].lower()
            if not name or name == "--" or name in seen: continue
            
            seen.add(name)
            is_active = (active_str == "yes") or (name == active_ssid)
            if is_active: wifi_status[name] = "connected"
            
            found.append({'name': name, 'active': is_active, 'security': parts[2], 'bars': parts[3]})
        wifi_ssids = sorted(found, key=lambda d: (not d['active'], d['name'].lower()))
    except Exception as e:
        debug_print("wifi-err", f"Scan: {e}")
    loading = False

def connect_to_wifi(password, ssid_to_use=None):
    global selected_ssid, wifi_status
    target = ssid_to_use if ssid_to_use else selected_ssid
    def do_connect():
        wifi_status[target] = "clearing..."
        # Force down all active wifi
        cons = subprocess.getoutput("sudo nmcli -t -f NAME,TYPE con show --active | grep ':802-11-wireless' | cut -d: -f1").splitlines()
        for c in cons:
            subprocess.run(['sudo', 'nmcli', 'connection', 'down', c.strip()], capture_output=True)
        
        subprocess.run(['sudo', 'nmcli', 'device', 'disconnect', 'wlan0'], capture_output=True)
        time.sleep(1.5) 
        
        for p in get_profiles_for_ssid(target):
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', p], capture_output=True)
        
        wifi_status[target] = "linking..."
        res = subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'connect', target, 'password', password], capture_output=True, timeout=30)
        
        if res.returncode == 0:
            wifi_status[target] = "connected"
        else:
            wifi_status[target] = "failed"
        scan_wifi()
    threading.Thread(target=do_connect, daemon=True).start()

def disconnect_wifi(ssid, forget):
    global wifi_status
    def do_discon():
        wifi_status[ssid] = "cleaning..."
        subprocess.run(['sudo', 'nmcli', 'device', 'disconnect', 'wlan0'], capture_output=True)
        if forget:
            for p in get_profiles_for_ssid(ssid):
                subprocess.run(['sudo', 'nmcli', 'connection', 'delete', p], capture_output=True)
        wifi_status[ssid] = ""
        scan_wifi()
    threading.Thread(target=do_discon, daemon=True).start()

# --- Bluetooth Logic ---
def scan_bt():
    global bt_devices, loading, bt_status
    debug_print("bt", "Scanning...")
    bt_status = {k: v for k, v in bt_status.items() if v == "pairing..."}
    try:
        subprocess.run(['sudo', 'bluetoothctl', '--timeout', '4', 'scan', 'on'], capture_output=True)
        raw_devices = subprocess.getoutput("sudo bluetoothctl devices").splitlines()
        temp_list = []
        for line in raw_devices:
            match = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
            if match:
                mac, name = match.group(1), match.group(2)
                info = subprocess.getoutput(f"sudo bluetoothctl info {mac}")
                is_connected = "Connected: yes" in info
                if is_connected:
                    bt_status[name] = "connected"
                temp_list.append(f"{name}|{mac}")
        bt_devices = temp_list
    except Exception as e:
        debug_print("bt-err", f"Scan: {e}")
    loading = False

def connect_bt(mac, name):
    global bt_status
    def do_connect():
        bt_status[name] = "pairing..."
        subprocess.run(['sudo', 'bluetoothctl', 'trust', mac], capture_output=True)
        res = subprocess.run(['sudo', 'bluetoothctl', 'connect', mac], capture_output=True)
        bt_status[name] = "connected" if res.returncode == 0 else "failed"
        scan_bt()
    threading.Thread(target=do_connect, daemon=True).start()

def disconnect_bt(mac, name):
    def do_discon():
        subprocess.run(['sudo', 'bluetoothctl', 'disconnect', mac], capture_output=True)
        scan_bt()
    threading.Thread(target=do_discon, daemon=True).start()

# --- Main Drawing ---
def draw_wifi_panel(screen, rect, touch_down, touch_x, touch_y):
    from ui_components import shared_keyboard
    global current_page, last_page, last_interaction_time, loading, loading_start
    global wifi_ssids, bt_devices, selected_ssid, wifi_status, bt_status, remembered_ssids, autoconnect_dict
    global scroll_y, scroll_dragging, last_touch_y, start_scroll_y

    now = time.time()
    if current_page != last_page:
        scroll_y = 0
        loading, loading_start = (True, now) if current_page < 2 else (False, 0)
        if current_page == 0: threading.Thread(target=scan_wifi, daemon=True).start()
        elif current_page == 1: threading.Thread(target=scan_bt, daemon=True).start()
        last_page = current_page

    title_t = FONT_TITLE.render("CONNECTIVITY", True, (0, 200, 255))
    screen.blit(title_t, (rect.centerx - title_t.get_width()//2, rect.y + 15))

    if current_page < 2:
        re_btn = pygame.Rect(rect.centerx - 90, rect.y + 50, 180, 40)
        pygame.draw.rect(screen, (35, 38, 50), re_btn, border_radius=10)
        pygame.draw.rect(screen, (0, 200, 255), re_btn, width=2, border_radius=10)
        lbl_txt = "REFRESH" if not loading else "SCANNING..."
        lbl = FONT_SMALL.render(lbl_txt, True, (255, 255, 255))
        screen.blit(lbl, (re_btn.centerx - lbl.get_width()//2, re_btn.centery - lbl.get_height()//2))
        if touch_down and re_btn.collidepoint(touch_x, touch_y) and (now - last_interaction_time) > 1.2:
            last_interaction_time, loading = now, True
            threading.Thread(target=scan_wifi if current_page == 0 else scan_bt, daemon=True).start()

    list_r = pygame.Rect(rect.x + 5, rect.y + 100, rect.width - 10, rect.height - 170)
    items = wifi_ssids if current_page == 0 else bt_devices
    total_h = len(items) * 65

    if touch_down and list_r.collidepoint(touch_x, touch_y):
        if not scroll_dragging:
            scroll_dragging, last_touch_y, start_scroll_y = True, touch_y, scroll_y
        scroll_y = start_scroll_y + (last_touch_y - touch_y)
    else: scroll_dragging = False
    scroll_y = max(0, min(scroll_y, max(0, total_h - list_r.height)))

    screen.set_clip(list_r)
    for i, item in enumerate(items):
        y = list_r.y + (i * 65) - scroll_y
        if y < list_r.y - 60 or y > list_r.bottom: continue
        row = pygame.Rect(rect.x + 10, y, list_r.width - 20, 60)
        pygame.draw.rect(screen, (25, 28, 38), row, border_radius=12)
        
        if current_page == 0:
            name = item['name']
            status = wifi_status.get(name, "")
            is_conn = (status == "connected")
            
            ssid_btn = pygame.Rect(row.x + 5, row.y + 10, 120, 40)
            btn_col = (30, 80, 50) if is_conn else (60, 100, 200) if name in remembered_ssids else (45, 50, 65)
            pygame.draw.rect(screen, btn_col, ssid_btn, border_radius=8)
            screen.blit(FONT_SMALL.render(name[:10], True, (255,255,255)), (ssid_btn.x + 8, ssid_btn.y + 12))
            
            if status and not is_conn:
                col = (255, 180, 0) if "ing" in status else (255, 50, 50)
                screen.blit(FONT_TINY.render(status.upper(), True, col), (row.x + 135, row.y + 22))

            if is_conn:
                is_auto = autoconnect_dict.get(name, False)
                cb_box = pygame.Rect(row.x + 150, row.y + 16, 28, 28)
                pygame.draw.rect(screen, (0, 200, 255) if is_auto else (100, 100, 100), cb_box, 3, border_radius=6)
                if is_auto: pygame.draw.rect(screen, (0, 200, 255), cb_box.inflate(-10, -10))
                if touch_down and cb_box.inflate(15,15).collidepoint(touch_x, touch_y) and (now - last_interaction_time) > 0.4:
                    last_interaction_time = now
                    def toggle():
                        subprocess.run(['sudo', 'nmcli', 'con', 'mod', get_profiles_for_ssid(name)[0], 'connection.autoconnect', 'no' if is_auto else 'yes'])
                    threading.Thread(target=toggle).start()
                    autoconnect_dict[name] = not is_auto

            if touch_down and ssid_btn.collidepoint(touch_x, touch_y) and not is_conn and (now - last_interaction_time) > 0.6:
                last_interaction_time = now
                if name in remembered_ssids:
                    threading.Thread(target=lambda: subprocess.run(['sudo', 'nmcli', 'con', 'up', get_profiles_for_ssid(name)[0]])).start()
                else:
                    selected_ssid = name
                    shared_keyboard.open(f"Pass: {name}", "", connect_to_wifi)
            
            screen.blit(FONT_SMALL.render(item['bars'], True, (0, 255, 255)), (row.right - 85, row.y + 22))

        elif current_page == 1:
            b_name, b_mac = item.split('|')
            status = bt_status.get(b_name, "")
            is_b_conn = (status == "connected")
            b_btn = pygame.Rect(row.x + 8, row.y + 10, 180, 40)
            btn_col = (30, 80, 50) if is_b_conn else (60, 100, 200) if status == "pairing..." else (45, 50, 65)
            pygame.draw.rect(screen, btn_col, b_btn, border_radius=8)
            screen.blit(FONT_SMALL.render(b_name[:18], True, (255,255,255)), (b_btn.x + 10, b_btn.y + 12))
            if status:
                col = (0, 255, 100) if is_b_conn else (255, 180, 0) if "pair" in status else (255, 50, 50)
                screen.blit(FONT_TINY.render(status.upper(), True, col), (row.right - 140, row.y + 22))
            if touch_down and b_btn.collidepoint(touch_x, touch_y) and not is_b_conn and (now - last_interaction_time) > 0.8:
                last_interaction_time = now
                connect_bt(b_mac, b_name)

        if (current_page == 0 and is_conn) or (current_page == 1 and is_b_conn):
            x_btn = pygame.Rect(row.right - 45, row.y + 10, 40, 40)
            pygame.draw.rect(screen, (200, 40, 40), x_btn, border_radius=8)
            screen.blit(FONT_SMALL.render("X", True, (255,255,255)), (x_btn.x + 15, x_btn.y + 12))
            if touch_down and x_btn.collidepoint(touch_x, touch_y) and (now - last_interaction_time) > 0.6:
                last_interaction_time = now
                if current_page == 0: disconnect_wifi(name, False)
                else: disconnect_bt(b_mac, b_name)

    screen.set_clip(None)

    # REVERTED TO ORIGINAL CIRCLE ANIMATION
    if loading:
        cx, cy = rect.centerx, rect.centery
        for i in range(4):
            rad = (((now - loading_start) * 70 + i * 35) % 140) + 10
            s = pygame.Surface((300,300), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 200, 255, max(0, 255 - rad*1.8)), (150,150), rad, 3)
            screen.blit(s, (cx-150, cy-150))

    p_rect, n_rect = pygame.Rect(rect.centerx - 100, rect.bottom - 55, 90, 45), pygame.Rect(rect.centerx + 10, rect.bottom - 55, 90, 45)
    for r, lbl, dr in [(p_rect, "<", -1), (n_rect, ">", 1)]:
        if touch_down and r.collidepoint(touch_x, touch_y) and (now - last_interaction_time) > 0.4:
            current_page, last_interaction_time = (current_page + dr) % 3, now
        pygame.draw.rect(screen, (45, 45, 55), r, border_radius=12)
        txt = FONT_ARROW.render(lbl, True, (255,255,255))
        screen.blit(txt, (r.centerx-txt.get_width()//2, r.centery-txt.get_height()//2))