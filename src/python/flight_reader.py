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
            data = {
                'latency_ms': 0.0,
                'rate_hz': 0.0,
                'connected': 0,
                'channels': [0] * 16,
                'tuned_signals': [0] * 23,
                'raw_signals': [0] * 23
            }
            for part in parts:
                if ':' in part:
                    k, v = part.split(':', 1)
                    try:
                        if k == 'latency_ms':
                            data['latency_ms'] = float(v)
                        elif k == 'rate_hz':
                            data['rate_hz'] = float(v)
                        elif k == 'connected':
                            data['connected'] = int(v)
                        elif k.startswith('ch'):
                            idx = int(k[2:]) - 1  # ch1 -> idx 0
                            if 0 <= idx < 16:
                                data['channels'][idx] = int(v)
                        elif k.startswith('tunedid'):
                            idx = int(k.replace('tunedid', ''))
                            if 0 <= idx < 23:
                                data['tuned_signals'][idx] = int(v)
                        elif k.startswith('rawid'):
                            idx = int(k.replace('rawid', ''))
                            if 0 <= idx < 23:
                                data['raw_signals'][idx] = int(v)
                    except ValueError:
                        # Silently ignore parse errors for individual fields
                        pass

            return now, data
    except FileNotFoundError:
        return now, None
    except Exception:
        return now, None
