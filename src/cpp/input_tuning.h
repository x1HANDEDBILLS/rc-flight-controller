#ifndef INPUT_TUNING_H
#define INPUT_TUNING_H

#include <cstdint>
#include <cmath>
#include <algorithm>

/**
 * Helper to apply Expo/Curve algorithms.
 */
static inline float apply_curve(float val, int type, float gui_expo) {
    if (std::abs(val) < 0.001f) return 0.0f;
    
    float abs_v = std::abs(val);
    float output = 0.0f;

    switch(type) {
        case 1: // STANDARD (Cubic Expo)
            {
                float k = std::clamp(gui_expo / 10.0f, -1.0f, 1.0f);
                if (k >= 0) output = k * std::pow(abs_v, 3) + (1.0f - k) * abs_v;
                else output = std::pow(abs_v, 1.0f / (1.0f - k));
            }
            break; 
        case 2: // DYNAMIC (S-Curve)
            {
                float k = std::clamp(gui_expo / 10.0f, 0.0f, 1.0f);
                #ifndef M_PI
                #define M_PI 3.14159265358979323846
                #endif
                output = (1.0f - k) * abs_v + k * (0.5f - 0.5f * std::cos(M_PI * abs_v));
            }
            break;
        case 3: // EXTREME
            {
                float k = std::clamp(gui_expo / 10.0f, -5.0f, 5.0f);
                if (std::abs(k) < 0.01f) output = abs_v;
                else output = (std::exp(k * abs_v) - 1.0f) / (std::exp(k) - 1.0f);
            }
            break;
        case 0: default: output = abs_v; break;
    }
    return (val > 0) ? output : -output;
}

/**
 * The Tuning Engine.
 * NOW UPDATED FOR 1000Hz LOOPS
 */
inline void apply_tuning(int& raw_val, float deadzone, float sens, float lowpass_alpha, 
                          int curve_type, float expo, bool cine_on, float cine_speed, float cine_accel,
                          int16_t& prev_val, float& cine_v, float& cine_pos, float dt) {
    
    // 1. Convert to normalized float
    float val = (float)raw_val / 32767.0f;

    // 2. Apply Deadzone (Standardized)
    float abs_val = std::abs(val);
    if (abs_val < deadzone) {
        val = 0.0f;
    } else {
        val = (val > 0 ? 1.0f : -1.0f) * (abs_val - deadzone) / (1.0f - deadzone);
    }

    // 3. Apply Curve
    val = apply_curve(val, curve_type, expo);

    // 4. Apply Sensitivity
    val *= sens;

    // 5. Cinematic Mode (Physics Engine)
    if (cine_on) {
        float target = val; 
        float dist_vec = target - cine_pos;
        float dist = std::abs(dist_vec);
        
        // Tuned for 1000Hz Loop:
        // cine_accel (from GUI 0-10) -> needs to be gentle. 
        float accel_rate = cine_accel * 0.5f; 
        float speed_limit = 1.0f; 
        
        // Calculate max safe speed to stop at target
        float max_safe_speed = std::sqrt(2.0f * accel_rate * dist);
        
        // Dampening factor based on cine_speed (GUI 0-10)
        // Higher cine_speed = Less dampening = Faster
        float dampening = 1.0f + (10.0f - cine_speed) * 0.5f;
        float target_speed = std::min(speed_limit, max_safe_speed) / dampening;

        float desired_v = (dist > 0.0001f) ? (dist_vec / dist) * target_speed : 0.0f;

        float diffV = desired_v - cine_v;
        float diffMag = std::abs(diffV);

        if (diffMag > 0.0001f) {
            float step = accel_rate * dt; 
            cine_v += (diffV / diffMag) * std::min(step, diffMag);
        }

        cine_pos += cine_v * dt;

        // Snap to target if close and slow
        if (dist < 0.001f && std::abs(cine_v) < 0.01f) {
            cine_pos = target;
            cine_v = 0.0f;
        }

        val = cine_pos;
    } else {
        cine_pos = val;
        cine_v = 0.0f;
    }

    // 6. Clamp
    val = std::clamp(val, -1.0f, 1.0f);

    // 7. Lowpass Filter
    float current_prev = (float)prev_val / 32767.0f;
    float filtered = (val * (1.0f - lowpass_alpha)) + (current_prev * lowpass_alpha);

    // 8. Output
    raw_val = (int)std::round(filtered * 32767.0f);
    prev_val = (int16_t)raw_val;
}

#endif