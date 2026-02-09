#ifndef INPUT_MAPPER_H
#define INPUT_MAPPER_H

#include <vector>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

struct LogicalSignals { int channels[16]; };

struct ChannelConfig {
    int primary_src = 22; // Default to ID 22 (Neutral)
    bool is_split = false;
    
    // Split Mix settings
    int pos_src = 22;
    int neg_src = 22;
    bool pos_center = false;
    bool pos_reverse = false;
    bool neg_center = false;
    bool neg_reverse = false;
};

class InputMapper {
public:
    ChannelConfig configs[16];

    // Helper to apply centering and reversing math exactly like Python
    int tune_val(int raw_val, bool center, bool reverse) {
        int val = raw_val;
        if (center) {
            val += 32768;
        }
        if (reverse) {
            val *= -1;
        }
        return std::clamp(val, -32768, 32767);
    }

    void load_from_json(const std::string& filename) {
        std::ifstream file(filename);
        if (!file.is_open()) return;

        try {
            json j;
            file >> j;

            // 1. Load Standard Channel Map
            if (j.contains("channel_map")) {
                auto mapping = j["channel_map"];
                for (int i = 0; i < std::min((int)mapping.size(), 16); i++) {
                    configs[i].primary_src = mapping[i];
                    configs[i].is_split = false; // Reset split status
                }
            }

            // 2. Load Split Config
            if (j.contains("split_config")) {
                auto s = j["split_config"];
                int target = s.value("target_ch", -1);
                
                if (target >= 0 && target < 16) {
                    configs[target].is_split = true;
                    configs[target].pos_src = s.value("pos_id", 22);
                    configs[target].neg_src = s.value("neg_id", 22);
                    configs[target].pos_center = s.value("pos_center", false);
                    configs[target].pos_reverse = s.value("pos_reverse", false);
                    configs[target].neg_center = s.value("neg_center", false);
                    configs[target].neg_reverse = s.value("neg_reverse", false);
                }
            }
            std::cout << "[MAPPER] Sync Complete: Json loaded and applied." << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "Mapper JSON Error: " << e.what() << std::endl;
        }
    }

    void update(const std::vector<int>& raw, LogicalSignals& out) {
        for (int i = 0; i < 16; i++) {
            if (configs[i].is_split) {
                // Split Mixer Logic
                int p_raw = get_raw(configs[i].pos_src, raw);
                int n_raw = get_raw(configs[i].neg_src, raw);
                
                int p_tuned = tune_val(p_raw, configs[i].pos_center, configs[i].pos_reverse);
                int n_tuned = tune_val(n_raw, configs[i].neg_center, configs[i].neg_reverse);
                
                out.channels[i] = std::clamp(p_tuned + n_tuned, -32768, 32767);
            } else {
                // Standard Logic (Simple Map)
                // Note: If you want centering/reverse on standard channels, 
                // you'd add those bools to the standard config too.
                out.channels[i] = get_raw(configs[i].primary_src, raw);
            }
        }
    }

private:
    int get_raw(int id, const std::vector<int>& signals) {
        if (id >= 0 && id < (int)signals.size()) {
            return signals[id];
        }
        return -32768; // Return "low" if ID is 22 or invalid
    }
};

#endif