#include "input_tuning.h"
#include <cmath>
#include <algorithm>

// Helper to apply Expo/Curve algorithms
float apply_curve(float val, int type, float expo) {
    if (std::abs(val) < 0.001f) return 0.0f;
    
    float abs_v = std::abs(val);
    float output = 0.0f;

    switch(type) {
        case 1: // STANDARD (Power Curve)
            output = std::pow(abs_v, 1.0f + expo);
            break;
        case 2: // DYNAMIC (S-Curve)
            output = abs_v * (1.0f - expo) + (std::pow(abs_v, 3) * expo);
            break;
        case 3: // EXTREME (Aggressive exponential)
            output = (std::exp(expo * abs_v) - 1.0f) / (std::exp(expo) - 1.0f);
            break;
        case 0: // LINEAR
        default:
            output = abs_v;
            break;
    }
    
    return (val > 0) ? output : -output;
}

void apply_tuning(int& raw_val, float deadzone, float sens, float lowpass_alpha, 
                  int curve_type, float expo, bool cine_on, float cine_intensity, 
                  int16_t& prev_val) {
    
    // 1. Convert to normalized float (-1.0 to 1.0)
    float val = (float)raw_val / 32767.0f;

    // 2. Apply Deadzone
    if (std::abs(val) < deadzone) {
        val = 0.0f;
    } else {
        // Rescale to prevent "jump" after deadzone
        val = (val > 0) ? (val - deadzone) / (1.0f - deadzone) : (val + deadzone) / (1.0f - deadzone);
    }

    // 3. Apply Response Curve (Expo)
    val = apply_curve(val, curve_type, expo);

    // 4. Apply Sensitivity / Global Rate
    val *= sens;

    // 5. Apply Cinematic Mode Scaling
    if (cine_on) {
        // cine_intensity from UI is 1.0 to 10.0. 
        // We divide by it to slow down the movement significantly.
        val /= cine_intensity;
    }

    // 6. Clamp to safety limits
    val = std::clamp(val, -1.0f, 1.0f);

    // 7. Lowpass Smoothing (The "Filter")
    // prev_val is stored in normalized float space inside the engine for precision
    float current_prev = (float)prev_val / 32767.0f;
    float filtered = (val * (1.0f - lowpass_alpha)) + (current_prev * lowpass_alpha);

    // 8. Output back to raw integer range for the Transmitter
    raw_val = (int)(filtered * 32767.0f);
    prev_val = (int16_t)raw_val;
}