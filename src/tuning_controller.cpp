#include <SDL2/SDL.h>
#include <SDL2/SDL_gamecontroller.h>
#include <fstream>
#include <iostream>
#include <chrono>
#include <thread>
#include <iomanip>
#include <string>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

// Globals for tuning (loaded from JSON)
int LEFT_STICK_DEADZONE = 0;
int RIGHT_STICK_DEADZONE = 0;

// Placeholder for your transmitter function (replace with real)
void send_to_transmitter(int lx, int ly, int rx, int ry, int l2, int r2) {
    // Your CRSF/SBUS/whatever code here - runs every loop
}

// Deadzone function in C++
int apply_deadzone(int raw, float dead) {
    float n = raw / 32768.0f;
    float a = std::abs(n);
    if (a < dead) return 0;
    return static_cast<int>(((a - dead) / (1.0f - dead)) * 32768.0f * (n >= 0 ? 1 : -1));
}

int main() {
    if (SDL_Init(SDL_INIT_GAMECONTROLLER) < 0) {
        std::cerr << "SDL_Init failed\n";
        return 1;
    }

    SDL_GameController* controller = nullptr;
    bool controller_connected = false;

    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        if (SDL_IsGameController(i)) {
            controller = SDL_GameControllerOpen(i);
            if (controller) {
                std::cout << "Controller connected\n";
                controller_connected = true;
                break;
            }
        }
    }

    if (!controller_connected) {
        std::cout << "No controller\n";
        SDL_Quit();
        return 1;
    }

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();
    auto last_settings_check = std::chrono::steady_clock::now();

    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
        }

        int raw_lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
        int raw_ly = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
        int raw_rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
        int raw_ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);
        int raw_l2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT);
        int raw_r2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT);

        // Reload settings from JSON every 300 ms
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_settings_check).count() >= 0.3) {
            last_settings_check = now;
            try {
                std::ifstream f("/home/pi4/.rc-flight-controller/settings.json");
                if (f) {
                    json data = json::parse(f);
                    LEFT_STICK_DEADZONE = data.value("left_stick_deadzone", 0);
                    RIGHT_STICK_DEADZONE = data.value("right_stick_deadzone", 0);
                }
            } catch (...) {}
        }

        // Apply deadzone in C++
        int tuned_lx = apply_deadzone(raw_lx, LEFT_STICK_DEADZONE / 100.0f);
        int tuned_ly = apply_deadzone(raw_ly, LEFT_STICK_DEADZONE / 100.0f);
        int tuned_rx = apply_deadzone(raw_rx, RIGHT_STICK_DEADZONE / 100.0f);
        int tuned_ry = apply_deadzone(raw_ry, RIGHT_STICK_DEADZONE / 100.0f);
        int tuned_l2 = raw_l2;
        int tuned_r2 = raw_r2;

        // Real transmitter path - runs every loop
        send_to_transmitter(tuned_lx, tuned_ly, tuned_rx, tuned_ry, tuned_l2, tuned_r2);

        // GUI monitoring file - every 20 ms
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            std::ofstream f("/tmp/flight_status.txt");
            if (f) {
                f << "latency_ms:0.00 rate_hz:0 "
                  << "lx:" << raw_lx << " ly:" << raw_ly
                  << " rx:" << raw_rx << " ry:" << raw_ry
                  << " l2:" << raw_l2 << " r2:" << raw_r2 << "\n";
                f.close();
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    if (controller) SDL_GameControllerClose(controller);
    SDL_Quit();
    return 0;
}
