#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/data_models.py
#
# Description:
# Data model classes for the WLAN Scanner application. Contains all data
# structures for projects, floors, access points, scan points, and site info.
# -----------------------------------------------------------------------------

import json
import re
from datetime import datetime

class APData:
    """
    Represents details of an Access Point detected during a scan.
    """
    def __init__(self, ssid, bssid, channel, signal_strength, security, frequency, quality, band):
        self.ssid = ssid
        self.bssid = bssid
        self.channel = channel
        self.signal_strength = signal_strength
        self.security = security
        self.frequency = frequency
        self.quality = quality
        self.band = band

    def to_dict(self):
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        """Create APData instance from dictionary."""
        return cls(
            ssid=data['ssid'],
            bssid=data['bssid'], 
            channel=data['channel'],
            signal_strength=data['signal_strength'],
            security=data['security'],
            frequency=data['frequency'],
            quality=data['quality'],
            band=data['band']
        )

class ScanPoint:
    """
    Represents a user-defined point on the map where a Wi-Fi scan was performed.
    """
    def __init__(self, map_x, map_y, timestamp, ap_list):
        self.map_x = map_x
        self.map_y = map_y
        self.timestamp = timestamp
        self.ap_list = ap_list # List of APData objects

    def to_dict(self):
        return {
            'map_x': self.map_x,
            'map_y': self.map_y,
            'timestamp': self.timestamp.isoformat(), # Store as ISO format string
            'ap_list': [ap.to_dict() for ap in self.ap_list]
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create ScanPoint instance from dictionary."""
        timestamp = datetime.fromisoformat(data['timestamp'])
        ap_list = [APData.from_dict(ap_data) for ap_data in data['ap_list']]
        return cls(
            map_x=data['map_x'],
            map_y=data['map_y'],
            timestamp=timestamp,
            ap_list=ap_list
        )

class PlacedAP:
    """
    Represents a user-placed Access Point on the map.
    """
    def __init__(self, name, manufacturer, model, ip_address, ethernet_mac, map_x, map_y, associated_scan_data=None, timestamp_last_scan=None):
        self.name = name
        self.manufacturer = manufacturer
        self.model = model
        self.ip_address = ip_address
        self.ethernet_mac = ethernet_mac
        self.map_x = map_x
        self.map_y = map_y
        self.associated_scan_data = associated_scan_data if associated_scan_data is not None else [] # List of APData objects
        self.timestamp_last_scan = timestamp_last_scan # datetime object

    def to_dict(self):
        return {
            'name': self.name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'ip_address': self.ip_address,
            'ethernet_mac': self.ethernet_mac,
            'map_x': self.map_x,
            'map_y': self.map_y,
            'associated_scan_data': [ap.to_dict() for ap in self.associated_scan_data],
            'timestamp_last_scan': self.timestamp_last_scan.isoformat() if self.timestamp_last_scan else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create PlacedAP instance from dictionary."""
        associated_scan_data = [APData.from_dict(ap_data) for ap_data in data['associated_scan_data']]
        timestamp_last_scan = datetime.fromisoformat(data['timestamp_last_scan']) if data['timestamp_last_scan'] else None
        return cls(
            name=data['name'],
            manufacturer=data['manufacturer'],
            model=data['model'],
            ip_address=data['ip_address'],
            ethernet_mac=data['ethernet_mac'],
            map_x=data['map_x'],
            map_y=data['map_y'],
            associated_scan_data=associated_scan_data,
            timestamp_last_scan=timestamp_last_scan
        )

class ScaleLine:
    """
    Represents a defined scale line on a floor plan image.
    Physical dimension is always stored internally in meters.
    """
    def __init__(self, x1, y1, x2, y2, physical_dimension_value, is_horizontal, physical_dimension_unit="m"):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        # Ensure physical_dimension_value is always stored in meters
        self.physical_dimension_value = physical_dimension_value
        self.physical_dimension_unit = physical_dimension_unit # Should always be 'm' internally
        self.is_horizontal = is_horizontal

    @property
    def pixel_length(self):
        """Calculates the length of the line in pixels."""
        return ((self.x2 - self.x1)**2 + (self.y2 - self.y1)**2)**0.5

    def to_dict(self):
        """Converts the ScaleLine object to a dictionary for serialization."""
        return {
            'x1': self.x1,
            'y1': self.y1,
            'x2': self.x2,
            'y2': self.y2,
            'physical_dimension_value': self.physical_dimension_value,
            'physical_dimension_unit': self.physical_dimension_unit,
            'is_horizontal': self.is_horizontal,
            'pixel_length': self.pixel_length
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create ScaleLine instance from dictionary."""
        return cls(
            x1=data['x1'],
            y1=data['y1'],
            x2=data['x2'],
            y2=data['y2'],
            physical_dimension_value=data['physical_dimension_value'],
            is_horizontal=data['is_horizontal'],
            physical_dimension_unit=data.get('physical_dimension_unit', 'm')
        )

    @staticmethod
    def parse_physical_dimension_input(input_string):
        """
        Parses a string like "40' 6"", "40 ft", "12.34m", "12.34 meters"
        and returns the value converted to meters and the unit "m".
        """
        input_string = input_string.strip().lower()
        value = None
        unit = None

        # Regex for feet and inches (e.g., 40' 6", 40 ft 6 in, 40')
        match_ft_in = re.match(r"(\d+)'\s*(?:(\d+)\s*\"|\s*(\d+)\s*in)?", input_string)
        if match_ft_in:
            feet = float(match_ft_in.group(1))
            inches = 0.0
            if match_ft_in.group(2): # "X' Y"" format
                inches = float(match_ft_in.group(2))
            elif match_ft_in.group(3): # "X' Y in" format
                inches = float(match_ft_in.group(3))
            
            total_feet = feet + (inches / 12.0)
            value = total_feet * 0.3048 # Convert feet to meters
            unit = "m"
            return value, unit

        # Regex for feet (e.g., 40 feet, 40.5 feet, 40ft)
        match_feet = re.match(r"(\d+(\.\d+)?)\s*(feet|ft)", input_string)
        if match_feet:
            total_feet = float(match_feet.group(1))
            value = total_feet * 0.3048 # Convert feet to meters
            unit = "m"
            return value, unit

        # Regex for meters (e.g., 12.34m, 12.34 meters)
        match_meters = re.match(r"(\d+(\.\d+)?)\s*(meters|m)", input_string)
        if match_meters:
            value = float(match_meters.group(1))
            unit = "m" # Already in meters
            return value, unit

        return None, None # No match

    @staticmethod
    def convert_to_feet(value_in_meters):
        """Converts a value from meters to feet."""
        return value_in_meters / 0.3048

    @staticmethod
    def convert_to_meters(value_in_feet):
        """Converts a value from feet to meters."""
        return value_in_feet * 0.3048


class Floor:
    """
    Encapsulates data for a single floor plan.
    """
    def __init__(self, floor_number, original_image_path, cropped_image_path, scaled_image_path,
                 scale_line_horizontal=None, scale_line_vertical=None, placed_aps=None, scan_points=None):
        self.floor_number = floor_number
        self.original_image_path = original_image_path
        self.cropped_image_path = cropped_image_path
        self.scaled_image_path = scaled_image_path
        self.scale_line_horizontal = scale_line_horizontal # ScaleLine object
        self.scale_line_vertical = scale_line_vertical   # ScaleLine object
        self.placed_aps = placed_aps if placed_aps is not None else [] # List of PlacedAP objects
        self.scan_points = scan_points if scan_points is not None else [] # List of ScanPoint objects

    def to_dict(self):
        return {
            'floor_number': self.floor_number,
            'original_image_path': self.original_image_path,
            'cropped_image_path': self.cropped_image_path,
            'scaled_image_path': self.scaled_image_path,
            'scale_line_horizontal': self.scale_line_horizontal.to_dict() if self.scale_line_horizontal else None,
            'scale_line_vertical': self.scale_line_vertical.to_dict() if self.scale_line_vertical else None,
            'placed_aps': [ap.to_dict() for ap in self.placed_aps],
            'scan_points': [sp.to_dict() for sp in self.scan_points]
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Floor instance from dictionary."""
        scale_line_horizontal = ScaleLine.from_dict(data['scale_line_horizontal']) if data['scale_line_horizontal'] else None
        scale_line_vertical = ScaleLine.from_dict(data['scale_line_vertical']) if data['scale_line_vertical'] else None
        placed_aps = [PlacedAP.from_dict(ap_data) for ap_data in data['placed_aps']]
        scan_points = [ScanPoint.from_dict(sp_data) for sp_data in data['scan_points']]
        return cls(
            floor_number=data['floor_number'],
            original_image_path=data['original_image_path'],
            cropped_image_path=data['cropped_image_path'],
            scaled_image_path=data['scaled_image_path'],
            scale_line_horizontal=scale_line_horizontal,
            scale_line_vertical=scale_line_vertical,
            placed_aps=placed_aps,
            scan_points=scan_points
        )

class SiteInfo:
    """
    Stores general site information.
    """
    def __init__(self, site_name="", street="", city="", state_province="", postal_code="", country="", contact="", telephone=""):
        self.site_name = site_name
        self.street = street
        self.city = city
        self.state_province = state_province
        self.postal_code = postal_code
        self.country = country
        self.contact = contact
        self.telephone = telephone

    def to_dict(self):
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        """Create SiteInfo instance from dictionary."""
        return cls(
            site_name=data.get('site_name', ''),
            street=data.get('street', ''),
            city=data.get('city', ''),
            state_province=data.get('state_province', ''),
            postal_code=data.get('postal_code', ''),
            country=data.get('country', ''),
            contact=data.get('contact', ''),
            telephone=data.get('telephone', '')
        )

class MapProject:
    """
    Encapsulates all data for a complete mapping project.
    """
    def __init__(self, site_info=None, floors=None, current_floor_index=0):
        self.site_info = site_info if site_info is not None else SiteInfo()
        self.floors = floors if floors is not None else [] # List of Floor objects
        self.current_floor_index = current_floor_index

    def to_dict(self):
        return {
            'site_info': self.site_info.to_dict(),
            'floors': [floor.to_dict() for floor in self.floors],
            'current_floor_index': self.current_floor_index
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create MapProject instance from dictionary."""
        site_info = SiteInfo.from_dict(data['site_info'])
        floors = [Floor.from_dict(floor_data) for floor_data in data['floors']]
        return cls(
            site_info=site_info,
            floors=floors,
            current_floor_index=data.get('current_floor_index', 0)
        )

