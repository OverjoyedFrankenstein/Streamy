# Streamy

**Version 1.5**

A desktop application for streaming RTSP video from 3D printer cameras and monitoring printer status in real-time.

**Contact:** data_heavy@proton.me

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Technical Specifications](#technical-specifications)
- [Data Structures](#data-structures)
- [Network Protocol](#network-protocol)
- [Troubleshooting](#troubleshooting)

---

## Overview

Streamy is a PyQt5-based desktop application designed to monitor Elegoo 3D resin printers. It provides:

- **Live video streaming** from the printer's built-in camera via RTSP
- **Real-time print monitoring** including progress, layers, and time remaining
- **Snapshot capture** with optional timestamps
- **Automatic printer discovery** on local network

### Supported Devices

- Elegoo resin 3D printers with network connectivity
- Any RTSP-compatible camera (port 554)
- Uses SDCP (Smart Device Communication Protocol) for Elegoo printer communication

---

## Features

### Video Streaming
- RTSP video streaming at ~30 FPS
- Support for UDP and TCP transport protocols
- Configurable RTSP path (default: `/video`)
- Video enable/disable toggle (monitoring continues when video is paused)
- Frame buffering for stability
- Timestamp overlay on video feed
- Real-time FPS counter

### Print Monitoring
- Print progress percentage (calculated from layers)
- Current layer / Total layer display
- Remaining layers calculation
- Total print time and remaining time
- Print job status (Idle, Preparing, Printing, Finishing)
- Task/file name display
- UV temperature monitoring
- 1-second status update interval

### Snapshot Capture
- Save current frame as JPG to Desktop
- Optional timestamp overlay on snapshots
- Filename format: `printer_snapshot_YYYYMMDD_HHMMSS.jpg`

### Network Discovery
- Automatic UDP broadcast discovery on port 3000
- Discovery message protocol: `M99999`
- Fallback to direct IP connection if discovery fails

### User Interface
- IP address input with recent printers dropdown (up to 5)
- Transport protocol selector (UDP/TCP)
- RTSP path customization
- Connect/Disconnect controls
- Color-coded status indicator:
  - **Red:** Error/Disconnected
  - **Yellow:** Connecting/Warning
  - **Green:** Connected
  - **Gray:** Idle
- Minimum video display: 640x480
- Progress, layer, and time information panels

### Keyboard Shortcuts
- **Enter** in IP field: Connect to printer

---

## Requirements

### System Requirements
- Python 3.7+
- macOS, Windows, or Linux

### Dependencies

The following packages are automatically installed if missing:

| Package | Purpose |
|---------|---------|
| `opencv-python` | Video capture and image processing |
| `numpy` | Image manipulation |
| `PyQt5` | GUI framework |
| `websocket-client` | WebSocket communication |
| `requests` | HTTP requests |

---

## Installation

1. **Clone or download** the repository to your local machine

2. **Run the application:**
   ```bash
   python main.py
   ```

   Missing dependencies will be automatically installed on first run.

3. **Manual dependency installation** (if needed):
   ```bash
   pip install opencv-python numpy PyQt5 websocket-client requests
   ```

---

## Usage

### Basic Usage

1. **Launch the application:**
   ```bash
   python main.py
   ```

2. **Connect to a printer:**
   - Enter the printer's IP address in the input field
   - Select transport protocol (UDP recommended for most cases)
   - Click **Connect**

3. **Monitor your print:**
   - View live video stream from printer camera
   - Monitor progress, layers, and time remaining
   - Take snapshots with the **Snapshot** button

4. **Disconnect:**
   - Click **Disconnect** when finished

### Command Line Arguments

```bash
python main.py --ip <IP_ADDRESS>
```

| Argument | Description |
|----------|-------------|
| `--ip` | IP address of the printer (overrides auto-connect) |

### Auto-Connect

When enabled, Streamy automatically connects to the last used printer on startup. This can be configured in the application settings.

---

## Configuration

### Configuration File

Settings are stored in `streamy_config.json`:

```json
{
    "recent_printers": ["192.168.1.100", "192.168.1.101"],
    "last_used_printer": "192.168.1.100",
    "include_timestamp": true,
    "video_enabled": true,
    "auto_connect": true,
    "transport": "udp",
    "rtsp_path": "/video"
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `recent_printers` | array | `[]` | List of up to 5 recent printer IPs |
| `last_used_printer` | string | `""` | Last connected printer IP |
| `include_timestamp` | boolean | `true` | Add timestamp to snapshots |
| `video_enabled` | boolean | `true` | Enable video streaming |
| `auto_connect` | boolean | `true` | Auto-connect on startup |
| `transport` | string | `"udp"` | RTSP transport: `"udp"` or `"tcp"` |
| `rtsp_path` | string | `"/video"` | RTSP stream path |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENCV_LOG_LEVEL` | Set to `ERROR` to suppress OpenCV messages |
| `OPENCV_FFMPEG_CAPTURE_OPTIONS` | RTSP transport options |

---

## Architecture

### Application Structure

```
Streamy/
├── main.py           # Main application window and UI
├── printmon.py       # Printer monitoring via WebSocket
├── vidstream.py      # RTSP video streaming
├── stats.py          # Alternative Tkinter GUI (standalone)
├── streamy_config.json  # User configuration
└── README.md         # This file
```

### Component Interaction

```
main.py (StreamyApp)
    │
    ├── VideoStreamer (vidstream.py)
    │   ├── Connects to RTSP stream at port 554
    │   ├── Handles frame capture and display
    │   └── Takes snapshots
    │
    └── PrinterMonitor (printmon.py)
        ├── Discovers printer via UDP broadcast (port 3000)
        ├── Connects via WebSocket (port 3030)
        ├── Receives status updates
        └── Parses printer data
```

### Main Classes

#### main.py

| Class | Description |
|-------|-------------|
| `StreamyApp` | Main application window, orchestrates all components |
| `StatusIndicator` | Custom widget for colored status dot |
| `Config` | Manages application configuration |

#### printmon.py

| Class | Description |
|-------|-------------|
| `PrinterMonitor` | WebSocket client for printer communication |
| `PrintInfo` | Dataclass for print job information |
| `Printer` | Dataclass for printer device information |
| `PrinterStatus` | Dataclass for overall printer status |
| `Temperature` | Dataclass for temperature readings |

#### vidstream.py

| Class | Description |
|-------|-------------|
| `VideoStreamer` | RTSP video stream handler |

---

## Technical Specifications

### Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 3000 | UDP | Printer discovery (broadcast) |
| 54780 | UDP | Discovery response binding |
| 3030 | WebSocket | Printer status communication |
| 554 | RTSP | Video streaming |

### Timeouts and Intervals

| Parameter | Value | Description |
|-----------|-------|-------------|
| Discovery timeout | 1 second | UDP broadcast timeout |
| WebSocket timeout | 5 seconds | Connection timeout |
| Video frame interval | 33 ms | ~30 FPS |
| Status update interval | 1 second | Printer status polling |
| FPS calculation interval | 1 second | FPS counter update |
| Auto-connect delay | 1 second | Startup delay |
| RTSP initialization | 1.5 seconds | Stream setup delay |

### Buffer Sizes

| Parameter | Value |
|-----------|-------|
| UDP receive buffer | 8192 bytes |
| OpenCV frame buffer | 3 frames |
| Recent printers list | 5 entries max |

### Image Specifications

| Parameter | Value |
|-----------|-------|
| Placeholder image | 853x480 (16:9) |
| Minimum video frame | 640x480 |
| Minimum window | 800x600 |
| Default window | 1000x700 |
| Status indicator | 16x16 pixels |
| Snapshot format | JPG |

### Video Specifications

- **Protocol:** RTSP (Real-Time Streaming Protocol)
- **Codec:** H.264 (typical)
- **Backend:** OpenCV FFMPEG
- **Transport:** UDP (default) or TCP
- **Output format:** RGB888 or Grayscale8

---

## Data Structures

### PrintInfo

Print job information received from printer:

| Field | Type | Description |
|-------|------|-------------|
| `is_printing` | bool | Whether currently printing |
| `progress` | float | Print progress percentage (0-100) |
| `current_layer` | int | Current layer number |
| `total_layer` | int | Total layers in print |
| `remain_time` | int | Remaining time in seconds |
| `total_time` | int | Total print time in seconds |
| `task_id` | str | Print job ID |
| `task_name` | str | File/task name |
| `status_code` | int | Raw status code |

### Printer Status Codes

| Code | Status |
|------|--------|
| 0 | Idle |
| 1 | Preparing to print |
| 2, 3, 4 | Printing |
| 7 | Finishing |
| 8 | Idle |

### Printer Info Format

Discovery returns printer info in format:
```
id|name|ip_address|model|firmware
```

---

## Network Protocol

### Discovery Protocol

1. Application sends UDP broadcast to port 3000
2. Discovery message: `M99999`
3. Printer responds with info string
4. Application parses response and extracts printer details

### WebSocket Protocol

**Message Topics:**
- `sdcp/request/{printer_id}` - Commands to printer
- `sdcp/response/{printer_id}` - Responses from printer
- `sdcp/status/{printer_id}` - Status updates
- `sdcp/notice/{printer_id}` - Notifications
- `sdcp/error/{printer_id}` - Error messages

**Status Request:**
```json
{
    "Topic": "sdcp/request/{printer_id}",
    "Data": {
        "Cmd": 255,
        "RequestID": "unique_id",
        "Data": {},
        "MainboardID": "printer_id",
        "From": 0
    }
}
```

### Field Name Compatibility

The parser supports multiple field name variations for different printer models:

| Data | Supported Field Names |
|------|----------------------|
| Is Printing | `IsPrinting`, `Printing`, `isPrinting`, `is_printing`, `Status` |
| Progress | `Progress`, `progress`, `PrintProgress`, `print_progress`, `Percent` |
| Current Layer | `CurrentLayer`, `Layer`, `current_layer`, `CurrentLine`, `LineNum`, `Layers` |
| Total Layers | `TotalLayer`, `TotalLayers`, `MaxLayer`, `Lines`, `total_layers`, `Slices` |
| Remaining Time | `RemainTime`, `TimeLeft`, `remain_time`, `RemainingTime` |
| Total Time | `TotalTime`, `total_time`, `TotalPrintTime`, `PrintTime` |
| UV Temperature | `UVTemp`, `UV`, `uv_temp`, `UVTemperature`, `LightTemp` |

---

## Troubleshooting

### Connection Issues

**Problem:** Cannot discover printer
- Ensure printer is on the same network
- Check if printer IP is reachable: `ping <printer_ip>`
- Try direct IP connection instead of discovery

**Problem:** WebSocket connection fails
- Verify port 3030 is not blocked by firewall
- Check printer is running latest firmware
- Restart the printer

**Problem:** Video stream not working
- Try switching transport from UDP to TCP
- Verify RTSP path is correct (default: `/video`)
- Check port 554 accessibility

### Video Quality Issues

**Problem:** Choppy or laggy video
- Switch to TCP transport for more reliable delivery
- Reduce network congestion
- Check printer camera status

**Problem:** Black or frozen video
- Click Disconnect then Connect again
- Restart the application
- Verify camera is not disabled on printer

### Performance Issues

**Problem:** High CPU usage
- Disable video streaming when not needed
- Close other resource-intensive applications

**Problem:** Application not responding
- Check network connectivity
- Disconnect and reconnect to printer

### Snapshot Issues

**Problem:** Snapshot not saving
- Check Desktop folder permissions
- Ensure disk space is available
- Verify video stream is active

---

## Alternative GUI

An alternative Tkinter-based interface is available in `stats.py`:

```bash
python stats.py
```

This provides a simpler interface with:
- Tabbed layout (Status/Logs)
- Progress bar visualization
- Log file management with rotation

---

## License

This project is provided as-is for personal use.

---

## Changelog

### Version 1.5
- Current release
- PyQt5 GUI with video streaming
- Real-time printer monitoring
- Snapshot capability with timestamps
- Auto-connect feature
- Recent printers list
- Configurable RTSP transport and path
