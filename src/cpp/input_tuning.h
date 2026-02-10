#ifndef INPUT_TUNING_H
#define INPUT_TUNING_H

#include <cstdint>
#include <cmath>
#include <algorithm>

/**
 * Helper to apply Expo/Curve algorithms.
 * Maps the GUI scale (-10.0 to 10.0) to internal math.
 */
static inline float apply_curve(float val, int type, float gui_expo) {
    if (std::abs(val) < 0.001f) return 0.0f;
    
    float abs_v = std::abs(val);
    float output = 0.0f;

    switch(type) {
        case 1: // STANDARD (Cubic Expo)
            {
                // Map GUI -10/10 to 0.0/1.0 factor
                // Formula: y = k(x^3) + (1-k)x
                float k = std::clamp(gui_expo / 10.0f, -1.0f, 1.0f);
                if (k >= 0) {
                    output = k * std::pow(abs_v, 3) + (1.0f - k) * abs_v;
                } else {
                    // Negative expo makes it more sensitive in the center
                    output = std::pow(abs_v, 1.0f / (1.0f - k));
                }
            }
            break;
            
        case 2: // DYNAMIC (S-Curve / Sine-based)
            {
                float k = std::clamp(gui_expo / 10.0f, 0.0f, 1.0f);
                // Mix between linear and a smooth sine curve
                output = (1.0f - k) * abs_v + k * (0.5f - 0.5f * std::cos(M_PI * abs_v));
            }
            break;
            
        case 3: // EXTREME (True Exponential)
            {
                // We cap gui_expo at 5 for math safety in EXP
                float k = std::clamp(gui_expo / 2.0f, -5.0f, 5.0f);
                if (std::abs(k) < 0.01f) {
                    output = abs_v;
                } else {
                    output = (std::exp(k * abs_v) - 1.0f) / (std::exp(k) - 1.0f);
                }
            }
            break;
            
        case 0: // LINEAR
        default:
            output = abs_v;
            break;
    }
    
    return (val > 0) ? output : -output;
}

/**
 * The Tuning Engine.
 */
inline void apply_tuning(int& raw_val, float deadzone, float sens, float lowpass_alpha, 
                         int curve_type, float expo, bool cine_on, float cine_intensity, 
                         int16_t& prev_val) {
    
    // 1. Convert to normalized float (-1.0 to 1.0)
    float val = (float)raw_val / 32767.0f;

    // 2. Apply Deadzone (GUI sends 0.1-5.0, Python sends value/10 to C++)
    // C++ expects 0.01 to 0.50 here.
    float abs_val = std::abs(val);
    if (abs_val < deadzone) {
        val = 0.0f;
    } else {
        // Smooth rescale
        val = (val > 0 ? 1.0f : -1.0f) * (abs_val - deadzone) / (1.0f - deadzone);
    }

    // 3. Apply Response Curve (Expects -10.0 to 10.0)
    val = apply_curve(val, curve_type, expo);

    // 4. Apply Sensitivity / Global Rate
    val *= sens;

    // 5. Apply Cinematic Mode Scaling
    if (cine_on && cine_intensity > 0.1f) {
        val /= cine_intensity;
    }

    // 6. Clamp to safety limits
    val = std::clamp(val, -1.0f, 1.0f);

    // 7. Lowpass Smoothing
    float current_prev = (float)prev_val / 32767.0f;
    float filtered = (val * (1.0f - lowpass_alpha)) + (current_prev * lowpass_alpha);

    // 8. Output
    raw_val = (int)std::round(filtered * 32767.0f);
    prev_val = (int16_t)raw_val;
}

#endif