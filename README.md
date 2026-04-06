# Controller Skills Benchmark - Gamepad Testing Application

A Python and pygame-based gamepad testing application suite for measuring reaction time, precision, and coordination skills, suitable for gaming research and user experience evaluation.

## Quick Start

### System Requirements
- Python 3.8+
- macOS 10.14+ or Linux
- Supported gamepad (Joy-Con, PlayStation, Xbox, etc.)

### Installation & Usage
```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/ntu-hci-lab/PartyAssist.git
cd PartyAssist

# Run application (auto-install dependencies)
uv run python main.py

# Run in English
uv run python main.py --english

# Run in Chinese
uv run python main.py
```

## Test Categories

### Button Test Series
1. **Simple Reaction Time Test** - Basic reaction speed measurement  
   ![Simple reaction timeline](imgs/button_simple_reaction_timeline.png)
2. **Prediction Countdown Test** - Time prediction and visual tracking ability  
   ![Prediction countdown timeline](imgs/button_prediction_countdown.png)
3. **Button Smash Test** - Rapid consecutive clicking ability  
   ![Button smash timeline](imgs/button_smash_timeline.png)
4. **Direction Selection Test** - Selective reaction and accuracy  
   ![Direction selection correct](imgs/button_direction_correct.png)  
   ![Direction selection incorrect](imgs/button_direction_incorrect.png)

### Analog Test Series
5. **Analog Stick Movement Test** - Basic joystick control ability  
   ![Analog stick movement](imgs/analog_stick_movement.png)
6. **Path Following Test** - Precise path tracking and fine motor control  
   ![Path following trajectory](imgs/analog_path_follow.png)

### Execution Methods
```bash
# Interactive menu
uv run python main.py

# Run individual tests
uv run python tests/button_reaction_time_test.py --user P1
uv run python tests/analog_move_test.py --user P1

# Gamepad connection test
uv run python common/connection_test.py
```

## Project Structure

```
controller-skills-benchmark/
├── main.py                    # Main application entry
├── tests/                     # Test modules
│   ├── button_*_test.py      # Button test series
│   └── analog_*_test.py      # Analog test series
├── common/                    # Shared modules
│   ├── controller_input.py   # Gamepad input handling
│   ├── result_saver.py       # Result storage
│   └── trace_plot.py         # Trajectory plotting
└── data/                      # Test results and charts
    ├── results/[user_id]/     # JSON results
    └── images/                # PNG trajectory plots
```

## Key Features

- **Colorblind-Friendly Design** - Blue-orange color scheme with high contrast
- **Modular Architecture** - Independent test modules, easy to extend
- **Automatic Result Storage** - JSON format with visualization charts
- **Multi-Gamepad Support** - Joy-Con, PlayStation, Xbox, etc.

## Troubleshooting

### Gamepad Connection Issues
```bash
# Gamepad connection diagnosis
uv run python common/connection_test.py

# Common solutions:
# - Ensure gamepad is connected and paired
# - Re-pair Bluetooth device
# - Check driver installation
```

### System-Related Issues
- macOS may require: `brew install sdl2`
- Linux may require: `apt install python3-tk`

## Development

```bash
# Development mode
uv shell
python main.py

# Install development dependencies
uv add --dev pytest black flake8

# Code formatting and linting
black .
flake8 .
```

## Test Results

All test results are automatically saved in standardized JSON format with accompanying visualization charts for trajectory-based tests. Results are organized by user ID and timestamp for easy analysis and comparison.

## Generate De-identified Test Data

`create_deidentified_test_data.py` is designed to work with the raw JSON and image outputs produced by `main.py` and the individual test scripts. It accepts any of the following as `--source-root`:

- the repository root, when results are stored under `data/results` and `data/images`
- the `data/` directory itself
- a legacy exported root that still contains `data/results` and `data/images`

Example workflow:

```bash
# 1. Run tests and collect raw data
uv run python main.py

# 2. Generate the de-identified bundle from the current repo data/
uv run python create_deidentified_test_data.py

# 3. Or point to a different source/output location explicitly
uv run python create_deidentified_test_data.py --source-root data --output-root /tmp/deidentified_test_data
```

The generated files will be written to `deidentified_test_data/` by default. Before sharing, review the output bundle to make sure it matches the data you intend to publish.

If you regenerate `deidentified_test_data/` from new `main.py` output, you can commit the refreshed de-identified dataset and open a PR back to this repository with the updated files.
