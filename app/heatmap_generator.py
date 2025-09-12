#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/heatmap_generator.py
#
# Description:
# Signal strength heatmap generation for the WLAN Scanner application.
# Creates visual overlays showing WiFi coverage based on scan point data.
# -----------------------------------------------------------------------------

import numpy as np
from PyQt5.QtGui import QColor, QPixmap, QPainter, QBrush
from PyQt5.QtCore import Qt
from typing import List, Tuple, Optional, Dict
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

from .data_models import ScanPoint, APData, Floor


class HeatmapGenerator:
    """
    Generates signal strength heatmaps from WiFi scan data.
    
    Color scheme based on actual scan data ranges:
    - Green: -20 to -45 dBm (Excellent)
    - Yellow: -45 to -60 dBm (Good) 
    - Orange: -60 to -75 dBm (Fair)
    - Red: -75 to -90 dBm (Poor)
    - Blue: -90+ dBm (Very Poor/No Signal)
    """
    
    # Signal strength ranges and corresponding colors (dBm)
    SIGNAL_RANGES = [
        (-20, -45, QColor(0, 255, 0, 180)),      # Green - Excellent
        (-45, -60, QColor(255, 255, 0, 180)),    # Yellow - Good
        (-60, -75, QColor(255, 165, 0, 180)),    # Orange - Fair  
        (-75, -90, QColor(255, 0, 0, 180)),      # Red - Poor
        (-90, -120, QColor(0, 0, 255, 180))      # Blue - Very Poor
    ]
    
    def __init__(self, width: int = 1920, height: int = 1080):
        """
        Initialize the heatmap generator.
        
        Args:
            width: Width of the heatmap in pixels (should match floor plan)
            height: Height of the heatmap in pixels (should match floor plan)
        """
        self.width = width
        self.height = height
        self.grid_resolution = 20  # Points per heatmap grid cell
        self.gaussian_sigma = 2.0  # Smoothing factor
    
    def generate_heatmap(self, scan_points: List[ScanPoint], 
                        target_network: Optional[str] = None,
                        floor: Optional[Floor] = None) -> QPixmap:
        """
        Generate a signal strength heatmap from scan point data.
        
        Args:
            scan_points: List of scan points containing AP data
            target_network: Specific network SSID to focus on (if None, uses strongest signal)
            floor: Floor object for coordinate scaling (optional)
            
        Returns:
            QPixmap containing the rendered heatmap overlay
        """
        if not scan_points:
            return self._create_empty_heatmap()
        
        # Extract signal data from scan points
        signal_data = self._extract_signal_data(scan_points, target_network)
        
        if not signal_data:
            return self._create_empty_heatmap()
        
        # Generate interpolated heatmap
        heatmap_array = self._interpolate_signals(signal_data)
        
        # Convert to QPixmap with color mapping
        return self._array_to_pixmap(heatmap_array)
    
    def _extract_signal_data(self, scan_points: List[ScanPoint], 
                           target_network: Optional[str]) -> List[Tuple[float, float, float]]:
        """
        Extract (x, y, signal_strength) tuples from scan points.
        
        Args:
            scan_points: List of scan points
            target_network: Target network SSID, or None for strongest signal
            
        Returns:
            List of (x, y, signal_strength) tuples
        """
        signal_data = []
        
        for scan_point in scan_points:
            if not scan_point.ap_list:
                continue
                
            # Find the signal strength for this point
            signal_strength = None
            
            if target_network:
                # Look for specific network
                for ap in scan_point.ap_list:
                    if ap.ssid == target_network:
                        signal_strength = ap.signal_strength
                        break
            else:
                # Use strongest signal at this point
                signal_strength = max(ap.signal_strength for ap in scan_point.ap_list)
            
            if signal_strength is not None:
                signal_data.append((
                    float(scan_point.map_x),
                    float(scan_point.map_y), 
                    float(signal_strength)
                ))
        
        return signal_data
    
    def _interpolate_signals(self, signal_data: List[Tuple[float, float, float]]) -> np.ndarray:
        """
        Create interpolated signal strength grid using scipy.
        
        Args:
            signal_data: List of (x, y, signal_strength) tuples
            
        Returns:
            2D numpy array with interpolated signal values
        """
        # Handle insufficient points for interpolation
        if len(signal_data) < 3:
            return self._create_simple_heatmap(signal_data)
        
        # Separate coordinates and values
        points = np.array([(x, y) for x, y, _ in signal_data])
        values = np.array([signal for _, _, signal in signal_data])
        
        # Create interpolation grid
        grid_x = np.linspace(0, self.width, self.width // self.grid_resolution)
        grid_y = np.linspace(0, self.height, self.height // self.grid_resolution)
        grid_X, grid_Y = np.meshgrid(grid_x, grid_y)
        
        # Interpolate using radial basis function
        try:
            grid_values = griddata(points, values, (grid_X, grid_Y), 
                                 method='cubic', fill_value=np.nan)
            
            # Apply gaussian smoothing
            grid_values = gaussian_filter(grid_values, sigma=self.gaussian_sigma)
            
        except Exception:
            try:
                # Fallback to linear interpolation if cubic fails
                grid_values = griddata(points, values, (grid_X, grid_Y), 
                                     method='linear', fill_value=np.nan)
            except Exception:
                # Last resort: use simple nearest neighbor
                grid_values = griddata(points, values, (grid_X, grid_Y), 
                                     method='nearest', fill_value=np.nan)
        
        return grid_values
    
    def _create_simple_heatmap(self, signal_data: List[Tuple[float, float, float]]) -> np.ndarray:
        """
        Create a simple heatmap for cases with too few points for interpolation.
        
        Args:
            signal_data: List of (x, y, signal_strength) tuples
            
        Returns:
            2D numpy array with signal values at specific points
        """
        # Create grid dimensions
        grid_width = self.width // self.grid_resolution
        grid_height = self.height // self.grid_resolution
        
        # Initialize with NaN
        grid_values = np.full((grid_height, grid_width), np.nan)
        
        # Place signal values at approximate grid positions
        for x, y, signal in signal_data:
            # Convert to grid coordinates
            grid_x = min(int(x * grid_width / self.width), grid_width - 1)
            grid_y = min(int(y * grid_height / self.height), grid_height - 1)
            
            # Set value and nearby cells to create a small coverage area
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    gx, gy = grid_x + dx, grid_y + dy
                    if 0 <= gx < grid_width and 0 <= gy < grid_height:
                        # Distance-based falloff
                        distance = np.sqrt(dx*dx + dy*dy)
                        if distance <= 2:
                            falloff = max(0, 1 - distance/3)
                            current_val = grid_values[gy, gx]
                            new_val = signal * falloff
                            
                            # Use strongest signal if multiple overlap
                            if np.isnan(current_val) or new_val > current_val:
                                grid_values[gy, gx] = new_val
        
        return grid_values
    
    def _array_to_pixmap(self, heatmap_array: np.ndarray) -> QPixmap:
        """
        Convert numpy array to QPixmap with proper color mapping.
        
        Args:
            heatmap_array: 2D array of signal strength values
            
        Returns:
            QPixmap with colored heatmap overlay
        """
        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Get array dimensions
        rows, cols = heatmap_array.shape
        cell_width = self.width / cols
        cell_height = self.height / rows
        
        # Draw heatmap cells
        for i in range(rows):
            for j in range(cols):
                signal_strength = heatmap_array[i, j]
                
                # Skip NaN values (no data)
                if np.isnan(signal_strength):
                    continue
                
                # Get color for this signal strength
                color = self._signal_to_color(signal_strength)
                
                # Draw the cell
                x = j * cell_width
                y = i * cell_height
                
                painter.fillRect(int(x), int(y), int(cell_width + 1), int(cell_height + 1), 
                               QBrush(color))
        
        painter.end()
        return pixmap
    
    def _signal_to_color(self, signal_strength: float) -> QColor:
        """
        Map signal strength to color based on defined ranges.
        
        Args:
            signal_strength: Signal strength in dBm
            
        Returns:
            QColor for the given signal strength
        """
        for min_signal, max_signal, color in self.SIGNAL_RANGES:
            if min_signal <= signal_strength <= max_signal:
                return color
        
        # Default to blue for very weak signals
        return self.SIGNAL_RANGES[-1][2]  # Blue
    
    def _create_empty_heatmap(self) -> QPixmap:
        """Create empty transparent heatmap."""
        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.transparent)
        return pixmap
    
    def get_connected_networks(self, scan_points: List[ScanPoint]) -> List[str]:
        """
        Get list of networks that appear to be the surveyed network.
        Uses heuristics like strongest consistent signal across points.
        
        Args:
            scan_points: List of scan points
            
        Returns:
            List of network SSIDs likely to be the surveyed network
        """
        if not scan_points:
            return []
        
        # Count network appearances and track signal strengths
        network_stats: Dict[str, List[float]] = {}
        
        for scan_point in scan_points:
            for ap in scan_point.ap_list:
                if ap.ssid not in network_stats:
                    network_stats[ap.ssid] = []
                network_stats[ap.ssid].append(ap.signal_strength)
        
        # Rank networks by coverage and signal strength
        network_scores = []
        total_scan_points = len(scan_points)
        
        for ssid, signals in network_stats.items():
            coverage_ratio = len(signals) / total_scan_points
            avg_signal = np.mean(signals)
            max_signal = max(signals)
            
            # Score based on coverage, average strength, and peak strength
            score = (coverage_ratio * 0.5 + 
                    (avg_signal + 100) / 100 * 0.3 +  # Normalize dBm to 0-1 range
                    (max_signal + 100) / 100 * 0.2)
            
            network_scores.append((score, ssid))
        
        # Sort by score and return top networks
        network_scores.sort(reverse=True)
        
        # Return networks with significant presence (>= 30% coverage)
        connected_networks = []
        for score, ssid in network_scores:
            coverage = len(network_stats[ssid]) / total_scan_points
            if coverage >= 0.3:  # At least 30% coverage
                connected_networks.append(ssid)
        
        return connected_networks
    
    def create_legend_pixmap(self, width: int = 200, height: int = 300) -> QPixmap:
        """
        Create a legend showing signal strength color mapping.
        
        Args:
            width: Legend width in pixels
            height: Legend height in pixels
            
        Returns:
            QPixmap containing the color legend
        """
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(255, 255, 255, 200))  # Semi-transparent white background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Draw title
        painter.setPen(Qt.black)
        painter.drawText(10, 20, "Signal Strength")
        painter.drawText(10, 35, "(dBm)")
        
        # Draw color bands with labels
        y_start = 50
        band_height = (height - y_start - 20) // len(self.SIGNAL_RANGES)
        
        labels = ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
        
        for i, ((min_sig, max_sig, color), label) in enumerate(zip(self.SIGNAL_RANGES, labels)):
            y = y_start + i * band_height
            
            # Draw color rectangle
            painter.fillRect(10, y, 30, band_height - 5, QBrush(color))
            
            # Draw label and range
            painter.setPen(Qt.black)
            painter.drawText(50, y + 15, f"{label}")
            painter.drawText(50, y + 30, f"{min_sig} to {max_sig}")
        
        painter.end()
        return pixmap