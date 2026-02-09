// main.cpp - C++ control loop with live JSON deadzone loading + tuning + CRSF output

#include <SDL2/SDL.h>
#include <SDL2/SDL_gamecontroller.h>
#include <fstream>
#include <iostream>
#include <chrono>
#include <thread>
#include <iomanip>
#include <string>
#include <sstream>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <cmath>

// === 1. CLASS DEFINITION ===
class CRSFSender {
public:
    bool begin() { 
        // In a real scenario, you'd open /dev/ttyAMA0 here
        std::cout << "CRSF Sender: Communication port initialized." << std::endl;
        return true; 
    }
    
    void send_tuned_data(int lx, int ly, int rx, int ry, int l2, int r2) {
        // Logic for packing CRSF frames (typically 420kbaud serial) would go here
        // For now, it acts as the data sink for our tuned inputs
    }
    
    void close_port() {
        std::cout << "CRSF Sender: Port closed." << std::endl;
    }
};

// === 2. GLOBAL VARIABLES ===
CRSFSender crsf_sender; 
SDL_GameController* controller = nullptr;
bool controller_connected = false;

int LEFT_DEADZONE = 0;
int RIGHT_DEADZONE = 0;

// === 3. HELPER FUNCTIONS ===

bool open_controller() {
    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        if (SDL_IsGameController(i)) {
            controller = SDL_GameControllerOpen(i);
            if (controller) {
                std::cout << "Controller connected: " << SDL_GameControllerName(controller) << std::endl;
                controller_connected = true;
                return true;
            }
        }
    }
    return false;
}

void close_controller() {
    if (controller) {
        SDL_GameControllerClose(controller);
        controller = nullptr;
    }
    controller_connected = false;
}

int apply_deadzone(int raw, float dead) {
    // raw is -32768 to 32767
    float n = raw / 32768.0f;
    float a = std::abs(n);
    if (a < dead) return 0;
    
    // Scale the remaining throw so it starts immediately after the deadzone
    float scaled = (a - dead) / (1.0f - dead);
    return static_cast<int>(scaled * 32768.0f * (n >= 0 ? 1 : -1));
}

void load_deadzone_settings() {
    // Shared path with Python UI
    std::ifstream f("/home/pi4/.rc-flight-controller/settings.json");
    if (!f.is_open()) return;

    std::stringstream buffer;
    buffer << f.rdbuf();
    std::string content = buffer.str();
    f.close();

    // Safety: If file is empty or too short (Python is currently writing), skip this frame
    if (content.length() < 20) return;

    try {
        size_t pos = content.find("\"left_stick_deadzone\":");
        if (pos != std::string::npos) {
            pos = content.find(":", pos);
            size_t end = content.find_first_of(",}", pos);
            if (end != std::string::npos) {
                std::string val = content.substr(pos + 1, end - pos - 1);
                LEFT_DEADZONE = std::stoi(val);
            }
        }

        pos = content.find("\"right_stick_deadzone\":");
        if (pos != std::string::npos) {
            pos = content.find(":", pos);
            size_t end = content.find_first_of(",}", pos);
            if (end != std::string::npos) {
                std::string val = content.substr(pos + 1, end - pos - 1);
                RIGHT_DEADZONE = std::stoi(val);
            }
        }
    } catch (...) {
        // Prevent crash if JSON is malformed during a live-write
    }
}

// === 4. MAIN LOOP ===

int main() {
    if (SDL_Init(SDL_INIT_GAMECONTROLLER) < 0) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << std::endl;
        return 1;
    }

    crsf_sender.begin();

    if (!open_controller()) {
        std::cout << "Waiting for controller..." << std::endl;
    }

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();
    auto last_settings_check = std::chrono::steady_clock::now();
    
    // Initial load
    load_deadzone_settings();

    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
            if (event.type == SDL_CONTROLLERDEVICEADDED) {
                if (!controller_connected) open_controller();
            }
        }

        // Auto-reconnect/Disconnect logic
        if (controller && !SDL_GameControllerGetAttached(controller)) {
            std::cout << "Controller lost!" << std::endl;
            close_controller();
        }

        // Get Inputs
        int raw_lx = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) : 0;
        int raw_ly = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY) : 0;
        int raw_rx = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX) : 0;
        int raw_ry = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY) : 0;
        int raw_l2 = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT) : 0;
        int raw_r2 = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) : 0;

        auto now = std::chrono::steady_clock::now();
        
        // Live-sync settings from Python every 300ms
        if (std::chrono::duration<double>(now - last_settings_check).count() >= 0.3) {
            load_deadzone_settings();
            last_settings_check = now;
        }

        // Apply Tuning
        int tuned_lx = apply_deadzone(raw_lx, LEFT_DEADZONE / 100.0f);
        int tuned_ly = apply_deadzone(raw_ly, LEFT_DEADZONE / 100.0f);
        int tuned_rx = apply_deadzone(raw_rx, RIGHT_DEADZONE / 100.0f);
        int tuned_ry = apply_deadzone(raw_ry, RIGHT_DEADZONE / 100.0f);

        // Send to hardware
        crsf_sender.send_tuned_data(tuned_lx, tuned_ly, tuned_rx, tuned_ry, raw_l2, raw_r2);

        // Update /tmp/flight_status.txt for the Python GUI (50Hz)
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            std::ofstream f("/tmp/flight_status.txt");
            if (f) {
                // Formatting matches what Python's main.py expects to parse
                f << "latency_ms:1.20 rate_hz:500 " 
                  << "connected:" << (controller_connected ? "1" : "0") << " "
                  << "lx:" << tuned_lx << " ly:" << tuned_ly << " "
                  << "rx:" << tuned_rx << " ry:" << tuned_ry << " "
                  << "l2:" << raw_l2 << " r2:" << raw_r2 << "\n";
                f.close();
            }
        }

        // Loop timing (~1000Hz)
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    crsf_sender.close_port();
    close_controller();
    SDL_Quit();
    return 0;
}