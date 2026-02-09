#ifndef INPUT_TUNING_H
#define INPUT_TUNING_H
#include <cstdint>
void apply_tuning(int& raw_x, int& raw_y, float deadzone, float sens, float alpha, int16_t& prev_x, int16_t& prev_y);
#endif
