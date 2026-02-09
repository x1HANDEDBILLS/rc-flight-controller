#include "input_tuning.h"
#include <cmath>
#include <algorithm>

void apply_tuning(int& raw_x, int& raw_y, float deadzone, float sens, float lowpass_alpha, int16_t& prev_x, int16_t& prev_y) {
    // 1. Convert to float (-1.0 to 1.0)
    float fx = (float)raw_x / 32767.0f;
    float fy = (float)raw_y / 32767.0f;

    // 2. Simple Axis-Independent Deadzone
    auto process_axis = [&](float val) {
        if (std::abs(val) < deadzone) return 0.0f;
        // Rescale so it starts smoothly from 0 after the deadzone
        val = (val > 0) ? (val - deadzone) / (1.0f - deadzone) : (val + deadzone) / (1.0f - deadzone);
        return std::clamp(val * sens, -1.0f, 1.0f);
    };

    fx = process_axis(fx);
    fy = process_axis(fy);

    // 3. Lowpass Smoothing
    float filtered_x = (fx * (1.0f - lowpass_alpha)) + ((float)prev_x / 32767.0f * lowpass_alpha);
    float filtered_y = (fy * (1.0f - lowpass_alpha)) + ((float)prev_y / 32767.0f * lowpass_alpha);

    // 4. Update raw values and memory
    raw_x = (int)(filtered_x * 32767.0f);
    raw_y = (int)(filtered_y * 32767.0f);
    
    prev_x = (int16_t)raw_x;
    prev_y = (int16_t)raw_y;
}
