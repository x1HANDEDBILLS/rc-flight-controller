#ifndef INPUT_TUNING_H
#define INPUT_TUNING_H

#include <cstdint>

void apply_tuning(int& raw_val, float deadzone, float sens, float lowpass_alpha, 
                  int curve_type, float expo, bool cine_on, float cine_intensity, 
                  int16_t& prev_val);

#endif