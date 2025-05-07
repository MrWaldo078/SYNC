import fitdecode

def parse_fit_file(filepath):
    records = []

    with fitdecode.FitReader(filepath) as fit:
        for frame in fit:
            if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                if frame.name == "record":
                    record = {}
                    for field in frame.fields:
                        record[field.name] = field.value
                    records.append(record)

    return records