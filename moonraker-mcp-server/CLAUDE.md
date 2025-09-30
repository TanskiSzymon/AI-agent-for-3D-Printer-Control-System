## CLAUDE.md
```markdown
# Moonraker MCP Server - Claude Integration Guide

## Overview

This MCP server allows you to control Creality K1 Max 3D printers through natural language. The server communicates with printers running Moonraker firmware via REST API.

## Available Tools

### 🔍 get_printer_status
Returns current printer state including:
- Busy/Ready status
- Print progress percentage
- Current filename being printed
- Hotend and bed temperatures (current/target)

### 📁 list_files
Lists available G-code files on the printer in JSON format with:
- Root directory
- Current working directory
- Array of printable files

### ⚡ start_print
Starts printing WITHOUT bed leveling (faster start):
- Validates filename format
- Automatically disables adaptive bed mesh
- Refuses if already printing

### 🎯 start_print_with_leveling
Starts printing WITH bed leveling (more precise):
- Same validation as start_print
- Enables adaptive bed mesh before printing
- Use for first print of the day or precision prints

### 🧹 set_purge_line
Controls purge line (nozzle cleaning before print):
- `state="off"` - Disable purge line (saves time and filament)
- `state="on"` - Enable purge line (cleaner first layer)
- Note: Uses inverted logic (off=1, on=0) for ADAPTIVE_PURGE_LINE pin

### ⏸️ pause_print
Pauses the current print job immediately

### ▶️ resume_print
Resumes a paused print job

### ⏹️ stop_print
Cancels the current print job completely

### 💡 control_light
Controls chamber LED lighting:
- `state="on"` - Turn chamber light on
- `state="off"` - Turn chamber light off
- Uses SET_PIN PIN=LED command

## Usage Patterns

### Basic Status Check
"What's the status of my printer?"
- Returns formatted status with temperatures and progress

### Starting a Print (Fast - No Leveling)
"Start printing calibration_cube.gcode"
- Disables bed leveling for quick start
- Best for subsequent prints when bed is already leveled

### Starting a Print (Precise - With Leveling)
"Start printing with leveling important_part.gcode"
- Performs bed mesh calibration
- Best for first print or critical parts

### Controlling Print Settings
"Turn off purge line" → "Start printing test.gcode"
- Disable purge line to save time/filament
- Then start print without initial purge

### Managing Active Prints
"Pause the print" → "Resume the print" → "Stop the print"
- Simple commands for print control

### Multiple Printers
"Check status of bedroom printer"
"Start print on 192.168.1.12"
- Resolves printer by IP, name, or substring

## Error Handling

The server provides user-friendly error messages:
- "Printer is busy" when trying to start during print
- "File not found" for invalid files
- "No printer found" when selector doesn't match
- Clear HTTP error codes when API fails

## Response Formats

### Status Response
🖨️ printer_name Status:
State: READY/BUSY
Progress: 45.2%
File: benchy.gcode
Hotend: 215.3°C / 220.0°C
Bed: 59.8°C / 60.0°C

### File List Response
Minimal JSON string:
```json
{"root":"/","cwd":"/","items":["benchy.gcode","cube.gcode"]}
Action Responses

Success: "🟢 Printing 'filename.gcode' started (no leveling)"
Success: "✅ Purge line disabled (no purge line)"
Error: "Error: Printer is busy (printing). Use 'pause_print' or 'stop_print' first"

Best Practices

Always check status first before starting prints
Use descriptive filenames to avoid confusion
First print of session - use start_print_with_leveling
Subsequent prints - use start_print for speed
Disable purge line when printing multiple small parts
Monitor temperatures during critical prints
Handle busy states - suggest pause/stop when needed

Integration Notes
Printer Heating

Printer may take 30-60 seconds to heat up
The server handles this gracefully
Users will see "Drukarka się rozgrzewa" message

Adaptive Settings
The server controls two adaptive features:

ADAPTIVE_BED_MESH: Bed leveling (0=off, 1=on)
ADAPTIVE_PURGE_LINE: Purge line (1=off, 0=on) - inverted logic!

File Selection Fallback
If direct print start fails, server automatically:

Selects the file first
Then starts the print
This handles different Moonraker configurations

Configuration Notes

Supports multiple printers via environment variables
Auto-detects single vs multi-printer setups
Validates all inputs for safety
Redacts API keys in logs
Provides soft-probe on startup for diagnostics

Limitations

Cannot modify printer firmware settings
Cannot upload new G-code files
Cannot access printer webcam (yet)
Requires network access to Moonraker API
Some printers may use different G-code commands

Troubleshooting Commands
If issues arise, try these diagnostic steps:

"Get printer status" - Basic connectivity test
"List files" - Verify API access
"Control light on" - Test command execution
Check Docker logs for connection details