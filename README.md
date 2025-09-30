# 🖨️ Autonomous 3D Printer Control System
## Creality K1 Max + Moonraker + AI Agent + Auto-Ejection

### ⚠️ BETA VERSION - USE AT YOUR OWN RISK

---

## 📋 Overview

This project creates a fully autonomous 3D printing system that combines:
- **Creality K1 Max** 3D printer with Moonraker/Klipper firmware
- **AI Agent** (Claude/GPT) for intelligent print management
- **Google Sheets** for print queue management
- **n8n** workflow automation platform
- **Telegram** bot for remote control
- **MCP (Model Context Protocol)** for AI-printer communication
- **Automatic print ejection** system for continuous printing

The system can automatically process a queue of print jobs, handle bed leveling decisions, manage purge lines, and physically eject completed prints from the build plate.

## 🎥 Demo Video

[YouTube Video Placeholder - Link to be added]

## 🔧 What I Used

### Hardware:
- Creality K1 Max 3D printer
- Modified toolhead cover for better print ejection ([Model Link](https://makerworld.com/en/models/816811-creality-k1-toolhead-cover-k1-burner-v2))

### Software Stack:
- **Moonraker** - Web API for Klipper
- **KAMP** (Klipper Adaptive Meshing & Purging)
- **Docker** with MCP Toolkit
- **n8n** (self-hosted via Docker)
- **Claude Desktop** with MCP integration
- **Telegram Bot API**
- **Google Sheets API**
- **Cloudflare Zero Trust** (for secure n8n access)

### AI Models:
- OpenRouter (GPT-5-mini or similar)
- OpenAI Whisper (for voice commands)

## 🚀 How It Works

1. **Print Queue Management**: Google Sheets maintains a queue with priorities, quantities, and print settings
2. **Automatic Scheduling**: n8n runs every 30 minutes to check if printer is ready
3. **AI Decision Making**: Agent analyzes queue, selects next job based on priority
4. **Smart Configuration**: Automatically handles bed leveling and purge line based on spreadsheet settings
5. **Physical Ejection**: After print completes and bed cools to 39°C, printer automatically ejects the part
6. **Remote Control**: Full control via Telegram bot with voice command support

## ⚙️ Complete Setup Guide

### Prerequisites

- Creality K1 Max printer
- Computer running Docker Desktop
- n8n instance (local or cloud)
- Google account (for Sheets)
- Telegram account
- API keys for AI services

### Step 1: Printer Preparation

#### 1.1 Root the Printer and Install Moonraker

[Link to rooting guide - to be added]

1. Root your Creality K1 Max
2. Install Moonraker and Klipper
3. Install KAMP (Klipper Adaptive Meshing & Purging)

#### 1.2 Configure Printer Macros

Add to `gcode_macros.cfg`:
```gcode
[gcode_macro POST_PRINT_EJECT_SIMPLE_RUN]
description: Fixed sweep path - no logic
variable_bed_cooldown: 39
gcode:
  ; Wait for bed to cool
  TEMPERATURE_WAIT SENSOR=heater_bed MAXIMUM={bed_cooldown}
  ; Ejection movements
  G90
  M83
  SET_VELOCITY_LIMIT ACCEL=500 ACCEL_TO_DECEL=250
  ; [Full macro code as provided above...]
Modify END_PRINT macro to include:
gcodePOST_PRINT_EJECT_SIMPLE
1.3 Configure KAMP Settings
In config/Helper-Script/KAMP/Start_Print.cfg, add virtual pins:
gcode[output_pin AUTO_EJECT]
pin: virtual_pin:AUTO_EJECT_pin
value: 0

[gcode_macro AUTO_EJECT_ON]
description: Enable auto eject after print
gcode:
  SET_PIN PIN=AUTO_EJECT VALUE=1
  RESPOND TYPE=command MSG="AUTO-EJECT enabled"
Modify Line_Purge.cfg with custom purge sequence (see full code in repository).
Note: If files are read-only, create copies with new names and update includes in KMAP_Settings.cfg
1.4 Print Modified Toolhead Cover
Print and install the modified toolhead cover for better print ejection.
Step 2: MCP Server Setup
[Link to MCP setup guide - to be added]

Build Docker image:

bashcd moonraker-mcp-server
docker build -t moonraker-mcp-server .
docker tag moonraker-mcp-server:latest mcp/moonraker:latest

Set secrets:

bashdocker mcp secret set PRINTER_URL="http://YOUR_PRINTER_IP:4409"
docker mcp secret set API_KEY="your-api-key"  # if needed

Configure Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json)

Step 3: n8n Setup
Link to n8n installation guide - Network Chuck Tutorial

Install n8n locally with Docker
Configure Cloudflare Zero Trust for secure access
Import the workflow (Simple_printers_Autonomus.json)
Configure credentials:

Telegram Bot API
Google Sheets OAuth
OpenRouter/OpenAI API


Adjust Schedule Trigger (recommended: 30 minutes to save API costs)

Step 4: Google Sheets Setup
Create spreadsheet with following structure:
idfile_nameqty_totalqty_doneprioritystatusauto_ejectlevelingpurge_linenotes1test.gcode301waitingonoffon2part.gcode522DONEoffonoff
Required columns: id, file_name, qty_total, qty_done, priority
Optional columns: status, auto_eject, leveling, purge_line, notes
Step 5: Run MCP Gateway
For n8n to work, MCP Gateway must be running:
bashdocker mcp gateway run --transport sse
Or ensure Claude Desktop is running with MCP configured.
🎮 Usage
Automatic Mode (CRON)

System checks printer every 30 minutes
Selects highest priority job with qty_done < qty_total
Configures leveling and purge based on spreadsheet
Updates spreadsheet after successful start

Manual Control (Telegram)

"Status" - check printer status
"List files" - show available G-code files
"Print test.gcode" - start specific print
"Print with leveling part.gcode" - force bed leveling
"Pause"/"Resume"/"Stop" - control active print
Voice messages supported via Whisper API

⚠️ Important Limitations

Auto-ejection doesn't work for low objects (< ~20mm height)
Requires ~80mm clearance at the back of build plate
BETA VERSION - system may have bugs or cause damage
USE AT YOUR OWN RISK - test thoroughly before production use
Monitor first few prints to ensure ejection works properly

🔒 Security Considerations

API keys stored in Docker secrets
Telegram bot restricted to authorized user IDs
n8n secured with Cloudflare Zero Trust
Printer network should be isolated/secure

📊 Cost Estimation

OpenRouter API: ~$0.10-0.50 per day (depending on usage)
Telegram: Free
Google Sheets: Free
n8n: Free (self-hosted)

🐛 Troubleshooting
Common Issues:

"Request timed out" - Normal during printer heating, wait 30-60s
Files not found - Ensure .gcode files are in printer's storage
Ejection fails - Check bed temperature threshold and print height
MCP not connecting - Verify Docker gateway is running

Debug Commands:
bash# Check MCP server
docker mcp server list

# View logs
docker logs $(docker ps -q --filter ancestor=mcp/moonraker:latest)

# Test printer connection
curl http://YOUR_PRINTER_IP:4409/printer/info
🤝 Contributing
Feel free to submit issues and enhancement requests!
📄 License
MIT License - Use at your own risk
🙏 Acknowledgments

Network Chuck for n8n tutorial
Moonraker/Klipper developers
KAMP project contributors
MCP toolkit team

📞 Contact
[Your contact information]

Remember: This is an experimental system. Always supervise initial prints and have emergency stop procedures ready. The auto-ejection system can potentially damage prints or printer if not properly configured.
