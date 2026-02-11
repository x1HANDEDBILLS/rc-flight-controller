import serial
import time
import struct
import random
import statistics
import argparse

# CRSF Constants
CRSF_ADDRESS = 0xC8  # Broadcast addr
CRSF_RC_TYPE = 0x16  # RC channels packet
CHANNEL_BITS = 11
CHANNEL_MASK = (1 << CHANNEL_BITS) - 1  # 0x7FF
MIN_CHANNEL = 172
MAX_CHANNEL = 1811

def crc8_dvb_s2(data: bytes) -> int:
    """Compute DVB-S2 CRC8 for CRSF packet."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0xD5
            else:
                crc <<= 1
            crc &= 0xFF
    return crc

def pack_channels(channels: list[int]) -> bytearray:
    """Pack list of 11-bit channels into bytearray."""
    bits = 0
    bit_count = 0
    output = bytearray()
    for ch in channels:
        bits |= (ch & CHANNEL_MASK) << bit_count
        bit_count += CHANNEL_BITS
        while bit_count >= 8:
            output.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8
    return output

def main(args):
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.01)
        if not ser.is_open:
            raise RuntimeError("Failed to open serial port.")
        ser.reset_input_buffer()
        
        latencies = []
        start_time = time.time()
        end_time = start_time + args.duration
        
        print(f"--- STARTING {args.duration}s STRESS TEST (16CH @ {args.baud} BAUD) ---")
        print("Saturating link... please wait.")

        while time.time() < end_time:
            # Generate random 16-ch data
            channels = [random.randint(MIN_CHANNEL, MAX_CHANNEL) for _ in range(16)]
            payload = pack_channels(channels)
            crc_data = bytearray([CRSF_RC_TYPE]) + payload
            crc = crc8_dvb_s2(crc_data)
            header = bytearray([CRSF_ADDRESS, len(payload) + 2, CRSF_RC_TYPE])  # len = payload + type + crc? Wait, len includes type + payload + crc = 1 + 22 + 1 = 24
            full_packet = header + payload + bytearray([crc])
            
            # Send and Measure
            t0 = time.perf_counter()
            ser.write(full_packet)
            
            # Wait for response
            while ser.in_waiting < len(full_packet):
                if time.perf_counter() - t0 > 0.05:
                    print("Timeout waiting for response.")
                    break
            
            if ser.in_waiting >= len(full_packet):
                response = ser.read(ser.in_waiting)
                # Optional: Validate response == full_packet for echo test
                if response != full_packet:
                    print("Warning: Response mismatch.")
                latencies.append((time.perf_counter() - t0) * 1000)

        if not latencies:
            raise ValueError("No successful packets processed.")

        # --- CALCULATE RESULTS ---
        total_packets = len(latencies)
        avg_lat = statistics.mean(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        std_dev = statistics.stdev(latencies)
        pps = total_packets / args.duration
        total_data_kb = (total_packets * len(full_packet)) / 1024

        print("\n" + "="*40)
        print("      CRSF STRESS TEST RESULTS")
        print("="*40)
        print(f"Test Duration:    {args.duration} seconds")
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

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRSF Hardware Bridge Stress Test")
    parser.add_argument('--port', default='/dev/ttyUSB0', help="Serial port")
    parser.add_argument('--baud', type=int, default=420000, help="Baud rate")
    parser.add_argument('--duration', type=int, default=30, help="Test duration in seconds")
    args = parser.parse_args()
    main(args)