#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/scan_simulator.py
#
# Description:
# Simulated WiFi scan data generator that matches the actual scan script format.
# Generates realistic AP data using the same JSON structure as get-wlans.ps1
# -----------------------------------------------------------------------------

import random
import json
from .data_models import APData

class ScanSimulator:
    """
    Generates simulated WiFi scan data matching the format from get-wlans.ps1
    """
    
    # Real-world SSID patterns based on your scan
    SAMPLE_SSIDS = [
        "LITS", "LITS-IOT", "LITS-Guest", "{Hidden}", 
        "SpectrumSetup-78", "SpectrumSetup-15D7", "SpectrumSetup-57", "SpectrumSetup-41", "SpectrumSetup-93",
        "Spectrum Mobile", "DIRECT-AA-HP DeskJet 4200 series", "HomeBase", "Littles", "ATTDsy66pi",
        "CorporateNet", "Guest_Network", "Office_Main", "Conference_Room_AP", "Building_WiFi", "Public_Access"
    ]
    
    def __init__(self, seed=None):
        """Initialize the simulator with optional random seed for reproducible results."""
        if seed:
            random.seed(seed)
    
    def generate_random_mac(self):
        """Generate a random MAC address in the format XX-XX-XX-XX-XX-XX (matching scan format)"""
        return "-".join([f"{random.randint(0, 255):02X}" for _ in range(6)])
    
    def generate_simulated_scan_json(self, count=None):
        """
        Generate simulated scan data in the exact JSON format as get-wlans.ps1
        
        Args:
            count (int, optional): Number of APs to generate. If None, random 8-20
            
        Returns:
            str: JSON string matching the scan script format
        """
        if count is None:
            count = random.randint(8, 20)
        
        scan_results = []
        
        # Common 2.4GHz and 5GHz channel/frequency mappings
        channels_2_4 = {
            1: 2412, 6: 2437, 8: 2447, 11: 2462
        }
        channels_5 = {
            36: 5180, 44: 5220, 100: 5500, 149: 5745
        }
        
        for _ in range(count):
            ssid = random.choice(self.SAMPLE_SSIDS)
            bssid = self.generate_random_mac()
            
            # Choose band and corresponding channel/frequency
            if random.choice([True, False]):  # 50% 2.4GHz, 50% 5GHz
                channel = random.choice(list(channels_2_4.keys()))
                frequency = channels_2_4[channel]
                band = "2.4 GHz"
            else:
                channel = random.choice(list(channels_5.keys()))
                frequency = channels_5[channel]
                band = "5 GHz"
            
            # RSSI ranges from your actual scan: -23 to -92
            rssi = random.randint(-92, -23)
            
            # Quality calculation based on RSSI (matching your scan patterns)
            if rssi >= -30:
                quality = random.randint(95, 99)
            elif rssi >= -40:
                quality = random.randint(85, 95)
            elif rssi >= -50:
                quality = random.randint(70, 87)
            elif rssi >= -60:
                quality = random.randint(60, 81)
            elif rssi >= -70:
                quality = random.randint(50, 70)
            elif rssi >= -80:
                quality = random.randint(25, 50)
            else:
                quality = random.randint(10, 30)
            
            ap_entry = {
                "SSID": ssid,
                "BSSID": bssid,
                "RSSI": rssi,
                "Quality": str(quality),  # Quality is string in the actual format
                "Frequency": frequency,
                "Channel": channel,
                "Band": band
            }
            
            scan_results.append(ap_entry)
        
        # Sort by RSSI (strongest first) like the actual scan
        scan_results.sort(key=lambda x: x["RSSI"], reverse=True)
        
        return json.dumps(scan_results, indent=2)
    
    def parse_scan_json_to_ap_data(self, json_str):
        """
        Parse scan JSON string into APData objects for the application
        
        Args:
            json_str (str): JSON string from scan or simulation
            
        Returns:
            List[APData]: List of APData objects
        """
        try:
            scan_data = json.loads(json_str)
            ap_list = []
            
            for entry in scan_data:
                # Map the scan format to APData constructor
                ap_data = APData(
                    ssid=entry["SSID"],
                    bssid=entry["BSSID"],
                    channel=entry["Channel"],
                    signal_strength=entry["RSSI"],  # RSSI maps to signal_strength
                    security="Unknown",  # Scan doesn't include security info
                    frequency=entry["Frequency"],
                    quality=int(entry["Quality"]),  # Convert quality back to int
                    band=entry["Band"]
                )
                ap_list.append(ap_data)
            
            return ap_list
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing scan JSON: {e}")
            return []
    
    def generate_ap_data_list(self, count=None):
        """
        Generate APData objects directly (convenience method)
        
        Args:
            count (int, optional): Number of APs to generate
            
        Returns:
            List[APData]: List of simulated APData objects
        """
        json_str = self.generate_simulated_scan_json(count)
        return self.parse_scan_json_to_ap_data(json_str)