// controller_manager.h

#pragma once

#include <SDL2/SDL.h>

extern SDL_GameController* controller;
extern bool controller_connected;

void close_controller();
bool open_controller();
