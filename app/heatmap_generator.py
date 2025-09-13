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
import time
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
        self.grid_resolution = 15  # Moderate resolution for realistic appearance
        self.gaussian_sigma = 1.5  # Light smoothing to preserve signal variations

    def generate_heatmap(self, scan_points: List[ScanPoint],
                        target_network: Optional[str] = None,
                        floor: Optional[Floor] = None,
                        status_callback=None) -> QPixmap:
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

        # Use direct signal-based rendering instead of grid interpolation
        return self._create_signal_based_heatmap(scan_points, target_network, floor, status_callback)

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
        Convert numpy array to QPixmap with circular signal patterns.

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
        
        # Calculate cell radius for circular coverage
        cell_radius = max(cell_width, cell_height) * 0.8

        # Draw heatmap cells as circles (realistic RF propagation)
        for i in range(rows):
            for j in range(cols):
                signal_strength = heatmap_array[i, j]

                # Skip NaN values (no data)
                if np.isnan(signal_strength):
                    continue

                # Get color for this signal strength
                color = self._signal_to_color(signal_strength)

                # Calculate center position
                center_x = j * cell_width + cell_width / 2
                center_y = i * cell_height + cell_height / 2

                # Draw filled circle
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    int(center_x - cell_radius), 
                    int(center_y - cell_radius),
                    int(cell_radius * 2), 
                    int(cell_radius * 2)
                )

        painter.end()
        return pixmap

    def _create_signal_based_heatmap(self, scan_points: List[ScanPoint], 
                                   target_network: Optional[str] = None, 
                                   floor: Optional[Floor] = None,
                                   status_callback=None) -> QPixmap:
        """
        Create heatmap by drawing signal coverage circles around APs based on scan measurements.
        APs are the signal sources, scan points provide measurement data for modeling.

        Args:
            scan_points: List of scan points containing measurement data
            target_network: Specific network SSID to focus on

        Returns:
            QPixmap with AP coverage visualization
        """
        if not scan_points:
            return self._create_empty_heatmap()
        
        # Report progress
        if status_callback:
            status_callback("analyzing_scan_data_status")
            time.sleep(1.0)  # Pause to show message
            
        # Find all APs for the target network from scan data
        ap_locations = self._identify_ap_locations(scan_points, target_network, floor)
        
        # Report progress
        if status_callback:
            status_callback("estimating_ap_locations_status")
            time.sleep(1.0)  # Pause to show message
        
        if not ap_locations:
            return self._create_empty_heatmap()

        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.transparent)

        # Create signal strength grid to determine strongest signal at each point
        signal_grid = self._create_signal_strength_grid(ap_locations)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw the signal strength grid as colored pixels
        self._draw_signal_grid(painter, signal_grid)

        painter.end()
        return pixmap

    def _identify_ap_locations(self, scan_points: List[ScanPoint], target_network: Optional[str] = None, floor: Optional[Floor] = None):
        """
        Estimate AP source locations from scan data signal strength patterns.
        
        Args:
            scan_points: List of scan points containing measurement data
            target_network: Specific network SSID to focus on
            floor: Floor object (used for boundary info, optional)
            
        Returns:
            List of estimated AP location data with coordinates and signal info
        """
        ap_locations = []
        
        if not scan_points:
            return ap_locations
        
        # Collect all networks matching the target
        network_measurements = {}  # bssid -> list of (x, y, signal_strength)
        
        for scan_point in scan_points:
            if not scan_point.ap_list:
                continue
                
            for ap in scan_point.ap_list:
                # Filter by target network if specified
                if target_network and ap.ssid != target_network:
                    continue
                    
                bssid = ap.bssid
                if bssid not in network_measurements:
                    network_measurements[bssid] = []
                    
                network_measurements[bssid].append({
                    'x': scan_point.map_x,
                    'y': scan_point.map_y,
                    'signal': ap.signal_strength,
                    'ap_data': ap
                })
        
        # For each unique BSSID, estimate the source location
        for bssid, measurements in network_measurements.items():
            if len(measurements) < 2:  # Need at least 2 measurements for estimation
                continue
                
            estimated_location = self._estimate_ap_source_location(measurements)
            if estimated_location:
                ap_locations.append(estimated_location)
        
        return ap_locations
    
    def _estimate_ap_source_location(self, measurements):
        """
        Estimate AP source location from signal strength measurements.
        
        Args:
            measurements: List of {'x': x, 'y': y, 'signal': signal, 'ap_data': ap_data}
            
        Returns:
            Dict with estimated AP location and signal info
        """
        if not measurements:
            return None
            
        # Find the measurement with strongest signal (closest to source)
        strongest_measurement = max(measurements, key=lambda m: m['signal'])
        
        # Use weighted average based on signal strength for more accuracy
        total_weight = 0
        weighted_x = 0
        weighted_y = 0
        
        for measurement in measurements:
            # Convert dBm to linear scale for weighting (higher signal = more weight)
            # Use exponential weighting: stronger signals get much more influence
            signal_linear = pow(10, measurement['signal'] / 10)
            weight = signal_linear
            
            weighted_x += measurement['x'] * weight
            weighted_y += measurement['y'] * weight
            total_weight += weight
        
        if total_weight == 0:
            return None
            
        estimated_x = weighted_x / total_weight
        estimated_y = weighted_y / total_weight
        
        return {
            'bssid': strongest_measurement['ap_data'].bssid,
            'x': estimated_x,  # Estimated AP source location
            'y': estimated_y,
            'max_signal': strongest_measurement['signal'],
            'ssid': strongest_measurement['ap_data'].ssid,
            'channel': strongest_measurement['ap_data'].channel,
            'band': getattr(strongest_measurement['ap_data'], 'band', '2.4 GHz'),
            'placed_ap': None  # This is an estimated location, not a placed AP
        }

    def _create_signal_strength_grid(self, ap_locations):
        """
        Create a grid where each cell contains the strongest signal at that location.
        
        Args:
            ap_locations: List of AP location data
            
        Returns:
            2D numpy array with signal strength values (strongest signal wins)
        """
        # Use a reasonable grid resolution for smooth gradients
        grid_resolution = 4  # pixels per grid cell
        grid_width = self.width // grid_resolution
        grid_height = self.height // grid_resolution
        
        # Initialize with very weak signal
        signal_grid = np.full((grid_height, grid_width), -999.0)
        
        # For each grid cell, calculate signal from all APs and take the strongest
        for row in range(grid_height):
            for col in range(grid_width):
                # Convert grid coordinates to pixel coordinates (center of cell)
                pixel_x = col * grid_resolution + grid_resolution // 2
                pixel_y = row * grid_resolution + grid_resolution // 2
                
                strongest_signal = -999
                
                # Check signal strength from each AP at this location
                for ap_location in ap_locations:
                    signal = self._calculate_signal_at_point(
                        ap_location, pixel_x, pixel_y
                    )
                    if signal > strongest_signal:
                        strongest_signal = signal
                
                # Only store if signal is above minimum threshold
                if strongest_signal > -95:
                    signal_grid[row, col] = strongest_signal
                else:
                    signal_grid[row, col] = np.nan  # No signal
        
        return signal_grid
    
    def _calculate_signal_at_point(self, ap_location, x, y):
        """
        Calculate signal strength from an AP at a specific point.
        
        Args:
            ap_location: AP location data
            x, y: Point coordinates
            
        Returns:
            Signal strength in dBm
        """
        ap_x = ap_location['x']
        ap_y = ap_location['y']
        max_signal = ap_location['max_signal']
        
        # Calculate distance in pixels
        distance_pixels = ((x - ap_x) ** 2 + (y - ap_y) ** 2) ** 0.5
        
        # Convert to feet
        distance_feet = distance_pixels * (164.0 / self.width)
        
        # Apply path loss model
        band = ap_location.get('band', '2.4 GHz')
        path_loss_per_foot = 0.5 if band == '2.4 GHz' else 0.6
        
        signal_loss = distance_feet * path_loss_per_foot
        signal_at_point = max_signal - signal_loss
        
        return signal_at_point
    
    def _draw_signal_grid(self, painter, signal_grid):
        """
        Draw the signal strength grid as colored rectangles.
        
        Args:
            painter: QPainter object
            signal_grid: 2D numpy array with signal values
        """
        grid_resolution = 4
        rows, cols = signal_grid.shape
        
        for row in range(rows):
            for col in range(cols):
                signal_strength = signal_grid[row, col]
                
                # Skip cells with no signal
                if np.isnan(signal_strength):
                    continue
                
                # Get color for this signal strength
                color = self._signal_to_color_gradient(signal_strength)
                color.setAlpha(150)  # Semi-transparent for blending
                
                # Calculate pixel position
                x = col * grid_resolution
                y = row * grid_resolution
                
                # Draw filled rectangle
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(x, y, grid_resolution, grid_resolution)

    def _draw_ap_coverage_circles(self, painter: QPainter, ap_location: dict):
        """
        Draw gradient coverage circles around an AP with smooth color transitions.
        
        Args:
            painter: QPainter object to draw with
            ap_location: AP location data with coordinates and signal info
        """
        ap_x = ap_location['x']
        ap_y = ap_location['y']
        max_signal = ap_location['max_signal']
        
        # Calculate maximum radius (where signal drops to -90 dBm)
        band = ap_location.get('band', '2.4 GHz')
        path_loss_per_foot = 0.5 if band == '2.4 GHz' else 0.6
        
        max_signal_drop = max_signal - (-90)  # Drop to -90 dBm
        max_distance_feet = abs(max_signal_drop) / path_loss_per_foot
        max_radius_pixels = max_distance_feet * (self.width / 164.0)
        
        # Don't draw if radius is too large
        if max_radius_pixels > max(self.width, self.height):
            max_radius_pixels = max(self.width, self.height)
        
        # Draw concentric circles with gradient from center outward
        # Use many small rings to create smooth gradient effect
        num_rings = int(max_radius_pixels / 5)  # Ring every 5 pixels
        
        for ring in range(num_rings, 0, -1):  # Draw from outside to inside
            radius_pixels = (ring / num_rings) * max_radius_pixels
            
            # Calculate signal strength at this distance
            distance_feet = radius_pixels * (164.0 / self.width)
            signal_loss = distance_feet * path_loss_per_foot
            signal_at_distance = max_signal - signal_loss
            
            # Clamp signal to reasonable range
            signal_at_distance = max(-95, min(-20, signal_at_distance))
            
            # Get color for this signal strength with gradient interpolation
            color = self._signal_to_color_gradient(signal_at_distance)
            
            # Make rings more transparent toward edges for smooth blending
            base_alpha = 120  # Base transparency
            edge_factor = 1.0 - (ring / num_rings)  # 0 at edge, 1 at center
            alpha = int(base_alpha * (0.3 + 0.7 * edge_factor))  # 30% to 100% of base
            color.setAlpha(alpha)
            
            # Draw ring (filled circle)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                int(ap_x - radius_pixels),
                int(ap_y - radius_pixels),
                int(radius_pixels * 2),
                int(radius_pixels * 2)
            )

    def _is_primary_network_bssid(self, bssid: str, target_network: str) -> bool:
        """
        Check if a BSSID belongs to a primary network family based on patterns.
        
        This method can be extended to support BSSID-based network identification
        for cases where SSIDs may be obfuscated but BSSID patterns are known.
        
        Args:
            bssid: The BSSID to check
            target_network: Target network SSID
            
        Returns:
            True if BSSID matches the primary network pattern
        """
        # Currently returns False - can be extended for specific deployment needs
        # without hardcoding sensitive network information in source code
        return False

    def _signal_to_color(self, signal_strength: float) -> QColor:
        """
        Map signal strength to color based on defined ranges.

        Args:
            signal_strength: Signal strength in dBm

        Returns:
            QColor for the given signal strength
        """
        for min_signal, max_signal, color in self.SIGNAL_RANGES:
            if max_signal <= signal_strength <= min_signal:
                return color

        # Default to blue for very weak signals
        return self.SIGNAL_RANGES[-1][2]  # Blue

    def _signal_to_color_gradient(self, signal_strength: float) -> QColor:
        """
        Map signal strength to color with smooth gradient interpolation.
        
        Args:
            signal_strength: Signal strength in dBm
            
        Returns:
            QColor with interpolated color based on signal strength
        """
        # Define color points for smooth interpolation
        # Format: (signal_dBm, red, green, blue)
        color_points = [
            (-20, 0, 255, 0),     # Bright green (excellent)
            (-45, 255, 255, 0),   # Yellow (good)
            (-60, 255, 165, 0),   # Orange (fair)
            (-75, 255, 0, 0),     # Red (poor)
            (-90, 0, 0, 255),     # Blue (very poor)
        ]
        
        # Clamp signal to our range
        signal_strength = max(-95, min(-15, signal_strength))
        
        # Find the two color points to interpolate between
        for i in range(len(color_points) - 1):
            signal1, r1, g1, b1 = color_points[i]
            signal2, r2, g2, b2 = color_points[i + 1]
            
            if signal1 >= signal_strength >= signal2:
                # Linear interpolation between the two points
                if signal1 == signal2:
                    factor = 0
                else:
                    factor = (signal_strength - signal2) / (signal1 - signal2)
                
                r = int(r2 + factor * (r1 - r2))
                g = int(g2 + factor * (g1 - g2))
                b = int(b2 + factor * (b1 - b2))
                
                return QColor(r, g, b)
        
        # Fallback to blue for very weak signals
        return QColor(0, 0, 255)

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
