import serial
import time

def pack_crsf_channels(channels):
    buffer = bytearray(22)
    bit_buf, bit_count, pos = 0, 0, 0
    for ch in channels:
        bit_buf |= (ch & 0x7FF) << bit_count
        bit_count += 11
        while bit_count >= 8:
            buffer[pos] = bit_buf & 0xFF
            bit_buf >>= 8
            bit_count -= 8
            pos += 1
    return buffer

def unpack_crsf_channels(payload):
    channels = [0] * 16
    bit_buf, bit_count, pos = 0, 0, 0
    for i in range(16):
        while bit_count < 11:
            bit_buf |= payload[pos] << bit_count
            pos += 1
            bit_count += 8
        channels[i] = bit_buf & 0x7FF
        bit_buf >>= 11
        bit_count -= 11
    return channels

def crc8_dvb_s2(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80: crc = (crc << 1) ^ 0xD5
            else: crc <<= 1
            crc &= 0xFF
    return crc

try:
    ser = serial.Serial('/dev/ttyUSB0', 420000, timeout=0.1)
    print("\n--- CRSF VALIDATION TEST RUNNING ---")
    
    while True:
        target = int(1024 + 500 * (time.time() % 2 - 1))
        tx_ch = [1024] * 16 
        tx_ch[2] = target
        
        # Send
        payload = pack_crsf_channels(tx_ch)
        frame = bytearray([0xC8, 24, 0x16]) + payload
        frame += bytearray([crc8_dvb_s2(frame[2:])])
        ser.write(frame)
        
        # Read back
        time.sleep(0.02)
        if ser.in_waiting >= 26:
            rx = ser.read(ser.in_waiting)
            if rx[0] == 0xC8:
                rx_ch = unpack_crsf_channels(rx[3:25])
                print(f"MATCH: Sent {target} -> Received {rx_ch[2]}")
            else:
                print("Checking for Sync...")
        else:
            print("Waiting for data... (Check Green/White twist)")
            
        time.sleep(0.1)
        
except KeyboardInterrupt:
    ser.close()
    print("\nStopped.")
