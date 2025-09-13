#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/wifi_scanner.py
#
# Description:
# Live WiFi scanning module that executes platform-specific scan scripts
# and parses their JSON output into APData objects.
# -----------------------------------------------------------------------------

import os
import sys
import platform
import subprocess
import json
import time
from typing import List, Optional
from .data_models import APData


class WiFiScanner:
    """
    Live WiFi scanner that executes platform-specific scripts for scanning.
    
    Supports:
    - Windows: PowerShell script using native WLAN APIs
    - Linux: Shell script with nmcli/iwlist fallback
    - macOS: Shell script with airport utility
    """
    
    def __init__(self):
        """Initialize the WiFi scanner with platform detection."""
        self.platform = platform.system()
        self.script_dir = self._get_script_directory()
        self.script_path = self._get_script_path()
        
    def _get_script_directory(self) -> str:
        """Get the absolute path to the scripts directory."""
        # Get the directory containing this Python file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the project root and into scripts
        return os.path.join(os.path.dirname(current_dir), 'scripts')
    
    def _get_script_path(self) -> str:
        """Get the appropriate script path for the current platform."""
        if self.platform == "Windows":
            return os.path.join(self.script_dir, "get-wlans.ps1")
        else:  # Linux, macOS, or other Unix-like
            return os.path.join(self.script_dir, "get-wlans.sh")
    
    def scan(self, timeout: int = 30) -> List[APData]:
        """
        Perform a WiFi scan and return list of detected access points.
        
        Args:
            timeout: Maximum time to wait for scan completion (seconds)
            
        Returns:
            List of APData objects representing detected APs
            
        Raises:
            WiFiScanError: If scanning fails or times out
        """
        try:
            print(f"Starting WiFi scan on {self.platform}...")
            
            # Execute the appropriate script
            if self.platform == "Windows":
                result = self._run_powershell_script(timeout)
            else:
                result = self._run_shell_script(timeout)
            
            # Parse JSON output
            scan_data = json.loads(result.stdout)
            
            # Convert to APData objects
            ap_list = self._parse_scan_data(scan_data)
            
            print(f"Scan completed. Found {len(ap_list)} access points.")
            return ap_list
            
        except json.JSONDecodeError as e:
            raise WiFiScanError(f"Failed to parse scan output as JSON: {e}")
        except subprocess.TimeoutExpired:
            raise WiFiScanError(f"WiFi scan timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise WiFiScanError(f"Scan script failed with exit code {e.returncode}: {e.stderr}")
        except Exception as e:
            raise WiFiScanError(f"Unexpected error during WiFi scan: {e}")
    
    def _run_powershell_script(self, timeout: int) -> subprocess.CompletedProcess:
        """Execute the PowerShell script on Windows."""
        if not os.path.exists(self.script_path):
            raise WiFiScanError(f"PowerShell script not found: {self.script_path}")
        
        # Run PowerShell with execution policy bypass
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", self.script_path
        ]
        
        print(f"Executing: {' '.join(cmd)}")
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.script_dir
        )
    
    def _run_shell_script(self, timeout: int) -> subprocess.CompletedProcess:
        """Execute the shell script on Linux/macOS."""
        if not os.path.exists(self.script_path):
            raise WiFiScanError(f"Shell script not found: {self.script_path}")
        
        # Make sure script is executable
        try:
            os.chmod(self.script_path, 0o755)
        except OSError as e:
            print(f"Warning: Could not make script executable: {e}")
        
        cmd = ["/bin/bash", self.script_path]
        
        print(f"Executing: {' '.join(cmd)}")
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.script_dir
        )
    
    def _parse_scan_data(self, scan_data: List[dict]) -> List[APData]:
        """
        Parse scan JSON data into APData objects.
        
        Args:
            scan_data: List of dictionaries from scan script output
            
        Returns:
            List of APData objects
        """
        ap_list = []
        
        for entry in scan_data:
            try:
                # Handle different script output formats
                ssid = entry.get("SSID", entry.get("ssid", "Unknown"))
                bssid = entry.get("BSSID", entry.get("bssid", "Unknown"))
                rssi = entry.get("RSSI", entry.get("rssi", -100))
                
                # Optional fields that may not be present in all scripts
                quality = entry.get("Quality", self._estimate_quality_from_rssi(rssi))
                frequency = entry.get("Frequency", 0)
                channel = entry.get("Channel", 0)
                band = entry.get("Band", self._estimate_band_from_frequency(frequency))
                
                # Convert quality to int if it's a string
                if isinstance(quality, str):
                    try:
                        quality = int(quality)
                    except ValueError:
                        quality = self._estimate_quality_from_rssi(rssi)
                
                # Create APData object
                ap_data = APData(
                    ssid=ssid,
                    bssid=bssid,
                    channel=channel,
                    signal_strength=rssi,
                    security="Unknown",  # Scripts don't provide security info
                    frequency=frequency,
                    quality=quality,
                    band=band
                )
                
                ap_list.append(ap_data)
                
            except Exception as e:
                print(f"Warning: Failed to parse AP entry {entry}: {e}")
                continue
        
        return ap_list
    
    def _estimate_quality_from_rssi(self, rssi: int) -> int:
        """Estimate quality percentage from RSSI value."""
        if rssi >= -30:
            return 95
        elif rssi >= -40:
            return 90
        elif rssi >= -50:
            return 80
        elif rssi >= -60:
            return 70
        elif rssi >= -70:
            return 60
        elif rssi >= -80:
            return 40
        else:
            return 20
    
    def _estimate_band_from_frequency(self, frequency: int) -> str:
        """Estimate band from frequency if not provided."""
        if 2400 <= frequency <= 2500:
            return "2.4 GHz"
        elif 5000 <= frequency <= 5900:
            return "5 GHz"
        elif 5955 <= frequency <= 7125:
            return "6 GHz"
        else:
            return "Unknown"
    
    def is_available(self) -> bool:
        """
        Check if WiFi scanning is available on this platform.
        
        Returns:
            True if scanning should work, False otherwise
        """
        if not os.path.exists(self.script_path):
            return False
        
        if self.platform == "Windows":
            # Check if PowerShell is available
            try:
                subprocess.run(["powershell.exe", "-Command", "Get-Host"], 
                             capture_output=True, timeout=5)
                return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        else:
            # Check if bash is available
            try:
                subprocess.run(["/bin/bash", "--version"], 
                             capture_output=True, timeout=5)
                return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
    
    def get_platform_info(self) -> dict:
        """Get information about the current platform and scanning capabilities."""
        return {
            "platform": self.platform,
            "script_path": self.script_path,
            "script_exists": os.path.exists(self.script_path),
            "scanning_available": self.is_available()
        }


class WiFiScanError(Exception):
    """Exception raised for WiFi scanning errors."""
    pass


# Convenience function for simple scanning
def perform_wifi_scan(timeout: int = 30) -> List[APData]:
    """
    Perform a WiFi scan using the appropriate platform script.
    
    Args:
        timeout: Maximum time to wait for scan completion (seconds)
        
    Returns:
        List of APData objects
        
    Raises:
        WiFiScanError: If scanning fails
    """
    scanner = WiFiScanner()
    return scanner.scan(timeout)