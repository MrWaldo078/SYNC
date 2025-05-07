import struct
import json
from datetime import datetime, timedelta


def parse_kdf_file(filepath, channel_type="RRI"):
    """
    Parses the KDF file and returns a dict of channels. Each channel is:
      { 'type': <type>, 'data': [ {timestamp: datetime, <field>: value}, ... ] }
    """
    parsed_data = {}

    with open(filepath, 'rb') as f:
        # Read file identifier and version
        identifier = f.read(7).decode('ascii')
        _ = f.read(3)

        # Read header size and header
        header_size = struct.unpack('<I', f.read(4))[0]
        header_bytes = f.read(header_size)
        if identifier == "KDFJSON":
            header = json.loads(header_bytes.decode('utf-8'))
        else:
            raise ValueError("Currently only JSON headers are supported.")

        # Determine start time
        start_time_str = header.get('measured_timestamp', header.get('create_timestamp'))
        if not start_time_str:
            raise ValueError("No timestamp found in header.")
        # Parse ISO8601 into datetime
        start_time = datetime.fromisoformat(start_time_str)

        # Normalize channels to list
        channels = header.get('channels', [])
        if isinstance(channels, dict):
            channels = [channels]

        header_end = 14 + header_size

        # Iterate each channel
        for channel in channels:
            label = channel.get('label', 'Unnamed_Channel')
            data_enc = channel['data_enc']
            data_url = channel['data_url']
            data_size = channel['data_size']
            data_start = header_end + data_url

            f.seek(data_start)
            raw = f.read(data_size)

            # JSON list type (Markers)
            if data_enc == "list":
                channel_data = json.loads(raw.decode('utf-8'))
            else:
                # Build struct format
                fmt = '<' + ''.join(ft for _, ft in data_enc)
                size = struct.calcsize(fmt)
                count = channel['total_values']
                points = [struct.unpack_from(fmt, raw, offset=i*size) for i in range(count)]
                names = [fn for fn, _ in data_enc]

                # Handle RR-type with datetime
                if channel['type'] in ('RRI', 'PPI'):
                    current = start_time
                    channel_data = []
                    for pt in points:
                        rr = pt[0]
                        current += timedelta(milliseconds=rr)
                        channel_data.append({
                            'timestamp': current,
                            names[0]: rr
                        })
                else:
                    # Other channels: no timestamps
                    channel_data = [dict(zip(names, pt)) for pt in points]

            parsed_data[label] = {
                'type': channel['type'],
                'data': channel_data
            }

    return parsed_data
