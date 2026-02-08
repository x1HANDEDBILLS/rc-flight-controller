// controller_manager.cpp

#include "controller_manager.h"
#include <iostream>

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
