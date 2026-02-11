#ifndef CRSF_PARSER_H
#define CRSF_PARSER_H

#include <vector>
#include <cstdint>
#include <string>
#include <iomanip>
#include <cstring>
#include <iostream>

// CRSF constants
const uint8_t CRSF_ADDRESS_RADIO_TRANSMITTER = 0xEE;
const uint8_t CRSF_SYNC_BYTE = 0xC8;
const uint8_t CRSF_CRC_POLY = 0xD5;

// Enum for CRSF frame types (expanded)
enum CrsfFrameType {
    CRSF_FRAMETYPE_GPS = 0x02,
    CRSF_FRAMETYPE_VARIO = 0x07,
    CRSF_FRAMETYPE_BATTERY_SENSOR = 0x08,
    CRSF_FRAMETYPE_LINK_STATISTICS = 0x14,
    CRSF_FRAMETYPE_RC_CHANNELS_PACKED = 0x16,
    CRSF_FRAMETYPE_ATTITUDE = 0x1E,
    CRSF_FRAMETYPE_FLIGHT_MODE = 0x21,
    CRSF_FRAMETYPE_DEVICE_INFO = 0x29,
    CRSF_FRAMETYPE_AIRSPEED = 0x0A, // Extended for airspeed
    CRSF_FRAMETYPE_ESC_TELEMETRY = 0x7E, // ESC data
    CRSF_FRAMETYPE_FUEL = 0x0B, // Fuel level
    CRSF_FRAMETYPE_UNKNOWN = 0xFF
};

// Expanded structure to hold all possible telemetry data
struct TelemetryData {
    // Link Statistics
    int8_t uplink_rssi_1 = 0;
    int8_t uplink_rssi_2 = 0;
    uint8_t uplink_link_quality = 0;
    int8_t uplink_snr = 0;
    uint8_t active_antenna = 0;
    uint8_t rf_mode = 0;
    uint8_t uplink_tx_power = 0;
    int8_t downlink_rssi = 0;
    uint8_t downlink_link_quality = 0;
    int8_t downlink_snr = 0;

    // GPS
    int32_t gps_latitude = 0;
    int32_t gps_longitude = 0;
    uint16_t gps_groundspeed = 0;
    uint16_t gps_heading = 0;
    uint16_t gps_altitude = 0;
    uint8_t gps_satellites = 0;
    float gps_hdop = 0.0f; // New: HDOP
    uint32_t gps_distance = 0; // New: Distance from home
    uint32_t gps_traveled_distance = 0; // New
    std::string gps_time_date = ""; // New: Timestamp

    // Battery
    uint16_t battery_voltage = 0;
    uint16_t battery_current = 0;
    uint32_t battery_capacity_used = 0;
    uint8_t battery_remaining = 0;
    std::vector<float> cell_voltages; // New: Per cell
    uint16_t rx_battery = 0; // RxBt

    // Vario/Altitude/Speed
    int16_t vario_vertical_speed = 0;
    uint16_t baro_altitude = 0; // New: Baro alt
    uint16_t airspeed = 0; // New: Airspeed

    // Attitude/Orientation (expanded with accel/gyro/mag)
    int16_t attitude_pitch = 0;
    int16_t attitude_roll = 0;
    int16_t attitude_yaw = 0;
    float accel_x = 0.0f; // New
    float accel_y = 0.0f;
    float accel_z = 0.0f;
    float gyro_x = 0.0f; // New
    float gyro_y = 0.0f;
    float gyro_z = 0.0f;
    float mag_x = 0.0f; // New
    float mag_y = 0.0f;
    float mag_z = 0.0f;
    uint16_t compass_heading = 0; // New

    // Vehicle/FC
    std::string flight_mode = "";
    uint8_t arm_status = 0;
    uint16_t rpm = 0;
    uint8_t esc_temperature = 0;
    uint16_t headspeed = 0;
    uint8_t mcu_temperature = 0;
    uint8_t load = 0;
    std::string vtx_telemetry = ""; // New: VTX status
    uint8_t heartbeat_status = 0;
    uint16_t fuel_level = 0; // New: Fuel
    uint8_t throttle = 0; // New: Throttle %
    float current_sensor = 0.0f; // New: Advanced current
};

// CRC8 function (table-based for consistency with sender)
static inline uint8_t crsf_crc8(const uint8_t* data, uint8_t len) {
    static const uint8_t crc_table[256] = {
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
    uint8_t crc = 0;
    for (uint8_t i = 0; i < len; i++) {
        crc = crc_table[crc ^ data[i]];
    }
    return crc;
}

// Parse function
inline bool parse_crsf_frame(const std::vector<uint8_t>& frame, TelemetryData& data) {
    if (frame.size() < 4) return false;

    uint8_t addr = frame[0];
    uint8_t len = frame[1];
    if (frame.size() != (size_t)(len + 2)) return false;
    if (addr != CRSF_ADDRESS_RADIO_TRANSMITTER && addr != CRSF_SYNC_BYTE) return false;

    uint8_t type = frame[2];
    const uint8_t* payload = &frame[3];
    size_t payload_len = len - 2;

    uint8_t computed_crc = crsf_crc8(&frame[2], len - 1);
    uint8_t received_crc = frame.back();
    if (computed_crc != received_crc) {
        return false;
    }

    switch (type) {
        case CRSF_FRAMETYPE_LINK_STATISTICS: {
            if (payload_len < 10) return false;
            data.uplink_rssi_1 = static_cast<int8_t>(payload[0]);
            data.uplink_rssi_2 = static_cast<int8_t>(payload[1]);
            data.uplink_link_quality = payload[2];
            data.uplink_snr = static_cast<int8_t>(payload[3]);
            data.active_antenna = payload[4];
            data.rf_mode = payload[5];
            data.uplink_tx_power = payload[6];
            data.downlink_rssi = static_cast<int8_t>(payload[7]);
            data.downlink_link_quality = payload[8];
            data.downlink_snr = static_cast<int8_t>(payload[9]);
            break;
        }
        case CRSF_FRAMETYPE_GPS: {
            if (payload_len < 15) return false;
            std::memcpy(&data.gps_latitude, payload + 0, 4);
            std::memcpy(&data.gps_longitude, payload + 4, 4);
            std::memcpy(&data.gps_groundspeed, payload + 8, 2);
            std::memcpy(&data.gps_heading, payload + 10, 2);
            std::memcpy(&data.gps_altitude, payload + 12, 2);
            data.gps_satellites = payload[14];
            
            data.gps_latitude = __builtin_bswap32(data.gps_latitude);
            data.gps_longitude = __builtin_bswap32(data.gps_longitude);
            data.gps_groundspeed = __builtin_bswap16(data.gps_groundspeed);
            data.gps_heading = __builtin_bswap16(data.gps_heading);
            data.gps_altitude = __builtin_bswap16(data.gps_altitude);

            if (payload_len >= 19) {
                uint32_t hdop_raw;
                std::memcpy(&hdop_raw, payload + 15, 4);
                data.gps_hdop = __builtin_bswap32(hdop_raw) / 100.0f;
            }
            break;
        }
        case CRSF_FRAMETYPE_BATTERY_SENSOR: {
            if (payload_len < 8) return false;
            std::memcpy(&data.battery_voltage, payload + 0, 2);
            std::memcpy(&data.battery_current, payload + 2, 2);
            data.battery_capacity_used = (payload[4] << 16) | (payload[5] << 8) | payload[6];
            data.battery_remaining = payload[7];
            data.battery_voltage = __builtin_bswap16(data.battery_voltage);
            data.battery_current = __builtin_bswap16(data.battery_current);
            break;
        }
        case CRSF_FRAMETYPE_VARIO: {
            if (payload_len < 2) return false;
            std::memcpy(&data.vario_vertical_speed, payload, 2);
            data.vario_vertical_speed = __builtin_bswap16(data.vario_vertical_speed);
            break;
        }
        case CRSF_FRAMETYPE_ATTITUDE: {
            if (payload_len < 6) return false;
            std::memcpy(&data.attitude_pitch, payload + 0, 2);
            std::memcpy(&data.attitude_roll, payload + 2, 2);
            std::memcpy(&data.attitude_yaw, payload + 4, 2);
            data.attitude_pitch = __builtin_bswap16(data.attitude_pitch);
            data.attitude_roll = __builtin_bswap16(data.attitude_roll);
            data.attitude_yaw = __builtin_bswap16(data.attitude_yaw);
            break;
        }
        case CRSF_FRAMETYPE_FLIGHT_MODE: {
            if (payload_len < 1) return false;
            data.flight_mode = std::string(reinterpret_cast<const char*>(payload), payload_len - 1);
            break;
        }
        case CRSF_FRAMETYPE_AIRSPEED: {
            if (payload_len < 2) return false;
            std::memcpy(&data.airspeed, payload, 2);
            data.airspeed = __builtin_bswap16(data.airspeed);
            break;
        }
        case CRSF_FRAMETYPE_ESC_TELEMETRY: {
            if (payload_len < 2) return false;
            std::memcpy(&data.rpm, payload + 0, 2);
            data.rpm = __builtin_bswap16(data.rpm);
            if (payload_len >= 3) data.esc_temperature = payload[2];
            break;
        }
        case CRSF_FRAMETYPE_FUEL: {
            if (payload_len < 2) return false;
            std::memcpy(&data.fuel_level, payload, 2);
            data.fuel_level = __builtin_bswap16(data.fuel_level);
            break;
        }
        case CRSF_FRAMETYPE_DEVICE_INFO: {
            if (payload_len >= 4) {
                data.mcu_temperature = payload[0];
                data.load = payload[1];
                data.heartbeat_status = payload[2];
                data.arm_status = payload[3];
            }
            break;
        }
        default:
            return false;
    }
    return true;
}

// Expanded print function
inline void print_telemetry(const TelemetryData& data) {
    std::cout << "\033[2J\033[H"; // Clear screen for readability
    std::cout << "--- CRSF Link Telemetry ---" << std::endl;
    std::cout << " 1RSS: " << (int)data.uplink_rssi_1 << " dBm | 2RSS: " << (int)data.uplink_rssi_2 << " dBm" << std::endl;
    std::cout << " LQly: " << (int)data.uplink_link_quality << " %   | SNR:  " << (int)data.uplink_snr << " dB" << std::endl;
    std::cout << " Mode: " << (int)data.rf_mode << " | PWR: " << (int)data.uplink_tx_power << " mW" << std::endl;

    std::cout << "\n--- GPS Telemetry ---" << std::endl;
    std::cout << " Lat: " << data.gps_latitude / 10000000.0 << " | Lon: " << data.gps_longitude / 10000000.0 << std::endl;
    std::cout << " Spd: " << data.gps_groundspeed / 10.0 << " km/h | Alt: " << (int)data.gps_altitude - 1000 << " m" << std::endl;
    std::cout << " Sats: " << (int)data.gps_satellites << " | HDOP: " << data.gps_hdop << std::endl;

    std::cout << "\n--- Battery Telemetry ---" << std::endl;
    std::cout << " Volt: " << data.battery_voltage / 10.0 << " V | Curr: " << data.battery_current / 10.0 << " A" << std::endl;
    std::cout << " Cap:  " << data.battery_capacity_used << " mAh | Rem: " << (int)data.battery_remaining << " %" << std::endl;

    std::cout << "\n--- Attitude & Flight ---" << std::endl;
    std::cout << " Pitch: " << data.attitude_pitch / 10000.0 << " rad" << std::endl;
    std::cout << " Roll:  " << data.attitude_roll / 10000.0 << " rad" << std::endl;
    std::cout << " Mode:  " << data.flight_mode << " | Arm: " << (data.arm_status ? "YES" : "NO") << std::endl;
    std::cout << "------------------------" << std::endl;
}

#endif // CRSF_PARSER_H
