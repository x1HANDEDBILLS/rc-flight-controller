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

// Socket headers for real-time UDP tuning from Python
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cstring> 

// Project Headers
#include "input_tuning.h"
#include "InputMapper.h"
#include "InputMixer.h"
#include "crsf_sender.h"

// Constants
const std::string MAPPER_PATH = "/home/pi4/rc-flight-controller/src/config/inputmapper.json";
const std::string TUNING_PATH = "/home/pi4/rc-flight-controller/src/config/inputtuning.json";

// Global Objects
CRSFSender crsf_sender;
InputMapper mapper;
InputMixer mixer;
SDL_GameController* controller = nullptr;
bool controller_connected = false;

// Filter memory for Smoothing (required for the lowpass math)
int16_t prev_lx = 0, prev_ly = 0, prev_rx = 0, prev_ry = 0;

// --- LIVE TUNING GLOBALS (Modified via UDP by Python UI) ---
float g_left_dz      = 0.5f;
float g_right_dz     = 0.5f;
float g_sens         = 1.0f;  // "Global Rate"
float g_alpha        = 0.2f;  // "Smoothing"
int   g_curve_type   = 0;     // 0:Linear, 1:Std, 2:Dyn, 3:Extreme
float g_expo         = 0.0f;  // "Stick Expo"
bool  g_cine_on      = false; // "Cinematic Toggle"
float g_cine_val     = 1.0f;  // "Cinematic Intensity"

// ---------------------------------------------------------
// Socket Listener Thread: Catches updates from Python UI
// ---------------------------------------------------------
void socket_listener() {
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in servaddr;
    memset(&servaddr, 0, sizeof(servaddr));
    
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = INADDR_ANY;
    servaddr.sin_port = htons(5005); 
    
    if (bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0) {
        std::cerr << "[SOCKET] Bind failed on port 5005" << std::endl;
        return;
    }

    char buffer[2048];
    while (true) {
        int n = recvfrom(sockfd, buffer, 2048, 0, NULL, NULL);
        if (n > 0) {
            buffer[n] = '\0';
            std::string msg(buffer);
            try {
                // 1. Full Mapping Update Trigger
                if (msg.find("SET_MAP|") == 0) {
                    mapper.load_from_json(MAPPER_PATH);
                } 
                // 2. Individual Live Tuning Updates (Standardized keys from Python)
                else if (msg.find("L_DZ:") == 0)      g_left_dz = std::stof(msg.substr(5));
                else if (msg.find("R_DZ:") == 0)      g_right_dz = std::stof(msg.substr(5));
                else if (msg.find("RATE:") == 0)      g_sens = std::stof(msg.substr(5));
                else if (msg.find("SMOOTH:") == 0)    g_alpha = std::stof(msg.substr(7));
                else if (msg.find("CURVE:") == 0)     g_curve_type = std::stoi(msg.substr(6));
                else if (msg.find("EXPO:") == 0)      g_expo = std::stof(msg.substr(5));
                else if (msg.find("CINE_ON:") == 0)   g_cine_on = (std::stoi(msg.substr(8)) == 1);
                else if (msg.find("CINE_VAL:") == 0)  g_cine_val = std::stof(msg.substr(9));
                
                // Sensitivity key support (if present in JSON)
                else if (msg.find("SENS:") == 0)      g_sens = std::stof(msg.substr(5));
            } catch (...) {
                // Silently ignore malformed UDP packets
            }
        }
    }
}

// ---------------------------------------------------------
// Startup: Load saved JSON configurations
// ---------------------------------------------------------
void load_system_config() {
    std::ifstream t_file(TUNING_PATH);
    if (t_file.is_open()) {
        try {
            nlohmann::json j;
            t_file >> j;
            if (j.contains("tuning")) {
                auto t = j["tuning"];
                g_left_dz    = t.value("left_deadzone", 0.5f);
                g_right_dz   = t.value("right_deadzone", 0.5f);
                g_sens       = t.value("global_rate", 1.0f);
                g_alpha      = t.value("smoothing", 0.2f);
                g_curve_type = t.value("curve_type", 0);
                g_expo       = t.value("expo", 0.0f);
                g_cine_on    = t.value("cine_on", false);
                g_cine_val   = t.value("cine_intensity", 1.0f);
                std::cout << "[CONFIG] Input Tuning parameters loaded from JSON." << std::endl;
            }
        } catch (...) {
            std::cerr << "[CONFIG] Error parsing Tuning JSON." << std::endl;
        }
    }
    mapper.load_from_json(MAPPER_PATH);
}

// ---------------------------------------------------------
// Main Execution Loop (1000Hz)
// ---------------------------------------------------------
int main(int argc, char* argv[]) {
    if (SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER) < 0) {
        std::cerr << "SDL Init Failed" << std::endl;
        return 1;
    }
    
    crsf_sender.begin(); // Setup Serial/SPI for Transmitter
    load_system_config();

    // Start background listener for GUI changes
    std::thread(socket_listener).detach();

    // Initial Controller Scan
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
    std::vector<int> raw_signals(23, -32768); 
    LogicalSignals mapped_output;

    while (running) {
        auto frame_start = std::chrono::steady_clock::now();
        
        // Handle SDL Events (Plugin/Unplug)
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
            if (event.type == SDL_CONTROLLERDEVICEREMOVED) {
                if (controller) {
                    SDL_GameControllerClose(controller);
                    controller = nullptr; controller_connected = false;
                }
            }
            if (event.type == SDL_CONTROLLERDEVICEADDED) {
                if (!controller) {
                    controller = SDL_GameControllerOpen(event.cdevice.which);
                    if (controller) controller_connected = true;
                }
            }
        }

        // Capture Hardware State
        if (controller) {
            raw_signals[0] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
            raw_signals[1] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
            raw_signals[2] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
            raw_signals[3] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);
            raw_signals[4] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT);
            raw_signals[5] = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT);
            for (int i = 0; i < 15; i++) {
                raw_signals[6+i] = SDL_GameControllerGetButton(controller, (SDL_GameControllerButton)i) ? 32767 : -32768;
            }
            raw_signals[22] = -32768; // Always-Off source
        } else {
            std::fill(raw_signals.begin(), raw_signals.end(), -32768);
        }

        // --- FLIGHT PROCESSING PIPELINE ---
        
        // 1. ROUTING: Map Raw IDs (0-22) to Logical Channels (Pitch/Roll/etc.)
        mapper.update(raw_signals, mapped_output);

        // 2. TUNING: Apply Deadzones, Response Curves, Global Rates, and Cinematic Modes
        // Processing Left Stick
        apply_tuning(mapped_output.channels[0], g_left_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_lx);
        apply_tuning(mapped_output.channels[1], g_left_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_ly);
        
        // Processing Right Stick
        apply_tuning(mapped_output.channels[2], g_right_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_rx);
        apply_tuning(mapped_output.channels[3], g_right_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_ry);

        // 3. MIXING: Scale and clip to final radio output ranges
        mixer.process(mapped_output);

        // 4. TRANSMISSION: Send over CRSF Protocol to the radio module
        crsf_sender.send_channels(mixer.final_channels);

        // --- TELEMETRY EXPORT (50Hz) ---
        // Writes to /tmp/ for the Python UI to read and display live bars
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            FILE* f = fopen("/tmp/flight_status.txt", "w");
            if (f) {
                fprintf(f, "latency_ms:%.2f rate_hz:800.0 connected:%d", 
                        std::chrono::duration<float, std::milli>(now - frame_start).count(), 
                        controller_connected ? 1 : 0);
                
                // CRSF Protocol values
                for (int i = 0; i < 16; i++) {
                    float norm = (mixer.final_channels[i] + 32768) / 65535.0f;
                    int crsf_val = std::clamp((int)(norm * 1639.0f + 172.0f), 172, 1811);
                    fprintf(f, " ch%d:%d", i + 1, crsf_val);
                }
                // Raw ID signals for UI feedback
                for (int i = 0; i < (int)raw_signals.size(); i++) {
                    fprintf(f, " rawid%d:%d", i, raw_signals[i]);
                }
                fprintf(f, "\n");
                fclose(f);
            }
        }
        
        // Target 1kHz (1000 loop iterations per second)
        std::this_thread::sleep_for(std::chrono::microseconds(950));
    }
    
    if (controller) SDL_GameControllerClose(controller);
    SDL_Quit();
    return 0;
}