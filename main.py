#!/usr/bin/env python3
"""
Streamy v1.5 with Elegoo Monitor Integration
A desktop application to stream RTSP video from your 3D printer camera
and display Elegoo printer status information.
Created and maintained by data_heavy@proton.me
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QMessageBox, QFrame, QSizePolicy, QLineEdit, QCheckBox,
                             QDialog, QFormLayout, QFileDialog, QDialogButtonBox)
from stats import PrinterMonitor
from vidstream import VideoStreamer
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QColor, QPainter, QIcon, QFontMetrics
import cv2  # Add this import here
import numpy as np
import sys
import os
import threading
import asyncio
import argparse
import subprocess
import importlib.util
import json
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Check required packages before importing


def check_and_install_dependencies():
    """Check if required packages are installed and install them if necessary"""
    required_packages = {
        'opencv-python': 'cv2',
        'numpy': 'numpy',
        'PyQt5': 'PyQt5',
        'websocket-client': 'websocket',
        'requests': 'requests'  # Add this line
    }

    missing_packages = []

    for package, module_name in required_packages.items():
        if module_name == 'cv2':
            # Special check for OpenCV since module name differs from package name
            if importlib.util.find_spec("cv2") is None:
                missing_packages.append(package)
        elif module_name == 'websocket':
            # Special check for websocket-client
            try:
                import websocket
            except ImportError:
                missing_packages.append(package)
        else:
            # Standard check for other packages
            if importlib.util.find_spec(module_name) is None:
                missing_packages.append(package)

    # Install missing packages
    if missing_packages:
        print("Installing missing dependencies...")
        for package in missing_packages:
            print(f"- {package}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing_packages)
            print("All dependencies installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            print("\nPlease install the following packages manually:")
            for package in missing_packages:
                print(f"- {package}")
            sys.exit(1)


# Check and install dependencies
check_and_install_dependencies()

# Standard imports

# Import our modules (updated import names)

# Application version
APP_VERSION = "1.5"

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("streamy")

# Config file for saving settings
CONFIG_FILE = "streamy_config.json"


class StatusIndicator(QWidget):
    """Custom widget that displays a colored status dot"""

    RED = QColor(255, 60, 60)       # Error/Disconnected
    YELLOW = QColor(255, 200, 60)   # Warning/Partial connection
    GREEN = QColor(60, 200, 60)     # Success/Connected
    GRAY = QColor(150, 150, 150)    # Neutral/Idle

    def __init__(self, parent=None, color=None, size=16):
        super().__init__(parent)
        self.color = color or self.GRAY
        self.size = size
        self.setMinimumSize(size, size)
        self.setMaximumSize(size, size)

    def setColor(self, color):
        """Set the indicator color"""
        self.color = color
        self.update()

    def paintEvent(self, event):
        """Paint the indicator dot"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circle with current color
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(2, 2, self.size-4, self.size-4)

        # Draw border
        painter.setPen(QColor(80, 80, 80, 100))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(2, 2, self.size-4, self.size-4)


class Config:
    """Class to manage configuration settings"""

    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from file"""
        default_config = {
            "recent_printers": [],
            "last_used_printer": "",
            "include_timestamp": True,
            "video_enabled": True,  # Add default for video toggle
            "auto_connect": True,   # Add default for auto-connect setting
            "transport": "udp",     # RTSP transport: "udp" or "tcp"
            "rtsp_path": "/video",  # RTSP path
            "rtsp_port": 554,       # RTSP port
            "screenshot_path": os.path.expanduser("~/Desktop"),  # Screenshot save path
            "show_big_progress": True,  # Show large progress percentage
            "show_fps": True,  # Show FPS counter
            "printer_display_name": ""  # Custom printer display name
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Ensure all required keys exist
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            return default_config

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f)
        except Exception as e:
            print(f"Error saving config: {e}")

    def add_printer(self, ip_address):
        """Add printer to recent list and set as last used"""
        if ip_address:
            # Remove if already exists (to avoid duplicates)
            if ip_address in self.config["recent_printers"]:
                self.config["recent_printers"].remove(ip_address)

            # Add to start of list
            self.config["recent_printers"].insert(0, ip_address)

            # Keep only last 5 printers
            self.config["recent_printers"] = self.config["recent_printers"][:5]

            # Set as last used
            self.config["last_used_printer"] = ip_address

            # Save changes
            self.save_config()

    def get_recent_printers(self):
        """Get list of recent printer IP addresses"""
        return self.config["recent_printers"]

    def get_last_used_printer(self):
        """Get last used printer IP address"""
        return self.config["last_used_printer"]

    def set_include_timestamp(self, value):
        """Set whether to include timestamp on snapshots"""
        self.config["include_timestamp"] = value
        self.save_config()

    def get_include_timestamp(self):
        """Get whether to include timestamp on snapshots"""
        return self.config.get("include_timestamp", True)

    def set_video_enabled(self, value):
        """Set whether video is enabled"""
        self.config["video_enabled"] = value
        self.save_config()

    def get_video_enabled(self):
        """Get whether video is enabled"""
        return self.config.get("video_enabled", True)

    def set_auto_connect(self, value):
        """Set whether to auto-connect on startup"""
        self.config["auto_connect"] = value
        self.save_config()

    def get_auto_connect(self):
        """Get whether to auto-connect on startup"""
        return self.config.get("auto_connect", True)

    def set_transport(self, value):
        """Set the RTSP transport protocol"""
        self.config["transport"] = value
        self.save_config()

    def get_transport(self):
        """Get the RTSP transport protocol"""
        return self.config.get("transport", "udp")

    def set_rtsp_path(self, value):
        """Set the RTSP path"""
        self.config["rtsp_path"] = value
        self.save_config()

    def get_rtsp_path(self):
        """Get the RTSP path"""
        return self.config.get("rtsp_path", "/video")

    def set_rtsp_port(self, value):
        """Set the RTSP port"""
        self.config["rtsp_port"] = value
        self.save_config()

    def get_rtsp_port(self):
        """Get the RTSP port"""
        return self.config.get("rtsp_port", 554)

    def set_screenshot_path(self, value):
        """Set the screenshot save path"""
        self.config["screenshot_path"] = value
        self.save_config()

    def get_screenshot_path(self):
        """Get the screenshot save path"""
        return self.config.get("screenshot_path", os.path.expanduser("~/Desktop"))

    def set_show_big_progress(self, value):
        """Set whether to show the big progress percentage"""
        self.config["show_big_progress"] = value
        self.save_config()

    def get_show_big_progress(self):
        """Get whether to show the big progress percentage"""
        return self.config.get("show_big_progress", True)

    def set_show_fps(self, value):
        """Set whether to show the FPS counter"""
        self.config["show_fps"] = value
        self.save_config()

    def get_show_fps(self):
        """Get whether to show the FPS counter"""
        return self.config.get("show_fps", True)

    def set_printer_display_name(self, value):
        """Set the printer display name"""
        self.config["printer_display_name"] = value
        self.save_config()

    def get_printer_display_name(self):
        """Get the printer display name"""
        return self.config.get("printer_display_name", "")


class SettingsDialog(QDialog):
    """Settings dialog for Streamy configuration"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Common style for input fields with grey outline
        input_style = "QLineEdit { border: 1px solid #666666; padding: 4px; background-color: #3a3a3a; }"
        checkbox_style = "QCheckBox { padding: 4px; }"

        # Form layout for settings
        form_layout = QFormLayout()

        # IP Address
        self.ip_input = QLineEdit()
        self.ip_input.setText(self.config.get_last_used_printer())
        self.ip_input.setStyleSheet(input_style)
        form_layout.addRow("IP Address:", self.ip_input)

        # Port
        self.port_input = QLineEdit()
        self.port_input.setText(str(self.config.get_rtsp_port()))
        self.port_input.setStyleSheet(input_style)
        form_layout.addRow("Port:", self.port_input)

        # Path
        self.path_input = QLineEdit()
        self.path_input.setText(self.config.get_rtsp_path())
        self.path_input.setStyleSheet(input_style)
        form_layout.addRow("RTSP Path:", self.path_input)

        # Transport
        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["UDP", "TCP"])
        self.transport_combo.setCurrentText(self.config.get_transport().upper())
        self.transport_combo.setStyleSheet("QComboBox { background-color: #3a3a3a; border: 1px solid #666666; padding: 4px; } QComboBox QAbstractItemView { background-color: #3a3a3a; }")
        form_layout.addRow("Transport:", self.transport_combo)

        # Printer Display Name
        self.display_name_input = QLineEdit()
        self.display_name_input.setText(self.config.get_printer_display_name())
        self.display_name_input.setPlaceholderText("Optional custom name")
        self.display_name_input.setStyleSheet(input_style)
        form_layout.addRow("Printer Name:", self.display_name_input)

        # Show big progress checkbox (moved below Printer Name)
        self.show_big_progress_checkbox = QCheckBox("Show large progress percentage")
        self.show_big_progress_checkbox.setChecked(self.config.get_show_big_progress())
        self.show_big_progress_checkbox.setStyleSheet(checkbox_style)
        form_layout.addRow("", self.show_big_progress_checkbox)

        # Show FPS checkbox
        self.show_fps_checkbox = QCheckBox("Show FPS counter")
        self.show_fps_checkbox.setChecked(self.config.get_show_fps())
        self.show_fps_checkbox.setStyleSheet(checkbox_style)
        form_layout.addRow("", self.show_fps_checkbox)

        # Screenshot path
        screenshot_widget = QWidget()
        screenshot_layout = QHBoxLayout(screenshot_widget)
        screenshot_layout.setContentsMargins(0, 0, 0, 0)
        self.screenshot_path_input = QLineEdit()
        self.screenshot_path_input.setText(self.config.get_screenshot_path())
        self.screenshot_path_input.setStyleSheet(input_style)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_screenshot_path)
        screenshot_layout.addWidget(self.screenshot_path_input)
        screenshot_layout.addWidget(browse_btn)
        form_layout.addRow("Screenshot Path:", screenshot_widget)

        # Timestamp checkbox
        self.timestamp_checkbox = QCheckBox("Include timestamp on screenshots")
        self.timestamp_checkbox.setChecked(self.config.get_include_timestamp())
        self.timestamp_checkbox.setStyleSheet(checkbox_style)
        form_layout.addRow("", self.timestamp_checkbox)

        # Auto-connect checkbox
        self.auto_connect_checkbox = QCheckBox("Auto-connect on startup")
        self.auto_connect_checkbox.setChecked(self.config.get_auto_connect())
        self.auto_connect_checkbox.setStyleSheet(checkbox_style)
        form_layout.addRow("", self.auto_connect_checkbox)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox()
        save_btn = QPushButton("Save Settings")
        cancel_btn = QPushButton("Cancel")
        button_box.addButton(save_btn, QDialogButtonBox.AcceptRole)
        button_box.addButton(cancel_btn, QDialogButtonBox.RejectRole)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def browse_screenshot_path(self):
        """Open folder browser for screenshot path"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Screenshot Folder",
            self.screenshot_path_input.text()
        )
        if folder:
            self.screenshot_path_input.setText(folder)

    def save_settings(self):
        """Save all settings and close dialog"""
        # Validate port
        try:
            port = int(self.port_input.text())
            if port < 1 or port > 65535:
                port = 554
        except ValueError:
            port = 554

        # Save all settings
        self.config.set_rtsp_port(port)
        self.config.set_rtsp_path(self.path_input.text() or "/video")
        self.config.set_transport(self.transport_combo.currentText().lower())
        self.config.set_printer_display_name(self.display_name_input.text())
        self.config.set_screenshot_path(self.screenshot_path_input.text())
        self.config.set_include_timestamp(self.timestamp_checkbox.isChecked())
        self.config.set_show_big_progress(self.show_big_progress_checkbox.isChecked())
        self.config.set_show_fps(self.show_fps_checkbox.isChecked())
        self.config.set_auto_connect(self.auto_connect_checkbox.isChecked())

        # Update last used printer if IP changed
        if self.ip_input.text().strip():
            self.config.add_printer(self.ip_input.text().strip())

        self.accept()


class StreamyApp(QMainWindow):
    """Main application integrating video stream and printer monitor"""
    # Signal for updating UI from background thread
    printer_status_updated = pyqtSignal(object)

    def __init__(self, ip_address=None, auto_connect_delay=1000):
        """Initialize the application"""
        super().__init__()

        # Set window properties
        self.setWindowTitle(f"Streamy v{APP_VERSION}")

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.resize(1000, 700)
        self.setMinimumSize(800, 600)

        # Load configuration
        self.config = Config()

        # Status variables
        # Store previous status for status timer
        self.previous_status = "Not connected"
        # Store current connected IP address
        self.current_ip = None

        # FPS calculation variables
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()

        # Create video streamer
        self.video_streamer = VideoStreamer()

        # Create printer monitor
        self.printer_monitor = PrinterMonitor()

        # Connect signal for printer status updates
        self.printer_status_updated.connect(self.update_printer_status_ui)

        # Setup UI
        self.setup_ui()

        # Set up timer for updating video (30fps)
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.update_frame)
        self.video_timer.setInterval(33)  # ~30 FPS

        # Set up timer for status message reset
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.reset_status)
        self.status_timer.setSingleShot(True)

        # Set up timer for printer status updates
        self.printer_status_timer = QTimer(self)
        self.printer_status_timer.timeout.connect(self.fetch_printer_status)
        # Update every 1 second
        self.printer_status_timer.setInterval(1000)

        # Set up timer for FPS calculation (update every second)
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self.calculate_fps)
        self.fps_timer.setInterval(1000)  # Update FPS every second

        # Populate recent printers
        self.populate_printer_combobox()

        # Update IP label to show printer name if set
        self.update_ip_label()

        # Handle auto-connection with precedence to command-line IP if provided
        if ip_address:
            # Command-line IP has highest priority
            self.ip_combo.setCurrentText(ip_address)
            self.auto_connect_to_printer()
        elif self.config.get_auto_connect() and self.config.get_last_used_printer():
            # Auto-connect to last used printer after a short delay (to let UI initialize)
            self.ip_combo.setCurrentText(self.config.get_last_used_printer())
            QTimer.singleShot(auto_connect_delay, self.auto_connect_to_printer)
        elif self.config.get_last_used_printer():
            # Just set the IP but don't connect
            self.ip_combo.setCurrentText(self.config.get_last_used_printer())

    def setup_ui(self):
        """Set up the user interface"""
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Controls frame with three sections: left (IP/name), center (buttons), right (status)
        controls_frame = QWidget()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(5, 5, 5, 5)

        # Left section - IP/Printer name
        left_section = QWidget()
        left_layout = QHBoxLayout(left_section)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.ip_label = QLabel("IP Address:")
        left_layout.addWidget(self.ip_label)
        left_layout.addStretch(1)

        # Hidden IP combo (kept for settings dialog compatibility)
        self.ip_line_edit = QLineEdit()
        self.ip_line_edit.returnPressed.connect(self.connect_to_printer)
        self.ip_combo = QComboBox()
        self.ip_combo.setEditable(True)
        self.ip_combo.setMinimumWidth(200)
        self.ip_combo.setLineEdit(self.ip_line_edit)
        self.ip_combo.setStyleSheet("QComboBox { background-color: #3a3a3a; } QComboBox QAbstractItemView { background-color: #3a3a3a; }")
        self.ip_combo.setVisible(False)  # Hidden by default
        left_layout.addWidget(self.ip_combo)

        # Center section - Buttons (fixed, no stretch)
        center_section = QWidget()
        center_layout = QHBoxLayout(center_section)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_to_printer)
        center_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_printer)
        center_layout.addWidget(self.disconnect_btn)

        self.video_toggle_btn = QPushButton("Disable Video")
        self.video_toggle_btn.clicked.connect(self.toggle_video)
        self.video_toggle_btn.setEnabled(False)
        center_layout.addWidget(self.video_toggle_btn)

        # Right section - Status
        right_section = QWidget()
        right_layout = QHBoxLayout(right_section)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addStretch(1)
        self.status_indicator = StatusIndicator(size=16)
        right_layout.addWidget(self.status_indicator)

        self.status_label = QLabel("Not connected")
        right_layout.addWidget(self.status_label)

        # Add all three sections to main controls layout with equal stretch
        controls_layout.addWidget(left_section, 1)
        controls_layout.addWidget(center_section, 0)  # No stretch - keeps buttons centered
        controls_layout.addWidget(right_section, 1)

        # Video display
        self.video_frame = QLabel()
        self.video_frame.setFrameStyle(QFrame.StyledPanel)
        self.video_frame.setAlignment(Qt.AlignCenter)
        self.video_frame.setMinimumSize(640, 480)
        self.video_frame.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Set initial "no connection" message
        self.show_no_connection_message()

        # Bottom frame with printer status and snapshot controls
        bottom_frame = QWidget()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(5, 5, 5, 5)

        # Left side - Printer Status Information
        left_status = QWidget()
        left_layout = QVBoxLayout(left_status)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        # Print status labels
        self.progress_label = QLabel("Progress: --")
        self.current_layer_label = QLabel("Current Layer: --")
        self.remain_layers_label = QLabel("Remaining Layers: --")
        self.total_time_label = QLabel("Total Print Time: --")
        self.remain_time_label = QLabel("Remaining Time: --")

        # Add the status labels to the left layout
        left_layout.addWidget(self.progress_label)
        left_layout.addWidget(self.current_layer_label)
        left_layout.addWidget(self.remain_layers_label)
        left_layout.addWidget(self.total_time_label)
        left_layout.addWidget(self.remain_time_label)

        # Center - Large percentage display
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.big_progress_label = QLabel("--%")
        self.big_progress_label.setAlignment(Qt.AlignLeft)
        self.big_progress_label.setStyleSheet("color: #a6a6a6; font-size: 72pt; font-weight: bold;")
        self.big_progress_label.setVisible(self.config.get_show_big_progress())

        center_layout.addStretch(1)
        center_layout.addWidget(self.big_progress_label)
        center_layout.addStretch(1)

        # Right side - Controls and Status
        right_controls = QWidget()
        right_layout = QVBoxLayout(right_controls)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(3)  # Minimal spacing for compact layout

        # Status and last updated labels - same width as snapshot button for alignment
        self.print_status_label = QLabel("Status: Not Connected")
        self.print_status_label.setAlignment(Qt.AlignLeft)
        self.print_status_label.setFixedWidth(213)  # Match snapshot button width
        self.last_updated_label = QLabel("Last Updated: --")
        self.last_updated_label.setAlignment(Qt.AlignLeft)
        self.last_updated_label.setFixedWidth(213)  # Match snapshot button width

        # Create snapshot button
        self.snapshot_btn = QPushButton("Snapshot")
        self.snapshot_btn.clicked.connect(self.take_snapshot)
        self.snapshot_btn.setFixedWidth(213)  # Adjust this value as needed
        # Disabled initially until connected
        self.snapshot_btn.setEnabled(False)

        # Bottom info widget (Settings and FPS) - same width as snapshot button for alignment
        bottom_info_widget = QWidget()
        bottom_info_widget.setFixedWidth(213)  # Match snapshot button width
        bottom_info_layout = QHBoxLayout(bottom_info_widget)
        bottom_info_layout.setContentsMargins(0, 0, 0, 0)
        bottom_info_layout.setAlignment(Qt.AlignVCenter)

        # Combined Settings button with text and gear icon
        self.settings_btn = QPushButton("Settings ⚙")
        self.settings_btn.setStyleSheet("QPushButton { border: none; color: gray; padding: 0; margin: 0; } QPushButton:hover { color: white; }")
        self.settings_btn.clicked.connect(self.open_settings)

        self.fps_label = QLabel("00.0 FPS")
        self.fps_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.fps_label.setStyleSheet("color: gray;")
        self.fps_label.setVisible(self.config.get_show_fps())
        # Set fixed width based on widest possible FPS (88.8 FPS)
        fps_metrics = QFontMetrics(self.fps_label.font())
        self.fps_label.setFixedWidth(fps_metrics.horizontalAdvance("88.8 FPS"))

        # Add widgets to bottom info layout
        bottom_info_layout.addWidget(self.fps_label)
        bottom_info_layout.addStretch(1)
        bottom_info_layout.addWidget(self.settings_btn)

        # Add elements to right layout in correct order
        right_layout.addWidget(self.print_status_label, 0, Qt.AlignRight)
        right_layout.addWidget(self.last_updated_label, 0, Qt.AlignRight)
        right_layout.addWidget(self.snapshot_btn, 0, Qt.AlignRight)
        right_layout.addWidget(bottom_info_widget, 0, Qt.AlignRight)

        # Add left, center, and right sides to bottom layout
        bottom_layout.addWidget(left_status, 1)
        bottom_layout.addWidget(center_widget, 1)
        bottom_layout.addWidget(right_controls)

        # Add all main widgets to main layout
        main_layout.addWidget(controls_frame)
        main_layout.addWidget(self.video_frame, 1)
        main_layout.addWidget(bottom_frame)

        # Initialize printer status UI elements with empty/default values
        self.clear_printer_status_ui()

    def auto_connect_to_printer(self):
        """Automatically connect to the printer using the current IP in the combo box"""
        ip_address = self.ip_combo.currentText().strip()
        if ip_address:
            logger.info(f"Auto-connecting to {ip_address}")
            self.connect_to_printer()
        else:
            logger.warning("Cannot auto-connect: No IP address available")

    def calculate_fps(self):
        """Calculate frames per second"""
        if self.frame_count > 0:
            elapsed_time = time.time() - self.fps_start_time
            self.fps = self.frame_count / elapsed_time
            self.fps_label.setText(f"{self.fps:.1f} FPS")

            # Reset counters
            self.frame_count = 0
            self.fps_start_time = time.time()

    def toggle_video(self):
        """Toggle video streaming on/off"""
        is_enabled = self.config.get_video_enabled()

        if is_enabled:
            # Disable video
            self.video_toggle_btn.setText("Enable Video")
            self.config.set_video_enabled(False)

            # Show paused message
            if self.video_streamer.is_running:
                img = self.video_streamer.create_paused_image()
                self.display_image(img)
                # Disable snapshot when paused
                self.snapshot_btn.setEnabled(False)
        else:
            # Enable video
            self.video_toggle_btn.setText("Disable Video")
            self.config.set_video_enabled(True)

            # Resume video if connected
            if self.video_streamer.is_running:
                self.snapshot_btn.setEnabled(True)  # Re-enable snapshot

    def clear_printer_status_ui(self):
        """Reset printer status UI elements to default values"""
        self.progress_label.setText("Progress: --")
        self.big_progress_label.setText("--%")
        self.remain_layers_label.setText("Remaining Layers: --")
        self.current_layer_label.setText("Current Layer: --")
        self.total_time_label.setText("Total Print Time: --")
        self.remain_time_label.setText("Remaining Time: --")
        self.print_status_label.setText("Status: Not Connected")
        self.last_updated_label.setText("Last Updated: --")

    def update_printer_status_ui(self, printer_data):
        """Update UI with printer status information"""
        if not printer_data:
            return

        # Extract print information
        status = printer_data.status
        print_info = status.print_info

        # Update timestamp
        self.last_updated_label.setText(
            f"Last Updated: {printer_data.last_updated}")

        # Determine status text based on status_code
        status_code = print_info.status_code
        if status_code in [0, 8]:
            status_text = "Idle"
        elif status_code == 1:
            status_text = "Preparing to print"
        elif status_code in [2, 3, 4]:
            status_text = "Printing"
        elif status_code == 7:
            status_text = "Finishing"
        else:
            status_text = "Unknown"

        # Update print status label
        self.print_status_label.setText(f"Status: {status_text}")

        # Check if there's an active print
        if print_info.is_printing:
            # Calculate progress from layers (current_layer / total_layer * 100)
            if print_info.total_layer > 0:
                progress = (print_info.current_layer / print_info.total_layer) * 100
            else:
                progress = 0.0
            progress = max(0, min(100, progress))
            self.progress_label.setText(f"Progress: {progress:.1f}%")
            self.big_progress_label.setText(f"{progress:.1f}%")

            # Update layer information
            if print_info.total_layer > 0:
                current_layer = print_info.current_layer
                total_layer = print_info.total_layer
                remaining_layers = max(0, total_layer - current_layer)

                self.current_layer_label.setText(
                    f"Current Layer: {current_layer}/{total_layer}")
                self.remain_layers_label.setText(
                    f"Remaining Layers: {remaining_layers}")
            else:
                self.current_layer_label.setText("Current Layer: --")
                self.remain_layers_label.setText("Remaining Layers: --")

            # Update time information
            # Try to calculate times if not provided directly
            total_time_secs = print_info.total_time
            remain_time_secs = print_info.remain_time

            # If we have total_time but no remain_time, calculate it from progress
            if total_time_secs > 0 and remain_time_secs == 0 and progress > 0:
                remain_time_secs = int(total_time_secs * (100 - progress) / 100)

            # If we have remain_time but no total_time, calculate it from progress
            if remain_time_secs > 0 and total_time_secs == 0 and progress > 0:
                total_time_secs = int(remain_time_secs * 100 / (100 - progress))

            if total_time_secs > 0:
                total_time = self.printer_monitor.format_time(total_time_secs)
                self.total_time_label.setText(f"Total Print Time: {total_time}")
            else:
                self.total_time_label.setText("Total Print Time: --")

            if remain_time_secs > 0:
                remain_time = self.printer_monitor.format_time(remain_time_secs)
                self.remain_time_label.setText(f"Remaining Time: {remain_time}")
            else:
                self.remain_time_label.setText("Remaining Time: --")
        else:
            # No active print, clear progress fields
            self.progress_label.setText("Progress: --")
            self.big_progress_label.setText("--%")
            self.current_layer_label.setText("Current Layer: --")
            self.remain_layers_label.setText("Remaining Layers: --")
            self.total_time_label.setText("Total Print Time: --")
            self.remain_time_label.setText("Remaining Time: --")

    def fetch_printer_status(self):
        """Fetch printer status in a background thread to avoid UI freezing"""
        if not self.printer_monitor.is_connected:
            return

        def get_status_thread():
            try:
                printer_data = self.printer_monitor.get_status()
                if printer_data:
                    self.printer_status_updated.emit(printer_data)
            except Exception as e:
                logger.error(f"Error fetching printer status: {e}")

        # Run in a separate thread to avoid blocking UI
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(get_status_thread)

    async def connect_to_printer_monitor(self, ip_address):
        """Connect to the Elegoo printer for status monitoring"""
        if not ip_address:
            return False

        # Set the IP address for the printer monitor
        self.printer_monitor.set_ip_address(ip_address)

        # Connect to the printer
        return await self.printer_monitor.connect()

    def transport_changed(self, text):
        """Handle transport protocol change"""
        self.config.set_transport(text.lower())

    def path_changed(self):
        """Handle RTSP path change"""
        path = self.path_input.text().strip()
        if not path:
            path = "/video"
            self.path_input.setText(path)
        self.config.set_rtsp_path(path)

    def port_changed(self):
        """Handle RTSP port change"""
        port_text = self.port_input.text().strip()
        try:
            port = int(port_text) if port_text else 554
            if port < 1 or port > 65535:
                port = 554
        except ValueError:
            port = 554
        self.port_input.setText(str(port))
        self.config.set_rtsp_port(port)

    def open_settings(self):
        """Open the settings dialog"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            # Apply settings changes to UI
            self.apply_settings()

    def update_ip_label(self):
        """Update the IP label to show printer name if set, otherwise show IP address"""
        printer_name = self.config.get_printer_display_name()
        last_printer = self.config.get_last_used_printer()

        if printer_name:
            # Show custom printer name - bold and larger font
            self.ip_label.setText(printer_name)
            self.ip_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        elif last_printer:
            # No custom name - show IP address instead
            self.ip_label.setText(last_printer)
            self.ip_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        else:
            # No printer at all - show placeholder
            self.ip_label.setText("No Printer")
            self.ip_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: gray;")

        # Always show label and hide combo
        self.ip_label.setVisible(True)
        self.ip_combo.setVisible(False)

    def apply_settings(self):
        """Apply settings changes to the UI"""
        # Update IP combo
        self.populate_printer_combobox()
        last_printer = self.config.get_last_used_printer()
        if last_printer:
            self.ip_combo.setCurrentText(last_printer)

        # Update IP label to show printer name if set
        self.update_ip_label()

        # Show/hide big progress label and FPS
        self.big_progress_label.setVisible(self.config.get_show_big_progress())
        self.fps_label.setVisible(self.config.get_show_fps())

    def show_no_connection_message(self):
        """Show a message when no camera is connected"""
        # Use the utility function from VideoStreamer
        img = self.video_streamer.create_no_connection_image()
        self.display_image(img)

    def populate_printer_combobox(self):
        """Populate the printer IP address combobox with recent printers"""
        recent_printers = self.config.get_recent_printers()
        self.ip_combo.clear()
        self.ip_combo.addItems(recent_printers)

    def reset_status(self):
        """Reset status message to previous state after temporary message"""
        # Only reset if not already reset and previous status exists
        if self.previous_status:
            self.status_label.setText(self.previous_status)
            self.previous_status = None  # Clear to avoid repeated resets

    def show_temporary_status(self, message, duration_ms=5000):
        """Show a temporary status message, then revert to previous status"""
        # Save current status before changing it
        self.previous_status = self.status_label.text()

        # Update status label with new message
        self.status_label.setText(message)

        # Stop any existing timer
        if self.status_timer.isActive():
            self.status_timer.stop()

        # Start timer to reset status after duration
        self.status_timer.start(duration_ms)

    def connect_to_printer(self):
        """Connect to the printer video stream and status monitor"""
        # Get IP from combo if visible, otherwise from config
        if self.ip_combo.isVisible():
            ip_address = self.ip_combo.currentText().strip()
        else:
            ip_address = self.config.get_last_used_printer()

        if not ip_address:
            QMessageBox.critical(
                self, "Error", "Please enter a printer IP address")
            return

        # Update status to connecting (yellow)
        self.status_indicator.setColor(StatusIndicator.YELLOW)
        self.status_label.setText(f"Connecting...")
        QApplication.processEvents()

        # Disconnect if already connected
        if self.video_streamer.is_running:
            self.disconnect_printer()

        # Set the IP address and RTSP settings for the video streamer
        self.video_streamer.set_ip_address(ip_address)
        self.video_streamer.set_port(self.config.get_rtsp_port())
        self.video_streamer.set_path(self.config.get_rtsp_path())
        self.video_streamer.set_transport(self.config.get_transport())

        # Try to connect to the camera
        if self.video_streamer.connect():
            # Successfully connected to video stream
            self.status_indicator.setColor(StatusIndicator.GREEN)
            # Store current IP and show in status
            self.current_ip = ip_address
            self.status_label.setText(f"Connected: {ip_address}")

            # Save to config
            self.config.add_printer(ip_address)
            self.populate_printer_combobox()

            # Enable snapshot button and video toggle
            self.snapshot_btn.setEnabled(True)
            self.video_toggle_btn.setEnabled(True)

            # Set video toggle button text based on current state
            if self.config.get_video_enabled():
                self.video_toggle_btn.setText("Disable Video")
            else:
                self.video_toggle_btn.setText("Enable Video")

            # Start video timer
            self.video_timer.start()

            # Start FPS timer
            self.fps_timer.start()

            # Start the status update timer (must be on main thread)
            self.printer_status_timer.start()

            # Connect to Elegoo printer monitor asynchronously
            def connect_printer_monitor_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(
                    self.connect_to_printer_monitor(ip_address))
                loop.close()

                if connected:
                    # Get initial status
                    self.fetch_printer_status()

            # Start the printer monitor connection in a separate thread
            threading.Thread(
                target=connect_printer_monitor_async, daemon=True).start()

        else:
            # Failed to connect to camera
            self.status_indicator.setColor(StatusIndicator.RED)
            self.status_label.setText("Not connected")
            rtsp_url = f"rtsp://{ip_address}:{self.config.get_rtsp_port()}{self.config.get_rtsp_path()}"
            QMessageBox.critical(self, "Connection Error",
                                 f"Could not connect to the camera at {rtsp_url}.\n\n"
                                 f"Please check that the printer is powered on, connected to the network, "
                                 f"and has the camera enabled.")

    def disconnect_printer(self):
        """Disconnect from the printer video stream and status monitor"""
        # Clear current IP
        self.current_ip = None

        # Disconnect from video stream
        if self.video_streamer.is_running:
            # Stop timers
            self.video_timer.stop()
            self.fps_timer.stop()

            # Disconnect video streamer
            self.video_streamer.disconnect()

            # Update status
            self.status_indicator.setColor(StatusIndicator.GRAY)
            self.status_label.setText("Not connected")

            # Disable buttons
            self.snapshot_btn.setEnabled(False)
            self.video_toggle_btn.setEnabled(False)

            # Reset FPS counter
            self.fps_label.setText("00.0 FPS")

            # Show no connection message
            self.show_no_connection_message()

        # Disconnect from printer monitor
        if self.printer_monitor.is_connected:
            # Stop the status timer
            self.printer_status_timer.stop()

            # Disconnect printer monitor
            self.printer_monitor.disconnect()

            # Clear printer status UI
            self.clear_printer_status_ui()

    def take_snapshot(self):
        """Take a snapshot of the current video frame and save it to desktop"""
        if not self.video_streamer.is_running:
            QMessageBox.warning(self, "Snapshot Error",
                                "No video stream is active")
            return

        # Take snapshot with timestamp if enabled in settings
        success, filepath = self.video_streamer.take_snapshot(
            add_timestamp=self.config.get_include_timestamp(),
            save_path=self.config.get_screenshot_path()
        )

        if success:
            # Show temporary success message
            self.show_temporary_status("Snapshot!", 5000)
        else:
            QMessageBox.critical(self, "Snapshot Error",
                                 "Failed to save snapshot")

    @pyqtSlot()
    def update_frame(self):
        """Update video frame (called by timer)"""
        if not self.video_streamer.is_running:
            return

        # Check if video is enabled in settings
        if not self.config.get_video_enabled():
            return

        # Get a new frame with timestamp
        success, frame = self.video_streamer.get_frame(add_timestamp=True)

        if success:
            # Frame received successfully - ensure status is green
            if self.status_indicator.color != StatusIndicator.GREEN:
                self.status_indicator.setColor(StatusIndicator.GREEN)
                if self.current_ip:
                    self.status_label.setText(f"Connected: {self.current_ip}")
                else:
                    self.status_label.setText("Connected")

            # Display the frame
            self.display_image(frame)

            # Update frame count for FPS calculation
            self.frame_count += 1
        else:
            # Failed to get frame - update status and disconnect
            self.status_indicator.setColor(StatusIndicator.YELLOW)
            self.status_label.setText("Connected but not able to stream")
            self.disconnect_printer()

    def display_image(self, img):
        """Convert OpenCV image to Qt format and display it"""
        if img is None:
            return

        # Convert the image to RGB format (OpenCV uses BGR)
        if len(img.shape) == 3:  # Color image
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            format = QImage.Format_RGB888
        else:  # Grayscale image
            format = QImage.Format_Grayscale8

        # Create QImage from the numpy array
        h, w = img.shape[:2]
        bytes_per_line = 3 * w if len(img.shape) == 3 else w
        q_img = QImage(img.data, w, h, bytes_per_line, format)

        # Get the size of the label
        label_size = self.video_frame.size()

        # Scale the image to fit the label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Display the image
        self.video_frame.setPixmap(scaled_pixmap)

    def closeEvent(self, event):
        """Handle window close event"""
        # Disconnect everything
        self.disconnect_printer()

        # Call parent's closeEvent
        super().closeEvent(event)


def main():
    """Main function"""
    print("==================================================")
    print("==================================================")
    print(f"                   Streamy v{APP_VERSION}                   ")
    print("       With Integrated Elegoo Printer Monitor     ")
    print("  Created and maintained by data_heavy@proton.me  ")
    print(" https://github.com/OverjoyedFrankenstein/Streamy")
    print("==================================================")
    print("==================================================")

    parser = argparse.ArgumentParser(
        description='RTSP Stream Viewer with Elegoo Printer Monitor')
    parser.add_argument('--ip', type=str, help='IP address of the printer')
    args = parser.parse_args()

    # Create QApplication
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')  # This style works well across platforms

    # Create main window
    window = StreamyApp(args.ip)
    window.show()

    # Start event loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()