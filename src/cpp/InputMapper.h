#ifndef INPUT_MAPPER_H
#define INPUT_MAPPER_H

#include <vector>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>
#include <sstream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

// Holds the 16 logical functions (Pitch, Roll, Throttle, Yaw, AUX 1-12)
struct LogicalSignals { 
    int channels[16]; 
};

// Configuration for a single output channel
struct ChannelConfig {
    int primary_src = 22; // Default to ID 22 (Neutral/Always -32768)
    bool is_split = false;
    
    // Split Mix settings (used when combining two inputs into one channel)
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

    /**
     * Helper to update mapping directly from the UDP packet string.
     * This fixes the "no member named channel_maps" errors by providing 
     * a single entry point for the packet data.
     */
    void set_from_packet(const std::vector<std::string>& map_vals, const std::vector<std::string>& split_vals) {
        // 1. Update Standard Mapping
        for (int i = 0; i < 16 && i < (int)map_vals.size(); i++) {
            configs[i].primary_src = std::stoi(map_vals[i]);
            configs[i].is_split = false; // Reset to standard unless overwritten below
        }

        // 2. Update Split Config
        if (split_vals.size() >= 7) {
            int target = std::stoi(split_vals[0]);
            if (target >= 0 && target < 16) {
                configs[target].is_split = true;
                configs[target].pos_src     = std::stoi(split_vals[1]);
                configs[target].neg_src     = std::stoi(split_vals[2]);
                configs[target].pos_center  = (std::stoi(split_vals[3]) == 1);
                configs[target].pos_reverse = (std::stoi(split_vals[4]) == 1);
                configs[target].neg_center  = (std::stoi(split_vals[5]) == 1);
                configs[target].neg_reverse = (std::stoi(split_vals[6]) == 1);
            }
        }
    }

    /**
     * Re-maps and transforms signal ranges.
     */
    int apply_map_transform(int raw_val, bool center, bool reverse) {
        long val = raw_val; 

        if (center) {
            val = (val * 2) - 32768;
        }
        
        if (reverse) {
            val *= -1;
        }

        return (int)std::clamp(val, -32768L, 32767L);
    }

    void load_from_json(const std::string& filename) {
        std::ifstream file(filename);
        if (!file.is_open()) {
            std::cerr << "[MAPPER] Failed to open: " << filename << std::endl;
            return;
        }

        try {
            json j;
            file >> j;

            if (j.contains("channel_map")) {
                auto mapping = j["channel_map"];
                for (int i = 0; i < std::min((int)mapping.size(), 16); i++) {
                    configs[i].primary_src = mapping[i];
                    configs[i].is_split = false;
                }
            }

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
        } catch (const std::exception& e) {
            std::cerr << "[MAPPER] JSON Parse Error: " << e.what() << std::endl;
        }
    }

    void update(const std::vector<int>& raw, LogicalSignals& out) {
        for (int i = 0; i < 16; i++) {
            if (configs[i].is_split) {
                int p_raw = get_raw_safe(configs[i].pos_src, raw);
                int n_raw = get_raw_safe(configs[i].neg_src, raw);
                
                int p_transformed = apply_map_transform(p_raw, configs[i].pos_center, configs[i].pos_reverse);
                int n_transformed = apply_map_transform(n_raw, configs[i].neg_center, configs[i].neg_reverse);
                
                out.channels[i] = std::clamp(p_transformed + n_transformed, -32768, 32767);
            } else {
                out.channels[i] = get_raw_safe(configs[i].primary_src, raw);
            }
        }
    }

private:
    int get_raw_safe(int id, const std::vector<int>& signals) {
        if (id >= 0 && id < (int)signals.size()) {
            return signals[id];
        }
        return -32768; 
    }
};

#endif