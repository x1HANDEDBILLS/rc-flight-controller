// main.cpp - updated: GUI file written every 20 ms, transmitter path unchanged

#include <SDL2/SDL.h>
#include <SDL2/SDL_gamecontroller.h>
#include <fstream>
#include <iostream>
#include <chrono>
#include <thread>
#include <iomanip>
#include <string>

// Your globals (adjust names if different)
extern SDL_GameController* controller;
extern bool controller_connected;

// Your real functions (fill in)
bool open_controller() { /* your code */ return false; }
void close_controller() { /* your code */ }
int apply_deadzone(int raw, float dead) { return raw; }  // your deadzone
void send_to_transmitter(int lx, int ly, int rx, int ry, int l2, int r2) { /* your transmitter code */ }

int main() {
    if (SDL_Init(SDL_INIT_GAMECONTROLLER) < 0) {
        std::cerr << "SDL_Init failed\n";
        return 1;
    }

    if (!open_controller()) {
        SDL_Quit();
        return 1;
    }

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();

    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
            // your event handling...
        }

        // Read raw controller (your code)
        int raw_lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
        int raw_ly = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
        int raw_rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
        int raw_ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);
        int raw_l2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT);
        int raw_r2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT);

        // Apply deadzone (your code)
        int tuned_lx = apply_deadzone(raw_lx, LEFT_STICK_DEADZONE / 100.0f);
        int tuned_ly = apply_deadzone(raw_ly, LEFT_STICK_DEADZONE / 100.0f);
        int tuned_rx = apply_deadzone(raw_rx, RIGHT_STICK_DEADZONE / 100.0f);
        int tuned_ry = apply_deadzone(raw_ry, RIGHT_STICK_DEADZONE / 100.0f);
        int tuned_l2 = raw_l2;
        int tuned_r2 = raw_r2;

        // Real transmitter send - runs every loop (fast)
        send_to_transmitter(tuned_lx, tuned_ly, tuned_rx, tuned_ry, tuned_l2, tuned_r2);

        // GUI monitoring - every 20 ms (50 Hz)
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            std::ofstream f("/tmp/flight_status.txt");
            if (f) {
                if (controller_connected) {
                    f << "latency_ms:0.00 rate_hz:0 "
                      << "lx:" << raw_lx << " ly:" << raw_ly
                      << " rx:" << raw_rx << " ry:" << raw_ry
                      << " l2:" << raw_l2 << " r2:" << raw_r2 << "\n";
                } else {
                    f << "latency_ms:-1.0 rate_hz:0 controller:disconnected\n";
                }
                f.close();
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    close_controller();
    SDL_Quit();
    return 0;
}
