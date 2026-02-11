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
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cstring> 
#include <mutex>
#include <csignal> 
#include <atomic> 

#include "input_tuning.h"
#include "InputMapper.h"
#include "InputMixer.h"
#include "crsf_sender.h"
#include "crsf_parser.h"

const std::string MAPPER_PATH = "/home/pi4/rc-flight-controller/src/config/inputmapper.json";
const std::string TUNING_PATH = "/home/pi4/rc-flight-controller/src/config/inputtuning.json";

// --- GLOBAL OBJECTS ---
CRSFSender crsf_sender;
InputMapper mapper;
InputMixer mixer;
SDL_GameController* controller = nullptr;
bool controller_connected = false;

// --- MUTEX DEFINITIONS ---
std::mutex mapper_mutex; 
std::mutex console_mutex; 

// --- GLOBAL ATOMIC FOR GRACEFUL SHUTDOWN ---
std::atomic<bool> g_running(true);

// --- STATE VARIABLES (Atomic for thread safety) ---
std::atomic<float> g_l_dz{0.05f};
std::atomic<float> g_r_dz{0.05f};
std::atomic<float> g_sens{1.0f};
std::atomic<float> g_expo{0.0f};
std::atomic<int>   g_curve{0};
std::atomic<float> g_smooth{0.2f};
std::atomic<bool>  g_cine_on{false};
std::atomic<float> g_cine_spd{8.0f};
std::atomic<float> g_cine_acc{3.5f};

// Physics Persistence
int16_t prev_vals[6] = {0};
float cine_vel[6] = {0.0f};
float cine_pos[6] = {0.0f};

// Signal Handler
void signal_handler(int signal) {
    g_running = false;
}

std::vector<std::string> split_string(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) tokens.push_back(token);
    return tokens;
}

void socket_listener() {
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in servaddr;
    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = INADDR_ANY;
    servaddr.sin_port = htons(5005); 
    bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr));

    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 500000; // 0.5s timeout
    setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

    char buffer[2048];
    while (g_running) {
        int n = recvfrom(sockfd, buffer, 2048, 0, NULL, NULL);
        if (n > 0) {
            buffer[n] = '\0';
            std::string msg(buffer);
            try {
                if (msg.find("SET_MAP|") == 0) {
                    std::vector<std::string> sections = split_string(msg, '|');
                    if (sections.size() >= 3) {
                        std::lock_guard<std::mutex> lock(mapper_mutex);
                        mapper.set_from_packet(split_string(sections[1], ','), split_string(sections[2], ','));
                    }
                } 
                else if (msg.find("L_DZ:") == 0)      g_l_dz = std::stof(msg.substr(5));
                else if (msg.find("R_DZ:") == 0)      g_r_dz = std::stof(msg.substr(5));
                else if (msg.find("RATE:") == 0)      g_sens = std::stof(msg.substr(5));
                else if (msg.find("EXPO:") == 0)      g_expo = std::stof(msg.substr(5));
                else if (msg.find("CURVE:") == 0)     g_curve = std::stoi(msg.substr(6));
                else if (msg.find("SMOOTH:") == 0)    g_smooth = std::stof(msg.substr(7));
                else if (msg.find("CINE_ON:") == 0)   g_cine_on = (std::stoi(msg.substr(8)) == 1);
                else if (msg.find("CINE_SPD:") == 0)  g_cine_spd = std::stof(msg.substr(9));
                else if (msg.find("CINE_ACC:") == 0)  g_cine_acc = std::stof(msg.substr(9));
            } catch (...) {}
        }
    }
    close(sockfd);
}

void load_system_config() {
    std::ifstream t_file(TUNING_PATH);
    if (t_file.is_open()) {
        try {
            nlohmann::json j;
            t_file >> j;
            if (j.contains("tuning")) {
                auto t = j["tuning"];
                g_l_dz = t.value("left_deadzone", 0.5f) / 10.0f;
                g_r_dz = t.value("right_deadzone", 0.5f) / 10.0f;
                g_sens = t.value("global_rate", 1.0f);
                g_expo = t.value("expo", 0.0f);
                g_curve = t.value("curve_type", 0);
                g_smooth = t.value("smoothing", 0.2f);
                g_cine_on = t.value("cine_on", false);
                g_cine_spd = t.value("cine_speed", 8.0f);
                g_cine_acc = t.value("cine_accel", 3.5f);
                std::cout << "Config Loaded. DZs: " << g_l_dz << " / " << g_r_dz << std::endl;
            }
        } catch (...) {}
    }
    std::lock_guard<std::mutex> lock(mapper_mutex);
    mapper.load_from_json(MAPPER_PATH);
}

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    int baud_rate = 420000; 
    if (argc > 1) {
        try {
            baud_rate = std::stoi(argv[1]);
        } catch (...) {
            baud_rate = 420000;
        }
    }

    if (SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER) < 0) return 1;
    
    if (!crsf_sender.begin(baud_rate)) {
        std::cerr << "CRSF Error: Failed to open port." << std::endl;
        return 1;
    }

    load_system_config();
    std::thread listener_thread(socket_listener);

    std::vector<int> raw_signals(23, -32768); 
    std::vector<int> true_raw(23, -32768); 
    LogicalSignals mapped_output;
    auto last_gui_write = std::chrono::steady_clock::now();

    std::cout << "Engine Started at 1000Hz (Baud: " << baud_rate << ")." << std::endl;

    while (g_running) {
        auto frame_start = std::chrono::steady_clock::now();
        
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
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
            true_raw = raw_signals; 

            for (int i = 0; i < 6; i++) {
                float dz = (i < 2) ? g_l_dz.load() : (i < 4 ? g_r_dz.load() : 0.05f);
                apply_tuning(raw_signals[i], dz, g_sens.load(), g_smooth.load(), 
                               g_curve.load(), g_expo.load(), g_cine_on.load(), 
                               g_cine_spd.load(), g_cine_acc.load(),
                               prev_vals[i], cine_vel[i], cine_pos[i], 0.001f);
            }
        } else {
            std::fill(raw_signals.begin(), raw_signals.end(), -32768);
            std::fill(true_raw.begin(), true_raw.end(), -32768);
        }

        {
            std::lock_guard<std::mutex> lock(mapper_mutex);
            mapper.update(raw_signals, mapped_output);
        }
        mixer.process(mapped_output);
        crsf_sender.send_channels(mixer.final_channels);

        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_gui_write).count() >= 0.02) {
            last_gui_write = now;
            FILE* f = fopen("/tmp/flight_status.txt", "w");
            if (f) {
                fprintf(f, "latency_ms:%.2f rate_hz:1000.0 connected:%d", 
                        std::chrono::duration<float, std::milli>(now - frame_start).count(), controller_connected);
                for (int i = 0; i < 16; i++) {
                    float norm = (mixer.final_channels[i] + 32768) / 65535.0f;
                    int crsf_val = std::clamp((int)(norm * 1639.0f + 172.0f), 172, 1811);
                    fprintf(f, " ch%d:%d", i + 1, crsf_val);
                }
                for (int i = 0; i < 23; i++) fprintf(f, " tunedid%d:%d", i, raw_signals[i]);
                for (int i = 0; i < 23; i++) fprintf(f, " rawid%d:%d", i, true_raw[i]);
                fprintf(f, "\n");
                fclose(f);
            }
        }

        // Precision timing to ensure 1000Hz loop
        auto frame_end = std::chrono::steady_clock::now();
        auto frame_duration = std::chrono::duration_cast<std::chrono::microseconds>(frame_end - frame_start);
        if (frame_duration < std::chrono::microseconds(1000)) {
            std::this_thread::sleep_for(std::chrono::microseconds(1000) - frame_duration);
        }
    }

    std::cout << "Shutting down gracefully..." << std::endl;
    crsf_sender.close_port();
    if (listener_thread.joinable()) listener_thread.join();
    if (controller) SDL_GameControllerClose(controller);
    SDL_Quit();
    
    return 0;
}
