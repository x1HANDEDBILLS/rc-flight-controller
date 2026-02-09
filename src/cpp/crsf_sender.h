#ifndef CRSF_SENDER_H
#define CRSF_SENDER_H

#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <cstring>
#include <stdint.h>

class CRSFSender {
private:
    int fd = -1;
    const char* port = "/dev/ttyACM0"; 

    // CRSF uses a specific polynomial (0xD5) for its 8-bit checksum
    uint8_t crc8(const uint8_t* data, uint8_t len) {
        uint8_t crc = 0;
        for (uint8_t i = 0; i < len; i++) {
            crc ^= data[i];
            for (uint8_t j = 0; j < 8; j++) {
                if (crc & 0x80) crc = (crc << 1) ^ 0xD5;
                else crc <<= 1;
            }
        }
        return crc;
    }

public:
    bool begin() {
        // Open port in Non-Blocking mode
        fd = open(port, O_RDWR | O_NOCTTY | O_NDELAY);
        if (fd < 0) return false;

        struct termios tty;
        memset(&tty, 0, sizeof(tty));
        if (tcgetattr(fd, &tty) != 0) return false;

        // Set Baud Rate to 400,000 (Standard for CRSF)
        // Note: On some systems B400000 is defined, on others we use the raw int
        cfsetospeed(&tty, 400000);
        cfsetispeed(&tty, 400000);
        
        // 8N1 (8 bits, no parity, 1 stop bit)
        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
        tty.c_cflag |= CLOCAL | CREAD;
        tty.c_cflag &= ~(PARENB | CSTOPB | CRTSCTS);
        tty.c_iflag &= ~(IXON | IXOFF | IXANY);
        tty.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
        tty.c_oflag &= ~OPOST;
        
        tcflush(fd, TCIFLUSH);
        if (tcsetattr(fd, TCSANOW, &tty) != 0) return false;
        
        return true;
    }

    void close_port() {
        if (fd >= 0) {
            close(fd);
            fd = -1;
            std::cout << "CRSF Sender: Communication port closed." << std::endl;
        }
    }

    void send_channels(const int* logical_channels) {
        if (fd < 0) return;

        uint8_t packet[26] = {0};
        packet[0] = 0xC8;   // Address: Receiver
        packet[1] = 24;     // Remaining Length
        packet[2] = 0x16;   // Type: RC Channels

        // --- THE MATH: Keeps your GUI big, but shrinks data for the wire ---
        uint16_t crsf_channels[16];
        for (int i = 0; i < 16; i++) {
            // Map PS4 (-32768 to 32767) to CRSF (172 to 1811)
            float norm = (logical_channels[i] + 32768) / 65535.0f;
            crsf_channels[i] = (uint16_t)(norm * 1639.0f + 172.0f);
            
            // Protocol Safety Clamping
            if (crsf_channels[i] < 172) crsf_channels[i] = 172;
            if (crsf_channels[i] > 1811) crsf_channels[i] = 1811;
        }

        // --- BIT PACKING: Shoves 11-bit values into 8-bit bytes ---
        
        packet[3]  = (uint8_t)(crsf_channels[0] & 0x07FF);
        packet[4]  = (uint8_t)((crsf_channels[0] >> 8) | (crsf_channels[1] << 3));
        packet[5]  = (uint8_t)((crsf_channels[1] >> 5) | (crsf_channels[2] << 6));
        packet[6]  = (uint8_t)(crsf_channels[2] >> 2);
        packet[7]  = (uint8_t)((crsf_channels[2] >> 10) | (crsf_channels[3] << 1));
        packet[8]  = (uint8_t)((crsf_channels[3] >> 7) | (crsf_channels[4] << 4));
        packet[9]  = (uint8_t)((crsf_channels[4] >> 4) | (crsf_channels[5] << 7));
        packet[10] = (uint8_t)(crsf_channels[5] >> 1);
        packet[11] = (uint8_t)((crsf_channels[5] >> 9) | (crsf_channels[6] << 2));
        packet[12] = (uint8_t)((crsf_channels[6] >> 6) | (crsf_channels[7] << 5));
        packet[13] = (uint8_t)(crsf_channels[7] >> 3);
        packet[14] = (uint8_t)(crsf_channels[8] & 0x07FF);
        packet[15] = (uint8_t)((crsf_channels[8] >> 8) | (crsf_channels[9] << 3));
        packet[16] = (uint8_t)((crsf_channels[9] >> 5) | (crsf_channels[10] << 6));
        packet[17] = (uint8_t)(crsf_channels[10] >> 2);
        packet[18] = (uint8_t)((crsf_channels[10] >> 10) | (crsf_channels[11] << 1));
        packet[19] = (uint8_t)((crsf_channels[11] >> 7) | (crsf_channels[12] << 4));
        packet[20] = (uint8_t)((crsf_channels[12] >> 4) | (crsf_channels[13] << 7));
        packet[21] = (uint8_t)(crsf_channels[13] >> 1);
        packet[22] = (uint8_t)((crsf_channels[13] >> 9) | (crsf_channels[14] << 2));
        packet[23] = (uint8_t)((crsf_channels[14] >> 6) | (crsf_channels[15] << 5));
        packet[24] = (uint8_t)(crsf_channels[15] >> 3);

        packet[25] = crc8(&packet[2], 23);

        write(fd, packet, 26);
    }
};

#endif