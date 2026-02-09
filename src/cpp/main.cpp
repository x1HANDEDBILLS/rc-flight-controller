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

// Socket headers for high-speed tuning
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>

#include "input_tuning.h"
#include "InputMapper.h"
#include "InputMixer.h"
#include "crsf_sender.h"

CRSFSender crsf_sender;
InputMapper mapper;
InputMixer mixer;
SDL_GameController* controller = nullptr;
bool controller_connected = false;

// Filter memory
int16_t prev_lx = 0, prev_ly = 0;
int16_t prev_rx = 0, prev_ry = 0;

// Live global variables
float g_left_dz  = 0.05f;
float g_right_dz = 0.05f;
float g_sens     = 1.0f;
float g_alpha    = 0.2f;

// ---------------------------------------------------------
// Socket Listener Thread: Catches updates from Python
// ---------------------------------------------------------
void socket_listener() {
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in servaddr;
    memset(&servaddr, 0, sizeof(servaddr));
    
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = INADDR_ANY;
    servaddr.sin_port = htons(5005); 
    
    if (bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0) {
        std::cerr << "[SOCKET] Bind failed" << std::endl;
        return;
    }

    char buffer[1024];
    while (true) {
        int n = recvfrom(sockfd, buffer, 1024, 0, NULL, NULL);
        if (n > 0) {
            buffer[n] = '\0';
            std::string msg(buffer);
            try {
                if (msg.find("L_DZ:") == 0) {
                    g_left_dz = std::stof(msg.substr(5));
                } else if (msg.find("R_DZ:") == 0) {
                    g_right_dz = std::stof(msg.substr(5));
                }
            } catch (...) {}
        }
    }
}

void load_system_config() {
    std::string path = "/home/pi4/rc-flight-controller/src/config/inputtuning.json";
    std::ifstream file(path);
    if (!file.is_open()) return;
    try {
        nlohmann::json j;
        file >> j;
        if (j.contains("tuning")) {
            g_left_dz  = j["tuning"].value("left_deadzone", 0.05f);
            g_right_dz = j["tuning"].value("right_deadzone", 0.05f);
            g_sens     = j["tuning"].value("sensitivity", 1.0f);
            g_alpha    = j["tuning"].value("lowpass_alpha", 0.2f);
            std::cout << "[CONFIG] Startup Load Success." << std::endl;
        }
        mapper.load_from_json(path);
    } catch (...) {}
}

int main(int argc, char* argv[]) {
    if (SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER) < 0) return 1;
    
    crsf_sender.begin();
    load_system_config();

    std::thread(socket_listener).detach();

    // Initial check for controller
    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        if (SDL_IsGameController(i)) {
            controller = SDL_GameControllerOpen(i);
            if (controller) {
                controller_connected = true;
                break;
            }
        }
    }

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();
    std::vector<int> raw_signals(23, 0); 
    LogicalSignals mapped_output;

    while (running) {
        auto frame_start = std::chrono::steady_clock::now();
        
        // --- UPDATED EVENT HANDLING FOR HOT-PLUGGING ---
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;

            if (event.type == SDL_CONTROLLERDEVICEREMOVED) {
                if (controller) {
                    SDL_GameControllerClose(controller);
                    controller = nullptr;
                    controller_connected = false;
                    std::cout << "[HARDWARE] Controller Disconnected" << std::endl;
                }
            }
            if (event.type == SDL_CONTROLLERDEVICEADDED) {
                if (!controller) {
                    controller = SDL_GameControllerOpen(event.cdevice.which);
                    if (controller) {
                        controller_connected = true;
                        std::cout << "[HARDWARE] Controller Reconnected!" << std::endl;
                    }
                }
            }
        }

        // Only read axes if we have a valid controller handle
        if (controller) {
            raw_signals[0] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
            raw_signals[1] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
            raw_signals[2] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
            raw_signals[3] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);
            for (int i = 0; i < 15; i++) {
                raw_signals[6 + i] = SDL_GameControllerGetButton(controller, (SDL_GameControllerButton)i) ? 32767 : -32768;
            }
        } else {
            // Reset signals to neutral if disconnected to prevent "runaway" drone
            std::fill(raw_signals.begin(), raw_signals.end(), 0);
        }

        mapper.update(raw_signals, mapped_output);

        apply_tuning(mapped_output.channels[0], mapped_output.channels[1], 
                     g_left_dz, g_sens, g_alpha, prev_lx, prev_ly);
        
        apply_tuning(mapped_output.channels[2], mapped_output.channels[3], 
                     g_right_dz, g_sens, g_alpha, prev_rx, prev_ry);

        mixer.process(mapped_output);
        crsf_sender.send_channels(mixer.final_channels);

        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            FILE* f = fopen("/tmp/flight_status.txt", "w");
            if (f) {
                fprintf(f, "latency_ms:%.2f rate_hz:800.0 connected:%d", 
                        std::chrono::duration<float, std::milli>(now - frame_start).count(), controller_connected ? 1 : 0);
                
                for (int i = 0; i < 16; i++) {
                    float norm = (mixer.final_channels[i] + 32768) / 65535.0f;
                    int crsf_val = std::clamp((int)(norm * 1639.0f + 172.0f), 172, 1811);
                    fprintf(f, " ch%d:%d", i + 1, crsf_val);
                }
                fprintf(f, " raw_lx:%d raw_ly:%d raw_rx:%d raw_ry:%d\n", 
                        raw_signals[0], raw_signals[1], raw_signals[2], raw_signals[3]);
                fclose(f);
            }
        }
        std::this_thread::sleep_for(std::chrono::microseconds(950));
    }
    
    if (controller) SDL_GameControllerClose(controller);
    SDL_Quit();
    return 0;
}