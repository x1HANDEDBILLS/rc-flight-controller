#ifndef CRSF_SENDER_H
#define CRSF_SENDER_H

#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <asm/termbits.h> 
#include <cstring>
#include <stdint.h>
#include <thread>
#include <atomic>
#include <vector>
#include <algorithm>
#include <mutex> 

#include "crsf_parser.h"

#define CRSF_CHANNELS_COUNT 16
#define CRSF_CH_BITS 11

// Reference to the mutex physically defined in main.cpp
extern std::mutex console_mutex;

class CRSFSender {
private:
    int fd = -1;
    std::thread receive_thread;
    std::atomic<bool> running {false};

    static constexpr uint8_t crc_table[256] = {
        0x00, 0xD5, 0x7F, 0xAA, 0xFE, 0x2B, 0x81, 0x54, 0x29, 0xFC, 0x56, 0x83, 0xD7, 0x02, 0xA8, 0x7D,
        0x52, 0x87, 0x2D, 0xF8, 0xAC, 0x79, 0xD3, 0x06, 0x7B, 0xAE, 0x04, 0xD1, 0x85, 0x50, 0xFA, 0x2F,
        0xA4, 0x71, 0xDB, 0x0E, 0x5A, 0x8F, 0x25, 0xF0, 0x8D, 0x58, 0xF2, 0x27, 0x73, 0xA6, 0x0C, 0xD9,
        0xF6, 0x23, 0x89, 0x5C, 0x08, 0xDD, 0x77, 0xA2, 0xDF, 0x0A, 0xA0, 0x75, 0x21, 0xF4, 0x5E, 0x8B,
        0x9D, 0x48, 0xE2, 0x37, 0x63, 0xB6, 0x1C, 0xC9, 0xB4, 0x61, 0xCB, 0x1E, 0x4A, 0x9F, 0x35, 0xE0,
        0xCF, 0x1A, 0xB0, 0x65, 0x31, 0xE4, 0x4E, 0x9B, 0xE6, 0x33, 0x99, 0x4C, 0x18, 0xCD, 0x67, 0xB2,
        0x39, 0xEC, 0x46, 0x93, 0xC7, 0x12, 0xB8, 0x6D, 0x10, 0xC5, 0x6F, 0xBA, 0xEE, 0x3B, 0x91, 0x44,
        0x6B, 0xBE, 0x14, 0xC1, 0x95, 0x40, 0xEA, 0x3F, 0x42, 0x97, 0x3D, 0xE8, 0xBC, 0x69, 0xC3, 0x16,
        0xEF, 0x3A, 0x90, 0x45, 0x11, 0xC4, 0x6E, 0xBB, 0xC6, 0x13, 0xB9, 0x6C, 0x38, 0xED, 0x47, 0x92,
        0xBD, 0x68, 0xC2, 0x17, 0x43, 0x96, 0x3C, 0xE9, 0x94, 0x41, 0xEB, 0x3E, 0x6A, 0xBF, 0x15, 0xC0,
        0x4B, 0x9E, 0x34, 0xE1, 0xB5, 0x60, 0xCA, 0x1F, 0x62, 0xB7, 0x1D, 0xC8, 0x9C, 0x49, 0xE3, 0x36,
        0x19, 0xCC, 0x66, 0xB3, 0xE7, 0x32, 0x98, 0x4D, 0x30, 0xE5, 0x4F, 0x9A, 0xCE, 0x1B, 0xB1, 0x64,
        0x72, 0xA7, 0x0D, 0xD8, 0x8C, 0x59, 0xF3, 0x26, 0x5B, 0x8E, 0x24, 0xF1, 0xA5, 0x70, 0xDA, 0x0F,
        0x20, 0xF5, 0x5F, 0x8A, 0xDE, 0x0B, 0xA1, 0x74, 0x09, 0xDC, 0x76, 0xA3, 0xF7, 0x22, 0x88, 0x5D,
        0xD6, 0x03, 0xA9, 0x7C, 0x28, 0xFD, 0x57, 0x82, 0xFF, 0x2A, 0x80, 0x55, 0x01, 0xD4, 0x7E, 0xAB,
        0x84, 0x51, 0xFB, 0x2E, 0x7A, 0xAF, 0x05, 0xD0, 0xAD, 0x78, 0xD2, 0x07, 0x53, 0x86, 0x2C, 0xF9
    };

    uint8_t crc8(const uint8_t* data, uint8_t len) {
        uint8_t crc = 0;
        for (uint8_t i = 0; i < len; i++) {
            crc = crc_table[crc ^ data[i]];
        }
        return crc;
    }

    void receive_loop() {
        TelemetryData telemetry;
        std::vector<uint8_t> buffer;
        uint8_t byte;

        while (running) {
            // High-speed drain: read everything in the serial buffer
            while (read(fd, &byte, 1) > 0) {
                if (buffer.empty()) {
                    if (byte == CRSF_ADDRESS_RADIO_TRANSMITTER || byte == CRSF_SYNC_BYTE) {
                        buffer.push_back(byte);
                    }
                } else {
                    buffer.push_back(byte);
                    if (buffer.size() >= 2 && buffer.size() == (buffer[1] + 2)) {
                        if (parse_crsf_frame(buffer, telemetry)) {
                            std::lock_guard<std::mutex> lock(console_mutex);
                            print_telemetry(telemetry);
                        }
                        buffer.clear();
                    }
                }
            }
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
    }

public:
    bool begin(int baud_rate) {
        const char* ports[] = {"/dev/ttyUSB0", "/dev/ttyACM0"};
        bool found = false;
        
        for (const char* p : ports) {
            fd = open(p, O_RDWR | O_NOCTTY | O_NDELAY);
            if (fd >= 0) {
                {
                    std::lock_guard<std::mutex> lock(console_mutex);
                    std::cout << "Successfully opened " << p << std::endl;
                }
                found = true;
                break;
            }
        }
        
        if (!found) return false;

        struct termios2 tty;
        if (ioctl(fd, TCGETS2, &tty) != 0) return false;

        tty.c_cflag &= ~CBAUD;
        tty.c_cflag |= BOTHER;
        tty.c_ispeed = baud_rate;
        tty.c_ospeed = baud_rate;

        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8 | CLOCAL | CREAD;
        tty.c_cflag &= ~(PARENB | CSTOPB | CRTSCTS);
        tty.c_iflag &= ~(IXON | IXOFF | IXANY);
        tty.c_lflag = 0;
        tty.c_oflag = 0;

        if (ioctl(fd, TCSETS2, &tty) != 0) return false;
        ioctl(fd, TCFLSH, TCIFLUSH); 
        
        running = true;
        receive_thread = std::thread(&CRSFSender::receive_loop, this);
        return true;
    }

    void close_port() {
        running = false;
        if (receive_thread.joinable()) receive_thread.join();
        if (fd >= 0) {
            close(fd);
            fd = -1;
        }
    }

    void send_channels(const int* logical_channels) {
        if (fd < 0) return;

        uint8_t packet[26] = {0};
        packet[0] = 0xEE; 
        packet[1] = 24;   
        packet[2] = 0x16; 

        uint8_t* buf = &packet[3];
        uint32_t bits = 0;
        uint8_t bitsavailable = 0;

        for (int i = 0; i < CRSF_CHANNELS_COUNT; i++) {
            float norm = (logical_channels[i] + 32768) / 65535.0f;
            uint32_t val = (uint32_t)(norm * 1639.0f + 172.0f);
            val = std::max(172U, std::min(1811U, val));

            bits |= val << bitsavailable;
            bitsavailable += CRSF_CH_BITS;

            while (bitsavailable >= 8) {
                *buf++ = (uint8_t)(bits & 0xFF);
                bits >>= 8;
                bitsavailable -= 8;
            }
        }

        packet[25] = crc8(&packet[2], 23);
        write(fd, packet, 26);
    }
};

#endif