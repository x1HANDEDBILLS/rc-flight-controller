#ifndef INPUT_MAPPER_H
#define INPUT_MAPPER_H

#include <vector>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

struct LogicalSignals { int channels[16]; };

struct ChannelConfig {
    bool is_split = false;
    int primary_src = 22; // Default to neutral
    int pos_src = 22;
    int neg_src = 22;
    bool inverted = false;
};

class InputMapper {
public:
    ChannelConfig configs[16];

    void load_from_json(const std::string& filename) {
        std::ifstream file(filename);
        if (!file.is_open()) {
            std::cerr << "Mapper: Could not open config " << filename << std::endl;
            return;
        }

        try {
            json j;
            file >> j;

            // Access the "mapping" section
            if (j.contains("mapping") && j["mapping"].contains("defaults")) {
                for (auto& item : j["mapping"]["defaults"]) {
                    int ch = item.value("ch", -1);
                    if (ch >= 0 && ch < 16) {
                        configs[ch].primary_src = item.value("src", 22);
                        configs[ch].inverted = item.value("inv", false);
                        configs[ch].is_split = false;
                    }
                }
            }

            // Apply custom overrides if they exist
            if (j["mapping"].contains("custom")) {
                for (auto& item : j["mapping"]["custom"]) {
                    int ch = item.value("ch", -1);
                    if (ch >= 0 && ch < 16) {
                        configs[ch].is_split = item.value("is_split", false);
                        if (configs[ch].is_split) {
                            configs[ch].pos_src = item.value("pos_src", 22);
                            configs[ch].neg_src = item.value("neg_src", 22);
                        } else {
                            configs[ch].primary_src = item.value("src", 22);
                        }
                        configs[ch].inverted = item.value("inv", false);
                    }
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "Mapper JSON Error: " << e.what() << std::endl;
        }
    }

    void update(const std::vector<int>& raw, LogicalSignals& out) {
        for (int i = 0; i < 16; i++) {
            int val = 0;
            if (configs[i].is_split) {
                val = get_val(configs[i].pos_src, raw) - get_val(configs[i].neg_src, raw);
            } else {
                val = get_val(configs[i].primary_src, raw);
            }
            if (configs[i].inverted) val = -val;
            out.channels[i] = std::clamp(val, -32768, 32767);
        }
    }

private:
    int get_val(int id, const std::vector<int>& signals) {
        return (id >= 0 && id < (int)signals.size()) ? signals[id] : 0;
    }
};

#endif