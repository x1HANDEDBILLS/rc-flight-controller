import serial
import time
import struct
import random
import statistics

# --- CONFIG ---
PORT = '/dev/ttyUSB0'
BAUD = 420000
TEST_DURATION = 30  # Seconds

def crc8_dvb_s2(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80: crc = (crc << 1) ^ 0xD5
            else: crc <<= 1
            crc &= 0xFF
    return crc

def pack_channels(channels):
    bits = 0
    bit_count = 0
    output = bytearray()
    for ch in channels:
        bits |= (ch & 0x7FF) << bit_count
        bit_count += 11
        while bit_count >= 8:
            output.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8
    return output

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.01)
        ser.reset_input_buffer()
        
        latencies = []
        start_time = time.time()
        end_time = start_time + TEST_DURATION
        
        print(f"--- STARTING 30s STRESS TEST (16CH @ {BAUD} BAUD) ---")
        print("Saturating link... please wait.")

        while time.time() < end_time:
            # Generate random 16-ch data
            channels = [random.randint(172, 1811) for _ in range(16)]
            payload = pack_channels(channels)
            header = bytearray([0xC8, 24, 0x16])
            full_packet = header + payload + bytearray([crc8_dvb_s2(bytearray([0x16]) + payload)])
            
            # Send and Measure
            t0 = time.perf_counter()
            ser.write(full_packet)
            
            while ser.in_waiting < 26:
                if time.perf_counter() - t0 > 0.05: break
            
            if ser.in_waiting >= 26:
                ser.read(ser.in_waiting)
                latencies.append((time.perf_counter() - t0) * 1000)

        # --- CALCULATE RESULTS ---
        total_packets = len(latencies)
        avg_lat = statistics.mean(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        std_dev = statistics.stdev(latencies)
        pps = total_packets / TEST_DURATION
        total_data_kb = (total_packets * 26) / 1024

        print("\n" + "="*40)
        print("      CRSF STRESS TEST RESULTS")
        print("="*40)
        print(f"Test Duration:    {TEST_DURATION} seconds")
        print(f"Total Packets:    {total_packets}")
        print(f"Total Data:       {total_data_kb:.2f} KB")
        print(f"Throughput:       {pps:.2f} pkts/sec")
        print("-" * 40)
        print(f"Min Latency:      {min_lat:.3f} ms")
        print(f"Max Latency:      {max_lat:.3f} ms")
        print(f"Avg Latency:      {avg_lat:.3f} ms")
        print(f"Jitter (StdDev):  {std_dev:.3f} ms")
        print("="*40)

        if max_lat > 10:
            print("ADVICE: High max latency detected. Close other apps on the Pi.")
        else:
            print("ADVICE: Connection is ultra-stable. Ready for flight.")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        ser.close()

if __name__ == "__main__":
    main()