Moonraker MCP Server + n8n Queue for Creality K1 Max

Semi-automated printing pipeline for Creality K1 Max using:

a custom MCP (Model Context Protocol) server for Moonraker,

n8n orchestration (CRON + Telegram trigger),

Google Sheets as the print queue,

Klipper/KAMP modifications (custom purge + automatic print ejection).

⚠️ Beta software/hardware integration. Use at your own risk.
⚠️ Mechanical limitation: auto-eject does not work reliably for very low-height prints and requires ~80 mm of free build plate at the rear.

Table of Contents

Overview

System Architecture

Features

Components

Requirements

Installation & Setup

1. Printer Preparation (Klipper/Moonraker/KAMP)

2. MCP Server (Docker build + secrets)

3. MCP Registry & Catalog

4. MCP Gateway (Claude Desktop / CLI)

5. n8n: CRON, Telegram & Google Sheets

6. Cloudflare Zero Trust (optional)

Klipper/KAMP Configuration (Purge & Auto-Eject)

Usage

Troubleshooting

Demo Video

Diagrams

Links & Resources

License

Overview

This project connects a Creality K1 Max running Klipper/Moonraker with an external orchestration layer:

MCP server exposes printer controls as structured tools.

n8n orchestrates automatic queue execution (CRON) and manual commands (Telegram).

Google Sheets stores print jobs (priority, quantities, leveling, purge line, etc.).

Klipper/KAMP macros handle custom purge sequences and post-print ejection.

System Architecture
[Klipper + Moonraker (K1 Max)]
          ↑ REST (Moonraker API)
[Moonraker MCP Server (Docker)]
          ↑ stdio/SSE
[MCP Gateway]  ←→  [n8n Orchestration] ←→ [Google Sheets Queue]
                           ↑
                 (Telegram / Schedule Trigger)

Features

Printer control

Status (READY/BUSY, temps, progress).

List .gcode files.

Start print:

Fast: no leveling.

Precise: with adaptive leveling (based on sheet or user command).

Purge line on/off.

Pause / resume / stop.

Chamber light control.

Queue management

Google Sheets as source of truth.

Auto-trigger via CRON in n8n.

Priority + FIFO scheduling.

Quantity tracking (qty_done vs qty_total).

Klipper/KAMP integration

Custom purge macro (replaces LINE_PURGE).

Auto-eject macro to sweep prints off the bed.

Components

moonraker_server.py – MCP server (Python 3.11, FastMCP, httpx).

Dockerfile – containerized build of the MCP server.

requirements.txt – dependencies (mcp[cli], httpx).

gcode_macros.cfg – custom macros for purge and eject.

docker-mcp.yaml – catalog entry for MCP.

registry.yaml – registry reference.

custom.yaml – local overrides/extensions.

n8n workflows – CRON, Telegram trigger, Google Sheets update.

Requirements

Creality K1 Max flashed with Klipper + Moonraker.

KAMP macros installed.

Docker.

n8n (local or Docker).

Google Sheets API.

MCP Gateway (Claude Desktop or CLI).

Cloudflare Zero Trust (optional, to expose n8n securely).

Installation & Setup
1. Printer Preparation (Klipper/Moonraker/KAMP)

Flash Klipper/Moonraker on your K1 Max.

Install KAMP macros.

Add custom purge and auto-eject macros (see Klipper/KAMP Configuration
).

Verify API access:

curl "http://PRINTER_IP:PORT/server/files/list"
curl -X POST "http://PRINTER_IP:PORT/printer/gcode/script" \
  -H "Content-Type: application/json" \
  -d '{"script":"G28"}'

2. MCP Server (Docker build + secrets)
cd /Users/youruser/moonraker-mcp-server
docker build -t mcp/moonraker:latest .


Set secrets (printer URL and API key):

docker mcp secret set PRINTER_URL="http://192.168.1.12:4409"
docker mcp secret set API_KEY="your-api-key"

3. MCP Registry & Catalog

~/.docker/mcp/catalogs/docker-mcp.yaml:

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


~/.docker/mcp/registry.yaml:

catalog:
  - catalogs/docker-mcp.yaml
  - catalogs/custom.yaml
config: config.yaml
tools: tools.yaml
secrets: secrets.yaml

4. MCP Gateway (Claude Desktop / CLI)

Claude Desktop config (macOS):

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

5. n8n: CRON, Telegram & Google Sheets

Install n8n locally.

Add Schedule Trigger (CRON) and Telegram Trigger.

Connect to Google Sheets.

Queue structure (sheet queue):

id	file_name	qty_total	qty_done	priority	status	auto_eject	leveling	purge_line	notes
1	0004.gcode	3	2	1	waiting	on	off	on	client #123
2	0003.gcode	6	6	1	DONE	on	off	on	–

CRON job picks first available row (qty_done < qty_total, not DONE/blocked).
leveling=yes → start with leveling.
purge_line=on → run purge before print.

6. Cloudflare Zero Trust (optional)

Expose n8n under your domain via Cloudflare Tunnel.

Protect with authentication.

Klipper/KAMP Configuration (Purge & Auto-Eject)

The repo includes:

LINEPURGE macro – nozzle cleaning sequence (custom moves, heating, extrusion, cooling).

POST_PRINT_EJECT_SIMPLE macro – sweeps prints off bed after cooldown.

END_PRINT macro modified to call auto-eject.

If files are read-only, copy them under a new filename and update [include ...] in KAMP_Settings.cfg.

Usage

Auto (CRON):

Check printer status.

Read queue from Google Sheets.

Verify .gcode exists.

Apply purge_line / leveling settings.

Start print.

Increment qty_done.

Manual (Telegram):

status → printer status.

files → list files.

print <file> → start without leveling.

print leveling <file> → start with leveling.

pause, resume, stop, light on/off.

Troubleshooting

Gateway ignores custom.yaml → check registry.yaml includes both catalogs.

File missing on printer → run list_files() and check filename matches sheet.

Temperature wait errors → use MINIMUM/MAXIMUM instead of TARGET.

Collisions on eject → disable with AUTOEJECT_OFF.

Fan control → ensure fan0 defined as output_pin with scale=255.

Demo Video

📹 [PLACEHOLDER – YouTube demo link]

Diagrams
Full System

[PLACEHOLDER – system architecture diagram image]

n8n Workflow

[PLACEHOLDER – screenshot of n8n flow with triggers, sheets, and MCP client]

Links & Resources

Moonraker

Klipper

KAMP macros

MakerWorld – K1 Toolhead Cover (improved part ejection)

n8n official docs

Cloudflare Zero Trust

License

MIT License (unless otherwise stated in source files).
External components retain their respective licenses.
