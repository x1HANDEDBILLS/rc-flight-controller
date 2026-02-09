#ifndef INPUT_MIXER_H
#define INPUT_MIXER_H

#include "InputMapper.h"

class InputMixer {
public:
    // This is the clean 16-channel array the Sender will eventually use
    int final_channels[16];

    InputMixer() {
        for(int i = 0; i < 16; i++) final_channels[i] = 0;
    }

    /**
     * @brief Pulls data from the Mapper and prepares the final flight array.
     */
    void process(const LogicalSignals &mapped_signals) {
        for (int i = 0; i < 16; i++) {
            // Currently 1:1 Pass-through. 
            // This is where you'd add "Fancy" math later.
            final_channels[i] = mapped_signals.channels[i];
        }
    }
};

#endif