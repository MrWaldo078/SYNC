import csv
import subprocess
import tempfile
import glob
from pathlib import Path
from divider import split_multisport_fit

from datetime import datetime
from typing import Callable
from fitparse import FitFile as FitParseFile
from fit_tool.fit_file import FitFile as FitToolFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.profile_type import FileType, Manufacturer
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.event_message import EventMessage


def write_fit_with_rr(input_fit: str,
                      merged: list[dict],
                      jar_path: str,
                      output_fit: str):
    """
    Embeds RR intervals into a new .fit file via Garmin's FitCSVTool.jar.
    """
    orig_csv = tempfile.mktemp(suffix=".csv")
    subprocess.run([
        "java", "-jar", jar_path,
        "-o", orig_csv,
        input_fit
    ], check=True)

    rr_map = {rec['rr_timestamp'].isoformat(): rec['rr_interval_ms'] for rec in merged}
    temp_csv = tempfile.mktemp(suffix="_rr.csv")
    with open(orig_csv, newline='') as inp, open(temp_csv, 'w', newline='') as outp:
        reader = csv.DictReader(inp)
        fieldnames = reader.fieldnames + ["rr_interval_ms"]
        writer = csv.DictWriter(outp, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            row["rr_interval_ms"] = rr_map.get(row.get("timestamp", ''), "")
            writer.writerow(row)

    subprocess.run([
        "java", "-jar", jar_path,
        "-t", "fit",
        "-o", output_fit,
        temp_csv
    ], check=True)

    for f in (orig_csv, temp_csv):
        try:
            Path(f).unlink()
        except OSError:
            pass
    print(f"Wrote new FIT with RR to {output_fit}")


def write_split_fits_pure_python(
    input_fit:      str,
    output_fit_path:str,
    on_progress: Callable[[], None] = lambda: None
):
    """
    Splits a multisport .fit file into separate files for each sport segment
    and each transition event. Ensures unique filenames by appending a counter
    if a name is reused.
    """
    result      = split_multisport_fit(input_fit)
    sessions    = result["sports"]
    transitions = result.get("transitions", [])

    ft = FitToolFile.from_file(input_fit)
    all_records = [rw.message for rw in ft.records if isinstance(rw.message, RecordMessage)]

    out_p   = Path(output_fit_path)
    out_dir = out_p.parent
    base    = out_p.stem
    ext     = out_p.suffix or ".fit"

    # Track how many times each suffix has been used
    name_counts = {}

    def build_and_write(msgs, raw_suffix):
        # Increment count
        count = name_counts.get(raw_suffix, 0) + 1
        name_counts[raw_suffix] = count
        # Determine final suffix
        suffix = f"{raw_suffix}{count}" if count > 1 else raw_suffix
        out_file = out_dir / f"{base}_{suffix}{ext}"

        fid = FileIdMessage()
        fid.type          = FileType.ACTIVITY
        fid.manufacturer  = Manufacturer.DEVELOPMENT.value
        fid.product       = 0
        fid.time_created  = round(datetime.now().timestamp() * 1000)
        fid.serial_number = 0x12345678

        builder = FitFileBuilder(auto_define=True, min_string_size=50)
        builder.add(fid)
        builder.add_all(msgs)
        new_fit = builder.build()
        new_fit.to_file(str(out_file))
        print(f"Wrote: {out_file}")

    # Write sport segments
    for seg in sessions:
        start_ms = int(seg["start"].timestamp() * 1000)
        end_ms   = int(seg["end"].timestamp() * 1000) if seg["end"] else None
        recs = [r for r in all_records if r.timestamp >= start_ms and (end_ms is None or r.timestamp < end_ms)]
        raw_suffix = str(seg["sport"]).lower().replace(" ", "_")
        build_and_write(recs, raw_suffix)
        on_progress()

    # Write transitions
    for idx, trans_msg in enumerate(transitions, start=1):
        raw_suffix = f"transition{idx}"
        build_and_write([trans_msg], raw_suffix)
        on_progress()
