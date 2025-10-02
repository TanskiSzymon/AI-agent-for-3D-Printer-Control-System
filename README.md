# Moonraker MCP Server + n8n Queue for Creality K1 Max

Semi-automated printing pipeline for **Creality K1 Max** built around:
- a custom **MCP (Model Context Protocol) server** that exposes Moonraker controls as tools,
- **n8n** orchestration (CRON + Telegram triggers),
- a **Google Sheets** print queue,
- **Klipper/KAMP** macros for custom purge and post-print auto-eject.

> **Beta disclaimer**
>
> - Use at your own risk.
> - Auto-eject is unreliable for very low-height parts and requires **~80 mm** free space at the **rear** of the build plate.
> - Collisions and mis-detections can happen if you ignore the above.


### Oto film:

<iframe
  width="100%"
  height="500"
  src="https://www.youtube.com/embed/yE1FC6HocyQ"
  title="YouTube video"
  frameborder="0"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>



---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Repository Layout](#repository-layout)
- [Requirements](#requirements)
- [Installation & Setup](#installation--setup)
  - [1. Printer (Klipper/Moonraker/KAMP)](#1-printer-klippermoonrakerkamp)
  - [2. MCP Server (Docker build + secrets)](#2-mcp-server-docker-build--secrets)
  - [3. MCP Registry & Catalog](#3-mcp-registry--catalog)
  - [4. MCP Gateway (Claude Desktop / CLI)](#4-mcp-gateway-claude-desktop--cli)
  - [5. n8n (CRON, Telegram, Google Sheets)](#5-n8n-cron-telegram-google-sheets)
  - [6. Cloudflare Zero Trust (optional)](#6-cloudflare-zero-trust-optional)
- [Klipper/KAMP Configuration (Purge & Auto-Eject)](#klipperkamp-configuration-purge--autoeject)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Demo Video](#demo-video)
- [Diagrams](#diagrams)
- [Links & Resources](#links--resources)
- [License](#license)

---

## Overview

This project links a K1 Max (Klipper/Moonraker) to an orchestration layer:
- **MCP server** exposes printer operations as structured tools (status, list files, start/stop, purge line, light).
- **n8n** runs scheduled prints from **Google Sheets** or executes **Telegram** commands.
- **Klipper/KAMP** macros customize purge behavior and sweep parts off the plate post-print.

---

## System Architecture
[Klipper + Moonraker (K1 Max)]
↑ REST (Moonraker API)
[Moonraker MCP Server (Docker)]
↑ stdio / SSE
[MCP Gateway] ←→ [n8n Orchestration] ←→ [Google Sheets Queue]
↑
(Telegram / Schedule Trigger)


---

## Features

- **Printer control**: status (READY/BUSY, temps, progress), list `.gcode`, start with/without leveling, purge line on/off, pause/resume/stop, chamber light on/off.
- **Queue management**: Google Sheets as source of truth; CRON picks next job by `priority`, progress, then FIFO; increments `qty_done` on successful start.
- **Klipper/KAMP integration**: alternative purge sequence; post-print auto-eject sweep.

---

## Repository Layout

> The repo contains full code, macros and config fragments referenced below.

/moonraker-mcp-server/
├─ moonraker_server.py # MCP server (Python): tools for Moonraker
├─ requirements.txt # mcp[cli] >= 1.2.0, httpx
└─ Dockerfile # builds mcp/moonraker:latest

~/.docker/mcp/
├─ registry.yaml # MCP gateway registry
├─ catalogs/
│ ├─ docker-mcp.yaml # base catalog (incl. 'moonraker' server entry)
│ └─ custom.yaml # your overrides/extensions
├─ config.yaml
├─ tools.yaml
└─ secrets.yaml


---

## Requirements

- Creality **K1 Max** with **Klipper + Moonraker** (REST reachable).
- **KAMP** installed.
- **Docker**.
- **n8n** (local or Docker).
- **Google Sheets** access (and n8n credentials).
- **MCP Gateway** (Claude Desktop or CLI).
- (Optional) **Cloudflare Zero Trust** to publish n8n behind your domain.

---

## Installation & Setup

### 1. Printer (Klipper/Moonraker/KAMP)

- Ensure Moonraker/REST is reachable:
  ```bash
  curl "http://PRINTER_IP:PORT/server/files/list"
  curl -X POST "http://PRINTER_IP:PORT/printer/gcode/script" \
    -H "Content-Type: application/json" \
    -d '{"script":"G28"}'
Install KAMP.

Add/adjust macros as in Klipper/KAMP Configuration
.

If a KAMP file is read-only, copy it under a new name and change the relevant [include ...] (e.g. swap Start_Print.cfg → Start_Print2.cfg in KAMP_Settings.cfg).

2. MCP Server (Docker build + secrets)

From the project folder:
cd /Users/youruser/moonraker-mcp-server
docker build -t mcp/moonraker:latest .
Set Moonraker endpoint and key:
docker mcp secret set PRINTER_URL="http://192.168.1.12:4409"
docker mcp secret set API_KEY="your-api-key"

The server supports a single printer via PRINTER_URL/API_KEY or multiple via PRINTER_URLS, API_KEYS, PRINTER_NAMES.

3. MCP Registry & Catalog

~/.docker/mcp/registry.yaml:
catalog:
  - catalogs/docker-mcp.yaml
  - catalogs/custom.yaml
config: config.yaml
tools: tools.yaml
secrets: secrets.yaml
~/.docker/mcp/catalo gs/docker-mcp.yaml (server entry):

moonraker:
  description: "Control Creality K1 Max 3D printers via Moonraker API"
  title: "Moonraker Printer Control"
  type: server
  image: mcp/moonraker:latest
  tools:
    - name: get_printer_status
    - name: list_files
    - name: start_print
    - name: start_print_with_leveling
    - name: set_purge_line
    - name: pause_print
    - name: resume_print
    - name: stop_print
    - name: control_light
  secrets:
    - name: PRINTER_URL
      env: PRINTER_URL
    - name: API_KEY
      env: API_KEY
Keep your changes in custom.yaml to survive updates.

4. MCP Gateway (Claude Desktop / CLI)

Claude Desktop (macOS) example (claude_desktop_config snippet):
{
  "mcpServers": {
    "mcp-toolkit-gateway": {
      "command": "docker",
      "args": [
        "run","-i","--rm",
        "-v","/var/run/docker.sock:/var/run/docker.sock",
        "-v","/Users/youruser/.docker/mcp:/mcp",
        "docker/mcp-gateway",
        "--catalog=/mcp/catalogs/docker-mcp.yaml",
        "--catalog=/mcp/catalogs/custom.yaml",
        "--config=/mcp/config.yaml",
        "--registry=/mcp/registry.yaml",
        "--tools-config=/mcp/tools.yaml",
        "--transport=stdio"
      ]
    }
  }
}
CLI alternative:
docker mcp gateway run --transport sse
On startup you should see:
Reading catalog from [docker-mcp.yaml, custom.yaml]

5. n8n (CRON, Telegram, Google Sheets)

Run n8n locally.

Add Schedule Trigger (CRON) and Telegram Trigger.

Connect Google Sheets credentials and create a queue sheet.

Sheet schema (example):

id	file_name	qty_total	qty_done	priority	status	auto_eject	leveling	purge_line	notes
1	0004.gcode	3	2	1	waiting	on	off	on	client #123
2	0003.gcode	6	6	1	DONE	on	off	on	—

Auto mode (CRON):

choose rows with qty_done < qty_total,

skip rows with status ∈ {hold, blocked, done},

sort by priority, then qty_done/qty_total, then FIFO,

check file exists on printer,

set purge line if the column exists,

if leveling ∈ {yes,true,1,tak} then start with leveling, else without,

on success, increment qty_done and optionally set status=printing.

6. Cloudflare Zero Trust (optional)

Publish n8n behind your domain via Cloudflare Tunnel and protect with authentication.

Klipper/KAMP Configuration (Purge & Auto-Eject)

These snippets are included in the repo. If your KAMP files are read-only, copy and update the corresponding [include ...].

A) Post-print auto-eject (sweep)

gcode_macros.cfg:
[gcode_macro POST_PRINT_EJECT_SIMPLE_RUN]
description: Fixed sweep path – no object logic
variable_bed_cooldown: 39   # °C threshold
gcode:
  TEMPERATURE_WAIT SENSOR=heater_bed MAXIMUM={bed_cooldown}
  G90
  M83
  SET_VELOCITY_LIMIT ACCEL=500 ACCEL_TO_DECEL=250
  G0 X150 Y295 F9000
  G0 Z5 F9000
  G1 Y5 F300
  G1 Y295 F9000
  G0 X5   Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X35  Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X65  Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X95  Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X125 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X155 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X185 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X215 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X245 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X275 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X295 Y295 F9000
  G1      Y5   F900
  G1      Y295 F9000
  G0 X5 Y295 F9000

[gcode_macro POST_PRINT_EJECT_SIMPLE]
description: Wrapper – checks AUTO_EJECT pin and runs sweep if enabled
gcode:
  {% if printer["output_pin AUTO_EJECT"].value|int == 0 %}
    RESPOND TYPE=command MSG="AUTO-EJECT: disabled (skip)"
  {% else %}
    RESPOND TYPE=command MSG="AUTO-EJECT: enabled (run)"
    POST_PRINT_EJECT_SIMPLE_RUN
  {% endif %}

Add to your END_PRINT:
[gcode_macro END_PRINT]
gcode:
  Qmode_exit
  EXCLUDE_OBJECT_RESET
  PRINT_PREPARE_CLEAR
  M220 S100
  SET_VELOCITY_LIMIT ACCEL=5000 ACCEL_TO_DECEL=2500
  TURN_OFF_HEATERS
  M107 P1
  M107 P2
  END_PRINT_POINT
  POST_PRINT_EJECT_SIMPLE
  M84

Enable/disable via virtual pin:
[virtual_pins]
[output_pin AUTO_EJECT]
pin: virtual_pin:AUTO_EJECT_pin
value: 0   # 0 = off (default), 1 = on

[gcode_macro AUTOEJECT_ON]
gcode:
  SET_PIN PIN=AUTO_EJECT VALUE=1

[gcode_macro AUTOEJECT_OFF]
gcode:
  SET_PIN PIN=AUTO_EJECT VALUE=0

B) Alternative purge (custom LINEPURGE)

Example macro (simplified excerpt):
[gcode_macro LINEPURGE]
description: Simple nozzle purge sequence
# positions / speeds
variable_x1: 300.0
variable_y1: 100.0
variable_z1: 10.0
variable_f1: 1000
# ... more variables ...
variable_extrude_mm: 50.0
variable_extrude_f: 1200
variable_t_hot: 225
variable_t_cool: 180
variable_fan_hi: 211.65
variable_fan_lo: 20
gcode:
  {% if "xyz" not in printer.toolhead.homed_axes %}
    G28
  {% endif %}
  G90
  M83
  G0 X{ x1 } Y{ y1 } Z{ z1 } F{ f1 }
  ; heat, wait, extrude, cool with fan, finish moves...
If you cannot edit Line_Purge.cfg directly, copy to a new file and update the [include ...] in your KAMP settings.

Usage

Auto (CRON via n8n):

get_printer_status → skip if BUSY.

Read queue from Google Sheets; pick next job by rules.

list_files → ensure file exists on printer.

If purge_line present → set_purge_line(on/off).

If leveling is ON → start_print_with_leveling(file) else start_print(file).

On success → increment qty_done (and optionally set status=printing).

Manual (Telegram):

status, files

print <file>, print leveling <file>

pause, resume, stop

light on, light off

Troubleshooting

custom.yaml not loaded → ensure registry.yaml lists both catalogs (docker-mcp.yaml, then custom.yaml) and gateway logs show both.

File missing → verify with list_files() and correct the sheet filename.

TEMPERATURE_WAIT error → use MINIMUM/MAXIMUM (not TARGET).

Auto-eject collisions → disable with AUTOEJECT_OFF and tune path.

Fan via SET_PIN → define output_pin fan0 with pwm: True, scale: 255 or use M106/M107.

Demo Video

YouTube walkthrough: [PLACEHOLDER – link will be added here]

Diagrams

System architecture: [PLACEHOLDER – image/diagram link]

n8n workflow: [PLACEHOLDER – image/screenshot link]

Links & Resources

Moonraker: https://moonraker.readthedocs.io/

Klipper: https://www.klipper3d.org/

KAMP: https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging

n8n: https://docs.n8n.io/

Cloudflare Zero Trust: https://developers.cloudflare.com/cloudflare-one/

Toolhead cover (improves ejection): https://makerworld.com/en/models/816811-creality-k1-toolhead-cover-k1-burner-v2

License

MIT License (unless stated otherwise in individual files). External components remain under their respective licenses.

Quick Start (TL;DR)
# Build MCP server image
cd /Users/youruser/moonraker-mcp-server
docker build -t mcp/moonraker:latest .

# Set Moonraker endpoint + key
docker mcp secret set PRINTER_URL="http://192.168.1.12:4409"
docker mcp secret set API_KEY="YOUR-API-KEY"

# Ensure registry points to both catalogs
# ~/.docker/mcp/registry.yaml -> catalogs/docker-mcp.yaml + catalogs/custom.yaml

# Run MCP gateway
docker mcp gateway run --transport sse
# Should log both catalogs being read

# Configure n8n (CRON + Telegram + Google Sheets 'queue')
# Test: get_printer_status, list_files, start_print/start_print_with_leveling
