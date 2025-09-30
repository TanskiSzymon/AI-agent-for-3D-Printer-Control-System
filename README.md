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

