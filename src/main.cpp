#include <SDL2/SDL.h>
#include <iostream>
#include <chrono>
#include <thread>
#include <iomanip>
#include <string>
#include <fstream>
#include <deque>
#include <numeric>

SDL_GameController* controller = nullptr;
bool controller_connected = false;

void close_controller() {
    if (controller) {
        SDL_GameControllerClose(controller);
        controller = nullptr;
    }
    controller_connected = false;
}

bool open_controller() {
    close_controller();

    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        if (SDL_IsGameController(i)) {
            controller = SDL_GameControllerOpen(i);
            if (controller) {
                std::cout << "[OK] Controller connected: " << SDL_GameControllerName(controller) << "\n";
                controller_connected = true;
                return true;
            }
        }
    }

    std::cout << "[STATUS] No controller connected.\n";
    controller_connected = false;
    return false;
}

int main() {
    std::cout << "PS4/PS5 Flight Controller - Step 5: Raw Inputs + Hotplug + GUI File\n\n";

    if (SDL_Init(SDL_INIT_GAMECONTROLLER) < 0) {
        std::cerr << "[ERROR] SDL_Init failed: " << SDL_GetError() << "\n";
        return 1;
    }

    open_controller();

    std::cout << "Running... Unplug/replug controller to test hotplug\n\n";

    auto last_print = std::chrono::steady_clock::now();
    auto last_write = std::chrono::steady_clock::now();

    std::deque<double> times_us;
    const size_t HISTORY = 200;

    while (true) {
        auto loop_start = std::chrono::steady_clock::now();

        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            switch (e.type) {
                case SDL_CONTROLLERDEVICEADDED:
                    std::cout << "[EVENT] Controller plugged in - opening...\n";
                    open_controller();
                    break;
                case SDL_CONTROLLERDEVICEREMOVED:
                    std::cout << "[EVENT] Controller unplugged!\n";
                    close_controller();
                    break;
            }
        }

        Sint16 lx = 0, ly = 0, rx = 0, ry = 0, l2 = 0, r2 = 0;
        std::string buttons = "none";

        if (controller_connected && controller) {
            lx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX);
            ly = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY);
            rx = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX);
            ry = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY);
            l2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT);
            r2 = SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT);

            buttons = "";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A))            buttons += "Cross ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_B))            buttons += "Circle ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_X))            buttons += "Square ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_Y))            buttons += "Triangle ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_LEFTSHOULDER))  buttons += "L1 ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) buttons += "R1 ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_BACK))          buttons += "Share ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_START))         buttons += "Options ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_GUIDE))         buttons += "PS ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_LEFTSTICK))    buttons += "L3 ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_RIGHTSTICK))   buttons += "R3 ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_UP))       buttons += "D-Up ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_DOWN))     buttons += "D-Down ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_LEFT))     buttons += "D-Left ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_RIGHT))    buttons += "D-Right ";
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_TOUCHPAD))      buttons += "Touchpad ";

            if (buttons.empty()) buttons = "none";
        } else {
            buttons = "DISCONNECTED";
        }

        auto loop_end = std::chrono::steady_clock::now();
        auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(loop_end - loop_start).count();

        times_us.push_back(duration_us);
        if (times_us.size() > HISTORY) times_us.pop_front();

        double total_us = std::accumulate(times_us.begin(), times_us.end(), 0LL);
        double avg_us = times_us.empty() ? 0.0 : total_us / times_us.size();
        double avg_ms = avg_us / 1000.0;
        double hz = (avg_us > 0) ? (1000000.0 / avg_us) : 0.0;

        // Console print every 100 ms
        if (std::chrono::duration<double>(std::chrono::steady_clock::now() - last_print).count() >= 0.1) {
            last_print = std::chrono::steady_clock::now();

            std::cout << "\rAxes: "
                      << std::setw(6) << lx << " "
                      << std::setw(6) << ly << " "
                      << std::setw(6) << rx << " "
                      << std::setw(6) << ry << " "
                      << std::setw(6) << l2 << " "
                      << std::setw(6) << r2
                      << "   Lat:" << std::fixed << std::setprecision(2) << std::setw(6) << avg_ms << " ms "
                      << std::setw(6) << static_cast<int>(std::min(hz, 99999.0)) << " Hz"
                      << "   | " << buttons
                      << "                     " << std::flush;
        }

        // Write to file every 200 ms
        if (std::chrono::duration<double>(std::chrono::steady_clock::now() - last_write).count() >= 0.2) {
            last_write = std::chrono::steady_clock::now();

            std::ofstream f("/tmp/flight_status.txt");
            if (f) {
                if (controller_connected) {
                    f << "latency_ms:" << std::fixed << std::setprecision(2) << avg_ms
                      << " rate_hz:" << std::setprecision(0) << static_cast<int>(hz)
                      << " lx:" << lx << " ly:" << ly
                      << " rx:" << rx << " ry:" << ry
                      << " l2:" << l2 << " r2:" << r2 << "\n";
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
