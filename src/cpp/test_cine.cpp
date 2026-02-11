#include <SDL2/SDL.h>
#include <iostream>
#include <cmath>
#include <algorithm>
#include <vector>

const float deadzone_radius = 0.10f; 
float tune_speed = 8.0f;    
float tune_agility = 3.5f;  

struct Point { float x, y; };

void draw_circle(SDL_Renderer* renderer, int centerX, int centerY, int radius) {
    for (int w = 0; w < radius * 2; w++) {
        for (int h = 0; h < radius * 2; h++) {
            int dx = radius - w, dy = radius - h;
            if ((dx*dx + dy*dy) <= (radius * radius)) SDL_RenderDrawPoint(renderer, centerX + dx, centerY + dy);
        }
    }
}

struct MasterCineEngine {
    float x = 0.0f, y = 0.0f;
    float vx = 0.0f, vy = 0.0f;
    std::vector<Point> trail;

    void update(float rawX, float rawY, float dt) {
        float raw_mag = std::sqrt(rawX * rawX + rawY * rawY);
        float tx = 0, ty = 0;

        if (raw_mag > deadzone_radius) {
            float scale = (raw_mag - deadzone_radius) / (1.0f - deadzone_radius);
            tx = (rawX / raw_mag) * std::min(1.0f, scale);
            ty = (rawY / raw_mag) * std::min(1.0f, scale);
        }

        // 1. Target Vector
        float dirX = tx - x;
        float dirY = ty - y;
        float dist = std::sqrt(dirX * dirX + dirY * dirY);
        
        // 2. Predictive Braking Logic
        // Calculate the maximum speed we can have and still stop in time
        float accel_rate = tune_agility * 5.0f; 
        float speed_limit = tune_speed * 0.5f;
        
        // Physics formula: v^2 = 2 * a * d  -> v = sqrt(2 * accel * distance)
        // This calculates the "Perfect Speed" for the current distance
        float max_safe_speed = std::sqrt(2.0f * accel_rate * dist);
        float current_target_speed = std::min(speed_limit, max_safe_speed);

        float desired_vx = 0, desired_vy = 0;
        if (dist > 0.0001f) {
            desired_vx = (dirX / dist) * current_target_speed;
            desired_vy = (dirY / dist) * current_target_speed;
        }

        // 3. Constant Acceleration toward Desired Velocity
        float diffX = desired_vx - vx;
        float diffY = desired_vy - vy;
        float diffMag = std::sqrt(diffX * diffX + diffY * diffY);

        if (diffMag > 0.001f) {
            float step = accel_rate * dt;
            if (step > diffMag) step = diffMag; 
            vx += (diffX / diffMag) * step;
            vy += (diffY / diffMag) * step;
        }

        // 4. Update Position
        x += vx * dt;
        y += vy * dt;

        // 5. Hard Snap to prevent micro-drifting
        if (dist < 0.002f && std::abs(vx) < 0.01f && std::abs(vy) < 0.01f) {
            x = tx; y = ty; vx = 0; vy = 0;
        }

        // Boundary Locking
        if (x > 1.0f)  { x = 1.0f;  vx = 0; }
        if (x < -1.0f) { x = -1.0f; vx = 0; }
        if (y > 1.0f)  { y = 1.0f;  vy = 0; }
        if (y < -1.0f) { y = -1.0f; vy = 0; }

        trail.push_back({x, y});
        if (trail.size() > 70) trail.erase(trail.begin());
    }
};

int main(int argc, char* argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    SDL_Window* window = SDL_CreateWindow("Predictive Braking Cine Engine", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, 900, 600, 0);
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);

    SDL_GameController* controller = (SDL_NumJoysticks() > 0) ? SDL_GameControllerOpen(0) : nullptr;
    MasterCineEngine cine;
    Uint32 last_tick = SDL_GetTicks();
    bool running = true;

    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) if (event.type == SDL_QUIT) running = false;

        Uint32 current_tick = SDL_GetTicks();
        float dt = (current_tick - last_tick) / 1000.0f;
        if (dt > 0.05f) dt = 0.05f; 
        last_tick = current_tick;

        if (controller) {
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_UP)) tune_speed += 0.05f;
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_DOWN)) tune_speed -= 0.05f;
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_RIGHT)) tune_agility += 0.05f;
            if (SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_LEFT)) tune_agility -= 0.05f;
        }

        Sint16 rX_i = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) : 0;
        Sint16 rY_i = controller ? SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTY) : 0;

        cine.update(rX_i / 32767.0f, rY_i / 32767.0f, dt);

        std::cout << "\rSPEED: " << tune_speed << " | AGILITY: " << tune_agility << "    " << std::flush;

        SDL_SetRenderDrawColor(renderer, 10, 10, 15, 255);
        SDL_RenderClear(renderer);

        // UI
        SDL_SetRenderDrawColor(renderer, 52, 152, 219, 255); 
        SDL_Rect sBar = {50, 40, (int)((tune_speed/15.0f)*150), 10};
        SDL_RenderFillRect(renderer, &sBar);
        SDL_SetRenderDrawColor(renderer, 46, 204, 113, 255); 
        SDL_Rect aBar = {50, 60, (int)((tune_agility/10.0f)*150), 10};
        SDL_RenderFillRect(renderer, &aBar);

        SDL_SetRenderDrawColor(renderer, 40, 40, 50, 255);
        SDL_Rect bL = {50, 150, 350, 350}, bR = {500, 150, 350, 350};
        SDL_RenderDrawRect(renderer, &bL); SDL_RenderDrawRect(renderer, &bR);

        // Trail & Dots
        SDL_SetRenderDrawColor(renderer, 100, 150, 255, 180);
        for (size_t i = 1; i < cine.trail.size(); i++) {
            SDL_RenderDrawLine(renderer, 675 + (cine.trail[i-1].x * 175), 325 + (cine.trail[i-1].y * 175), 675 + (cine.trail[i].x * 175), 325 + (cine.trail[i].y * 175));
        }

        SDL_SetRenderDrawColor(renderer, 46, 204, 113, 255); // Input
        draw_circle(renderer, 225 + ((rX_i/32767.0f)*175), 325 + ((rY_i/32767.0f)*175), 8);
        SDL_SetRenderDrawColor(renderer, 52, 152, 219, 255); // Output
        draw_circle(renderer, 675 + (cine.x * 175), 325 + (cine.y * 175), 14);

        SDL_RenderPresent(renderer);
    }
    SDL_Quit();
    return 0;
}