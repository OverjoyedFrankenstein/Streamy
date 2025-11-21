#!/usr/bin/env python3
"""
Elegoo Printer GUI Monitor - A GUI application to monitor Elegoo printers.
Built upon the functionality in goo.py.
"""

import asyncio
import json
import logging
import os
import socket
import sys
import threading
import time
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Configure logging for printmon
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("streamy.printmon")

# Note: Package checking is handled by main.py for Streamy app

# Import websocket (required for PrinterMonitor)
import websocket

# Conditional imports for GUI (only needed when running stats.py directly)
# These may fail in PyInstaller builds that exclude tkinter
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    from PIL import Image, ImageTk, ImageDraw
    _HAS_GUI = True
except ImportError:
    _HAS_GUI = False
    tk = None
    ttk = None
    scrolledtext = None
    messagebox = None
    ImageTk = None

# Import all the classes and functions from goo.py that we need
# We're copying the relevant classes directly to make the script self-contained

# -----------------------------------------------------------------------------
# Classes from goo.py - Copy of the data models and client implementation
# -----------------------------------------------------------------------------

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
            except (ValueError, IndexError):
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
    temperature: Temperature = None
    print_info: PrintInfo = None
    status_code: int = 0
    status_text: str = "Unknown"
    raw_data: dict = None

    def __post_init__(self):
        if self.temperature is None:
            self.temperature = Temperature()
        if self.print_info is None:
            self.print_info = PrintInfo()
        if self.raw_data is None:
            self.raw_data = {}
    
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
                print_info=PrintInfo.from_dict(print_info_data)
            )
        
        except Exception as e:
            logger = logging.getLogger("elegoo_monitor")
            logger.error(f"Error parsing printer status JSON: {e}")
            logger.debug(f"Problematic JSON: {json_str[:200]}...")
            # Return a default status object
            return cls()


@dataclass
class PrinterData:
    """Container for all printer data."""
    status: PrinterStatus = None
    last_updated: str = ""

    def __post_init__(self):
        if self.status is None:
            self.status = PrinterStatus()
        if not self.last_updated:
            self.last_updated = ""


class ElegooPrinterClientWebsocketError(Exception):
    """Exception to indicate a general API error."""


class ElegooPrinterClientWebsocketConnectionError(Exception):
    """Exception to indicate a Websocket Connection error."""


class ElegooPrinterClient:
    """
    Client for interacting with an Elegoo printer.
    Uses the SDCP Protocol.
    """

    def __init__(self, ip_address: str, logger: Any) -> None:
        """Initialize the ElegooPrinterClient."""
        self.ip_address: str = ip_address
        self.printer_websocket: Optional[websocket.WebSocketApp] = None
        self.printer: Printer = Printer()
        self.printer_data = PrinterData()
        self.logger = logger
        self.connected = False
        
    def get_printer_status(self) -> PrinterData:
        """Retrieves the printer status."""
        if not self.connected:
            self.logger.warning("Cannot get status: Not connected")
            return self.printer_data
            
        try:
            self._send_printer_cmd(0)
            
            # On Elegoo printers, we may need additional commands to get complete data
            # Send a few alternative commands to get more detailed status
            try:
                # Command for detailed printer status 
                self._send_printer_cmd(100)  # Try alternative status command
            except:
                pass
                
            try:
                # Command for print info
                self._send_printer_cmd(200)  # Try print info command
            except:
                pass
                
            try:
                # Command for temperature data
                self._send_printer_cmd(300)  # Try temperature command
            except:
                pass
                
        except (ElegooPrinterClientWebsocketError, OSError):
            self.logger.exception("Error sending printer command")
            self.connected = False
            
        # Add short delay to allow responses to be processed
        time.sleep(0.2)
        
        return self.printer_data

    def _send_printer_cmd(self, cmd: int, data: Dict[str, Any] = None) -> None:
        """Send a command to the printer."""
        if not self.connected:
            raise ElegooPrinterClientWebsocketConnectionError("Not connected")
            
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
        
        if self.printer_websocket:
            try:
                self.printer_websocket.send(json.dumps(payload))
            except (
                websocket.WebSocketConnectionClosedException,
                websocket.WebSocketException,
            ) as e:
                self.logger.exception("WebSocket connection closed error")
                self.connected = False
                raise ElegooPrinterClientWebsocketError from e
            except OSError:
                self.logger.exception("Operating System error during send")
                self.connected = False
                raise
        else:
            self.logger.warning("Attempted to send command but websocket is not connected.")
            self.connected = False
            raise ElegooPrinterClientWebsocketConnectionError from Exception("Not connected")

    def discover_printer(self) -> Optional[Printer]:
        """Discover the Elegoo printer on the network."""
        self.logger.info(f"Starting printer discovery at {self.ip_address}")
        msg = b"M99999"
        try:
            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            ) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1)
                try:
                    sock.bind(("", 54780))
                except OSError as e:
                    self.logger.warning(f"Could not bind to port 54780: {e}")
                    # Try an alternative approach - don't bind to a specific port
                
                try:
                    # Send the discovery message
                    self.logger.debug(f"Sending discovery message to {self.ip_address}:3000")
                    sock.sendto(msg, (self.ip_address, 3000))
                    
                    # Try to receive a response
                    self.logger.debug("Waiting for response...")
                    data, addr = sock.recvfrom(8192)
                    self.logger.debug(f"Received response from {addr}")
                    
                    # Process the response
                    printer = self._save_discovered_printer(data)
                    if printer:
                        self.logger.debug("Discovery done.")
                        self.printer = printer
                        return printer
                except TimeoutError:
                    self.logger.warning("Printer discovery timed out.")
                except Exception as e:
                    self.logger.warning(f"Socket error during discovery: {e}")
        
        except Exception as e:
            self.logger.exception(f"Unexpected error during discovery: {e}")
        
        self.logger.warning("Could not discover printer details, will attempt direct connection.")
        
        # Use a fallback with the IP we know
        fallback_printer = Printer()
        fallback_printer.name = "Elegoo Printer"
        fallback_printer.ip_address = self.ip_address
        fallback_printer.id = "ElegooPrinter" 
        fallback_printer.connection = "ElegooPrinterAPI"
        self.printer = fallback_printer
        
        return self.printer

    def _save_discovered_printer(self, data: bytes) -> Optional[Printer]:
        """Parse and save discovered printer information."""
        try:
            printer_info = data.decode("utf-8")
            self.logger.debug(f"Raw printer info: {printer_info!r}")
            
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
            self.logger.info(f"Discovered: {printer.name} ({printer.ip_address})")
            return printer
            
        except UnicodeDecodeError:
            self.logger.exception("Error decoding printer discovery data. Data may be malformed.")
        except Exception as e:
            self.logger.exception(f"Error creating Printer object: {e}")
        
        return None

    def connect(self) -> bool:
        """
        Connect to the Elegoo printer.
        Returns True if successful, False otherwise.
        """
        # This is a synchronous version of the original connect_printer method
        if not self.printer.ip_address:
            self.logger.warning("No IP address set")
            return False
            
        url = f"ws://{self.printer.ip_address}:3030/websocket"
        self.logger.info(f"Connecting to: {self.printer.name} at {url}")

        websocket.setdefaulttimeout(1)
        
        # Create a simple event to track connection success
        connection_event = threading.Event()

        def ws_msg_handler(ws, msg: str) -> None:
            self._parse_response(msg)

        def ws_connected_handler(ws):
            self.logger.info(f"Connected to: {self.printer.name}")
            self.connected = True
            connection_event.set()

        def on_close(ws, close_status_code, close_msg):
            self.logger.debug(f"Connection to {self.printer.name} closed: {close_msg} ({close_status_code})")
            self.printer_websocket = None
            self.connected = False

        def on_error(ws, error):
            self.logger.error(f"Connection to {self.printer.name} error: {error}")
            self.printer_websocket = None
            self.connected = False

        try:
            ws = websocket.WebSocketApp(
                url,
                on_message=ws_msg_handler,
                on_open=ws_connected_handler,
                on_close=on_close,
                on_error=on_error,
            )
            self.printer_websocket = ws

            thread = threading.Thread(target=ws.run_forever, kwargs={"reconnect": 1}, daemon=True)
            thread.start()

            # Wait for the connection to establish or timeout
            if connection_event.wait(timeout=5):
                self.logger.info(f"Successfully connected to {self.printer.name}")
                return True
            else:
                self.logger.warning(f"Failed to connect to {self.printer.name} within timeout")
                self.printer_websocket = None
                return False
                
        except Exception as e:
            self.logger.exception(f"Error during connect: {e}")
            self.printer_websocket = None
            return False

    def disconnect(self):
        """Disconnect from the printer."""
        if self.printer_websocket:
            try:
                self.printer_websocket.close()
                self.logger.info(f"Disconnected from {self.printer.name}")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
            self.printer_websocket = None
        self.connected = False

    def _parse_response(self, response: str) -> None:
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
                    self.logger.debug(f"notice >> {json.dumps(data)[:200]}")
                elif topic_type == "error":
                    self.logger.debug(f"error >> {json.dumps(data)[:200]}")
                else:
                    self.logger.debug(f"Unknown message type: {topic_type}")
            else:
                # Even without a topic, the data might contain useful information
                if "Data" in data or "StatusData" in data or "PrintInfo" in data:
                    self.logger.debug("Message without Topic but contains data, attempting to parse")
                    self._status_handler(data)
        except json.JSONDecodeError:
            self.logger.exception("Invalid JSON received")

    def _response_handler(self, data: Dict[str, Any]) -> None:
        self.logger.debug("Received response data")

    def _status_handler(self, data: Dict[str, Any]) -> None:
        """Handle printer status messages with debug logging."""
        try:
            printer_status = PrinterStatus.from_json(json.dumps(data))
            self.printer_data.status = printer_status
            self.logger.debug(f"Updated printer status: Temperature={printer_status.temperature.uv_temp}°C, " + 
                           f"Printing={printer_status.print_info.is_printing}, " +
                           f"Progress={printer_status.print_info.progress}%")
        except Exception as e:
            self.logger.error(f"Error parsing printer status: {e}")

# -----------------------------------------------------------------------------
# PrinterMonitor Wrapper Class
# -----------------------------------------------------------------------------

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
        logger = logging.getLogger("streamy.printmon")
        logger.info("PrinterMonitor initialized")

    def set_ip_address(self, ip_address):
        """Set the IP address for the printer connection"""
        self.ip_address = ip_address
        logger = logging.getLogger("streamy.printmon")
        logger.info(f"Printer IP address set to: {ip_address}")

    async def connect(self):
        """Connect to the printer monitoring API

        Returns:
            bool: True if connected successfully, False otherwise
        """
        logger = logging.getLogger("streamy.printmon")
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

        # Connect with WebSocket
        connected = await self.connect_printer()
        if connected:
            # Get initial status
            try:
                self.get_status()
            except Exception as e:
                logger.error(f"Error getting initial status: {e}")

            return True

        return False

    def discover_printer(self):
        """Discover the Elegoo printer on the network."""
        logger = logging.getLogger("streamy.printmon")
        logger.info(f"Starting printer discovery at {self.ip_address}")
        msg = b"M99999"
        try:
            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            ) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1)
                try:
                    sock.bind(("", 54780))
                except OSError as e:
                    logger.warning(f"Could not bind to port 54780: {e}")
                    sock.settimeout(1)

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
        logger = logging.getLogger("streamy.printmon")
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
                printer.name = "Elegoo Printer"
                printer.ip_address = self.ip_address
                printer.id = "ElegooPrinter"

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
        logger = logging.getLogger("streamy.printmon")
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
        start_time = time.time()
        timeout = 5
        while time.time() - start_time < timeout:
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
        logger = logging.getLogger("streamy.printmon")
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
        logger = logging.getLogger("streamy.printmon")
        logger.debug(f"Response received: {json.dumps(data)[:200]}...")

    def _status_handler(self, data):
        """Handle status messages from the printer."""
        logger = logging.getLogger("streamy.printmon")
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
        logger = logging.getLogger("streamy.printmon")
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
        """Get the current printer status"""
        logger = logging.getLogger("streamy.printmon")
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

            # Add short delay to allow responses to be processed
            time.sleep(0.2)

        except Exception as e:
            logger.error(f"Error sending printer commands: {e}")

        # Update timestamp if we have data
        if self.printer_data:
            self.printer_data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return self.printer_data

    def _send_printer_cmd(self, cmd, data=None):
        """Send a command to the printer"""
        logger = logging.getLogger("streamy.printmon")
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

# -----------------------------------------------------------------------------
# Log Management Class
# -----------------------------------------------------------------------------

class LogManager:
    """Manages log files and rotation."""
    
    def __init__(self, log_dir="logs"):
        """Initialize the log manager."""
        self.log_dir = log_dir
        self.max_log_files = 3
        
        # Create log directory if it doesn't exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Clean up old logs if needed
        self._cleanup_old_logs()
        
        # Set up logging
        self._setup_logging()
        
    def _cleanup_old_logs(self):
        """Cleanup logs if we have more than self.max_log_files."""
        try:
            log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
            
            if len(log_files) >= self.max_log_files:
                # Sort by creation time (oldest first)
                log_files.sort(key=lambda x: os.path.getctime(os.path.join(self.log_dir, x)))
                
                # Delete oldest files until we're under the limit
                for old_file in log_files[:(len(log_files) - self.max_log_files + 1)]:
                    try:
                        os.remove(os.path.join(self.log_dir, old_file))
                        print(f"Deleted old log file: {old_file}")
                    except Exception as e:
                        print(f"Error deleting log file {old_file}: {e}")
        except Exception as e:
            print(f"Error cleaning up logs: {e}")
            
    def _setup_logging(self):
        """Set up logging configuration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.log_dir, f"elegoo_monitor_{timestamp}.log")
        
        handlers = [
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers
        )
        
        self.logger = logging.getLogger("elegoo_monitor")
        self.logger.info("Log initialized")
        
    def get_logger(self):
        """Get the logger."""
        return self.logger

# -----------------------------------------------------------------------------
# GUI Application Class
# -----------------------------------------------------------------------------

class ElegooMonitorGUI:
    """GUI application for monitoring Elegoo printers."""
    
    def __init__(self, root):
        """Initialize the GUI application."""
        self.root = root
        self.root.title("Elegoo Printer Monitor")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Set up the log manager
        self.log_manager = LogManager()
        self.logger = self.log_manager.get_logger()
        
        # Initialize variables
        self.client = None
        self.ip_address = tk.StringVar(value="")
        self.connected = False
        self.update_interval = 1000  # Update interval in milliseconds
        self.update_task = None
        
        # Create and place UI elements
        self._create_ui()
        
        # Start in disconnected state
        self._update_connection_status(False)
        
        # Protocol handler for closing the window
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _create_ui(self):
        """Create the user interface elements."""
        # Create main layout frames
        self._create_top_frame()
        self._create_main_frame()
        self._create_status_frame()
        
    def _create_top_frame(self):
        """Create the top frame with IP input and connect button."""
        top_frame = ttk.Frame(self.root, padding="10 5 10 5")
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # IP Address Label and Entry
        ttk.Label(top_frame, text="Printer IP:").pack(side=tk.LEFT, padx=(0, 5))
        ip_entry = ttk.Entry(top_frame, textvariable=self.ip_address, width=15)
        ip_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Connect/Disconnect button
        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        # Connection status indicator (right side)
        status_frame = ttk.Frame(top_frame)
        status_frame.pack(side=tk.RIGHT)
        
        # Create a canvas for the status indicator (circle)
        self.status_canvas = tk.Canvas(status_frame, width=20, height=20)
        self.status_canvas.pack(side=tk.LEFT, padx=5)
        
        # Status text label
        self.status_label = ttk.Label(status_frame, text="Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Draw the initial status indicator
        self._draw_status_indicator("red")
        
    def _create_main_frame(self):
        """Create the main content frame."""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create a notebook (tabs)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # First tab - Printer Status
        self.status_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.status_tab, text="Printer Status")
        
        # Second tab - Logs
        self.log_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.log_tab, text="Logs")
        
        # Set up the status tab
        self._setup_status_tab()
        
        # Set up the log tab
        self._setup_log_tab()
        
    def _setup_status_tab(self):
        """Set up the printer status tab with info displays."""
        # Create frames for organizing content
        info_frame = ttk.LabelFrame(self.status_tab, text="Printer Information", padding="10")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Printer info grid
        self.printer_name_var = tk.StringVar(value="N/A")
        self.printer_model_var = tk.StringVar(value="N/A")
        self.printer_firmware_var = tk.StringVar(value="N/A")
        
        # Row 1
        ttk.Label(info_frame, text="Printer Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.printer_name_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(info_frame, text="Model:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.printer_model_var).grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        # Row 2
        ttk.Label(info_frame, text="Firmware:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.printer_firmware_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Print Status Frame
        print_frame = ttk.LabelFrame(self.status_tab, text="Print Status", padding="10")
        print_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status variables
        self.print_status_var = tk.StringVar(value="No active print")
        self.task_name_var = tk.StringVar(value="N/A")
        self.progress_var = tk.DoubleVar(value=0)
        self.uv_temp_var = tk.StringVar(value="N/A")
        self.current_layer_var = tk.StringVar(value="N/A")
        self.total_layer_var = tk.StringVar(value="N/A")
        self.total_time_var = tk.StringVar(value="N/A")
        self.remain_time_var = tk.StringVar(value="N/A")
        
        # Create status display
        status_grid = ttk.Frame(print_frame)
        status_grid.pack(fill=tk.BOTH, expand=True)
        
        # Row 1
        ttk.Label(status_grid, text="Status:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.print_status_var, font=("", 11, "bold")).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(status_grid, text="UV Temperature:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.uv_temp_var).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Row 2
        ttk.Label(status_grid, text="File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.task_name_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5, columnspan=3)
        
        # Row 3
        ttk.Label(status_grid, text="Progress:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.progress_bar = ttk.Progressbar(status_grid, variable=self.progress_var, length=200, mode="determinate", maximum=100)
        self.progress_bar.grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5, columnspan=3)
        
        # Row 4
        ttk.Label(status_grid, text="Layer:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.current_layer_var).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(status_grid, text="Total Layers:").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.total_layer_var).grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Row 5
        ttk.Label(status_grid, text="Elapsed Time:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.total_time_var).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(status_grid, text="Remaining Time:").grid(row=4, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_grid, textvariable=self.remain_time_var).grid(row=4, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Make the columns expand properly
        status_grid.columnconfigure(1, weight=1)
        status_grid.columnconfigure(3, weight=1)
        
    def _setup_log_tab(self):
        """Set up the log tab with scrollable text area."""
        # Create a frame for the log display
        log_display_frame = ttk.Frame(self.log_tab, padding="5")
        log_display_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(log_display_frame, width=80, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state='disabled')  # Read-only
        
        # Create a custom handler for the logger that updates the text widget
        class TextWidgetHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                    self.text_widget.configure(state='disabled')
                # Schedule in the UI thread
                self.text_widget.after(0, append)
        
        # Add the custom handler to our logger
        handler = TextWidgetHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
    def _create_status_frame(self):
        """Create the bottom status bar."""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _draw_status_indicator(self, color):
        """Draw the status indicator circle with the specified color."""
        self.status_canvas.delete("all")
        x, y, r = 10, 10, 7  # Center coordinates and radius
        self.status_canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="")
        
    def _update_connection_status(self, connected, warning=False):
        """Update the connection status indicators."""
        self.connected = connected
        
        if warning:
            # Yellow for warning
            self._draw_status_indicator("yellow")
            self.status_label.config(text="Check logs")
        elif connected:
            # Green for connected
            self._draw_status_indicator("green")
            self.status_label.config(text="Connected")
            self.connect_btn.config(text="Disconnect")
        else:
            # Red for disconnected
            self._draw_status_indicator("red")
            self.status_label.config(text="Disconnected")
            self.connect_btn.config(text="Connect")
            
            # Reset printer info fields
            self.printer_name_var.set("N/A")
            self.printer_model_var.set("N/A")
            self.printer_firmware_var.set("N/A")
            
            # Reset print status fields
            self.print_status_var.set("No active print")
            self.task_name_var.set("N/A")
            self.progress_var.set(0)
            self.uv_temp_var.set("N/A")
            self.current_layer_var.set("N/A")
            self.total_layer_var.set("N/A")
            self.total_time_var.set("N/A")
            self.remain_time_var.set("N/A")
        
    def _toggle_connection(self):
        """Toggle the connection state based on the current state."""
        if self.connected:
            self._disconnect()
        else:
            self._connect()
            
    def _connect(self):
        """Connect to the printer."""
        ip = self.ip_address.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter a valid IP address")
            return
            
        # Update status temporarily to yellow during connection attempt
        self._update_connection_status(False, warning=True)
        self.status_bar.config(text=f"Connecting to {ip}...")
        self.root.update()
        
        # Create a new client
        self.client = ElegooPrinterClient(ip, self.logger)
        
        # Run the discovery and connect in a separate thread to avoid freezing the UI
        def connect_thread():
            try:
                # Discover the printer
                self.client.discover_printer()
                
                # Connect to the printer
                success = self.client.connect()
                
                # Update UI based on connection result
                if success:
                    # Update connection status to connected
                    self.root.after(0, lambda: self._on_connect_success())
                else:
                    # Connection failed
                    self.root.after(0, lambda: self._on_connect_failed("Connection failed or timed out"))
            except Exception as e:
                # Handle any exceptions
                self.root.after(0, lambda: self._on_connect_failed(str(e)))
        
        # Start the connection thread
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def _on_connect_success(self):
        """Handle successful connection."""
        self._update_connection_status(True)
        self.status_bar.config(text=f"Connected to {self.client.printer.name} at {self.client.printer.ip_address}")
        
        # Update printer info fields
        self.printer_name_var.set(self.client.printer.name)
        self.printer_model_var.set(self.client.printer.model or "Unknown")
        self.printer_firmware_var.set(self.client.printer.firmware or "Unknown")
        
        # Start the status update timer
        self._schedule_status_update()
        
    def _on_connect_failed(self, reason):
        """Handle failed connection."""
        self._update_connection_status(False)
        self.status_bar.config(text=f"Connection failed: {reason}")
        messagebox.showerror("Connection Failed", f"Could not connect to the printer: {reason}")
        
        # Clean up the client
        if self.client:
            self.client.disconnect()
            self.client = None
    
    def _disconnect(self):
        """Disconnect from the printer."""
        if self.client:
            # Cancel any pending updates
            if self.update_task:
                self.root.after_cancel(self.update_task)
                self.update_task = None
                
            # Disconnect the client
            self.client.disconnect()
            self.client = None
            
        # Update the UI
        self._update_connection_status(False)
        self.status_bar.config(text="Disconnected from printer")
    
    def _schedule_status_update(self):
        """Schedule the next status update."""
        if self.update_task:
            self.root.after_cancel(self.update_task)
            
        self.update_task = self.root.after(self.update_interval, self._update_printer_status)
    
    def _update_printer_status(self):
        """Update the printer status display."""
        if not self.client or not self.connected:
            return
            
        try:
            # Get the printer status
            printer_data = self.client.get_printer_status()
            
            if not self.client.connected:
                # Lost connection, update UI
                self._update_connection_status(False)
                self.status_bar.config(text="Lost connection to printer")
                return
                
            # Update the UI with the current status
            status = printer_data.status
            
            # Extract values
            is_printing = status.print_info.is_printing
            progress = status.print_info.progress
            current_layer = status.print_info.current_layer
            total_layers = status.print_info.total_layer
            remaining_time = status.print_info.remain_time
            total_time = status.print_info.total_time
            task_name = status.print_info.task_name
            uv_temp = status.temperature.uv_temp
            
            # Format times
            formatted_remain_time = self._format_time(remaining_time)
            formatted_total_time = self._format_time(total_time)
            
            # Update status display
            if is_printing:
                self.print_status_var.set("PRINTING")
                self.task_name_var.set(task_name or "Unknown")
                self.progress_var.set(progress)
                self.current_layer_var.set(str(current_layer))
                self.total_layer_var.set(str(total_layers))
                self.total_time_var.set(formatted_total_time)
                self.remain_time_var.set(formatted_remain_time)
            else:
                self.print_status_var.set("IDLE")
                self.task_name_var.set("No active print")
                self.progress_var.set(0)
                self.current_layer_var.set("N/A")
                self.total_layer_var.set("N/A")
                self.total_time_var.set("N/A")
                self.remain_time_var.set("N/A")
                
            # Always update temperature
            self.uv_temp_var.set(f"{uv_temp:.1f}°C")
            
            # Update status bar with last update time
            now = datetime.now().strftime("%H:%M:%S")
            self.status_bar.config(text=f"Last update: {now}")
            
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            self.status_bar.config(text=f"Error updating status: {str(e)}")
            
        # Schedule the next update
        self._schedule_status_update()
    
    def _format_time(self, seconds):
        """Format seconds into hours, minutes, seconds string."""
        if seconds <= 0:
            return "N/A"
        
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    def _on_close(self):
        """Handle window close event."""
        # Cancel any pending updates
        if self.update_task:
            self.root.after_cancel(self.update_task)
            
        # Disconnect from the printer
        if self.client:
            self.client.disconnect()
            
        # Destroy the window
        self.root.destroy()

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def main():
    if not _HAS_GUI:
        print("Error: tkinter not available. Cannot run GUI.")
        return

    # Create the main window
    root = tk.Tk()

    try:
        # Try to set the app icon
        try:
            from PIL import Image, ImageDraw
            # Create a 64x64 image with a printer icon
            icon = Image.new('RGBA', (64, 64), (255, 255, 255, 0))
            draw = ImageDraw.Draw(icon)

            # Draw a simple printer shape
            draw.rectangle([10, 20, 54, 44], fill=(30, 144, 255))  # Printer body
            draw.rectangle([20, 44, 44, 50], fill=(30, 144, 255))  # Printer base
            draw.rectangle([16, 10, 48, 20], fill=(30, 144, 255))  # Paper tray
            draw.ellipse([40, 26, 48, 34], fill=(255, 0, 0))       # Power button

            # Set the window icon
            root.iconphoto(True, ImageTk.PhotoImage(icon))
        except:
            # If setting the icon fails, just continue
            pass

        # Create and run the application
        app = ElegooMonitorGUI(root)
        root.mainloop()

    except Exception as e:
        print(f"Error initializing application: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Application error: {str(e)}")

if __name__ == "__main__":
    main()