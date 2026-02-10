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
#include <sstream>
#include <nlohmann/json.hpp>

// Socket headers for real-time UDP tuning from Python
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cstring> 
#include <mutex>

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
std::mutex mapper_mutex; // Safety lock for live mapping updates

// Filter memory for Smoothing
int16_t prev_lx = 0, prev_ly = 0, prev_rx = 0, prev_ry = 0;

// --- LIVE TUNING GLOBALS ---
float g_left_dz     = 0.5f;
float g_right_dz    = 0.5f;
float g_sens        = 1.0f; 
float g_alpha       = 0.2f; 
int   g_curve_type  = 0;    
float g_expo        = 0.0f; 
bool  g_cine_on     = false;
float g_cine_val    = 1.0f; 

// --- HELPER FUNCTIONS ---
std::vector<std::string> split_string(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        tokens.push_back(token);
    }
    return tokens;
}

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
                // 1. FULL MAPPING & SPLIT-MIXER SYNC
                if (msg.find("SET_MAP|") == 0) {
                    std::vector<std::string> sections = split_string(msg, '|');
                    if (sections.size() >= 3) {
                        std::vector<std::string> map_vals = split_string(sections[1], ',');
                        std::vector<std::string> split_vals = split_string(sections[2], ',');
                        
                        // LOCK: Ensure the main loop isn't mid-calculation
                        std::lock_guard<std::mutex> lock(mapper_mutex);
                        mapper.set_from_packet(map_vals, split_vals);
                        
                        std::cout << "[SOCKET] Mapping & Split-Mixer Synced" << std::endl;
                    }
                } 
                // 2. INDIVIDUAL LIVE TUNING UPDATES
                else if (msg.find("L_DZ:") == 0)      g_left_dz = std::stof(msg.substr(5));
                else if (msg.find("R_DZ:") == 0)      g_right_dz = std::stof(msg.substr(5));
                else if (msg.find("RATE:") == 0)      g_sens = std::stof(msg.substr(5));
                else if (msg.find("SMOOTH:") == 0)    g_alpha = std::stof(msg.substr(7));
                else if (msg.find("CURVE:") == 0)     g_curve_type = std::stoi(msg.substr(6));
                else if (msg.find("EXPO:") == 0)      g_expo = std::stof(msg.substr(5));
                else if (msg.find("CINE_ON:") == 0)   g_cine_on = (std::stoi(msg.substr(8)) == 1);
                else if (msg.find("CINE_VAL:") == 0)  g_cine_val = std::stof(msg.substr(9));
                else if (msg.find("SENS:") == 0)      g_sens = std::stof(msg.substr(5));
            } catch (...) {
                // Protect against malformed UDP strings
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
                std::cout << "[CONFIG] Input Tuning parameters loaded." << std::endl;
            }
        } catch (...) {
            std::cerr << "[CONFIG] Error parsing Tuning JSON." << std::endl;
        }
    }
    
    // Safety lock during initial file load
    std::lock_guard<std::mutex> lock(mapper_mutex);
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
    
    crsf_sender.begin(); 
    load_system_config();

    // Start background listener thread
    std::thread(socket_listener).detach();

    bool running = true;
    auto last_gui_write = std::chrono::steady_clock::now();
    
    std::vector<int> raw_signals(23, -32768); 
    std::vector<int> true_raw(23, -32768); 
    LogicalSignals mapped_output;

    

    while (running) {
        auto frame_start = std::chrono::steady_clock::now();
        
        // Handle SDL Events
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) running = false;
            if (event.type == SDL_CONTROLLERDEVICEADDED || event.type == SDL_CONTROLLERDEVICEREMOVED) {
                if (controller) SDL_GameControllerClose(controller);
                controller = nullptr; controller_connected = false;
                for (int i = 0; i < SDL_NumJoysticks(); ++i) {
                    if (SDL_IsGameController(i)) {
                        controller = SDL_GameControllerOpen(i);
                        if (controller) { controller_connected = true; break; }
                    }
                }
            }
        }

        // --- ENTRANCE: CAPTURE HARDWARE ---
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
            raw_signals[22] = -32768; 
            true_raw = raw_signals; 
        } else {
            std::fill(raw_signals.begin(), raw_signals.end(), -32768);
            std::fill(true_raw.begin(), true_raw.end(), -32768);
        }

        // --- STAGE 1: INPUT TUNING (Cleaning) ---
        apply_tuning(raw_signals[0], g_left_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_lx);
        apply_tuning(raw_signals[1], g_left_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_ly);
        apply_tuning(raw_signals[2], g_right_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_rx);
        apply_tuning(raw_signals[3], g_right_dz, g_sens, g_alpha, g_curve_type, g_expo, g_cine_on, g_cine_val, prev_ry);

        // --- STAGE 2: INPUT MAPPER (Routing) ---
        {
            // Protect against concurrent writes from socket_listener thread
            std::lock_guard<std::mutex> lock(mapper_mutex);
            mapper.update(raw_signals, mapped_output);
        }

        // --- STAGE 3: MIXER (Scaling & Safety) ---
        mixer.process(mapped_output);

        // --- STAGE 4: TRANSMISSION (Wire) ---
        crsf_sender.send_channels(mixer.final_channels);

        // --- TELEMETRY EXPORT (50Hz) ---
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            FILE* f = fopen("/tmp/flight_status.txt", "w");
            if (f) {
                fprintf(f, "latency_ms:%.2f rate_hz:1000.0 connected:%d", 
                        std::chrono::duration<float, std::milli>(now - frame_start).count(), 
                        controller_connected ? 1 : 0);
                
                for (int i = 0; i < 16; i++) {
                    float norm = (mixer.final_channels[i] + 32768) / 65535.0f;
                    int crsf_val = std::clamp((int)(norm * 1639.0f + 172.0f), 172, 1811);
                    fprintf(f, " ch%d:%d", i + 1, crsf_val);
                }
                for (int i = 0; i < (int)raw_signals.size(); i++) {
                    fprintf(f, " tunedid%d:%d", i, raw_signals[i]);
                }
                for (int i = 0; i < (int)true_raw.size(); i++) {
                    fprintf(f, " rawid%d:%d", i, true_raw[i]);
                }
                fprintf(f, "\n");
                fclose(f);
            }
        }
        
        // Ensure 1ms timing
        std::this_thread::sleep_for(std::chrono::microseconds(950));
    }
    
    if (controller) SDL_GameControllerClose(controller);
    SDL_Quit();
    return 0;
}