#ifndef CONTROLLER_MANAGER_H
#define CONTROLLER_MANAGER_H

#include <SDL2/SDL.h>
#include <iostream>

// 'inline' allowed here for global variables in C++17+ 
// This prevents "multiple definition" errors when included in main.cpp
inline SDL_GameController* controller = nullptr;
inline bool controller_connected = false;

inline void close_controller() {
    if (controller) {
        SDL_GameControllerClose(controller);
        controller = nullptr;
    }
    controller_connected = false;
}

inline bool open_controller() {
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

#endif