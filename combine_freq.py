import os
import re
import pandas as pd
from collections import defaultdict
from datetime import datetime

# Setup folder path
base_path = os.path.dirname(os.path.abspath(__file__))
raw_data_path = os.path.join(base_path, "raw_data")

# Function to parse filenames
def parse_filename(filename):
    pattern = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})_"  
        r"(?P<device_chemistry>[^-]+)-"  
        r"(?P<device_pixel>[^_]+)_"  
        r"(?P<device_configuration>.+?)-config_"  
        r"(?P<device_degradation>[^_]+)_"  
        r"(?P<frequency_range>[^_]+)_"  
        r"(?P<datapoint_capture>[^_]+)_"  
        r"(?P<voltage_offset>[^_]+)_"  
        r"(?P<voltage_amplitude>[^V]+)Vpk"  
    )
    match = pattern.match(filename)
    if match:
        return match.groupdict()
    return None

# Function to load data from a txt file in raw_data
def load_data(filename):
    filepath = os.path.join(raw_data_path, filename)
    with open(filepath, "r") as file:
        lines = file.readlines()
    
    header_line = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), None)
    df = pd.read_csv(filepath, delim_whitespace=True, comment="#", names=header_line.split("\t"))
    return df

# Combine dataframes, averaging duplicate frequencies
def combine_dataframes(dfs):
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.groupby("Oscilator_frequency (Hz)", as_index=False).mean()
    combined_df.sort_values(by="Oscilator_frequency (Hz)", inplace=True)
    return combined_df

# Function to sum integers in datapoint_capture strings
def sum_datapoint_capture(datapoint_captures):
    total = 0
    for dc in datapoint_captures:
        numbers = re.findall(r"\d+", dc)
        total += sum(int(num) for num in numbers)
    return total

# Function to find the highest number in device_degradation strings
def find_highest_degradation(device_degradations):
    highest = 0
    for dd in device_degradations:
        numbers = re.findall(r"\d+", dd)
        if numbers:
            highest = max(highest, max(int(num) for num in numbers))
    return highest

# Get all .txt files in the directory
txt_files = [f for f in os.listdir(raw_data_path) if f.endswith(".txt")]

# Parse filenames and organize data
parsed_files = {file: parse_filename(file) for file in txt_files if parse_filename(file)}

# Print parsed files for debugging
print("Parsed files:")
for file, characteristics in parsed_files.items():
    print(f"File: {file}, Date: {characteristics['date']}, Frequency Range: {characteristics['frequency_range']}, Datapoint Capture: {characteristics['datapoint_capture']}, Device Degradation: {characteristics['device_degradation']}")

# Group files by relevant characteristics
grouped_files = defaultdict(list)
for file, characteristics in parsed_files.items():
    key = tuple((k, v) for k, v in characteristics.items() if k not in {"frequency_range", "datapoint_capture", "device_degradation", "date"})
    grouped_files[key].append(file)

print("\nGrouped files:")
for key, files in grouped_files.items():
    print(f"Group Key: {key}, Files: {files}")

# Combine data per group
for key, files in grouped_files.items():
    required_ranges = {"500k-5kHz", "5k-200Hz", "200-1Hz"}
    frequency_ranges = [parsed_files[file]["frequency_range"] for file in files]

    print(f"\nGroup Key: {key}")
    print(f"Frequency Ranges: {frequency_ranges}")

    if set(frequency_ranges) == required_ranges:
        print(f"Found required frequency ranges: {required_ranges}")
        dfs = [load_data(file) for file in files]
        combined_df = combine_dataframes(dfs)

        characteristics = dict(key)
        datapoint_captures = [parsed_files[file]["datapoint_capture"] for file in files]
        total_datapoint_capture = sum_datapoint_capture(datapoint_captures)

        dates = [parsed_files[file]["date"] for file in files]
        newest_date = max(dates, key=lambda x: datetime.strptime(x, "%Y-%m-%d"))

        device_degradations = [parsed_files[file]["device_degradation"] for file in files]
        highest_degradation = find_highest_degradation(device_degradations)

        combined_freq_range = "500k-1Hz"

        new_filename = (
            f"{newest_date}_"
            f"{characteristics['device_chemistry']}-{characteristics['device_pixel']}_"
            f"{characteristics['device_configuration']}-config_"
            f"{highest_degradation}daydeg_"
            f"{combined_freq_range}_"
            f"{total_datapoint_capture}p-1s_"
            f"{characteristics['voltage_offset']}_"
            f"{characteristics['voltage_amplitude']}Vpk.txt"
        )

        # Write the new file to current directory
        with open(new_filename, "w") as new_file:
            new_file.write("# " + "\t".join(combined_df.columns) + "\n")
            combined_df.to_csv(new_file, sep="\t", index=False, header=False)

        print(f"Created new file: {new_filename}")
    else:
        print(f"Skipping group: Required frequency ranges not found.")

print("\nProcessing complete.")