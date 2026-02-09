// input_tuning.cpp - tuning functions

#include "input_tuning.h"
#include <algorithm>  // std::abs, std::max

InputTuning input_tuning;  // global instance

int16_t apply_deadzone(int16_t value, float deadzone) {
    float normalized = static_cast<float>(value) / 32768.0f;
    float abs_val = std::abs(normalized);
    if (abs_val < deadzone) {
        return 0;
    }
    float scaled = (abs_val - deadzone) / (1.0f - deadzone);
    return static_cast<int16_t>(scaled * 32768.0f * (normalized < 0 ? -1.0f : 1.0f));
}

int16_t apply_tuning(int16_t raw, float deadzone, float offset, float sens, bool invert, float lowpass_alpha, int16_t& prev) {
    // Apply center offset first
    float offset_applied = raw + static_cast<int16_t>(offset * 32768.0f);

    // Deadzone
    int16_t deadzoned = apply_deadzone(offset_applied, deadzone);

    // Sensitivity
    float tuned = deadzoned * sens;

    // Clamp
    tuned = std::max(-32768.0f, std::min(32767.0f, tuned));

    // Low-pass filter
    if (lowpass_alpha > 0.0f && lowpass_alpha <= 1.0f) {
        tuned = (lowpass_alpha * tuned) + ((1.0f - lowpass_alpha) * prev);
    }

    prev = static_cast<int16_t>(tuned);

    // Invert
    return invert ? -static_cast<int16_t>(tuned) : static_cast<int16_t>(tuned);
}
