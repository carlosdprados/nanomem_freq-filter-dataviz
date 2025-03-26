import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re

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

# Function to load data from a txt file
def load_data(filename):
    full_path = os.path.join(raw_data_path, filename)
    with open(full_path, "r") as file:
        lines = file.readlines()

    header_line = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), None)
    df = pd.read_csv(full_path, delim_whitespace=True, comment="#", names=header_line.split("\t"))
    return df

# Get all .txt files in the directory
txt_files = [f for f in os.listdir(raw_data_path) if f.endswith(".txt")]

# Parse filenames and organize data
parsed_files = {file: parse_filename(file) for file in txt_files if parse_filename(file)}

def group_data():
    grouped_data = {}

    for file, metadata in parsed_files.items():
        # Group by all metadata except a few
        key = tuple(metadata[k] for k in metadata if k not in [
            "device_chemistry", "date", "device_degradation", "device_pixel", "voltage_amplitude"
        ])
        df = load_data(file)
        df["voltage_amplitude"] = float(metadata["voltage_amplitude"])
        df["device_chemistry"] = metadata["device_chemistry"]

        df["Normalized_Vout (%)"] = (df["Demod_4_X_A (V)"] / (df["voltage_amplitude"] / 1.4142)) * 100

        if key in grouped_data:
            grouped_data[key].append(df)
        else:
            grouped_data[key] = [df]

    # === Compute mean and std ===
    grouped_results = {}
    for key, dfs in grouped_data.items():
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df["Oscilator_frequency (Hz)"] = pd.to_numeric(combined_df["Oscilator_frequency (Hz)"], errors="coerce")

        numeric_cols = combined_df.select_dtypes(include=["number"]).columns

        mean_df = combined_df.groupby(["device_chemistry", "voltage_amplitude", "Oscilator_frequency (Hz)"])[numeric_cols].mean()
        std_df = combined_df.groupby(["device_chemistry", "voltage_amplitude", "Oscilator_frequency (Hz)"])[numeric_cols].std()

        grouped_results[key] = (mean_df, std_df)

    return grouped_results

grouped_results = group_data()

# Streamlit UI
# Optional title
# st.title("Vout (V) vs Frequency (Hz) Graph")

# Create two tabs
tab_chemistry, tab_voltage = st.tabs(["Tab Chemistry", "Tab Voltage"])

# Extract unique voltage offsets and device configurations from parsed files
available_voltage_offsets = sorted(list(set(metadata["voltage_offset"] for metadata in parsed_files.values())))
available_device_configurations = sorted(list(set(metadata["device_configuration"] for metadata in parsed_files.values())))

# Add a filter for voltage_offset
selected_voltage_offset = st.sidebar.radio(
    "Select Voltage Offset:", 
    available_voltage_offsets, 
    key="voltage_offset_filter"
)

# Add a filter for device_configuration
selected_device_configuration = st.sidebar.radio(
    "Select Device Configuration:", 
    available_device_configurations, 
    key="device_configuration_filter"
)

# Filter unique_keys based on the selected voltage_offset and device_configuration
filtered_keys = [
    key for key in grouped_results.keys() 
    if any(
        metadata["voltage_offset"] == selected_voltage_offset 
        and metadata["device_configuration"] == selected_device_configuration
        for file, metadata in parsed_files.items() 
        if key == tuple(metadata[k] for k in metadata if k not in ["device_chemistry", "date", "device_degradation", "device_pixel", "voltage_amplitude"])
    )
]

# Dropdown for selecting a device configuration (shared across tabs)
selected_key = st.sidebar.selectbox(
    "Select a Device Configuration", 
    filtered_keys, 
    key="device_configuration_dropdown"
)

# Add a checkbox to toggle error bars
show_error_bars = st.sidebar.checkbox("Show Error Bars", value=True, key="error_bars_toggle")

# Define the required frequency ranges
required_frequency_ranges = {"500k-5kHz", "5k-200Hz", "200-1Hz"}

# Group files by metadata (excluding 'date', 'device_degradation', 'datapoint_capture', and 'frequency_range')
# Also, track which groups have the required frequency ranges
grouped_files = {}
group_combine_frequencies = {}  # Dictionary to track which groups can combine frequencies

for file, metadata in parsed_files.items():
    # Create a key based on the relevant metadata
    key = tuple(metadata[k] for k in metadata if k not in ["date", "device_degradation", "datapoint_capture", "frequency_range"])
    
    # Add the file to the corresponding group
    if key in grouped_files:
        grouped_files[key].append(file)
    else:
        grouped_files[key] = [file]


if selected_key:
    mean_df, std_df = grouped_results[selected_key]
    
    # Extract unique device chemistries and voltage amplitudes
    available_chemistries = mean_df.index.get_level_values("device_chemistry").unique()
    available_voltages = mean_df.index.get_level_values("voltage_amplitude").unique()

    # Tab Chemistry
    with tab_chemistry:
        # Optional title
        # st.header("Tab Chemistry: Overlay by Device Chemistry")
        
        # Multiselect for choosing device chemistries
        selected_chemistries = st.multiselect(
            "Choose Device Chemistry:", 
            available_chemistries, 
            default=[available_chemistries[0]],  # Default to the first chemistry
            key="chemistry_multiselect"
        )
    
        # Display voltage amplitude selection as buttons
        selected_voltage = st.radio("Choose Voltage Amplitude:", available_voltages, key="chemistry_voltage")
    
        # Dropdown for selecting Y-axis variable
        x_column = "Oscilator_frequency (Hz)"
        default_y_column = "Demod_4_X_A (V)"
        filtered_columns = [col for col in mean_df.columns if not (col.startswith("Demod_1") or col.startswith("DemodAll"))]
        y_column = st.selectbox("Select Y-axis Variable", filtered_columns, index=filtered_columns.index(default_y_column) if default_y_column in filtered_columns else 0, key="chemistry_y_column")
    
        # Checkbox for logarithmic x-axis
        use_log_scale = st.checkbox("Use Logarithmic X-axis", value=False, key="chemistry_log_scale")
    
        # Create a Plotly figure
        fig_chemistry = px.scatter()
    
        # Add traces for each selected device chemistry
        for chemistry in selected_chemistries:
            # Filter data for selected chemistry and voltage
            mean_df_selected = mean_df.xs((chemistry, selected_voltage), level=["device_chemistry", "voltage_amplitude"])
            std_df_selected = std_df.xs((chemistry, selected_voltage), level=["device_chemistry", "voltage_amplitude"])
    
            # Add trace to the figure
            fig_chemistry.add_scatter(
                x=mean_df_selected[x_column],
                y=mean_df_selected[y_column],
                error_y=dict(
                    array=std_df_selected[y_column] if show_error_bars else None,  # Toggle error bars
                    visible=show_error_bars  # Toggle error bar visibility
                ),
                mode="markers+lines",
                name=f"{chemistry} ({selected_voltage} Vpk)",
                line=dict(width=2),
                marker=dict(size=8)
            )
    
        # Update layout for better visualization
        fig_chemistry.update_layout(
            title=f"{y_column} vs {x_column} (Voltage Amplitude: {selected_voltage} Vpk)",
            xaxis_title="Frequency (Hz)",
            yaxis_title=y_column,
            legend_title="Device Chemistry",
            showlegend=True
        )
    
        # Set x-axis to logarithmic if the checkbox is checked
        if use_log_scale:
            fig_chemistry.update_xaxes(type="log")
    
        # Show graph
        st.plotly_chart(fig_chemistry, use_container_width=True)
    
    # Tab Voltage
    with tab_voltage:
        # Optional title
        # st.header("Tab Voltage: Overlay by Voltage Amplitude")
        
        # Radio buttons for selecting device chemistry
        selected_chemistry = st.radio(
            "Choose Device Chemistry:", 
            available_chemistries, 
            key="voltage_chemistry"
        )
    
        # Multiselect for choosing voltage amplitudes
        selected_voltages = st.multiselect(
            "Choose Voltage Amplitude:", 
            available_voltages, 
            default=[available_voltages[0]],  # Default to the first voltage
            key="voltage_multiselect"
        )
    
        # Dropdown for selecting Y-axis variable
        y_column_voltage = st.selectbox("Select Y-axis Variable", filtered_columns, index=filtered_columns.index(default_y_column) if default_y_column in filtered_columns else 0, key="voltage_y_column")
    
        # Checkbox for logarithmic x-axis
        use_log_scale_voltage = st.checkbox("Use Logarithmic X-axis", value=False, key="voltage_log_scale")
    
        # Create a Plotly figure
        fig_voltage = px.scatter()
    
        # Add traces for each selected voltage amplitude
        for voltage in selected_voltages:
            # Filter data for selected chemistry and voltage
            mean_df_selected = mean_df.xs((selected_chemistry, voltage), level=["device_chemistry", "voltage_amplitude"])
            std_df_selected = std_df.xs((selected_chemistry, voltage), level=["device_chemistry", "voltage_amplitude"])
    
            # Add trace to the figure
            fig_voltage.add_scatter(
                x=mean_df_selected[x_column],
                y=mean_df_selected[y_column_voltage],
                error_y=dict(
                    array=std_df_selected[y_column_voltage] if show_error_bars else None,  # Toggle error bars
                    visible=show_error_bars  # Toggle error bar visibility
                ),
                mode="markers+lines",
                name=f"{selected_chemistry} ({voltage} Vpk)",
                line=dict(width=2),
                marker=dict(size=8)
            )
    
        # Update layout for better visualization
        fig_voltage.update_layout(
            title=f"{y_column_voltage} vs {x_column} (Device Chemistry: {selected_chemistry})",
            xaxis_title="Frequency (Hz)",
            yaxis_title=y_column_voltage,
            legend_title="Voltage Amplitude",
            showlegend=True
        )
    
        # Set x-axis to logarithmic if the checkbox is checked
        if use_log_scale_voltage:
            fig_voltage.update_xaxes(type="log")
    
        # Show graph
        st.plotly_chart(fig_voltage, use_container_width=True)