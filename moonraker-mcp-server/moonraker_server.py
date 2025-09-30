#!/usr/bin/env python3
"""
Simple Moonraker MCP Server - Controls Creality K1 Max 3D printers via Moonraker REST API
"""
import os
import sys
import logging
import json
import asyncio
from mcp.server.fastmcp import FastMCP
import httpx

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("moonraker-server")

# Initialize MCP server - NO PROMPT PARAMETER!
mcp = FastMCP("moonraker")

# Configuration
def get_printer_configs():
    """Parse environment variables for printer configurations."""
    configs = []
    
    # Try comma-separated lists first
    urls = os.environ.get("PRINTER_URLS", "").split(",") if os.environ.get("PRINTER_URLS") else []
    keys = os.environ.get("API_KEYS", "").split(",") if os.environ.get("API_KEYS") else []
    names = os.environ.get("PRINTER_NAMES", "").split(",") if os.environ.get("PRINTER_NAMES") else []
    
    # If no lists, try single printer fallback
    if not urls or not urls[0]:
        single_url = os.environ.get("PRINTER_URL", "")
        single_key = os.environ.get("API_KEY", "")
        if single_url:
            urls = [single_url]
            keys = [single_key] if single_key else [""]
            names = ["default"]
    
    # Build config list
    for i, url in enumerate(urls):
        if url.strip():
            config = {
                "url": url.strip(),
                "key": keys[i].strip() if i < len(keys) else "",
                "name": names[i].strip() if i < len(names) else f"printer_{i}"
            }
            configs.append(config)
    
    return configs

PRINTERS = get_printer_configs()

# === UTILITY FUNCTIONS ===

def redact_key(key):
    """Redact API key for logging."""
    if not key:
        return "no-key"
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}...{key[-3:]}"

def resolve_printer(selector):
    """Resolve printer by IP, name, or substring match."""
    if not selector or not selector.strip():
        if len(PRINTERS) == 1:
            return PRINTERS[0]
        return None
    
    selector = selector.strip()
    
    # Try exact match by URL/IP
    for printer in PRINTERS:
        if selector in printer["url"]:
            return printer
    
    # Try exact name match
    for printer in PRINTERS:
        if printer["name"] == selector:
            return printer
    
    # Try case-insensitive substring match
    selector_lower = selector.lower()
    for printer in PRINTERS:
        if selector_lower in printer["name"].lower():
            return printer
    
    return None

def validate_filename(filename):
    """Validate and sanitize filename."""
    if not filename or not filename.strip():
        return None, "Filename cannot be empty"
    
    filename = filename.strip()
    
    # Check for allowed extensions
    allowed_extensions = [".gcode", ".g", ".gco"]
    has_valid_extension = any(filename.lower().endswith(ext) for ext in allowed_extensions)
    
    if not has_valid_extension:
        return None, f"Invalid file extension. Must be one of: {', '.join(allowed_extensions)}"
    
    # Basic sanitization - remove path traversal attempts
    filename = filename.replace("..", "").replace("//", "/")
    
    return filename, None

async def make_request(method, url, headers=None, json_data=None, timeout=15):
    """Make HTTP request with proper error handling."""
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers, timeout=timeout)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json(), None
    except httpx.TimeoutException:
        return None, "Request timed out"
    except httpx.HTTPStatusError as e:
        try:
            error_data = e.response.json()
            error_msg = error_data.get("error", {}).get("message", str(e))
        except:
            error_msg = f"HTTP {e.response.status_code}"
        return None, error_msg
    except Exception as e:
        return None, str(e)

def format_temp(temp):
    """Format temperature value."""
    if temp is None:
        return "N/A"
    try:
        return f"{float(temp):.1f}°C"
    except:
        return "N/A"

# === MCP TOOLS ===

@mcp.tool()
async def get_printer_status(printer: str = "") -> str:
    """Get current printer status including temperatures and print progress."""
    config = resolve_printer(printer)
    if not config:
        return "Error: No printer found. Specify printer IP, name, or substring"
    
    url = f"{config['url']}/printer/objects/query?print_stats&heater_bed&extruder"
    headers = {"X-Api-Key": config["key"]} if config["key"] else {}
    
    data, error = await make_request("GET", url, headers, timeout=10)
    if error:
        return f"Error: {error}"
    
    try:
        result = data.get("result", {})
        status = result.get("status", {})
        
        # Extract print stats
        print_stats = status.get("print_stats", {})
        state = print_stats.get("state", "unknown")
        progress = print_stats.get("progress", 0) * 100
        filename = print_stats.get("filename", "none")
        
        # Determine busy/ready state
        if state in ["printing", "paused"]:
            busy_status = "BUSY"
        elif state in ["standby", "complete", "idle"]:
            busy_status = "READY"
        else:
            busy_status = state.upper()
        
        # Extract temperatures
        extruder = status.get("extruder", {})
        heater_bed = status.get("heater_bed", {})
        
        hotend_temp = format_temp(extruder.get("temperature"))
        hotend_target = format_temp(extruder.get("target"))
        bed_temp = format_temp(heater_bed.get("temperature"))
        bed_target = format_temp(heater_bed.get("target"))
        
        # Format response
        response = f"🖨️ {config['name']} Status:\n"
        response += f"State: {busy_status}\n"
        response += f"Progress: {progress:.1f}%\n"
        response += f"File: {filename}\n"
        response += f"Hotend: {hotend_temp} / {hotend_target}\n"
        response += f"Bed: {bed_temp} / {bed_target}"
        
        return response
    except Exception as e:
        return f"Error parsing response: {str(e)}"

@mcp.tool()
async def list_files(printer: str = "", path: str = "") -> str:
    """List available G-code files on the printer."""
    config = resolve_printer(printer)
    if not config:
        return "Error: No printer found. Specify printer IP, name, or substring"
    
    url = f"{config['url']}/server/files/list"
    if path:
        url += f"?path={path}"
    
    headers = {"X-Api-Key": config["key"]} if config["key"] else {}
    
    data, error = await make_request("GET", url, headers, timeout=10)
    if error:
        return f"Error: {error}"
    
    try:
        # Handle the response structure from your printer
        files = []
        
        # Your printer returns {"result": [...]} where result is directly the file list
        if isinstance(data, dict) and "result" in data:
            result = data["result"]
            
            # If result is a list of files
            if isinstance(result, list):
                for file_info in result:
                    if isinstance(file_info, dict):
                        # Get the filename from 'path' field (your printer uses 'path' not 'filename')
                        filename = file_info.get("path", "")
                        if filename and filename.lower().endswith((".gcode", ".g", ".gco")):
                            files.append(filename)
        
        # Format response
        response_data = {
            "root": "/",
            "cwd": path or "/",
            "items": files
        }
        
        return json.dumps(response_data, separators=(',', ':'))
        
    except Exception as e:
        logger.error(f"Error parsing file list: {e}")
        return f"Error: {str(e)}"
    
@mcp.tool()
async def set_purge_line(printer: str = "", state: str = "off") -> str:
    """
    Sterowanie PURGE LINE według Twojej logiki:
      - state="off"  → chcemy BEZ PURGE LINE → ustaw PIN=ADAPTIVE_PURGE_LINE na 1
      - state="on"   → chcemy PURGE LINE     → ustaw PIN=ADAPTIVE_PURGE_LINE na 0
    Akceptuje też: "0"/"1", "true"/"false".
    """
    cfg = resolve_printer(printer)
    if not cfg:
        return "Error: No printer found. Specify printer IP, name, or substring"

    s = str(state).strip().lower()
    if s in ("off", "0", "false"):
        val = 1.0   # bez purge line
        msg = "disabled (no purge line)"
    elif s in ("on", "1", "true"):
        val = 0.0   # z purge line
        msg = "enabled (purge line active)"
    else:
        return "Error: Unknown state. Use 'on' or 'off'."

    base = cfg["url"].rstrip("/")
    headers = {"X-Api-Key": cfg["key"]} if cfg.get("key") else {}
    url = f"{base}/printer/gcode/script"
    payload = {"script": f"SET_PIN PIN=ADAPTIVE_PURGE_LINE VALUE={val:.2f}"}

    _, err = await make_request("POST", url, headers, payload, timeout=10)
    if err:
        return f"Error: could not set ADAPTIVE_PURGE_LINE to {val:.2f} - {err}"

    return f"✅ Purge line {msg}"


@mcp.tool()
async def start_print(printer: str = "", filename: str = "") -> str:
    """
    Start wydruku BEZ poziomowania (szybszy start).
    Dodatkowo wymusza ADAPTIVE_BED_MESH=0 przed startem.
    """
    cfg = resolve_printer(printer)
    if not cfg:
        return "Error: No printer found. Specify printer IP, name, or substring"
    if not filename:
        return "Error: Missing filename"

    base = cfg["url"].rstrip("/")
    headers = {"X-Api-Key": cfg["key"]} if cfg.get("key") else {}

    async def gcode(cmd: str):
        url = f"{base}/printer/gcode/script"
        return await make_request("POST", url, headers, {"script": cmd}, timeout=10)

    # 1) wyłącz adaptacyjne poziomowanie
    _, err = await gcode("SET_PIN PIN=ADAPTIVE_BED_MESH VALUE=0")
    if err:
        return f"Error: could not set ADAPTIVE_BED_MESH=0 - {err}"

    # 2) uruchom wydruk jak dotychczas
    #    NIE zmieniamy zachowania: najpierw /printer/print/start z filename,
    #    jeśli drukarka ma humory, fallback na select+start.
    start_url = f"{base}/printer/print/start"
    data, error = await make_request("POST", start_url, headers, {"filename": filename}, timeout=15)
    if error:
        # fallback: select plik, potem start
        sel_url = f"{base}/server/files/select"
        _, e1 = await make_request("POST", sel_url, headers, {"filename": filename}, timeout=10)
        if e1:
            return f"Error: cannot select file '{filename}' - {e1}"
        _, e2 = await make_request("POST", start_url, headers, None, timeout=15)
        if e2:
            return f"Error: cannot start print for '{filename}' - {e2}"

    return f"🟢 Printing '{filename}' started (no leveling). Drukarka się rozgrzewa, wydruk rozpocznie się za chwilę."


@mcp.tool()
async def start_print_with_leveling(printer: str = "", filename: str = "") -> str:
    """
    Start wydruku Z poziomowaniem (precyzyjniej).
    Dodatkowo wymusza ADAPTIVE_BED_MESH=1 przed startem.
    """
    cfg = resolve_printer(printer)
    if not cfg:
        return "Error: No printer found. Specify printer IP, name, or substring"
    if not filename:
        return "Error: Missing filename"

    base = cfg["url"].rstrip("/")
    headers = {"X-Api-Key": cfg["key"]} if cfg.get("key") else {}

    async def gcode(cmd: str):
        url = f"{base}/printer/gcode/script"
        return await make_request("POST", url, headers, {"script": cmd}, timeout=10)

    # 1) włącz adaptacyjne poziomowanie
    _, err = await gcode("SET_PIN PIN=ADAPTIVE_BED_MESH VALUE=1")
    if err:
        return f"Error: could not set ADAPTIVE_BED_MESH=1 - {err}"

    # 2) uruchom wydruk jak dotychczas
    start_url = f"{base}/printer/print/start"
    data, error = await make_request("POST", start_url, headers, {"filename": filename}, timeout=15)
    if error:
        sel_url = f"{base}/server/files/select"
        _, e1 = await make_request("POST", sel_url, headers, {"filename": filename}, timeout=10)
        if e1:
            return f"Error: cannot select file '{filename}' - {e1}"
        _, e2 = await make_request("POST", start_url, headers, None, timeout=15)
        if e2:
            return f"Error: cannot start print for '{filename}' - {e2}"

    return f"🟢 Printing '{filename}' started (with leveling). Drukarka się rozgrzewa, wydruk rozpocznie się za chwilę."

@mcp.tool()
async def pause_print(printer: str = "") -> str:
    """Pause the current print job."""
    config = resolve_printer(printer)
    if not config:
        return "Error: No printer found. Specify printer IP, name, or substring"
    
    url = f"{config['url']}/printer/print/pause"
    headers = {"X-Api-Key": config["key"]} if config["key"] else {}
    
    data, error = await make_request("POST", url, headers, timeout=15)
    if error:
        return f"Error: {error}"
    
    return "✅ Print paused"

@mcp.tool()
async def resume_print(printer: str = "") -> str:
    """Resume a paused print job."""
    config = resolve_printer(printer)
    if not config:
        return "Error: No printer found. Specify printer IP, name, or substring"
    
    url = f"{config['url']}/printer/print/resume"
    headers = {"X-Api-Key": config["key"]} if config["key"] else {}
    
    data, error = await make_request("POST", url, headers, timeout=15)
    if error:
        return f"Error: {error}"
    
    return "✅ Print resumed"

@mcp.tool()
async def stop_print(printer: str = "") -> str:
    """Stop/cancel the current print job."""
    config = resolve_printer(printer)
    if not config:
        return "Error: No printer found. Specify printer IP, name, or substring"
    
    url = f"{config['url']}/printer/print/cancel"
    headers = {"X-Api-Key": config["key"]} if config["key"] else {}
    
    data, error = await make_request("POST", url, headers, timeout=15)
    if error:
        return f"Error: {error}"
    
    return "✅ Print stopped"


@mcp.tool()
async def control_light(printer: str = "", state: str = "on") -> str:
    """
    Proste sterowanie światłem komory ON/OFF dla K1 Max
    (bez RGB, bez cudów). Używa SET_PIN PIN=LED VALUE=1|0.

    Parametry:
      - printer: jak dotychczas (IP/nazwa/substring)
      - state: "on" lub "off" (akceptuje też "1"/"0", "true"/"false")
    """
    cfg = resolve_printer(printer)
    if not cfg:
        return "Error: No printer found. Specify printer IP, name, or substring"

    base = cfg["url"].rstrip("/")
    headers = {"X-Api-Key": cfg["key"]} if cfg.get("key") else {}

    s = str(state).strip().lower()
    if s in ("on", "1", "true"):
        val = 1.0
        target_txt = "on"
    elif s in ("off", "0", "false"):
        val = 0.0
        target_txt = "off"
    else:
        return "Error: Unknown state. Use 'on' or 'off'."

    cmd = f"SET_PIN PIN=LED VALUE={val:.3f}"

    url = f"{base}/printer/gcode/script"
    payload = {"script": cmd}

    data, error = await make_request("POST", url, headers, payload, timeout=10)

    if error:
        return f"Error: Could not switch light {target_txt} - {error}"

    # Moonraker zwykle zwraca {"result": ...} przy sukcesie
    return f"✅ Chamber light turned {target_txt}"



# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Moonraker MCP server...")
    
    # Log configuration (redacted)
    if PRINTERS:
        logger.info(f"Configured printers: {len(PRINTERS)}")
        for i, printer in enumerate(PRINTERS):
            logger.info(f"  [{i}] {printer['name']} @ {printer['url']} (key: {redact_key(printer['key'])})")
        
        # Soft probe first printer if only one configured
        if len(PRINTERS) == 1:
            async def probe_printer():
                try:
                    url = f"{PRINTERS[0]['url']}/printer/info"
                    headers = {"X-Api-Key": PRINTERS[0]["key"]} if PRINTERS[0]["key"] else {}
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, headers=headers, timeout=5)
                        if response.status_code == 200:
                            logger.info(f"✅ Successfully connected to {PRINTERS[0]['name']}")
                        else:
                            logger.warning(f"⚠️ Printer returned status {response.status_code}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not connect to printer: {e}")
            
            asyncio.run(probe_printer())
    else:
        logger.warning("No printers configured. Set PRINTER_URL/PRINTER_URLS environment variables")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)