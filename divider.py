from fitparse import FitFile
from datetime import datetime
from collections import defaultdict

def split_multisport_fit(fit_path):
    """
    Splits a multisport .fit file into sport segments + transition events.
    
    Returns a dict with:
      - 'sports': list of dicts { 'sport': <Sport>, 'start': <datetime>, 'end': <datetime or None>, 'messages': [FitMessage,...] }
      - 'transitions': [FitMessage,...]
    """
    fitfile = FitFile(fit_path)

    # 1) Read all session messages to get sport & start times
    sessions = []
    for session in fitfile.get_messages('session'):
        data = {f.name: f.value for f in session}
        sessions.append({
            'sport': data.get('sport'),
            'start': data.get('start_time'),
            # we'll infer end time from the next session
        })
    # sort by start time
    sessions.sort(key=lambda s: s['start'])
    for i in range(len(sessions) - 1):
        sessions[i]['end'] = sessions[i+1]['start']
    sessions[-1]['end'] = None

    # 2) Bucket all messages by timestamp into each sport segment
    sports_segments = []
    for sess in sessions:
        bucket = []
        for msg in fitfile.get_messages():
            # most messages have a 'timestamp' field
            ts_field = next((f for f in msg if f.name=='timestamp'), None)
            if ts_field is None or ts_field.value is None:
                continue
            ts = ts_field.value
            if ts >= sess['start'] and (sess['end'] is None or ts < sess['end']):
                bucket.append(msg)
        sports_segments.append({
            'sport': sess['sport'],
            'start': sess['start'],
            'end': sess['end'],
            'messages': bucket
        })

    # 3) Extract all transition events
    transitions = []
    for msg in fitfile.get_messages('event'):
        ev = {f.name: f.value for f in msg}
        if ev.get('event_type') == 'transition':
            transitions.append(msg)

    return {
        'sports': sports_segments,
        'transitions': transitions
    }