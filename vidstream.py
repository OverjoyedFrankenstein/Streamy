#!/usr/bin/env python3
"""
Simplified video streaming module for Streamy application
Handles RTSP video streaming from Elegoo 3D printers
"""

import os
import cv2
import numpy as np
from datetime import datetime
import logging
import time
import warnings

# Configure logging
logger = logging.getLogger("streamy.vidstream")

class VideoStreamer:
    """Class to handle video streaming from RTSP sources (Elegoo printers)"""
    
    def __init__(self):
        """Initialize the VideoStreamer with default values"""
        self.ip_address = None
        self.cap = None
        self.is_running = False
        self.last_frame = None

        # RTSP settings
        self.transport = "udp"  # "udp" or "tcp"
        self.path = "/video"    # RTSP path (default: /video)

        # Suppress OpenCV error messages
        self._suppress_opencv_errors()

    def set_transport(self, transport):
        """Set the transport protocol (udp or tcp)"""
        self.transport = transport.lower()

    def set_path(self, path):
        """Set the RTSP path"""
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path
        self.path = path
    
    def _suppress_opencv_errors(self):
        """Suppress OpenCV error messages in a way compatible with all versions"""
        try:
            # Approach 1: Use environment variables (works on all versions)
            os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
            
            # Suppress Python warnings
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            
            # Disable standard error output (works on all platforms)
            if hasattr(os, 'devnull'):
                os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
            
            logger.info("OpenCV error messages suppressed")
        except Exception as e:
            logger.error(f"Failed to suppress OpenCV errors: {e}")
    
    def set_ip_address(self, ip_address):
        """Set the IP address for the video stream"""
        self.ip_address = ip_address
    
    def connect(self):
        """Connect to the video stream"""
        if not self.ip_address:
            logger.error("Cannot connect: No IP address provided")
            return False
        
        # Construct the RTSP URL
        rtsp_url = f"rtsp://{self.ip_address}:554{self.path}"
        logger.info(f"Connecting to RTSP stream at: {rtsp_url} (transport: {self.transport})")

        try:
            # Simple direct approach - minimize options for reliable connection
            cv2.setUseOptimized(True)

            # Set environment variable for RTSP transport before creating capture
            if self.transport == "tcp":
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"

            # Try to use FFMPEG backend if available
            try:
                self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            except:
                # Fallback for older OpenCV versions
                self.cap = cv2.VideoCapture(rtsp_url)

            # Set additional capture properties for more stable streaming
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Increase buffer size
            except:
                pass  # Ignore if this property isn't supported
            
            # Check if connected successfully
            if not self.cap.isOpened():
                logger.error(f"Failed to connect to RTSP stream at {rtsp_url}")
                return False
            
            # Give it time to properly initialize connection
            time.sleep(1.5)  # Increased initialization time
            
            # Try to read the first frame
            valid_frame = False
            for _ in range(10):  # Increased retry attempts
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    # Store the first frame
                    self.last_frame = frame.copy()
                    self.is_running = True
                    valid_frame = True
                    logger.info(f"Successfully connected to RTSP stream at {rtsp_url}")
                    break
                time.sleep(0.3)  # Longer delay between retries
            
            if valid_frame:
                return True
                
            # If we've tried multiple times and still no frame
            logger.error("Connected to RTSP stream but failed to read valid frames")
            self.cap.release()
            self.cap = None
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to RTSP stream: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def disconnect(self):
        """Disconnect from the video stream"""
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_running = False
        self.last_frame = None
        logger.info("Disconnected from video stream")
    
    def get_frame(self, add_timestamp=False):
        """Get a frame from the video stream
        
        Args:
            add_timestamp (bool): Whether to add a timestamp to the frame
            
        Returns:
            tuple: (success, frame) where success is a bool and frame is a numpy array
        """
        if not self.is_running or self.cap is None:
            return False, None
        
        try:
            # Read frame from video stream
            ret, frame = self.cap.read()
            
            if not ret or frame is None or frame.size == 0:
                # If no frame but we have a last frame, use that
                if self.last_frame is not None:
                    frame = self.last_frame.copy()
                    ret = True
                else:
                    return False, None
            else:
                # Successfully read frame, update last_frame
                self.last_frame = frame.copy()
            
            # Add timestamp if requested
            if add_timestamp:
                self.add_timestamp_to_frame(frame)
            
            return True, frame
            
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return False, None
    
    def add_timestamp_to_frame(self, frame):
        """Add timestamp to the frame
        
        Args:
            frame (numpy.ndarray): The frame to add the timestamp to
        """
        try:
            if frame is None:
                return
                
            # Get current time
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add timestamp to frame
            cv2.putText(
                frame,
                timestamp,
                (10, 30),  # Position (bottom-left corner)
                cv2.FONT_HERSHEY_SIMPLEX,  # Font
                0.7,  # Font scale
                (255, 255, 255),  # Color (white)
                2,  # Thickness
                cv2.LINE_AA  # Line type
            )
        except Exception as e:
            logger.error(f"Error adding timestamp to frame: {e}")
    
    def take_snapshot(self, add_timestamp=True):
        """Take a snapshot of the current frame and save it to the desktop
        
        Args:
            add_timestamp (bool): Whether to add a timestamp to the snapshot
            
        Returns:
            tuple: (success, filepath) where success is a bool and filepath is the path to the saved file
        """
        if not self.is_running:
            logger.error("Cannot take snapshot: Stream is not running")
            return False, None
        
        try:
            # Get current frame
            success, frame = self.get_frame(add_timestamp=False)
            
            if not success or frame is None:
                logger.error("Failed to get frame for snapshot")
                return False, None
            
            # Add timestamp if requested
            if add_timestamp:
                self.add_timestamp_to_frame(frame)
            
            # Create filename with date and time
            now = datetime.now()
            filename = f"printer_snapshot_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
            
            # Save to desktop
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            filepath = os.path.join(desktop_path, filename)
            
            # Ensure the directory exists
            os.makedirs(desktop_path, exist_ok=True)
            
            # Save the image
            cv2.imwrite(filepath, frame)
            logger.info(f"Snapshot saved to: {filepath}")
            
            return True, filepath
            
        except Exception as e:
            logger.error(f"Error taking snapshot: {e}")
            return False, None
    
    def create_no_connection_image(self):
        """Create an image indicating no connection
        
        Returns:
            numpy.ndarray: Image with "No Connection" message
        """
        # Create black image with same aspect ratio as video (16:9)
        height = 480
        width = 853
        img = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text with message
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "No Connection"
        text_size = cv2.getTextSize(text, font, 1.2, 2)[0]
        
        # Calculate position to center text
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        
        # Add text to image
        cv2.putText(
            img,
            text,
            (text_x, text_y),
            font,
            1.2,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
        
        # Add subtext with instruction
        subtext = "Enter printer IP and click Connect"
        subtext_size = cv2.getTextSize(subtext, font, 0.7, 1)[0]
        subtext_x = (width - subtext_size[0]) // 2
        subtext_y = text_y + 40
        
        cv2.putText(
            img,
            subtext,
            (subtext_x, subtext_y),
            font,
            0.7,
            (180, 180, 180),
            1,
            cv2.LINE_AA
        )
        
        return img
    
    def create_paused_image(self):
        """Create an image indicating video is paused but monitoring continues
        
        Returns:
            numpy.ndarray: Image with "Video Paused" message
        """
        # Use last frame if available, otherwise create black image
        if self.last_frame is not None:
            # Create a darkened copy of the last frame
            img = self.last_frame.copy()
            overlay = np.zeros_like(img)
            cv2.addWeighted(img, 0.4, overlay, 0.6, 0, img)  # Darken the image
        else:
            # Create black image with same aspect ratio as video (16:9)
            height = 480
            width = 853
            img = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text with message
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "Video Paused"
        text_size = cv2.getTextSize(text, font, 1.2, 2)[0]
        
        # Calculate position to center text
        text_x = (img.shape[1] - text_size[0]) // 2
        text_y = (img.shape[0] + text_size[1]) // 2
        
        # Add text to image
        cv2.putText(
            img,
            text,
            (text_x, text_y),
            font,
            1.2,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
        
        # Add subtext
        subtext = "Printer monitoring continues in background"
        subtext_size = cv2.getTextSize(subtext, font, 0.7, 1)[0]
        subtext_x = (img.shape[1] - subtext_size[0]) // 2
        subtext_y = text_y + 40
        
        cv2.putText(
            img,
            subtext,
            (subtext_x, subtext_y),
            font,
            0.7,
            (180, 180, 180),
            1,
            cv2.LINE_AA
        )
        
        return img