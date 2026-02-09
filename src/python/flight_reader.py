# flight_reader.py - reading and parsing flight status file

import time

def read_flight_data(last_read_time):
    now = time.time()
    if now - last_read_time < 0.05:
        return last_read_time, None

    try:
        with open('/tmp/flight_status.txt', 'r') as f:
            line = f.read().strip()
            if not line:
                return now, None

            parts = line.split()
            data = {}
            for part in parts:
                if ':' in part:
                    k, v = part.split(':', 1)
                    data[k] = v

            return now, data
    except:
        return now, None
