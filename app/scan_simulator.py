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
import math
from .data_models import APData

class ScanSimulator:
    """
    Generates simulated WiFi scan data matching the format from get-wlans.ps1
    Now includes spatial consistency for realistic site surveys.
    """
    
    # Primary site networks (appear consistently across the site)
    PRIMARY_NETWORKS = [
        {"ssid": "LITS", "bssid_base": "2C-B4-3A-12-34", "channel": 6, "band": "2.4 GHz", "base_power": -25},
        {"ssid": "LITS-Guest", "bssid_base": "2C-B4-3A-12-35", "channel": 11, "band": "2.4 GHz", "base_power": -30},
        {"ssid": "LITS-IOT", "bssid_base": "2C-B4-3A-56-78", "channel": 149, "band": "5 GHz", "base_power": -28},
    ]
    
    # Secondary networks (appear at some locations)
    SECONDARY_NETWORKS = [
        {"ssid": "Building_WiFi", "bssid_base": "AC-67-B2-34-56", "channel": 1, "band": "2.4 GHz", "base_power": -35},
        {"ssid": "Conference_Room_AP", "bssid_base": "AC-67-B2-78-90", "channel": 36, "band": "5 GHz", "base_power": -32},
        {"ssid": "Office_Main", "bssid_base": "D4-CA-6E-AB-CD", "channel": 44, "band": "5 GHz", "base_power": -38},
    ]
    
    # Background networks (neighbor/external networks, appear randomly)
    BACKGROUND_NETWORKS = [
        "SpectrumSetup-78", "SpectrumSetup-15D7", "SpectrumSetup-57", "SpectrumSetup-41", 
        "HomeBase", "Littles", "ATTDsy66pi", "Spectrum Mobile", 
        "DIRECT-AA-HP DeskJet 4200 series", "{Hidden}", "Public_Access"
    ]
    
    def __init__(self, seed=None, floor_width=1920, floor_height=1080, placed_aps=None):
        """
        Initialize the simulator with optional random seed for reproducible results.
        
        Args:
            seed: Random seed for reproducible results
            floor_width: Width of the floor plan in pixels  
            floor_height: Height of the floor plan in pixels
            placed_aps: List of actual placed APs from the project (optional)
        """
        if seed:
            random.seed(seed)
        
        self.floor_width = floor_width
        self.floor_height = floor_height
        
        # Use actual placed APs if provided, otherwise generate simulated ones
        if placed_aps:
            self.primary_ap_locations = self._map_placed_aps_to_networks(placed_aps)
        else:
            self.primary_ap_locations = self._generate_primary_ap_locations()
        
        # Generate some secondary AP locations
        self.secondary_ap_locations = self._generate_secondary_ap_locations()
    
    def _generate_primary_ap_locations(self):
        """Generate fixed AP locations for primary networks (simulates real deployment)"""
        locations = []
        
        # Create realistic AP placement - distributed around the floor
        ap_positions = [
            (self.floor_width * 0.25, self.floor_height * 0.25),  # NW quadrant
            (self.floor_width * 0.75, self.floor_height * 0.25),  # NE quadrant  
            (self.floor_width * 0.50, self.floor_height * 0.75),  # S center
        ]
        
        for i, (network, (x, y)) in enumerate(zip(self.PRIMARY_NETWORKS, ap_positions)):
            # Add some randomness but keep consistent per seed
            x += random.randint(-50, 50)
            y += random.randint(-50, 50)
            
            locations.append({
                'network': network,
                'x': x,
                'y': y,
                'bssid': f"{network['bssid_base']}-{i:02X}"
            })
        
        return locations
    
    def _map_placed_aps_to_networks(self, placed_aps):
        """
        Map actual placed APs to primary network types.
        
        Args:
            placed_aps: List of placed AP objects from the project
            
        Returns:
            List of AP locations mapped to primary networks
        """
        locations = []
        
        # Map each placed AP to a primary network (cycling through available networks)
        for i, ap in enumerate(placed_aps):
            network_index = i % len(self.PRIMARY_NETWORKS)
            network = self.PRIMARY_NETWORKS[network_index]
            
            locations.append({
                'network': network,
                'x': ap.map_x,  # Use actual AP coordinates
                'y': ap.map_y,
                'bssid': f"{network['bssid_base']}-{i:02X}",
                'placed_ap': ap  # Keep reference to original AP
            })
        
        return locations
    
    def _generate_secondary_ap_locations(self):
        """Generate locations for secondary networks"""
        locations = []
        
        # Secondary networks have fewer, more random locations
        for i, network in enumerate(self.SECONDARY_NETWORKS):
            # Only place 60% of secondary networks
            if random.random() < 0.6:
                x = random.randint(int(self.floor_width * 0.1), int(self.floor_width * 0.9))
                y = random.randint(int(self.floor_height * 0.1), int(self.floor_height * 0.9))
                
                locations.append({
                    'network': network,
                    'x': x,
                    'y': y,  
                    'bssid': f"{network['bssid_base']}-{i:02X}"
                })
        
        return locations
    
    def _calculate_signal_strength(self, ap_x, ap_y, scan_x, scan_y, base_power):
        """
        Calculate signal strength based on distance using realistic RF propagation.
        
        Args:
            ap_x, ap_y: AP location coordinates
            scan_x, scan_y: Scan location coordinates  
            base_power: Base power level of the AP (dBm)
            
        Returns:
            int: Signal strength in dBm
        """
        # Calculate distance in pixels
        distance_pixels = math.sqrt((scan_x - ap_x)**2 + (scan_y - ap_y)**2)
        
        # Convert pixels to approximate meters (assuming 1920px = ~50m floor width)
        distance_meters = distance_pixels * (50.0 / self.floor_width)
        
        # Prevent division by zero
        distance_meters = max(distance_meters, 0.1)
        
        # Free space path loss: 20*log10(d) + 20*log10(f) + 32.44
        # Simplified for 2.4GHz: roughly 40*log10(distance) + environmental factors
        path_loss = 40 * math.log10(distance_meters) + random.randint(-5, 5)  # Some randomness
        
        # Calculate final signal strength
        signal_strength = base_power - path_loss
        
        # Clamp to realistic WiFi ranges
        return max(-95, min(-20, int(signal_strength)))
    
    def generate_random_mac(self):
        """Generate a random MAC address in the format XX-XX-XX-XX-XX-XX (matching scan format)"""
        return "-".join([f"{random.randint(0, 255):02X}" for _ in range(6)])
    
    def generate_simulated_scan_json(self, count=None, scan_x=None, scan_y=None):
        """
        Generate simulated scan data in the exact JSON format as get-wlans.ps1
        Now with spatial consistency based on scan location.
        
        Args:
            count (int, optional): Number of APs to generate. If None, uses realistic count
            scan_x, scan_y (float, optional): Scan location coordinates for spatial consistency
            
        Returns:
            str: JSON string matching the scan script format
        """
        scan_results = []
        
        # Channel/frequency mappings  
        channel_freq_map = {
            1: (2412, "2.4 GHz"), 6: (2437, "2.4 GHz"), 8: (2447, "2.4 GHz"), 11: (2462, "2.4 GHz"),
            36: (5180, "5 GHz"), 44: (5220, "5 GHz"), 100: (5500, "5 GHz"), 149: (5745, "5 GHz")
        }
        
        # Add primary networks (always visible with distance-based signal strength)
        for ap_location in self.primary_ap_locations:
            network = ap_location['network']
            
            if scan_x is not None and scan_y is not None:
                # Calculate realistic signal strength based on distance
                rssi = self._calculate_signal_strength(
                    ap_location['x'], ap_location['y'],
                    scan_x, scan_y,
                    network['base_power']
                )
            else:
                # Fallback to random but weighted toward stronger signals
                rssi = random.randint(-80, -30)
            
            frequency, band = channel_freq_map[network['channel']]
            quality = self._calculate_quality_from_rssi(rssi)
            
            ap_entry = {
                "SSID": network['ssid'],
                "BSSID": ap_location['bssid'],
                "RSSI": rssi,
                "Quality": str(quality),
                "Frequency": frequency,
                "Channel": network['channel'],
                "Band": band
            }
            scan_results.append(ap_entry)
        
        # Add secondary networks (sometimes visible)
        for ap_location in self.secondary_ap_locations:
            # 70% chance to appear
            if random.random() < 0.7:
                network = ap_location['network']
                
                if scan_x is not None and scan_y is not None:
                    rssi = self._calculate_signal_strength(
                        ap_location['x'], ap_location['y'],
                        scan_x, scan_y,
                        network['base_power']
                    )
                else:
                    rssi = random.randint(-85, -40)
                
                frequency, band = channel_freq_map[network['channel']]
                quality = self._calculate_quality_from_rssi(rssi)
                
                ap_entry = {
                    "SSID": network['ssid'],
                    "BSSID": ap_location['bssid'], 
                    "RSSI": rssi,
                    "Quality": str(quality),
                    "Frequency": frequency,
                    "Channel": network['channel'],
                    "Band": band
                }
                scan_results.append(ap_entry)
        
        # Add some background/neighbor networks (random)
        background_count = random.randint(2, 6)
        for _ in range(background_count):
            ssid = random.choice(self.BACKGROUND_NETWORKS)
            bssid = self.generate_random_mac()
            channel = random.choice(list(channel_freq_map.keys()))
            frequency, band = channel_freq_map[channel]
            rssi = random.randint(-90, -50)  # Usually weaker
            quality = self._calculate_quality_from_rssi(rssi)
            
            ap_entry = {
                "SSID": ssid,
                "BSSID": bssid,
                "RSSI": rssi,
                "Quality": str(quality),
                "Frequency": frequency,
                "Channel": channel,
                "Band": band
            }
            scan_results.append(ap_entry)
        
        # Sort by RSSI (strongest first) like the actual scan
        scan_results.sort(key=lambda x: x["RSSI"], reverse=True)
        
        return json.dumps(scan_results, indent=2)
    
    def _calculate_quality_from_rssi(self, rssi):
        """Calculate quality percentage from RSSI value"""
        if rssi >= -30:
            return random.randint(95, 99)
        elif rssi >= -40:
            return random.randint(85, 95)
        elif rssi >= -50:
            return random.randint(70, 87)
        elif rssi >= -60:
            return random.randint(60, 81)
        elif rssi >= -70:
            return random.randint(50, 70)
        elif rssi >= -80:
            return random.randint(25, 50)
        else:
            return random.randint(10, 30)
    
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
    
    def generate_ap_data_list(self, count=None, scan_x=None, scan_y=None):
        """
        Generate APData objects directly (convenience method)
        
        Args:
            count (int, optional): Number of APs to generate
            scan_x, scan_y (float, optional): Scan location for spatial consistency
            
        Returns:
            List[APData]: List of simulated APData objects
        """
        json_str = self.generate_simulated_scan_json(count, scan_x, scan_y)
        return self.parse_scan_json_to_ap_data(json_str)