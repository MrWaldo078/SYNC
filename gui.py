import tkinter as tk
from tkinter import filedialog, PhotoImage, ttk
from parser_fit import parse_fit_file
from parser_kdf import parse_kdf_file
from writer_fit import write_fit_with_rr, write_split_fits_pure_python  # import the FIT writer to ensure it’s defined
from sync import sync_rr_to_fit_cpp
from pathlib import Path
import subprocess, tempfile, csv
import threading
import os
from divider import split_multisport_fit

# --- Variables to store file paths and mode ---
garmin_file_path = None
kubios_file_path = None
output_fit_path = None
merged_data = None
mode = 'sync'  # 'sync' or 'multisport'

# --- Helper to shorten long file names ---
def shorten_filename(name, max_length=25):
    return name if len(name) <= max_length else name[:max_length-3] + "..."

# --- File Openers ---
def open_garmin_file():
    global garmin_file_path
    filename = filedialog.askopenfilename(filetypes=[("FIT files", "*.fit")])
    if filename:
        garmin_file_path = filename
        label_garmin.config(text=f"Garmin File: {shorten_filename(Path(filename).name)}")
        print("Garmin FIT file selected:", garmin_file_path)

def open_kubios_file():
    global kubios_file_path
    filename = filedialog.askopenfilename(filetypes=[("KDF files", "*.kdf")])
    if filename:
        kubios_file_path = filename
        label_kubios.config(text=f"Kubios File: {shorten_filename(Path(filename).name)}")
        print("Kubios KDF file selected:", kubios_file_path)

# --- Write FIT with RR ---
def write_fit_with_rr(input_fit, merged, jar_path, output_fit):
    orig_csv = tempfile.mktemp(suffix='.csv')
    subprocess.run(['java', '-jar', jar_path, '-b', input_fit, orig_csv], check=True)
    temp_csv = tempfile.mktemp(suffix='_rr.csv')
    with open(orig_csv, newline='') as inp, open(temp_csv, 'w', newline='') as outp:
        reader = csv.DictReader(inp)
        fieldnames = reader.fieldnames + ['rr_interval_ms']
        writer = csv.DictWriter(outp, fieldnames=fieldnames)
        writer.writeheader()
        field_cols = [h for h in reader.fieldnames if h.lower().startswith('field')]
        rr_map = {rec['rr_timestamp'].strftime('%Y-%m-%d %H:%M:%S'): rec['rr_interval_ms'] for rec in merged}
        for row in reader:
            ts_value = None
            for fcol in field_cols:
                val = row.get(fcol)
                if val and val.strip().lower() == 'timestamp':
                    idx = fcol.split()[-1]
                    vcol = f'Value {idx}'
                    raw = row.get(vcol, '')
                    ts_value = raw.split('.')[0] if raw else None
                    break
            row['rr_interval_ms'] = rr_map.get(ts_value, '')
            writer.writerow(row)
    subprocess.run(['java', '-jar', jar_path, '-c', temp_csv, output_fit], check=True)
    for f in (orig_csv, temp_csv):
        try: Path(f).unlink()
        except: pass
    print(f"Wrote new FIT with RR to {output_fit}")

# --- Save Dialog ---
def choose_output_file():
    global output_fit_path, merged_data
    filename = filedialog.asksaveasfilename(defaultextension='.fit', filetypes=[("FIT files","*.fit")])
    if filename:
        output_fit_path = filename
        label_output.config(text=f"Output File: {shorten_filename(Path(filename).name)}")
        print("Output FIT file will be saved as:", output_fit_path)
        if merged_data:
            jar = Path(__file__).parent / 'FitCSVTool.jar'
            if jar.exists(): write_fit_with_rr(garmin_file_path, merged_data, str(jar), output_fit_path)
            else: print(f"FitCSVTool.jar not found at {jar}")
        else:
            print("Please run Sync first before saving.")

# --- Multisport Split ---
def split_multisport():
    global garmin_file_path, output_fit_path
    if not garmin_file_path:
        return
    if not output_fit_path:
        choose_output_file()
        if not output_fit_path:
            return

    # 1) Figure out how many files we'll write
    result = split_multisport_fit(garmin_file_path)
    total = len(result["sports"]) + len(result.get("transitions", []))
    if total == 0:
        return

    # 2) Configure bar
    progress_bar.config(value=0, maximum=total)

    # 3) Smooth 40% prefill over 5 seconds
    pre_fill_steps = max(1, int(total * 0.4))
    delay_ms = int(5000 / pre_fill_steps)
    remaining_capacity = total - pre_fill_steps

    def do_prefill(count=[0]):
        if count[0] < pre_fill_steps:
            progress_bar.step(1)
            count[0] += 1
            window.after(delay_ms, do_prefill)
        else:
            # as soon as prefill is done, kick off the real split
            threading.Thread(
                target=write_split_fits_pure_python,
                args=(garmin_file_path, output_fit_path, on_progress),
                daemon=True
            ).start()

    # 4) Real progress: each callback adds a fractional step
    def on_progress(_=None, idx=[0]):
        idx[0] += 1
        # each write gets (remaining_capacity / total) units
        increment = remaining_capacity / total
        window.after(0, progress_bar.step, increment)

    # 5) Start the warm-up
    window.after(0, do_prefill)

# --- Processing (in background) ---
def start_process():
    threading.Thread(target=process_records, daemon=True).start()

def process_records():
    global merged_data
    if not garmin_file_path or not kubios_file_path:
        print("Select both Garmin and Kubios files first.")
        return
    fit_records = parse_fit_file(garmin_file_path)
    rr_data = parse_kdf_file(kubios_file_path).get('RRI', {}).get('data', [])
    print(f'Parsed {len(fit_records)} FIT records and {len(rr_data)} RR intervals')
    merged_data = sync_rr_to_fit_cpp(fit_records, rr_data)
    window.after(0, lambda: progress_bar.config(value=0, maximum=len(merged_data)))
    print("\n--- Synced Records ---")
    for rec in merged_data:
        ts, hr, rr = rec['timestamp'], rec.get('heart_rate','–'), rec['rr_interval_ms']
        print(f"{ts}   HR: {hr}   RR: {rr} ms")
        window.after(0, lambda ts=ts: [label_current.config(text=f"Processing: {ts}"), progress_bar.step(1)])
    print(f"Displayed {len(merged_data)} synced records.")
    if output_fit_path:
        jar = Path(__file__).parent / 'FitCSVTool.jar'
        if jar.exists(): write_fit_with_rr(garmin_file_path, merged_data, str(jar), output_fit_path)
        else: print(f"FitCSVTool.jar not found at {jar}")

# --- GUI Setup ---

# Toggle function for mode
def toggle_mode():
    global mode, garmin_file_path, kubios_file_path, output_fit_path, merged_data

    # 0) clear out any previously chosen files
    garmin_file_path = None
    kubios_file_path = None
    output_fit_path  = None
    merged_data      = None
    label_garmin .config(text="No Garmin file loaded")
    label_kubios .config(text="No Kubios file loaded")
    label_output .config(text="No output file selected")

    # 1) switch UI widgets
    if mode == 'sync':
        mode = 'multisport'
        btn_mode.config(text='Mode: Multisport')
        btn_kubios.grid_remove()
        label_kubios.grid_remove()
        btn_start.grid_remove()
        btn_split.grid(row=8, column=0, columnspan=2, pady=10, sticky='ew')
    else:
        mode = 'sync'
        btn_mode.config(text='Mode: Synchronize')
        btn_kubios.grid(row=2, column=1, padx=10, pady=10, sticky='ew')
        label_kubios.grid(row=3, column=1, padx=10)
        btn_split.grid_remove()
        btn_start.grid(row=7, column=0, columnspan=2, pady=20, sticky='ew')
# Build the window
window = tk.Tk()
window.title("Polar-Garmin Synchronizer")

logo = PhotoImage(file="assets/logo.png")
tk.Label(window, image=logo).grid(row=1, column=0, columnspan=2, pady=20)

window.rowconfigure(list(range(9)), minsize=40)
window.columnconfigure([0,1], weight=1)

# Buttons and widgets
btn_mode = tk.Button(window, text='Mode: Synchronize', command=toggle_mode)
btn_mode.grid(row=0, column=0, columnspan=2, pady=5, sticky='ew')

btn_split = tk.Button(window, text="Split Multisport", command=split_multisport)
btn_split.grid(row=8, column=0, columnspan=2, pady=10, sticky='ew')
btn_split.grid_remove()  # hide in sync mode

btn_garmin = tk.Button(window, text="Load Garmin FIT File", command=open_garmin_file)
btn_garmin.grid(row=2, column=0, padx=10, pady=10, sticky='ew')
btn_kubios = tk.Button(window, text="Load Polar KDF File", command=open_kubios_file)
btn_kubios.grid(row=2, column=1, padx=10, pady=10, sticky='ew')

label_garmin = tk.Label(window, text="No Garmin file loaded", width=30, anchor='w', wraplength=200)
label_garmin.grid(row=3, column=0, padx=10)
label_kubios = tk.Label(window, text="No Kubios file loaded", width=30, anchor='w', wraplength=200)
label_kubios.grid(row=3, column=1, padx=10)

progress_bar = ttk.Progressbar(window, orient="horizontal", mode="determinate")
progress_bar.grid(row=4, column=0, columnspan=2, padx=20, pady=10, sticky='ew')

label_current = tk.Label(window, text="", font=(None, 10), anchor='center')
label_current.grid(row=5, column=0, columnspan=2)

btn_output = tk.Button(window, text="Choose Output FIT Location", command=choose_output_file)
btn_output.grid(row=6, column=0, padx=10, pady=10, sticky='ew')
label_output = tk.Label(window, text="No output file selected", width=30, anchor='w', wraplength=200)
label_output.grid(row=6, column=1, padx=10)

btn_start = tk.Button(window, text="Synchronize", command=start_process)
btn_start.grid(row=7, column=0, columnspan=2, pady=20, sticky='ew')

window.geometry("420x520")
window.mainloop()