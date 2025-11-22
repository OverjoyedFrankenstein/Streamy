# Streamy

**Version 1.5**

A desktop application for streaming RTSP video from 3D printer cameras and monitoring printer status in real-time.

**Contact:** data_heavy@proton.me
**GitHub:** https://github.com/OverjoyedFrankenstein/Streamy

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Running as Python Script](#running-as-python-script)
  - [Building as macOS Application](#building-as-macos-application)
  - [Command Line Arguments](#command-line-arguments)
- [Configuration](#configuration)
- [File Descriptions](#file-descriptions)
- [Technical Specifications](#technical-specifications)
- [Data Structures](#data-structures)
- [Network Protocol](#network-protocol)
- [Troubleshooting](#troubleshooting)

---

## Overview

Streamy is a comprehensive PyQt5-based desktop application designed to monitor Elegoo 3D resin printers. It combines real-time video streaming with advanced printer status monitoring, providing a complete solution for remote 3D printer management.

### Key Capabilities

- **Live RTSP video streaming** from printer's built-in camera at ~30 FPS
- **Real-time print monitoring** including progress, layers, and time remaining
- **Snapshot capture** with optional timestamps
- **Automatic printer discovery** on local network via UDP broadcast
- **Custom printer naming** for managing multiple printers
- **Configurable RTSP settings** (transport, path, port)
- **Auto-connect on startup** for seamless monitoring

### Supported Devices

- Elegoo resin 3D printers with network connectivity (Mars, Saturn series)
- Any RTSP-compatible camera (port 554)
- Uses SDCP (Smart Device Communication Protocol) for Elegoo printer communication

---

## Features

### Video Streaming
- **RTSP video streaming** at ~30 FPS with frame buffering
- **UDP and TCP transport** protocols (configurable)
- **Customizable RTSP settings** (path, port)
- **Video enable/disable toggle** (monitoring continues when video is paused)
- **Real-time timestamp overlay** on video feed
- **Live FPS counter** (toggleable)
- **Frame buffering** for stability

### Print Monitoring
- **Print progress percentage** (calculated from layers)
- **Layer information**: Current layer / Total layers / Remaining layers
- **Time tracking**: Total print time and remaining time
- **Print job status**: Idle, Preparing, Printing, Finishing
- **Task/file name display**
- **UV temperature monitoring**
- **1-second status update interval** for real-time feedback
- **Large progress percentage display** (toggleable)

### Snapshot Capture
- **Save current frame** as JPG to custom location
- **Optional timestamp overlay** on snapshots
- **Custom save path configuration**
- **Filename format**: `printer_snapshot_YYYYMMDD_HHMMSS.jpg`

### Network Discovery
- **Automatic UDP broadcast discovery** on port 3000
- **Discovery message protocol**: `M99999`
- **Fallback to direct IP connection** if discovery fails
- **WebSocket communication** on port 3030 for status updates

### User Interface
- **Custom printer naming** for managing multiple printers
- **Recent printers dropdown** (up to 5)
- **Transport protocol selector** (UDP/TCP)
- **RTSP path and port customization**
- **Connect/Disconnect controls**
- **Settings dialog** with comprehensive configuration options
- **Color-coded status indicator**:
  - **Red:** Error/Disconnected
  - **Yellow:** Connecting/Warning
  - **Green:** Connected
  - **Gray:** Idle
- **Responsive layout** with minimum window size: 800x600
- **Video display**: minimum 640x480, scales to fit

### Keyboard Shortcuts
- **Enter** in IP field: Connect to printer

### Configuration
- **Auto-connect on startup** option
- **Custom printer display names**
- **Screenshot save path** configuration
- **Toggle timestamp on screenshots**
- **Toggle large progress display**
- **Toggle FPS counter**
- **Persistent settings** saved in JSON config file

---

## Project Structure

```
Streamy/
├── main.py                 # Main PyQt5 application (primary interface)
├── vidstream.py            # RTSP video streaming module
├── stats.py                # Printer monitoring module (also standalone Tkinter GUI)
├── build_app.py            # PyInstaller build script for macOS app
├── streamy_config.json     # User configuration file (auto-generated)
├── icon.png               # Application icon (optional)
├── README.md              # This file
└── build_app/             # Build directory (created by build_app.py)
    └── dist/              # Distribution directory
        └── Streamy-v1.5.app  # macOS application bundle
```

---

## Requirements

### System Requirements
- **Python**: 3.7 or higher
- **Operating System**: macOS, Windows, or Linux
- **Network**: Local network access to printer
- **Disk Space**: ~500 MB for app build (optional)

### Python Dependencies

All dependencies are automatically installed on first run:

| Package | Version | Purpose |
|---------|---------|---------|
| `opencv-python` | Latest | Video capture and image processing |
| `numpy` | Latest | Image manipulation |
| `PyQt5` | Latest | GUI framework |
| `websocket-client` | Latest | WebSocket communication with printer |
| `requests` | Latest | HTTP requests |

### Optional Build Dependencies

For building the standalone macOS app:

| Package | Purpose |
|---------|---------|
| `pyinstaller` | Create standalone application bundles |

---

## Installation

### Basic Installation

1. **Clone or download** the repository:
   ```bash
   git clone https://github.com/OverjoyedFrankenstein/Streamy.git
   cd Streamy
   ```

2. **Run the application**:
   ```bash
   python main.py
   ```

   Dependencies will be automatically installed on first run.

3. **Manual dependency installation** (if needed):
   ```bash
   pip install opencv-python numpy PyQt5 websocket-client requests
   ```

---

## Usage

### Running as Python Script

#### Basic Usage

1. **Launch the application**:
   ```bash
   python main.py
   ```

2. **First-time setup**:
   - Click the **Settings ⚙** button (bottom right)
   - Enter your printer's IP address
   - Configure RTSP settings if needed (defaults work for most Elegoo printers)
   - Optionally set a custom printer name
   - Click **Save Settings**

3. **Connect to printer**:
   - Click **Connect** button
   - Application will automatically:
     - Connect to RTSP video stream
     - Discover printer via UDP broadcast
     - Establish WebSocket connection for status updates
     - Begin streaming video and monitoring print status

4. **Monitor your print**:
   - View live video stream from printer camera
   - Monitor progress, layers, and time remaining
   - Take snapshots with the **Snapshot** button
   - Toggle video on/off with **Disable Video** button (monitoring continues)

5. **Disconnect**:
   - Click **Disconnect** when finished

#### Alternative Tkinter GUI

For a simpler, text-based interface with logging capabilities:

```bash
python stats.py
```

Features of the alternative GUI:
- Tabbed layout (Status/Logs)
- Progress bar visualization
- Log file management with rotation
- Text-based status display

### Building as macOS Application

To create a standalone macOS application bundle that can run without Python installed:

1. **Install PyInstaller** (if not already installed):
   ```bash
   pip install pyinstaller
   ```

2. **Run the build script**:
   ```bash
   python build_app.py
   ```

3. **Locate the built application**:
   - The app will be created at: `build_app/dist/Streamy-v1.5.app`
   - Build process includes:
     - Code signing (removes quarantine attributes)
     - Icon embedding
     - Dependency bundling
     - macOS compatibility fixes

4. **Run the application**:
   - Double-click `Streamy-v1.5.app` in Finder
   - Or from terminal:
     ```bash
     open build_app/dist/Streamy-v1.5.app
     ```

5. **Install the application** (optional):
   - Drag `Streamy-v1.5.app` to your Applications folder
   - Launch from Spotlight or Applications folder

#### Build Script Options

The `build_app.py` script performs the following:
- Creates PyInstaller spec file with all dependencies
- Bundles Python interpreter and all libraries
- Includes icon (if `icon.png` exists)
- Removes quarantine attributes for macOS
- Code signs the application
- Creates one-folder bundle in `build_app/dist/`

**Note:** The built application is ~200-500 MB due to bundled Python environment and dependencies.

### Command Line Arguments

```bash
python main.py [OPTIONS]
```

| Argument | Description | Example |
|----------|-------------|---------|
| `--ip <ADDRESS>` | IP address of printer (overrides auto-connect) | `--ip 192.168.1.100` |

**Examples:**

```bash
# Connect to specific printer on startup
python main.py --ip 192.168.1.100

# Launch with default settings
python main.py
```

---

## Configuration

### Configuration File

Settings are automatically saved in `streamy_config.json` in the application directory:

```json
{
  "recent_printers": ["192.168.1.100", "192.168.1.101"],
  "last_used_printer": "192.168.1.100",
  "include_timestamp": true,
  "video_enabled": true,
  "auto_connect": true,
  "transport": "udp",
  "rtsp_path": "/video",
  "rtsp_port": 554,
  "printer_display_name": "My Mars 3",
  "screenshot_path": "/Users/username/Desktop",
  "show_big_progress": true,
  "show_fps": true
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
| `rtsp_port` | number | `554` | RTSP port number |
| `printer_display_name` | string | `""` | Custom name for printer |
| `screenshot_path` | string | `"~/Desktop"` | Directory for saving snapshots |
| `show_big_progress` | boolean | `true` | Show large progress percentage |
| `show_fps` | boolean | `true` | Show FPS counter |

### Accessing Settings

All settings can be configured through the **Settings ⚙** dialog in the application.

---

## File Descriptions

### Core Application Files

#### `main.py` (Primary Application)
The main entry point and GUI application built with PyQt5.

**Key Components:**
- `StreamyApp`: Main application window class
  - Integrates video streaming and printer monitoring
  - Manages UI updates and user interactions
  - Handles connection/disconnection logic
  - Updates status indicators and labels
- `Config`: Configuration management class
  - Loads/saves settings from/to JSON file
  - Manages recent printers list
  - Handles all user preferences
- `StatusIndicator`: Custom colored status dot widget
- `SettingsDialog`: Settings and About dialog

**Features:**
- Real-time video display with OpenCV → Qt conversion
- Asynchronous printer connection
- FPS calculation and display
- Snapshot capture functionality
- Auto-connect on startup
- Comprehensive settings management

**Usage:**
```bash
python main.py [--ip IP_ADDRESS]
```

#### `vidstream.py` (Video Streaming Module)
Handles all RTSP video streaming functionality.

**Key Components:**
- `VideoStreamer`: Main video streaming class
  - Connects to RTSP streams using OpenCV
  - Manages frame capture and buffering
  - Handles transport protocol (UDP/TCP)
  - Creates placeholder images

**Features:**
- RTSP connection with configurable transport
- Frame capture with error handling
- Timestamp overlay on frames
- Snapshot capture with custom save paths
- "No Connection" and "Paused" image generation
- OpenCV error suppression

**Methods:**
- `connect()`: Establish RTSP connection
- `disconnect()`: Close RTSP connection
- `get_frame()`: Retrieve current frame
- `take_snapshot()`: Save current frame to file
- `add_timestamp_to_frame()`: Overlay timestamp
- `set_transport()`, `set_path()`, `set_port()`: Configure RTSP

#### `stats.py` (Printer Monitor Module)
Printer monitoring via WebSocket and UDP discovery. Also includes a standalone Tkinter GUI.

**Key Components:**
- `PrinterMonitor`: WebSocket client for printer status
  - Discovers printers via UDP broadcast
  - Connects to WebSocket on port 3030
  - Sends status requests (Cmd: 255)
  - Parses printer responses
  - Extracts print information
- `PrintInfo`: Dataclass for print job information
- `Printer`: Dataclass for printer device information
- `PrinterStatus`: Dataclass for overall printer status
- `Temperature`: Dataclass for temperature readings

**Features:**
- Automatic printer discovery
- WebSocket communication using SDCP protocol
- Flexible field mapping for different printer models
- Time formatting utilities
- Status code interpretation
- Standalone Tkinter GUI (when run directly)

**Usage:**
```bash
# As standalone Tkinter GUI
python stats.py

# As module (imported by main.py)
from stats import PrinterMonitor
```

#### `build_app.py` (Build Script)
PyInstaller build script for creating standalone macOS application.

**Features:**
- Generates PyInstaller spec file
- Configures one-folder bundle
- Includes all dependencies
- Adds application icon
- Removes macOS quarantine attributes
- Code signs the application
- Handles missing modules gracefully

**Usage:**
```bash
python build_app.py
```

**Output:**
- Creates `build_app/dist/Streamy-v1.5.app`
- Application bundle includes:
  - Python interpreter
  - All dependencies
  - Application resources
  - Code signature

### Configuration Files

#### `streamy_config.json`
Auto-generated configuration file storing user preferences.

- Created on first run
- Updated when settings change
- Contains all configuration options (see [Configuration](#configuration))

#### `icon.png` (Optional)
Application icon file.

- Used for window icon in Python script
- Embedded in macOS app bundle
- Recommended size: 512x512 pixels
- Format: PNG with transparency

---

## Technical Specifications

### Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 3000 | UDP | Printer discovery (broadcast) |
| 54780 | UDP | Discovery response binding |
| 3030 | WebSocket | Printer status communication (SDCP) |
| 554 | RTSP | Video streaming |

### Timeouts and Intervals

| Parameter | Value | Description |
|-----------|-------|-------------|
| Discovery timeout | 1 second | UDP broadcast timeout |
| WebSocket timeout | 5 seconds | Connection timeout |
| Video frame interval | 33 ms | ~30 FPS update rate |
| Status update interval | 1 second | Printer status polling |
| FPS calculation interval | 1 second | FPS counter update |
| Auto-connect delay | 1 second | Startup delay before auto-connect |
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
| Minimum window size | 800x600 |
| Default window size | 1000x700 |
| Status indicator size | 16x16 pixels |
| Snapshot format | JPG |

### Video Specifications

- **Protocol:** RTSP (Real-Time Streaming Protocol)
- **Codec:** H.264 (typical for Elegoo printers)
- **Backend:** OpenCV with FFMPEG
- **Transport:** UDP (default, faster) or TCP (more reliable)
- **Output format:** RGB888 or Grayscale8
- **Frame rate:** ~30 FPS
- **Resolution:** Depends on printer camera (typically 640x480 or 1280x720)

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
| `status_code` | int | Raw status code from printer |

### Printer Status Codes

| Code | Status |
|------|--------|
| 0 | Idle |
| 1 | Preparing to print |
| 2, 3, 4 | Printing |
| 7 | Finishing |
| 8 | Idle |

### Printer Info Format

Discovery returns printer info in pipe-delimited format:
```
id|name|ip_address|model|firmware|connection
```

Example:
```
12345|My Mars|192.168.1.100|Mars 3 Pro|V4.5.3|ElegooPrinterAPI
```

---

## Network Protocol

### Discovery Protocol

1. Application sends UDP broadcast to `255.255.255.255:3000`
2. Discovery message: `M99999`
3. Printer responds with info string (pipe-delimited)
4. Application parses response and extracts printer details
5. If discovery fails, direct IP connection is used

### WebSocket Protocol (SDCP)

**Connection URL:**
```
ws://{printer_ip}:3030
```

**Message Topics:**
- `sdcp/request/{printer_id}` - Commands to printer
- `sdcp/response/{printer_id}` - Responses from printer
- `sdcp/status/{printer_id}` - Status updates
- `sdcp/notice/{printer_id}` - Notifications
- `sdcp/error/{printer_id}` - Error messages

**Status Request Message:**
```json
{
    "Topic": "sdcp/request/{printer_id}",
    "Data": {
        "Cmd": 255,
        "RequestID": "streamy_12345",
        "Data": {},
        "MainboardID": "{printer_id}",
        "From": 0
    }
}
```

**Status Response Format:**
```json
{
    "Topic": "sdcp/status/{printer_id}",
    "Data": {
        "Attributes": {
            "Name": "printer_name"
        },
        "Data": {
            "Status": 2,
            "CurrentLayer": 150,
            "TotalLayer": 1000,
            "Progress": 15.0,
            "RemainTime": 3600,
            "TotalTime": 4200,
            "FileName": "model.ctb"
        }
    }
}
```

### Field Name Compatibility

The parser supports multiple field name variations for different Elegoo printer models:

| Data | Supported Field Names |
|------|----------------------|
| Is Printing | `IsPrinting`, `Printing`, `isPrinting`, `is_printing`, `Status` |
| Progress | `Progress`, `progress`, `PrintProgress`, `print_progress`, `Percent` |
| Current Layer | `CurrentLayer`, `Layer`, `current_layer`, `CurrentLine`, `LineNum`, `Layers` |
| Total Layers | `TotalLayer`, `TotalLayers`, `MaxLayer`, `Lines`, `total_layers`, `Slices` |
| Remaining Time | `RemainTime`, `TimeLeft`, `remain_time`, `RemainingTime` |
| Total Time | `TotalTime`, `total_time`, `TotalPrintTime`, `PrintTime` |
| Task Name | `FileName`, `File`, `TaskName`, `task_name`, `file_name` |
| UV Temperature | `UVTemp`, `UV`, `uv_temp`, `UVTemperature`, `LightTemp` |

---

## Troubleshooting

### Connection Issues

**Problem:** Cannot discover printer
- Ensure printer is on the same **local network**
- Check if printer IP is reachable: `ping <printer_ip>`
- Verify printer is powered on and connected to WiFi
- Try direct IP connection instead of discovery
- Check firewall settings (allow UDP port 3000)

**Problem:** WebSocket connection fails
- Verify port 3030 is not blocked by firewall
- Check printer is running latest firmware
- Restart the printer and try again
- Verify printer's WebSocket service is enabled

**Problem:** Video stream not working
- Try switching transport from **UDP to TCP** in settings
- Verify RTSP path is correct (default: `/video`)
- Check port 554 is accessible
- Ensure camera is enabled on printer
- Some printers may use different RTSP paths (try `/` or `/stream`)

**Problem:** Auto-connect not working
- Verify **Auto-connect on startup** is enabled in Settings
- Check that **last_used_printer** is set in config file
- Ensure printer is powered on before launching Streamy
- Try manual connection first to verify settings

### Video Quality Issues

**Problem:** Choppy or laggy video
- Switch to **TCP transport** for more reliable delivery
- Reduce network congestion (close other bandwidth-heavy apps)
- Check WiFi signal strength on printer
- Restart your router
- Try connecting via Ethernet (if supported by printer)

**Problem:** Black or frozen video
- Click **Disconnect** then **Connect** again
- Restart the application
- Verify camera is not disabled on printer
- Check RTSP path and port in settings
- Try the alternative transport protocol

**Problem:** Video shows "No Connection"
- Verify you've clicked **Connect** button
- Check IP address is correct
- Ensure printer camera is enabled
- Try disabling and re-enabling video with **Disable Video** button

### Performance Issues

**Problem:** High CPU usage
- Disable video streaming when not needed (**Disable Video** button)
- Close other resource-intensive applications
- Reduce window size
- Consider using the lightweight Tkinter GUI (`stats.py`)

**Problem:** Application not responding
- Check network connectivity
- Click **Disconnect** and wait 5 seconds
- Reconnect to printer
- Restart the application
- Check system resources (RAM, CPU)

### Snapshot Issues

**Problem:** Snapshot not saving
- Check screenshot folder permissions in Settings
- Ensure disk space is available
- Verify video stream is active (not paused)
- Try changing screenshot save path in Settings
- Check folder path is valid and exists

**Problem:** Snapshot has no timestamp
- Enable **Include timestamp on screenshots** in Settings
- Verify system clock is correct

### Printer Status Issues

**Problem:** Status not updating
- Verify WebSocket connection is established (status shows "Connected")
- Check printer firmware version (update if available)
- Restart printer
- Check network stability
- Look for errors in application logs

**Problem:** Incorrect layer/time information
- Some printer models report data differently
- Progress calculation is based on layers (current/total × 100)
- Times are estimated and may vary
- Verify print is actually running

**Problem:** Status shows "Not Connected" but video works
- WebSocket connection may have failed
- Video (RTSP) and status (WebSocket) use different protocols
- Check printer's WebSocket service
- Try reconnecting

### macOS Application Issues

**Problem:** App won't open (security warning)
- macOS may block unsigned apps
- Right-click app → **Open** → Confirm
- Or: System Preferences → Security → Allow app
- Build script includes code signing, but may need developer certificate

**Problem:** App crashes on launch
- Verify macOS version compatibility (10.13+)
- Check build process completed successfully
- Try running from terminal to see error messages:
  ```bash
  /Applications/Streamy-v1.5.app/Contents/MacOS/Streamy-v1.5
  ```
- Rebuild application with `python build_app.py`

**Problem:** App size is very large (~500 MB)
- This is normal - includes Python and all dependencies
- PyInstaller bundles entire Python environment
- Can't be reduced without excluding dependencies

### General Troubleshooting Steps

1. **Check Printer**:
   - Is it powered on?
   - Is it connected to WiFi?
   - Is camera enabled?
   - Is firmware up to date?

2. **Check Network**:
   - Is computer on same network as printer?
   - Can you ping printer IP?
   - Is firewall blocking connections?
   - Try connecting to printer via Elegoo app first

3. **Check Application**:
   - Are settings correct?
   - Try deleting `streamy_config.json` and reconfiguring
   - Restart application
   - Check for Python errors in terminal

4. **Check Dependencies**:
   - Reinstall dependencies: `pip install --upgrade opencv-python numpy PyQt5 websocket-client requests`
   - Verify Python version: `python --version` (should be 3.7+)

5. **Get Help**:
   - Open an issue on GitHub with:
     - Error messages
     - Printer model and firmware version
     - Operating system and Python version
     - Steps to reproduce the problem

---

## Development

### Running in Debug Mode

Enable detailed logging for troubleshooting:

```python
# Edit main.py, line 92-95
logging.basicConfig(
    level=logging.DEBUG,  # Change ERROR to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENCV_LOG_LEVEL` | Set to `ERROR` to suppress OpenCV messages |
| `OPENCV_FFMPEG_CAPTURE_OPTIONS` | RTSP transport options (set by app) |

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## License

This project is provided as-is for personal use.

---

## Changelog

### Version 1.5 (Current)
- PyQt5 GUI with video streaming
- Real-time printer monitoring via WebSocket
- Snapshot capability with timestamps
- Auto-connect feature
- Recent printers list (up to 5)
- Configurable RTSP transport and path
- Custom printer naming
- Settings dialog with all options
- Large progress percentage display
- FPS counter (toggleable)
- Custom screenshot save path
- macOS app build script with PyInstaller
- Comprehensive error handling
- Status indicator with color coding
- Video pause/resume functionality
- Alternative Tkinter GUI in stats.py

### Future Enhancements
- Multiple printer monitoring
- Print queue management
- Time-lapse recording
- Email/push notifications
- Temperature graphing
- Print history tracking

---

## Credits

Created and maintained by **data_heavy@proton.me**

Special thanks to:
- The Elegoo community for protocol documentation
- OpenCV and PyQt5 teams for excellent libraries
- Beta testers and contributors

---

## Support

For issues, questions, or suggestions:
- **GitHub Issues**: https://github.com/OverjoyedFrankenstein/Streamy/issues
- **Email**: data_heavy@proton.me

When reporting issues, please include:
- Streamy version
- Printer model and firmware
- Operating system
- Python version
- Error messages or screenshots
- Steps to reproduce

---

**Enjoy monitoring your 3D prints with Streamy!** 🖨️
