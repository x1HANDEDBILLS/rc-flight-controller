#ifndef INPUT_MIXER_H
#define INPUT_MIXER_H

#include "InputMapper.h"
#include <algorithm>

class InputMixer {
public:
    // This holds the 16-channel output that the CRSFSender will read.
    // Range: -32768 to 32767
    int final_channels[16];

    InputMixer() {
        // Initialize all channels to 0 (neutral) on startup
        for (int i = 0; i < 16; i++) {
            final_channels[i] = 0;
        }
    }

    /**
     * @brief Simple passthrough from the Mapper to the final output array.
     * This keeps the pipeline clean and provides a future entry point for 
     * complex channel mixing math.
     */
    void process(const LogicalSignals &mapped_signals) {
        for (int i = 0; i < 16; i++) {
            // Direct 1:1 passthrough
            final_channels[i] = mapped_signals.channels[i];
        }
    }
};

#endif