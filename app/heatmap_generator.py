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

        # Find all APs for the target network from scan data
        ap_locations = self._identify_ap_locations(scan_points, target_network, floor)

        if not ap_locations:
            return self._create_empty_heatmap()

        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.transparent)

        # Create signal strength grid to determine strongest signal at each point
        if status_callback:
            status_callback(10, target_network)

        signal_grid = self._create_signal_strength_grid(ap_locations, target_network, status_callback)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw the signal strength grid as colored pixels
        self._draw_signal_grid(painter, signal_grid)

        if status_callback:
            status_callback(100, target_network)

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

    def _create_signal_strength_grid(self, ap_locations, target_network=None, progress_callback=None):
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

        # Calculate progress increment for each row
        pct = 20
        pct_increment = 80 / grid_height

        # For each grid cell, calculate signal from all APs and take the strongest
        for row in range(grid_height):
            # Report progress for each row processed
            if progress_callback:
                progress_callback(int(pct), target_network)
                pct += pct_increment

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

    def generate_interference_heatmap(self, scan_points: List[ScanPoint],
                                    target_prefixes: List[str] = None,
                                    floor: Optional[Floor] = None,
                                    status_callback=None) -> QPixmap:
        """
        Generate an interference heatmap showing interference hot spots.

        Args:
            scan_points: List of scan points containing AP data
            target_prefixes: List of target network prefixes (e.g., ['LITS'])
            floor: Floor object for coordinate scaling (optional)
            status_callback: Progress callback function

        Returns:
            QPixmap containing the rendered interference heatmap overlay
        """
        if not scan_points:
            return self._create_empty_heatmap()

        # Import here to avoid circular imports
        from .interference_analyzer import InterferenceAnalyzer

        # Create analyzer and use device grouping
        analyzer = InterferenceAnalyzer(target_prefixes)

        # Extract interference data for each scan point
        interference_data = self._extract_interference_data(scan_points, analyzer, target_prefixes)

        if not interference_data:
            return self._create_empty_heatmap()

        return self._create_interference_based_heatmap(interference_data, status_callback)

    def _extract_interference_data(self, scan_points: List[ScanPoint],
                                 analyzer, target_prefixes: List[str]) -> List[Tuple[float, float, float]]:
        """
        Triangulate interference sources and calculate interference propagation coverage.

        Returns:
            List of (x, y, interference_level) tuples representing interference coverage
        """
        # Step 1: Identify interfering devices and triangulate their locations
        interfering_sources = self._triangulate_interfering_sources(scan_points, analyzer, target_prefixes)

        if not interfering_sources:
            return []

        # Step 2: Generate interference coverage grid
        interference_coverage = self._calculate_interference_coverage(interfering_sources)

        return interference_coverage

    def _triangulate_interfering_sources(self, scan_points: List[ScanPoint], analyzer, target_prefixes: List[str]):
        """
        Triangulate the estimated locations of interfering devices.

        Returns:
            List of interfering source locations with estimated coordinates and power
        """
        # Collect all measurements for each interfering device
        device_measurements = {}  # device_id -> [(x, y, rssi, ssid)]

        # Identify target device IDs first
        target_device_ids = set()
        for scan_point in scan_points:
            device_groups = analyzer._group_networks_by_device(scan_point.ap_list)
            for device_id, device_networks in device_groups.items():
                for network in device_networks:
                    if target_prefixes and any(network.ssid.startswith(prefix) for prefix in target_prefixes):
                        target_device_ids.add(device_id)
                        break

        # Collect measurements for interfering devices
        for scan_point in scan_points:
            device_groups = analyzer._group_networks_by_device(scan_point.ap_list)

            for device_id, device_networks in device_groups.items():
                # Skip target devices
                if device_id in target_device_ids:
                    continue

                # Find strongest signal from this device at this scan point
                strongest_network = None
                for network in device_networks:
                    if (network.ssid != "{Hidden}" and
                        network.signal_strength > analyzer.interference_threshold):
                        if strongest_network is None or network.signal_strength > strongest_network.signal_strength:
                            strongest_network = network

                if strongest_network:
                    if device_id not in device_measurements:
                        device_measurements[device_id] = []

                    device_measurements[device_id].append((
                        scan_point.map_x,
                        scan_point.map_y,
                        strongest_network.signal_strength,
                        strongest_network.ssid
                    ))

        # Triangulate source location for each interfering device
        interfering_sources = []
        for device_id, measurements in device_measurements.items():
            # Only triangulate if we have enough measurements for reliable positioning
            if len(measurements) >= 3:  # Need at least 3 points for real triangulation
                source_location = self._estimate_interference_source_location(measurements)
                if source_location:
                    interfering_sources.append(source_location)
            # Skip single/dual measurements - not enough data for reliable external positioning
            # Single measurements could be anywhere, dual measurements lack directional certainty

        return interfering_sources

    def _estimate_interference_source_location(self, measurements):
        """
        Estimate source location using signal strength triangulation with physical propagation analysis.

        Args:
            measurements: List of (x, y, rssi, ssid) tuples

        Returns:
            Dict with estimated source location and properties
        """
        if len(measurements) < 3:
            return None

        import numpy as np

        # Sort measurements by signal strength
        sorted_measurements = sorted(measurements, key=lambda m: m[2], reverse=True)
        max_rssi = sorted_measurements[0][2]
        ssid = measurements[0][3]  # Use SSID from first measurement

        # Analyze signal gradient to determine probable source direction
        # Filter out potential NLOS anomalies by looking at signal patterns
        valid_measurements = self._filter_nlos_measurements(measurements)

        if len(valid_measurements) < 3:
            # Fall back to all measurements if filtering removes too many
            valid_measurements = measurements

        # Determine source location based on signal gradient analysis
        source_direction = self._analyze_signal_gradient(valid_measurements)

        # Use proper triangulation to find EXTERNAL source location
        # The key insight: interference sources are OUTSIDE the measurement area
        estimated_x, estimated_y = self._triangulate_external_source(valid_measurements, source_direction)

        # Estimate transmit power based on strongest received signal and distance
        closest_measurement = max(measurements, key=lambda m: m[2])
        distance_to_closest = ((estimated_x - closest_measurement[0])**2 + (estimated_y - closest_measurement[1])**2)**0.5

        # Indoor path loss model accounting for physical obstructions
        if distance_to_closest > 0:
            estimated_path_loss = 40 * np.log10(max(distance_to_closest / 100, 0.1)) + 40
            estimated_tx_power = closest_measurement[2] + estimated_path_loss
        else:
            estimated_tx_power = max_rssi + 30

        return {
            'x': estimated_x,
            'y': estimated_y,
            'tx_power': min(estimated_tx_power, 30),
            'ssid': ssid,
            'measurement_count': len(measurements),
            'max_rssi': max_rssi
        }

    def _filter_nlos_measurements(self, measurements):
        """
        Filter out potential NLOS measurements that might be anomalous due to reflections.

        Returns measurements that follow expected propagation patterns.
        """
        if len(measurements) < 5:
            return measurements  # Too few points to filter reliably

        import numpy as np

        # Calculate median signal strength
        signals = [rssi for _, _, rssi, _ in measurements]
        median_signal = np.median(signals)

        # Filter out measurements that are significantly stronger than expected
        # based on their position relative to the signal gradient
        filtered = []
        for measurement in measurements:
            x, y, rssi, ssid = measurement

            # Allow measurements within reasonable range of median
            # or weaker measurements (which are more likely to be legitimate)
            if rssi <= median_signal + 15:  # Allow up to 15dB above median
                filtered.append(measurement)
            elif rssi > median_signal + 15:
                # For very strong signals, only keep if they fit the pattern
                # This helps exclude window reflections and other NLOS effects
                if self._fits_propagation_pattern(measurement, measurements):
                    filtered.append(measurement)

        return filtered if len(filtered) >= 3 else measurements

    def _fits_propagation_pattern(self, test_measurement, all_measurements):
        """
        Check if a measurement fits expected RF propagation patterns.
        """
        x, y, rssi, _ = test_measurement

        # Look for nearby measurements to validate the signal strength
        nearby_measurements = []
        for mx, my, mrssi, _ in all_measurements:
            distance = ((x - mx)**2 + (y - my)**2)**0.5
            if 50 <= distance <= 200:  # Look at measurements 50-200 pixels away
                nearby_measurements.append((distance, mrssi))

        if not nearby_measurements:
            return True  # Can't validate, so allow it

        # Check if signal strength follows expected distance relationship
        for distance, nearby_rssi in nearby_measurements:
            # Expect signal to decrease with distance (basic sanity check)
            expected_loss = 20 * np.log10(distance / 50)  # Rough estimate
            if rssi > nearby_rssi + expected_loss + 10:  # Allow 10dB tolerance
                return False  # This measurement seems too strong for its position

        return True

    def _analyze_signal_gradient(self, measurements):
        """
        Analyze signal strength gradient to determine likely source direction.

        Returns direction vector (dx, dy) pointing toward probable source location.
        """
        import numpy as np

        if len(measurements) < 4:
            return None

        # Calculate centroid of measurements
        center_x = np.mean([x for x, _, _, _ in measurements])
        center_y = np.mean([y for _, y, _, _ in measurements])

        # Analyze signal strength vs position to find gradient
        # Look for patterns like "stronger signals in the north" or "stronger signals to the east"

        # Split measurements into regions and compare average signal strengths
        north_signals = [rssi for x, y, rssi, _ in measurements if y < center_y]
        south_signals = [rssi for x, y, rssi, _ in measurements if y > center_y]
        east_signals = [rssi for x, y, rssi, _ in measurements if x > center_x]
        west_signals = [rssi for x, y, rssi, _ in measurements if x < center_x]

        # Calculate average signals for each direction
        avg_north = np.mean(north_signals) if north_signals else -100
        avg_south = np.mean(south_signals) if south_signals else -100
        avg_east = np.mean(east_signals) if east_signals else -100
        avg_west = np.mean(west_signals) if west_signals else -100

        # Determine direction with strongest signals
        dx = 0
        dy = 0

        # Y-axis gradient (north/south)
        if abs(avg_north - avg_south) > 5:  # Significant difference
            if avg_north > avg_south:
                dy = -1  # Source is north (negative Y)
            else:
                dy = 1   # Source is south (positive Y)

        # X-axis gradient (east/west)
        if abs(avg_east - avg_west) > 5:  # Significant difference
            if avg_east > avg_west:
                dx = 1   # Source is east (positive X)
            else:
                dx = -1  # Source is west (negative X)

        return (dx, dy) if (dx != 0 or dy != 0) else None

    def _triangulate_external_source(self, measurements, direction):
        """
        Triangulate interference source location OUTSIDE the measurement area.

        This is the key fix: interference sources are external APs, not at scan points.
        """
        import numpy as np

        if len(measurements) < 3:
            return None, None

        # Find the boundary of measurement area
        all_x = [x for x, _, _, _ in measurements]
        all_y = [y for _, y, _, _ in measurements]

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        # Find measurements with strongest signals - these are closest to the source
        sorted_measurements = sorted(measurements, key=lambda m: m[2], reverse=True)

        # Use the top 3 strongest measurements for triangulation
        top_measurements = sorted_measurements[:3]

        # Calculate weighted centroid of strongest measurements
        total_weight = 0
        weighted_x = 0
        weighted_y = 0

        for x, y, rssi, _ in top_measurements:
            # Strong exponential weighting - strongest signals dominate
            weight = pow(10, (rssi + 100) / 20)  # Convert dBm to linear-ish scale
            weighted_x += x * weight
            weighted_y += y * weight
            total_weight += weight

        if total_weight == 0:
            return None, None

        centroid_x = weighted_x / total_weight
        centroid_y = weighted_y / total_weight

        # Determine which edge the source is closest to based on signal pattern
        # The source should be OUTSIDE the measurement area

        if direction:
            dx, dy = direction
        else:
            # Fallback: use strongest measurement to estimate direction
            strongest_x, strongest_y = top_measurements[0][0], top_measurements[0][1]

            # Determine which boundary the strongest signal is closest to
            to_left = strongest_x - min_x
            to_right = max_x - strongest_x
            to_top = strongest_y - min_y
            to_bottom = max_y - strongest_y

            min_distance = min(to_left, to_right, to_top, to_bottom)

            if min_distance == to_left:
                dx, dy = -1, 0  # Source is to the left (west)
            elif min_distance == to_right:
                dx, dy = 1, 0   # Source is to the right (east)
            elif min_distance == to_top:
                dx, dy = 0, -1  # Source is to the top (north)
            else:
                dx, dy = 0, 1   # Source is to the bottom (south)

        # Calculate distance to place source outside measurement area
        # Stronger signals = source is closer to boundary
        strongest_rssi = top_measurements[0][2]

        if strongest_rssi > -40:
            # Very strong signal - source is just outside boundary
            offset_distance = 80
        elif strongest_rssi > -50:
            # Strong signal - source is moderately outside
            offset_distance = 150
        elif strongest_rssi > -60:
            # Medium signal - source is further out
            offset_distance = 250
        else:
            # Weak signal - source is quite far
            offset_distance = 400

        # Place source outside the measurement area
        if dx < 0:  # West
            estimated_x = min_x - offset_distance
            estimated_y = centroid_y
        elif dx > 0:  # East
            estimated_x = max_x + offset_distance
            estimated_y = centroid_y
        elif dy < 0:  # North
            estimated_x = centroid_x
            estimated_y = min_y - offset_distance
        else:  # South
            estimated_x = centroid_x
            estimated_y = max_y + offset_distance

        return estimated_x, estimated_y

    def _estimate_edge_interference_source(self, measurement):
        """
        Estimate source location for single measurement point (edge case).

        Assumes we're near the edge of the interfering device's range,
        so the source is likely nearby in the direction of strongest propagation.

        Args:
            measurement: Single (x, y, rssi, ssid) tuple

        Returns:
            Dict with estimated source location and properties
        """
        x, y, rssi, ssid = measurement

        # For single measurement, assume we're detecting at edge of coverage
        # Estimate distance based on signal strength
        # Using typical indoor path loss: stronger signal = closer source

        if rssi > -50:  # Very strong signal - source is very close
            estimated_distance = 20  # pixels
        elif rssi > -60:  # Strong signal - source is close
            estimated_distance = 50  # pixels
        elif rssi > -70:  # Moderate signal - source is medium distance
            estimated_distance = 100  # pixels
        else:  # Weak signal - source is farther away
            estimated_distance = 150  # pixels

        # Place source slightly offset from measurement point
        # Use a random direction to avoid clustering
        import random
        import math

        angle = random.uniform(0, 2 * math.pi)
        source_x = x + estimated_distance * math.cos(angle)
        source_y = y + estimated_distance * math.sin(angle)

        # Estimate transmit power based on distance and received signal
        estimated_path_loss = 40 * math.log10(max(estimated_distance / 100, 0.1)) + 40
        estimated_tx_power = rssi + estimated_path_loss

        return {
            'x': source_x,
            'y': source_y,
            'tx_power': min(max(estimated_tx_power, 10), 30),  # Reasonable range 10-30 dBm
            'ssid': ssid,
            'measurement_count': 1,
            'max_rssi': rssi,
            'estimation_type': 'edge_detection'
        }

    def _estimate_dual_point_interference_source(self, measurements):
        """
        Estimate source location from two measurement points.

        Uses signal strength gradient to estimate source direction.

        Args:
            measurements: List of 2 (x, y, rssi, ssid) tuples

        Returns:
            Dict with estimated source location and properties
        """
        if len(measurements) != 2:
            return None

        (x1, y1, rssi1, ssid1), (x2, y2, rssi2, ssid2) = measurements
        ssid = ssid1  # Use SSID from first measurement

        # Determine which point has stronger signal (closer to source)
        if rssi1 > rssi2:
            stronger_x, stronger_y, stronger_rssi = x1, y1, rssi1
            weaker_x, weaker_y, weaker_rssi = x2, y2, rssi2
        else:
            stronger_x, stronger_y, stronger_rssi = x2, y2, rssi2
            weaker_x, weaker_y, weaker_rssi = x1, y1, rssi1

        # Calculate signal strength gradient
        signal_diff = stronger_rssi - weaker_rssi
        distance_between = ((stronger_x - weaker_x)**2 + (stronger_y - weaker_y)**2)**0.5

        if distance_between == 0:
            # Points are the same - treat as single point
            return self._estimate_edge_interference_source((stronger_x, stronger_y, stronger_rssi, ssid))

        # Estimate source location along the line extending from weaker to stronger point
        # The stronger the gradient, the closer the source is to the stronger point
        if signal_diff > 10:  # Strong gradient - source is close to stronger point
            extrapolation_factor = 0.3
        elif signal_diff > 5:  # Medium gradient
            extrapolation_factor = 0.5
        else:  # Weak gradient - source might be farther
            extrapolation_factor = 0.8

        # Calculate direction vector from weaker to stronger point
        dx = stronger_x - weaker_x
        dy = stronger_y - weaker_y

        # Extrapolate beyond the stronger point
        estimated_x = stronger_x + dx * extrapolation_factor
        estimated_y = stronger_y + dy * extrapolation_factor

        # Estimate transmit power
        import math
        distance_to_stronger = distance_between * extrapolation_factor
        estimated_path_loss = 40 * math.log10(max(distance_to_stronger / 100, 0.1)) + 40
        estimated_tx_power = stronger_rssi + estimated_path_loss

        return {
            'x': estimated_x,
            'y': estimated_y,
            'tx_power': min(max(estimated_tx_power, 10), 30),  # Reasonable range
            'ssid': ssid,
            'measurement_count': 2,
            'max_rssi': stronger_rssi,
            'estimation_type': 'dual_point_gradient'
        }

    def _calculate_interference_coverage(self, interfering_sources):
        """
        Calculate contiguous interference coverage from estimated source locations.

        Returns:
            List of interfering sources with coverage parameters for rendering
        """
        if not interfering_sources:
            return []

        # Return the sources with calculated coverage parameters
        # The rendering will create contiguous coverage areas
        coverage_sources = []

        for source in interfering_sources:
            # Calculate realistic interference radius based on transmit power and signal strength
            max_rssi = source.get('max_rssi', -70)
            tx_power = source.get('tx_power', 20)

            # Strong sources (high TX power or strong received signal) create larger interference zones
            if max_rssi > -45 or tx_power > 25:
                max_radius = 200  # Strong interference source
                falloff_rate = 0.7  # Slower falloff
            elif max_rssi > -55 or tx_power > 20:
                max_radius = 150  # Medium interference source
                falloff_rate = 0.8
            else:
                max_radius = 100  # Weaker interference source
                falloff_rate = 0.9  # Faster falloff

            coverage_sources.append({
                'x': source['x'],
                'y': source['y'],
                'max_radius': max_radius,
                'falloff_rate': falloff_rate,
                'tx_power': tx_power,
                'max_rssi': max_rssi,
                'ssid': source['ssid']
            })

        return coverage_sources

    def _create_interference_based_heatmap(self, coverage_sources: List[dict],
                                         status_callback=None) -> QPixmap:
        """
        Create interference heatmap with contiguous coverage areas from each source.
        """
        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        import math

        total_sources = len(coverage_sources)

        for source_idx, source in enumerate(coverage_sources):
            # Report progress
            if status_callback:
                progress = int((source_idx / total_sources) * 100)
                status_callback(progress, "interference")

            source_x = source['x']
            source_y = source['y']
            max_radius = source['max_radius']
            falloff_rate = source['falloff_rate']

            # Draw concentric circles with decreasing transparency (contiguous coverage)
            num_rings = 8  # Number of concentric rings for smooth coverage

            for ring in range(num_rings, 0, -1):  # Draw from outside to inside
                # Calculate ring radius and interference level
                radius = max_radius * (ring / num_rings)

                # Calculate interference level based on distance from source
                # Closer = higher interference
                distance_factor = 1.0 - (ring / num_rings)  # 0 at edge, 1 at center
                base_interference = 60 * distance_factor  # Max 60% interference at center

                # Apply falloff rate
                interference_level = base_interference * (falloff_rate ** (ring - 1))

                # Skip very weak interference to avoid cluttering
                if interference_level < 2:
                    continue

                # Get color for this interference level
                color = self._interference_level_to_color(interference_level)

                # Draw filled circle for this ring
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)

                # Use true source location - don't clamp external sources to map bounds
                circle_x = source_x
                circle_y = source_y

                # Draw circle from true location, but clip drawing to visible map area
                painter.drawEllipse(
                    int(circle_x - radius),
                    int(circle_y - radius),
                    int(radius * 2),
                    int(radius * 2)
                )

        painter.end()
        return pixmap

    def _interference_level_to_color(self, interference_level: float) -> QColor:
        """
        Map interference level (0-100) to transparent color.

        Color scheme for interference (all transparent):
        - Very Light Blue: 0-10 (Minimal interference)
        - Light Blue: 10-20 (Low interference)
        - Light Yellow: 20-40 (Moderate interference)
        - Light Orange: 40-60 (High interference)
        - Light Red: 60-80 (Very high interference)
        - Red: 80-100 (Extreme interference)
        """
        if interference_level <= 10:
            return QColor(173, 216, 230, 15)    # Very light blue, extremely transparent
        elif interference_level <= 20:
            return QColor(135, 206, 250, 25)    # Light sky blue, very transparent
        elif interference_level <= 40:
            return QColor(255, 255, 224, 35)    # Light yellow, very transparent
        elif interference_level <= 60:
            return QColor(255, 218, 185, 50)    # Light orange (peach), transparent
        elif interference_level <= 80:
            return QColor(255, 182, 193, 70)    # Light pink, transparent
        else:
            return QColor(255, 99, 71, 90)      # Tomato red, still transparent
