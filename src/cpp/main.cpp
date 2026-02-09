// main.cpp - Integrated Flight Controller Engine
#include <SDL2/SDL.h>
#include <SDL2/SDL_gamecontroller.h>
#include <fstream>
#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <nlohmann/json.hpp>

// === PROJECT HEADERS ===
#include "input_tuning.h"
#include "InputMapper.h"
#include "InputMixer.h"
#include "crsf_sender.h"

// === GLOBAL OBJECTS ===
CRSFSender crsf_sender;
InputMapper mapper;
InputMixer mixer;
SDL_GameController* controller = nullptr;
bool controller_connected = false;

int16_t prev_lx = 0, prev_ly = 0, prev_rx = 0, prev_ry = 0;

float g_deadzone = 0.05f;
float g_sens     = 1.0f;
float g_alpha    = 0.2f;

// === CONFIGURATION LOADER ===
void load_system_config() {
    std::string path = "/home/pi4/rc-flight-controller/src/config/inputtuning.json";
    std::ifstream file(path);
    if (!file.is_open()) return;

    try {
        nlohmann::json j;
        file >> j;
        if (j.contains("tuning")) {
            g_deadzone = j["tuning"].value("deadzone", 0.05f);
            g_sens     = j["tuning"].value("sensitivity", 1.0f);
            g_alpha    = j["tuning"].value("lowpass_alpha", 0.2f);
        }
        mapper.load_from_json(path);
    } catch (const std::exception& e) {
        std::cerr << "Config Loader Error: " << e.what() << std::endl;
    }
}

// === CONTROLLER MANAGEMENT ===
bool open_controller() {
    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        if (SDL_IsGameController(i)) {
            controller = SDL_GameControllerOpen(i);
            if (controller) {
                controller_connected = true;
                return true;
            }
        }
    }
    return false;
}

void close_controller() {
    if (controller) SDL_GameControllerClose(controller);
    controller_connected = false;
}

// === MAIN ENGINE ===
int main(int argc, char* argv[]) {
    if (SDL_Init(SDL_INIT_GAMECONTROLLER) < 0) return 1;
    crsf_sender.begin();
    open_controller();
    load_system_config();

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();
    auto loop_start_time = std::chrono::steady_clock::now();
    int frame_count = 0;
    float live_hz = 0.0f;

    std::vector<int> raw_signals(23, 0); 
    LogicalSignals mapped_output;

    while (running) {
        auto frame_start = std::chrono::steady_clock::now();

        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
            if (event.type == SDL_CONTROLLERDEVICEADDED && !controller_connected) open_controller();
        }

        if (controller && !SDL_GameControllerGetAttached(controller)) close_controller();

        // --- STAGE 1: RAW GATHERING (TRUE HARDWARE STATE) ---
        if (controller) {
            // 1. Get Literal Hardware Axis Values
            int16_t hw_lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
            int16_t hw_ly = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
            int16_t hw_rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
            int16_t hw_ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);

            // 2. Save the DIRTY/RAW data so GUI can show jitter/drift
            raw_signals[0] = hw_lx;
            raw_signals[1] = hw_ly;
            raw_signals[2] = hw_rx;
            raw_signals[3] = hw_ry;

            // 3. Triggers & Buttons (Raw State)
            raw_signals[4] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT);
            raw_signals[5] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT);
            for (int i = 0; i < 15; i++) {
                raw_signals[6 + i] = SDL_GameControllerGetButton(controller, (SDL_GameControllerButton)i) ? 32767 : -32768;
            }
        } else {
            std::fill(raw_signals.begin(), raw_signals.end(), 0);
        }

        // --- STAGE 2: MAPPING & ROUTING ---
        mapper.update(raw_signals, mapped_output);

        // --- STAGE 2.5: APPLY TUNING TO LOGICAL OUTPUTS ---
        // Roll, Pitch, Yaw, Throttle = indices 0–3 in the channels array
        mapped_output.channels[0] = apply_tuning(mapped_output.channels[0], g_deadzone, 0.0f, g_sens, false, g_alpha, prev_lx);
        mapped_output.channels[1] = apply_tuning(mapped_output.channels[1], g_deadzone, 0.0f, g_sens, false, g_alpha, prev_ly);
        mapped_output.channels[2] = apply_tuning(mapped_output.channels[2], g_deadzone, 0.0f, g_sens, false, g_alpha, prev_rx);
        mapped_output.channels[3] = apply_tuning(mapped_output.channels[3], g_deadzone, 0.0f, g_sens, false, g_alpha, prev_ry);

        // --- STAGE 3: MIXING ---
        mixer.process(mapped_output);

        // --- STAGE 4: HARDWARE SEND ---
        crsf_sender.send_channels(mixer.final_channels);

        // --- STAGE 5: PERFORMANCE & GUI LOGGING ---
        auto now = std::chrono::steady_clock::now();
        auto frame_end = std::chrono::steady_clock::now();
        float live_latency = std::chrono::duration<float, std::milli>(frame_end - frame_start).count();

        frame_count++;
        double total_elapsed = std::chrono::duration<double>(frame_end - loop_start_time).count();
        if (total_elapsed >= 1.0) {
            live_hz = (float)(frame_count / total_elapsed);
            frame_count = 0;
            loop_start_time = frame_end;
        }

        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            FILE* f = fopen("/tmp/flight_status.txt", "w");
            if (f) {
                fprintf(f, "latency_ms:%.2f rate_hz:%.1f connected:%d", 
                        live_latency, live_hz, controller_connected ? 1 : 0);
                
                // Log all 16 final channels (post-mixing)
                for (int i = 0; i < 16; i++) {
                    fprintf(f, " ch%d:%d", i + 1, mixer.final_channels[i]);
                }

                // Raw hardware values (with possible jitter/drift) for GUI debug row
                fprintf(f, " raw_lx:%d raw_ly:%d raw_rx:%d raw_ry:%d", 
                        raw_signals[0], raw_signals[1], raw_signals[2], raw_signals[3]);
                
                fprintf(f, "\n");
                fclose(f);
            }
        }

        std::this_thread::sleep_for(std::chrono::microseconds(950));
    }

    crsf_sender.close_port();
    close_controller();
    SDL_Quit();
    return 0;
}