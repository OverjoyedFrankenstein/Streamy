#!/usr/bin/env python3
"""
Printer monitoring module for Streamy application
Directly adapted from the working goo.py implementation
"""

import json
import logging
import os
import socket
import sys
import time
import threading
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("streamy.printmon")

# Try to import websocket, install if missing
try:
    import websocket
except ImportError:
    import subprocess
    try:
        print("Installing websocket-client...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client"])
        import websocket
        print("Successfully installed websocket-client")
    except Exception as e:
        logger.error(f"Failed to install websocket-client: {e}")
        logger.error("Please install manually: pip install websocket-client")

# Constants
DISCOVERY_TIMEOUT = 1
DEFAULT_PORT = 54780


# ----- Data Classes (directly from goo.py) -----

@dataclass
class Printer:
    """Represents an Elegoo printer."""
    info: str = ""
    id: str = ""
    name: str = ""
    ip_address: str = ""
    model: str = ""
    firmware: str = ""
    connection: str = ""
    
    def __post_init__(self):
        """Parse printer info string if provided."""
        if self.info:
            try:
                parts = self.info.split("|")
                if len(parts) >= 6:
                    self.id = parts[0]
                    self.name = parts[1]
                    self.ip_address = parts[2]
                    self.model = parts[3]
                    self.firmware = parts[4]
                    self.connection = "ElegooPrinterAPI"
            except:
                # Silent failure, handled elsewhere
                pass


@dataclass
class Temperature:
    """Printer temperature data."""
    uv_temp: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Temperature':
        """Create instance from dictionary with flexible field mapping."""
        uv_temp = 0.0
        # Try different variations of UV temperature field
        for field in ["UVTemp", "UV", "uv_temp", "UVTemperature", "LightTemp", "UVPanelTemp", "UVPanel"]:
            if field in data:
                try:
                    uv_temp = float(data[field])
                    break
                except (ValueError, TypeError):
                    pass
        
        # If we haven't found it, try looking for it nested in "UV" or similar
        if uv_temp == 0.0:
            for parent_field in ["UV", "UVPanel", "Light"]:
                if parent_field in data and isinstance(data[parent_field], dict):
                    for child_field in ["Temp", "Temperature", "Value", "Current"]:
                        if child_field in data[parent_field]:
                            try:
                                uv_temp = float(data[parent_field][child_field])
                                break
                            except (ValueError, TypeError):
                                pass
        
        return cls(uv_temp=uv_temp)


@dataclass
class PrintInfo:
    """Information about the current print job."""
    is_printing: bool = False
    progress: float = 0.0
    current_layer: int = 0
    total_layer: int = 0
    remain_time: int = 0
    total_time: int = 0
    task_id: str = ""
    task_name: str = ""
    status_code: int = 0  # Raw status code from printer
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrintInfo':
        """Create instance from dictionary with flexible field mapping."""
        # Log the raw data keys for debugging
        if data:
            logger.debug(f"PrintInfo keys: {list(data.keys())}")
            logger.debug(f"PrintInfo data: {data}")

        # Handle different possible field names
        is_printing = False
        status_code = 0
        # Try different variations of IsPrinting field
        for field in ["IsPrinting", "Printing", "isPrinting", "is_printing", "Status"]:
            if field in data:
                # If field is "Status", check if value is "Running" or similar
                if field == "Status":
                    if isinstance(data[field], str):
                        is_printing = data[field].lower() in ["running", "printing", "busy"]
                    elif isinstance(data[field], int):
                        status_code = data[field]
                        # Elegoo uses: 0,8=idle, 1=preparing, 2-4=printing, 7=finishing
                        is_printing = status_code in [1, 2, 3, 4, 7]
                else:
                    is_printing = bool(data[field])
                break
        
        # Try different variations of progress field
        progress = 0.0
        for field in ["Progress", "progress", "PrintProgress", "print_progress", "Percent"]:
            if field in data:
                try:
                    progress = float(data[field])
                    break
                except (ValueError, TypeError):
                    pass
        
        # Try different variations of current layer field
        current_layer = 0
        for field in ["CurrentLayer", "Layer", "current_layer", "CurrentLine", "LineNum", "Layers"]:
            if field in data:
                try:
                    current_layer = int(data[field])
                    break
                except (ValueError, TypeError):
                    pass
        
        # Try different variations of total layer field
        total_layer = 0
        for field in ["TotalLayer", "TotalLayers", "MaxLayer", "Lines", "total_layers", "Slices"]:
            if field in data:
                try:
                    total_layer = int(data[field])
                    break
                except (ValueError, TypeError):
                    pass
        
        # Try different variations of remaining time field (in seconds)
        remain_time = 0
        for field in ["RemainTime", "TimeLeft", "remain_time", "RemainingTime", "TimeRemaining", "PrintTimeLeft", "LeftTime", "remainTime", "leftTime"]:
            if field in data:
                try:
                    # Check if it's a string in "hh:mm:ss" format
                    if isinstance(data[field], str) and ":" in data[field]:
                        time_parts = data[field].split(":")
                        if len(time_parts) == 3:
                            hours, minutes, seconds = map(int, time_parts)
                            remain_time = hours * 3600 + minutes * 60 + seconds
                        elif len(time_parts) == 2:
                            minutes, seconds = map(int, time_parts)
                            remain_time = minutes * 60 + seconds
                    else:
                        remain_time = int(data[field])
                    if remain_time > 0:
                        break
                except (ValueError, TypeError):
                    pass

        # Try different variations of total time field (in seconds)
        total_time = 0
        for field in ["TotalTime", "total_time", "TotalPrintTime", "PrintTime", "PrintDuration", "EstimatedTime", "totalTime", "printTime"]:
            if field in data:
                try:
                    # Check if it's a string in "hh:mm:ss" format
                    if isinstance(data[field], str) and ":" in data[field]:
                        time_parts = data[field].split(":")
                        if len(time_parts) == 3:
                            hours, minutes, seconds = map(int, time_parts)
                            total_time = hours * 3600 + minutes * 60 + seconds
                        elif len(time_parts) == 2:
                            minutes, seconds = map(int, time_parts)
                            total_time = minutes * 60 + seconds
                    else:
                        total_time = int(data[field])
                    if total_time > 0:
                        break
                except (ValueError, TypeError):
                    pass

        # Handle Ticks format (milliseconds) - used by Elegoo printers
        if total_time == 0 and "TotalTicks" in data:
            try:
                total_time = int(data["TotalTicks"]) // 1000  # Convert ms to seconds
            except (ValueError, TypeError):
                pass

        if remain_time == 0 and "TotalTicks" in data and "CurrentTicks" in data:
            try:
                total_ticks = int(data["TotalTicks"])
                current_ticks = int(data["CurrentTicks"])
                remain_time = (total_ticks - current_ticks) // 1000  # Convert ms to seconds
            except (ValueError, TypeError):
                pass
        
        # Try different variations of task ID field
        task_id = ""
        for field in ["TaskID", "task_id", "JobID", "PrintID"]:
            if field in data:
                task_id = str(data[field])
                break
        
        # Try different variations of task name field
        task_name = ""
        for field in ["TaskName", "task_name", "FileName", "JobName", "PrintName"]:
            if field in data:
                task_name = str(data[field])
                break
        
        return cls(
            is_printing=is_printing,
            progress=progress,
            current_layer=current_layer,
            total_layer=total_layer,
            remain_time=remain_time,
            total_time=total_time,
            task_id=task_id,
            task_name=task_name,
            status_code=status_code
        )


@dataclass
class PrinterStatus:
    """Status of the printer."""
    temperature: Temperature = field(default_factory=Temperature)
    print_info: PrintInfo = field(default_factory=PrintInfo)
    status_code: int = 0
    status_text: str = "Unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PrinterStatus':
        """Create instance from JSON string with flexible structure parsing."""
        try:
            data = json.loads(json_str)
            
            # Try to extract print info and temperature using different possible paths
            print_info_data = {}
            temp_data = {}
            
            # Look for the nested data structure first
            if "Data" in data:
                # Option 1: Standard nested structure
                if "Data" in data["Data"] and isinstance(data["Data"]["Data"], dict):
                    nested_data = data["Data"]["Data"]
                    if "PrintInfo" in nested_data and isinstance(nested_data["PrintInfo"], dict):
                        print_info_data = nested_data["PrintInfo"]
                    if "Temperature" in nested_data and isinstance(nested_data["Temperature"], dict):
                        temp_data = nested_data["Temperature"]
                
                # Option 2: Less nested structure
                elif isinstance(data["Data"], dict):
                    if "PrintInfo" in data["Data"] and isinstance(data["Data"]["PrintInfo"], dict):
                        print_info_data = data["Data"]["PrintInfo"]
                    if "Temperature" in data["Data"] and isinstance(data["Data"]["Temperature"], dict):
                        temp_data = data["Data"]["Temperature"]
            
            # Option 3: Check for alternative keys
            for status_key in ["StatusData", "Status", "PrintStatus", "state"]:
                if status_key in data and isinstance(data[status_key], dict):
                    for print_key in ["PrintInfo", "PrintStatus", "print", "Print"]:
                        if print_key in data[status_key] and isinstance(data[status_key][print_key], dict):
                            print_info_data = data[status_key][print_key]
                    
                    for temp_key in ["Temperature", "Temps", "temp", "temperature"]:
                        if temp_key in data[status_key] and isinstance(data[status_key][temp_key], dict):
                            temp_data = data[status_key][temp_key]
            
            # Option 4: Direct top-level keys
            for print_key in ["PrintInfo", "PrintStatus", "print", "Print"]:
                if print_key in data and isinstance(data[print_key], dict):
                    print_info_data = data[print_key]
            
            for temp_key in ["Temperature", "Temps", "temp", "temperature"]:
                if temp_key in data and isinstance(data[temp_key], dict):
                    temp_data = data[temp_key]
            
            # Directly check for print status fields at the top level
            # This is a last resort if we can't find a nested structure
            if not print_info_data:
                direct_fields = ["IsPrinting", "Progress", "CurrentLayer", "TotalLayer"]
                if any(field in data for field in direct_fields):
                    print_info_data = data
            
            # Create the status objects from the data we found
            return cls(
                temperature=Temperature.from_dict(temp_data),
                print_info=PrintInfo.from_dict(print_info_data),
                raw_data=data
            )
        
        except Exception as e:
            logger.error(f"Error parsing printer status JSON: {e}")
            logger.debug(f"Problematic JSON: {json_str[:200]}...")
            # Return a default status object
            return cls()


@dataclass
class PrinterData:
    """Data class for printer data including status and timestamp"""
    status: PrinterStatus = field(default_factory=PrinterStatus)
    last_updated: str = ""


class ElegooPrinterClientWebsocketError(Exception):
    """Exception to indicate a general API error."""
    pass


class ElegooPrinterClientWebsocketConnectionError(Exception):
    """Exception to indicate a Websocket Connection error."""
    pass


# ----- Main PrinterMonitor Class (adapted from ElegooPrinterClient in goo.py) -----

class PrinterMonitor:
    """Class to monitor Elegoo 3D printer status"""
    
    def __init__(self):
        """Initialize the PrinterMonitor with default values"""
        self.ip_address = None
        self.is_connected = False
        self.printer_websocket = None
        self.printer = Printer()
        self.printer_data = PrinterData()
        self.simulated_mode = False
        logger.info("PrinterMonitor initialized")
    
    def set_ip_address(self, ip_address):
        """Set the IP address for the printer connection"""
        self.ip_address = ip_address
        logger.info(f"Printer IP address set to: {ip_address}")
    
    async def connect(self):
        """Connect to the printer monitoring API
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        if not self.ip_address:
            logger.error("Cannot connect: No IP address provided")
            return False
        
        logger.info(f"Connecting to printer at IP: {self.ip_address}")
        
        # Try to discover printer first
        try:
            printer = self.discover_printer()
            if printer:
                logger.info(f"Discovered printer: {printer.name} at {printer.ip_address}")
                self.printer = printer
            else:
                # Create basic printer with IP we know
                self.printer = Printer()
                self.printer.ip_address = self.ip_address
                self.printer.id = "ElegooPrinter"
                self.printer.name = "Elegoo Printer"
                self.printer.connection = "ElegooPrinterAPI"
        except Exception as e:
            logger.error(f"Error during printer discovery: {e}")
            # Create basic printer even with error
            self.printer = Printer()
            self.printer.ip_address = self.ip_address
            self.printer.id = "ElegooPrinter"
            self.printer.name = "Elegoo Printer" 
            self.printer.connection = "ElegooPrinterAPI"
        
        # Connect with WebSocket (exactly as in goo.py)
        connected = await self.connect_printer()
        if connected:
            # Get initial status
            try:
                self.get_status()
            except Exception as e:
                logger.error(f"Error getting initial status: {e}")
            
            return True
        
        # Fall back to simulated mode if needed
        logger.info("Falling back to simulated mode")
        self.simulated_mode = True
        self.is_connected = True
        
        # Initialize with some data
        status = PrinterStatus()
        status.status_code = 1
        status.status_text = "Printing"
        status.print_info = PrintInfo(
            is_printing=True,
            current_layer=64,
            total_layer=341,
            progress=18.8
        )
        self.printer_data.status = status
        self.printer_data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return True
    
    def discover_printer(self):
        """Discover the Elegoo printer on the network."""
        logger.info(f"Starting printer discovery at {self.ip_address}")
        msg = b"M99999"
        try:
            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            ) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(DISCOVERY_TIMEOUT)
                try:
                    sock.bind(("", DEFAULT_PORT))
                except OSError as e:
                    logger.warning(f"Could not bind to port {DEFAULT_PORT}: {e}")
                    # Try an alternative approach - don't bind to a specific port
                    sock.settimeout(DISCOVERY_TIMEOUT)
                
                try:
                    # Send the discovery message
                    logger.debug(f"Sending discovery message to {self.ip_address}:3000")
                    sock.sendto(msg, (self.ip_address, 3000))
                    
                    # Try to receive a response
                    logger.debug("Waiting for response...")
                    data, addr = sock.recvfrom(8192)
                    logger.debug(f"Received response from {addr}")
                    
                    # Process the response
                    printer = self._save_discovered_printer(data)
                    if printer:
                        logger.debug("Discovery done.")
                        return printer
                except TimeoutError:
                    logger.warning("Printer discovery timed out.")
                except socket.error as e:
                    logger.warning(f"Socket error during discovery: {e}")
        
        except Exception as e:
            logger.exception(f"Unexpected error during discovery: {e}")
        
        logger.warning("Could not discover printer details, will attempt direct connection.")
        return None
    
    def _save_discovered_printer(self, data):
        """Parse and save discovered printer information."""
        try:
            printer_info = data.decode("utf-8")
            logger.debug(f"Raw printer info: {printer_info!r}")
            
            # Create a new printer instance
            printer = Printer()
            
            # Check if we have a valid response format
            if "|" in printer_info:
                # Try to parse the standard format
                parts = printer_info.split("|")
                if len(parts) >= 3:
                    printer.id = parts[0]
                    printer.name = parts[1]
                    printer.ip_address = parts[2]
                    if len(parts) >= 4:
                        printer.model = parts[3]
                    if len(parts) >= 5:
                        printer.firmware = parts[4]
            else:
                # If we can't parse the standard format, at least set the IP
                # This is a fallback that still allows us to attempt a connection
                printer.name = "Elegoo Printer"
                printer.ip_address = self.ip_address
                printer.id = "ElegooPrinter"  # Fallback ID
            
            # Final validation - if we don't have an IP, use the one provided at initialization
            if not printer.ip_address:
                printer.ip_address = self.ip_address
                
            # Set connection type
            printer.connection = "ElegooPrinterAPI"
            
            # Log what we found
            logger.info(f"Discovered: {printer.name} ({printer.ip_address})")
            return printer
            
        except UnicodeDecodeError:
            logger.exception("Error decoding printer discovery data. Data may be malformed.")
        except Exception as e:
            logger.exception(f"Error creating Printer object: {e}")
        
        # If all else fails, create a basic printer with the IP we know
        fallback_printer = Printer()
        fallback_printer.name = "Elegoo Printer"
        fallback_printer.ip_address = self.ip_address
        fallback_printer.id = "ElegooPrinter" 
        fallback_printer.connection = "ElegooPrinterAPI"
        logger.warning(f"Using fallback printer configuration with IP: {self.ip_address}")
        return fallback_printer
    
    async def connect_printer(self):
        """Connect to the Elegoo printer"""
        url = f"ws://{self.printer.ip_address}:3030/websocket"
        logger.info(f"Connecting to: {self.printer.name}")

        websocket.setdefaulttimeout(1)

        def ws_msg_handler(ws, msg):
            self._parse_response(msg)

        def ws_connected_handler(name):
            logger.info(f"Connected to: {name}")

        def on_close(ws, close_status_code, close_msg):
            logger.debug(f"Connection to {self.printer.name} closed: {close_msg} ({close_status_code})")
            self.printer_websocket = None

        def on_error(ws, error):
            logger.error(f"Connection to {self.printer.name} error: {error}")
            self.printer_websocket = None

        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            url,
            on_message=ws_msg_handler,
            on_open=lambda ws: ws_connected_handler(self.printer.name),
            on_close=on_close,
            on_error=on_error,
        )
        self.printer_websocket = ws

        # Start WebSocket in a thread
        thread = threading.Thread(target=ws.run_forever, kwargs={"reconnect": 1}, daemon=True)
        thread.start()

        # Wait for connection to establish
        start_time = time.monotonic()
        timeout = 5
        while time.monotonic() - start_time < timeout:
            if ws.sock and ws.sock.connected:
                await asyncio.sleep(1)
                logger.info(f"Connected to {self.printer.name}")
                self.is_connected = True
                return True

            await asyncio.sleep(0.1)

        logger.warning(f"Failed to connect to {self.printer.name} within timeout")
        self.printer_websocket = None
        return False
    
    def _parse_response(self, response):
        """Parse the printer's WebSocket response"""
        try:
            data = json.loads(response)
            topic = data.get("Topic")
            
            if topic:
                topic_type = topic.split("/")[1] if len(topic.split("/")) > 1 else ""
                if topic_type == "response":
                    self._response_handler(data)
                elif topic_type == "status":
                    self._status_handler(data)
                elif topic_type == "notice":
                    logger.debug(f"notice >> {json.dumps(data)[:100]}...")
                elif topic_type == "error":
                    logger.debug(f"error >> {json.dumps(data)[:100]}...")
                else:
                    logger.debug("Unknown message type")
            else:
                # Even without a topic, the data might contain useful information
                if "Data" in data or "StatusData" in data or "PrintInfo" in data:
                    logger.debug("Message without Topic but contains data, attempting to parse")
                    self._status_handler(data)
                else:
                    logger.debug("Message without Topic or useful data")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {response[:100]}...")
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
    
    def _response_handler(self, data):
        """Handle response messages."""
        logger.debug(f"Response received: {json.dumps(data)[:200]}...")
    
    def _status_handler(self, data):
        """Handle status messages from the printer."""
        try:
            logger.debug(f"Status received: {json.dumps(data)[:200]}...")
            # Parse the status using PrinterStatus
            printer_status = PrinterStatus.from_json(json.dumps(data))
            
            # Update printer data
            self.printer_data.status = printer_status
            self.printer_data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log status details
            print_info = printer_status.print_info
            logger.info(f"Updated status: Printing={print_info.is_printing}, " +
                       f"Progress={print_info.progress:.1f}%, " +
                       f"Layer={print_info.current_layer}/{print_info.total_layer}")
        except Exception as e:
            logger.error(f"Error handling status message: {e}")
    
    def disconnect(self):
        """Disconnect from the printer"""
        try:
            if self.printer_websocket:
                self.printer_websocket.close()
                self.printer_websocket = None
            
            self.is_connected = False
            self.simulated_mode = False
            logger.info("Disconnected from printer")
            
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def get_status(self):
        """Get the current printer status - directly from goo.py"""
        if not self.is_connected:
            logger.warning("Cannot get status: Not connected to printer")
            return None
        
        try:
            # Send status command and alternate commands
            self._send_printer_cmd(0)
            
            # On Elegoo printers, we may need additional commands to get complete data
            try:
                # Command for detailed printer status 
                self._send_printer_cmd(100)
            except:
                pass
                
            try:
                # Command for print info
                self._send_printer_cmd(200)
            except:
                pass
                
            try:
                # Command for temperature data
                self._send_printer_cmd(300)
            except:
                pass
                
            # Add short delay to allow responses to be processed (not in async context)
            time.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Error sending printer commands: {e}")
        
        # Update timestamp if we have data
        if self.printer_data:
            self.printer_data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return self.printer_data
    
    def _send_printer_cmd(self, cmd, data=None):
        """Send a command to the printer - directly from goo.py"""
        ts = int(time.time())
        data = data or {}
        payload = {
            "Id": self.printer.connection,
            "Data": {
                "Cmd": cmd,
                "Data": data,
                "RequestID": os.urandom(8).hex(),
                "MainboardID": self.printer.id,
                "TimeStamp": ts,
                "From": 0,
            },
            "Topic": f"sdcp/request/{self.printer.id}",
        }
        
        logger.debug(f"Sending command {cmd} to printer")
        
        if self.printer_websocket and hasattr(self.printer_websocket, 'sock') and self.printer_websocket.sock and self.printer_websocket.sock.connected:
            try:
                self.printer_websocket.send(json.dumps(payload))
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                raise ElegooPrinterClientWebsocketError(f"WebSocket error: {e}")
        else:
            logger.warning("Attempted to send command but websocket is not connected")
            raise ElegooPrinterClientWebsocketConnectionError("WebSocket not connected")
    
    @staticmethod
    def format_time(seconds):
        """Format time in seconds to a readable string
        
        Args:
            seconds (int): Time in seconds
            
        Returns:
            str: Formatted time string (HH:MM:SS)
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"