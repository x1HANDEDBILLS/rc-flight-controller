// input_tuning.h - deadzone, sensitivity, invert, center calibration

#pragma once

#include <cstdint>  // for int16_t

struct InputTuning {
    float deadzone = 0.10f;          // 0.0 to 0.3 (10% default)
    float center_offset_lx = 0.0f;   // left stick X center correction (-0.1 to 0.1)
    float center_offset_ly = 0.0f;
    float center_offset_rx = 0.0f;
    float center_offset_ry = 0.0f;
    float center_offset_l2 = 0.0f;
    float center_offset_r2 = 0.0f;
    float sensitivity = 1.0f;        // 0.5 to 2.0
    bool invert_x = false;
    bool invert_y = false;
    float lowpass_alpha = 0.0f;      // 0.0 = no filter, 0.3 = light smoothing
};

extern InputTuning input_tuning;

int16_t apply_deadzone(int16_t value, float deadzone);
int16_t apply_tuning(int16_t raw, float deadzone, float offset, float sens, bool invert, float lowpass_alpha, int16_t& prev);
