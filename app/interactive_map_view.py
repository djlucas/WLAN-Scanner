#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/interactive_map_view.py
#
# Description:
# Interactive map view widget that displays floor plans and allows users to
# place Access Points by clicking on the map. Shows AP markers and handles
# drag operations for repositioning.
# -----------------------------------------------------------------------------

import datetime
import random
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QInputDialog, QMenu, QAction
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QFont, QMouseEvent
from .data_models import PlacedAP, ScanPoint
from .scan_simulator import ScanSimulator
from .heatmap_generator import HeatmapGenerator

class InteractiveMapView(QWidget):
    """
    Interactive map view widget for displaying floor plans and placing APs
    """
    
    # Signals
    ap_placed = pyqtSignal(object)  # Emitted when an AP is placed
    scan_point_added = pyqtSignal(object)  # Emitted when a scan point is added
    
    def __init__(self, i18n_manager, debug_mode=False, parent=None):
        """
        Initialize the interactive map view
        
        Args:
            i18n_manager: Internationalization manager
            debug_mode (bool): Enable debug output
            parent: Parent widget
        """
        super().__init__(parent)
        self.i18n = i18n_manager
        self.debug_mode = debug_mode
        
        # Map data
        self.current_floor = None
        self.base_pixmap = None  # Original floor plan image
        self.display_pixmap = None  # Rendered image with APs
        
        # Heatmap functionality
        self.heatmap_generator = HeatmapGenerator()
        self.heatmap_enabled = False
        self.current_heatmap_network = None  # None means strongest signal
        self.heatmap_pixmap = None
        
        # UI state
        self.placement_mode = "ap"  # "ap" or "scan_point"
        self.dragging_ap = None
        self.drag_offset = QPoint(0, 0)
        self.right_click_position = QPoint(0, 0)  # Store right-click position for context menu
        
        # Simulator for testing
        self.simulator = ScanSimulator(seed=42)  # Fixed seed for consistent results
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Main map display label
        self.map_label = QLabel()
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setStyleSheet("QLabel { border: 1px solid #ccc; background-color: #f0f0f0; }")
        self.map_label.setMinimumSize(800, 600)
        self.map_label.mousePressEvent = self._map_mouse_press
        self.map_label.mouseMoveEvent = self._map_mouse_move
        self.map_label.mouseReleaseEvent = self._map_mouse_release
        
        layout.addWidget(self.map_label)
        
        # Status label
        self.status_label = QLabel("🔵 Blue APs = Scanned • 🟠 Orange APs = Need scanning • Right-click to place/scan • Drag APs to move")
        self.status_label.setStyleSheet("QLabel { padding: 5px; background-color: #e8f4f8; }")
        layout.addWidget(self.status_label)
        
    def set_floor(self, floor):
        """
        Set the current floor to display
        
        Args:
            floor (Floor): Floor object to display
        """
        self.current_floor = floor
        self._load_floor_image()
        
        # Update simulator with actual placed APs
        if floor and hasattr(floor, 'placed_aps') and floor.placed_aps:
            self.simulator = ScanSimulator(
                seed=42, 
                floor_width=self.width(), 
                floor_height=self.height(),
                placed_aps=floor.placed_aps
            )
        else:
            # Fallback to simulated APs if no placed APs
            self.simulator = ScanSimulator(seed=42)
            
        self._render_map()
    
    def _refresh_simulator(self):
        """Refresh the simulator with current placed APs"""
        if self.current_floor and hasattr(self.current_floor, 'placed_aps') and self.current_floor.placed_aps:
            self.simulator = ScanSimulator(
                seed=42,
                floor_width=self.width() if self.width() > 0 else 1920,
                floor_height=self.height() if self.height() > 0 else 1080,
                placed_aps=self.current_floor.placed_aps
            )
        else:
            self.simulator = ScanSimulator(seed=42)
        
    def _load_floor_image(self):
        """Load the floor plan image"""
        if not self.current_floor or not self.current_floor.scaled_image_path:
            self.base_pixmap = None
            self.map_label.setText("No floor plan loaded")
            return
            
        self.base_pixmap = QPixmap(self.current_floor.scaled_image_path)
        if self.base_pixmap.isNull():
            self.base_pixmap = None
            self.map_label.setText(f"Error loading floor plan: {self.current_floor.scaled_image_path}")
            if self.debug_mode:
                print(f"DEBUG: Failed to load image: {self.current_floor.scaled_image_path}")
        else:
            if self.debug_mode:
                print(f"DEBUG: Loaded floor plan: {self.current_floor.scaled_image_path}")
    
    def _render_map(self):
        """Render the map with placed APs and scan points"""
        if not self.base_pixmap:
            return
            
        # Create a copy of the base image to draw on
        self.display_pixmap = self.base_pixmap.copy()
        painter = QPainter(self.display_pixmap)
        
        # Draw heatmap overlay if enabled
        if self.heatmap_enabled:
            self._draw_heatmap_overlay(painter)
        
        # Draw placed APs
        self._draw_placed_aps(painter)
        
        # Draw scan points
        self._draw_scan_points(painter)
        
        painter.end()
        
        # Scale to fit the label
        scaled_pixmap = self.display_pixmap.scaled(
            self.map_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.map_label.setPixmap(scaled_pixmap)
        self.map_label.setText("")  # Clear any text
        
    def _draw_placed_aps(self, painter):
        """Draw AP markers on the map"""
        if not self.current_floor or not self.current_floor.placed_aps:
            return
            
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        
        for ap in self.current_floor.placed_aps:
            x, y = int(ap.map_x), int(ap.map_y)
            
            # Choose colors based on whether AP has scan data
            if self._has_scan_data(ap):
                # AP with scan data - solid blue
                pen_color = QColor(0, 100, 200)
                brush_color = QColor(100, 150, 255, 180)
            else:
                # AP without scan data - orange/yellow to indicate needs scanning
                pen_color = QColor(200, 100, 0)
                brush_color = QColor(255, 180, 100, 180)
            
            # Draw AP marker (circle with antenna symbol)
            painter.setPen(QPen(pen_color, 2))
            painter.setBrush(QBrush(brush_color))
            painter.drawEllipse(x - 12, y - 12, 24, 24)
            
            # Draw antenna lines
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(x - 8, y - 8, x + 8, y + 8)
            painter.drawLine(x - 8, y + 8, x + 8, y - 8)
            
            # Draw AP name
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawText(x - 30, y + 25, 60, 15, Qt.AlignCenter, ap.name)
            
    def _draw_scan_points(self, painter):
        """Draw scan point markers on the map"""
        if not self.current_floor or not self.current_floor.scan_points:
            return
            
        for scan_point in self.current_floor.scan_points:
            x, y = int(scan_point.map_x), int(scan_point.map_y)
            
            # Draw scan point marker (small green circle)
            painter.setPen(QPen(QColor(0, 150, 0), 2))
            painter.setBrush(QBrush(QColor(0, 200, 0, 150)))
            painter.drawEllipse(x - 6, y - 6, 12, 12)
            
            # Draw number of detected APs
            ap_count = len(scan_point.ap_list)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawText(x - 10, y + 20, 20, 10, Qt.AlignCenter, str(ap_count))
    
    def _draw_heatmap_overlay(self, painter):
        """Draw heatmap overlay on the map"""
        if not self.current_floor or not self.current_floor.scan_points:
            return
            
        # Generate or update heatmap
        self._update_heatmap()
        
        if self.heatmap_pixmap and not self.heatmap_pixmap.isNull():
            # Draw the heatmap overlay
            painter.setOpacity(0.6)  # Semi-transparent overlay
            painter.drawPixmap(0, 0, self.heatmap_pixmap)
            painter.setOpacity(1.0)  # Reset opacity
    
    def _update_heatmap(self):
        """Update the heatmap based on current scan data"""
        if not self.current_floor or not self.current_floor.scan_points:
            self.heatmap_pixmap = None
            return
            
        # Set heatmap dimensions to match floor plan
        if self.base_pixmap:
            width, height = self.base_pixmap.width(), self.base_pixmap.height()
            self.heatmap_generator.width = width
            self.heatmap_generator.height = height
        
        # Generate heatmap
        self.heatmap_pixmap = self.heatmap_generator.generate_heatmap(
            self.current_floor.scan_points,
            target_network=self.current_heatmap_network,
            floor=self.current_floor
        )
        
        if self.debug_mode:
            networks = self.heatmap_generator.get_connected_networks(self.current_floor.scan_points)
            print(f"DEBUG: Heatmap updated. Connected networks: {networks}")
    
    def set_heatmap_enabled(self, enabled: bool):
        """Enable or disable heatmap display"""
        if self.heatmap_enabled != enabled:
            self.heatmap_enabled = enabled
            if self.heatmap_enabled:
                self._update_heatmap()
            self._render_map()
            
            if self.debug_mode:
                print(f"DEBUG: Heatmap {'enabled' if enabled else 'disabled'}")
    
    def set_heatmap_network(self, network_ssid: str = None):
        """Set the target network for heatmap display"""
        if self.current_heatmap_network != network_ssid:
            self.current_heatmap_network = network_ssid
            if self.heatmap_enabled:
                self._update_heatmap()
                self._render_map()
                
            if self.debug_mode:
                network_name = network_ssid if network_ssid else "Strongest Signal"
                print(f"DEBUG: Heatmap network set to: {network_name}")
    
    def get_available_networks(self):
        """Get list of networks available for heatmap display"""
        if not self.current_floor or not self.current_floor.scan_points:
            return []
            
        return self.heatmap_generator.get_connected_networks(self.current_floor.scan_points)
    
    def _map_mouse_press(self, event):
        """Handle mouse press events on the map"""
        if not self.base_pixmap:
            return
            
        # Convert label coordinates to image coordinates
        map_pos = self._label_to_map_coords(event.pos())
        if not map_pos:
            return
            
        x, y = map_pos.x(), map_pos.y()
        
        if event.button() == Qt.RightButton:
            # Handle right-click - show context menu
            self.right_click_position = QPoint(x, y)
            self._show_context_menu(event.globalPos())
            return
        elif event.button() == Qt.LeftButton:
            if self.debug_mode:
                print(f"DEBUG: Left mouse click at map coords ({x}, {y})")
            
            # Check if clicking on an existing AP for dragging
            clicked_ap = self._get_ap_at_position(x, y)
            if clicked_ap:
                self.dragging_ap = clicked_ap
                self.drag_offset = QPoint(x - int(clicked_ap.map_x), y - int(clicked_ap.map_y))
                return
            
            # Left-click on empty space does nothing - use right-click for placement
    
    def _map_mouse_move(self, event):
        """Handle mouse move events (for dragging)"""
        if not self.dragging_ap or not self.base_pixmap:
            return
            
        map_pos = self._label_to_map_coords(event.pos())
        if not map_pos:
            return
            
        # Update AP position
        self.dragging_ap.map_x = map_pos.x() - self.drag_offset.x()
        self.dragging_ap.map_y = map_pos.y() - self.drag_offset.y()
        
        # Re-render the map
        self._render_map()
    
    def _map_mouse_release(self, event):
        """Handle mouse release events"""
        if self.dragging_ap:
            # Refresh simulator after AP position change
            self._refresh_simulator()
            
            if self.debug_mode:
                print(f"DEBUG: AP '{self.dragging_ap.name}' moved to ({self.dragging_ap.map_x}, {self.dragging_ap.map_y})")
        
        self.dragging_ap = None
        self.drag_offset = QPoint(0, 0)
    
    def _show_context_menu(self, global_pos):
        """
        Show context menu for right-click on map
        
        Args:
            global_pos (QPoint): Global position for menu display
        """
        if not self.current_floor:
            return
            
        context_menu = QMenu(self)
        
        # Check if right-clicking on an existing AP
        clicked_ap = self._get_ap_at_position(self.right_click_position.x(), self.right_click_position.y())
        
        if clicked_ap:
            # Menu options for existing AP
            context_menu.addAction("Edit AP Properties", lambda: self._edit_ap_properties(clicked_ap))
            
            # Smart scan options based on whether AP has scan data
            if self._has_scan_data(clicked_ap):
                context_menu.addAction("Rescan at This AP", lambda: self._scan_at_ap(clicked_ap))
                context_menu.addAction("Clear This AP's Scan Data", lambda: self._clear_ap_scan_data(clicked_ap))
            else:
                context_menu.addAction("Scan at This AP", lambda: self._scan_at_ap(clicked_ap))
            
            context_menu.addAction("Remove AP", lambda: self._remove_ap(clicked_ap))
            context_menu.addSeparator()
        
        # General placement options
        place_ap_action = QAction("Place Access Point Here", self)
        place_ap_action.triggered.connect(lambda: self._place_ap_at_position(
            self.right_click_position.x(), 
            self.right_click_position.y()
        ))
        context_menu.addAction(place_ap_action)
        
        scan_here_action = QAction("Run Scan Here (Simulated)", self)
        scan_here_action.triggered.connect(lambda: self._add_scan_point_at_position(
            self.right_click_position.x(), 
            self.right_click_position.y()
        ))
        context_menu.addAction(scan_here_action)
        
        context_menu.addSeparator()
        
        # Bulk scan operations
        if self.current_floor.placed_aps:
            context_menu.addSeparator()
            context_menu.addAction("Scan at All AP Locations", self._scan_at_all_aps)
            context_menu.addAction("Clear All AP Scan Data", self._clear_all_ap_scan_data)
        
        # View options
        context_menu.addSeparator()
        if self.current_floor.placed_aps:
            context_menu.addAction("Clear All APs", self.clear_all_aps)
        
        if self.current_floor.scan_points:
            context_menu.addAction("Clear All Scan Points", self.clear_all_scan_points)
        
        # Show the context menu
        context_menu.exec_(global_pos)
        
        if self.debug_mode:
            print(f"DEBUG: Context menu shown at map coords ({self.right_click_position.x()}, {self.right_click_position.y()})")
    
    def _edit_ap_properties(self, ap):
        """
        Edit properties of an existing AP
        
        Args:
            ap (PlacedAP): The AP to edit
        """
        new_name, ok = QInputDialog.getText(
            self, 
            "Edit Access Point",
            f"Edit name for AP at ({int(ap.map_x)}, {int(ap.map_y)}):",
            text=ap.name
        )
        
        if ok and new_name.strip():
            old_name = ap.name
            ap.name = new_name.strip()
            self._render_map()
            self.status_label.setText(f"AP renamed from '{old_name}' to '{ap.name}'")
            
            if self.debug_mode:
                print(f"DEBUG: AP renamed from '{old_name}' to '{ap.name}'")
    
    def _remove_ap(self, ap):
        """
        Remove an AP from the floor
        
        Args:
            ap (PlacedAP): The AP to remove
        """
        reply = QMessageBox.question(
            self, 
            "Remove Access Point",
            f"Are you sure you want to remove AP '{ap.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.current_floor.placed_aps.remove(ap)
            self._render_map()
            self.status_label.setText(f"AP '{ap.name}' removed")
            
            if self.debug_mode:
                print(f"DEBUG: AP '{ap.name}' removed from floor")
    
    def _label_to_map_coords(self, label_pos):
        """
        Convert label widget coordinates to map image coordinates
        
        Args:
            label_pos (QPoint): Position in the label widget
            
        Returns:
            QPoint: Position in the map image coordinates, or None if invalid
        """
        if not self.display_pixmap or not self.map_label.pixmap():
            return None
            
        # Get the displayed pixmap size and the label size
        displayed_pixmap = self.map_label.pixmap()
        label_size = self.map_label.size()
        pixmap_size = displayed_pixmap.size()
        
        # Calculate offset (image is centered in label)
        x_offset = (label_size.width() - pixmap_size.width()) // 2
        y_offset = (label_size.height() - pixmap_size.height()) // 2
        
        # Check if click is within the displayed image
        if (label_pos.x() < x_offset or label_pos.x() > x_offset + pixmap_size.width() or
            label_pos.y() < y_offset or label_pos.y() > y_offset + pixmap_size.height()):
            return None
        
        # Convert to image coordinates
        rel_x = label_pos.x() - x_offset
        rel_y = label_pos.y() - y_offset
        
        # Scale to original image size
        scale_x = self.base_pixmap.width() / pixmap_size.width()
        scale_y = self.base_pixmap.height() / pixmap_size.height()
        
        map_x = int(rel_x * scale_x)
        map_y = int(rel_y * scale_y)
        
        return QPoint(map_x, map_y)
    
    def _get_ap_at_position(self, x, y, radius=15):
        """
        Find an AP near the given position
        
        Args:
            x, y (int): Map coordinates
            radius (int): Search radius in pixels
            
        Returns:
            PlacedAP: AP at position, or None
        """
        if not self.current_floor:
            return None
            
        for ap in self.current_floor.placed_aps:
            ap_x, ap_y = int(ap.map_x), int(ap.map_y)
            distance = ((x - ap_x) ** 2 + (y - ap_y) ** 2) ** 0.5
            if distance <= radius:
                return ap
                
        return None
    
    def _place_ap_at_position(self, x, y):
        """
        Place a new AP at the specified position
        
        Args:
            x, y (int): Map coordinates
        """
        # Get AP name from user
        ap_name, ok = QInputDialog.getText(
            self, 
            "Place Access Point",
            "Enter AP name:",
            text=f"AP_{len(self.current_floor.placed_aps) + 1}"
        )
        
        if not ok or not ap_name.strip():
            return
        
        # Create new placed AP
        new_ap = PlacedAP(
            name=ap_name.strip(),
            manufacturer="Unknown",
            model="Unknown", 
            ip_address="",
            ethernet_mac="",
            map_x=x,
            map_y=y,
            timestamp_last_scan=None  # No scan data initially
        )
        
        # Add to current floor
        self.current_floor.placed_aps.append(new_ap)
        
        # Refresh simulator with updated AP locations
        self._refresh_simulator()
        
        # Re-render map
        self._render_map()
        
        # Emit signal
        self.ap_placed.emit(new_ap)
        
        if self.debug_mode:
            print(f"DEBUG: Placed AP '{ap_name}' at ({x}, {y})")
        
        # Immediately offer to scan at the new AP location
        self._offer_immediate_scan(new_ap)
    
    def _add_scan_point_at_position(self, x, y):
        """
        Add a scan point with simulated data at the specified position
        
        Args:
            x, y (int): Map coordinates  
        """
        # Generate simulated scan data
        simulated_ap_data = self.simulator.generate_ap_data_list(count=random.randint(5, 12), scan_x=x, scan_y=y)
        
        # Create scan point
        scan_point = ScanPoint(
            map_x=x,
            map_y=y,
            timestamp=datetime.datetime.now(),
            ap_list=simulated_ap_data
        )
        
        # Add to current floor
        self.current_floor.scan_points.append(scan_point)
        
        # Update heatmap if enabled (new scan data available)
        if self.heatmap_enabled:
            self._update_heatmap()
        
        # Re-render map
        self._render_map()
        
        # Emit signal
        self.scan_point_added.emit(scan_point)
        
        # Update status
        self.status_label.setText(f"Scan point added at ({x}, {y}) - {len(simulated_ap_data)} APs detected")
        
        if self.debug_mode:
            print(f"DEBUG: Added scan point at ({x}, {y}) with {len(simulated_ap_data)} APs")
    
    def set_placement_mode(self, mode):
        """
        Set the placement mode (legacy method - now placement is only via right-click)
        
        Args:
            mode (str): "ap" or "scan_point" (for compatibility)
        """
        self.placement_mode = mode  # Keep for legacy compatibility
        # All placement now happens via right-click context menu
        self.status_label.setText("🔵 Blue APs = Scanned • 🟠 Orange APs = Need scanning • Right-click to place/scan • Drag APs to move")
        
        if self.debug_mode:
            print(f"DEBUG: Placement mode set to: {mode} (but all placement now via right-click)")
    
    def clear_all_aps(self):
        """Remove all placed APs from the current floor"""
        if self.current_floor:
            self.current_floor.placed_aps.clear()
            self._render_map()
            self.status_label.setText("All APs cleared")
    
    def clear_all_scan_points(self):
        """Remove all scan points from the current floor"""
        if self.current_floor:
            self.current_floor.scan_points.clear()
            # Update heatmap if enabled (scan data cleared)
            if self.heatmap_enabled:
                self._update_heatmap()
            self._render_map()
            self.status_label.setText("All scan points cleared")
    
    def _scan_at_all_aps(self):
        """
        Add scan points at all placed AP locations with simulated data
        """
        if not self.current_floor or not self.current_floor.placed_aps:
            return
        
        added_count = 0
        for ap in self.current_floor.placed_aps:
            # Generate simulated scan data for this location
            simulated_ap_data = self.simulator.generate_ap_data_list(count=random.randint(4, 10), scan_x=ap.map_x, scan_y=ap.map_y)
            
            # Create scan point at AP location
            scan_point = ScanPoint(
                map_x=ap.map_x,
                map_y=ap.map_y,
                timestamp=datetime.datetime.now(),
                ap_list=simulated_ap_data
            )
            
            self.current_floor.scan_points.append(scan_point)
            added_count += 1
        
        # Update heatmap if enabled (new scan data available)
        if self.heatmap_enabled:
            self._update_heatmap()
        
        # Re-render map
        self._render_map()
        
        # Update status
        self.status_label.setText(f"Added scan points at {added_count} AP locations")
        
        if self.debug_mode:
            print(f"DEBUG: Added scan points at {added_count} AP locations")
    
    def _clear_all_ap_scan_data(self):
        """
        Clear associated scan data from all APs while keeping the AP placements
        """
        if not self.current_floor or not self.current_floor.placed_aps:
            return
        
        cleared_count = 0
        for ap in self.current_floor.placed_aps:
            if ap.associated_scan_data:
                ap.associated_scan_data.clear()
                ap.timestamp_last_scan = None
                cleared_count += 1
        
        # Update status
        self.status_label.setText(f"Cleared scan data from {cleared_count} APs (keeping AP placements)")
        
        if self.debug_mode:
            print(f"DEBUG: Cleared scan data from {cleared_count} APs while keeping placements")
    
    def _scan_at_ap(self, ap):
        """
        Add a scan point at a specific AP location with simulated data
        
        Args:
            ap (PlacedAP): The AP to scan at
        """
        # Generate simulated scan data for this location  
        simulated_ap_data = self.simulator.generate_ap_data_list(count=random.randint(5, 12), scan_x=ap.map_x, scan_y=ap.map_y)
        
        # Create scan point at AP location
        scan_point = ScanPoint(
            map_x=ap.map_x,
            map_y=ap.map_y,
            timestamp=datetime.datetime.now(),
            ap_list=simulated_ap_data
        )
        
        self.current_floor.scan_points.append(scan_point)
        
        # Update heatmap if enabled (new scan data available)
        if self.heatmap_enabled:
            self._update_heatmap()
        
        # Re-render map
        self._render_map()
        
        # Update status
        self.status_label.setText(f"Scan completed at AP '{ap.name}' - {len(simulated_ap_data)} networks detected")
        
        if self.debug_mode:
            print(f"DEBUG: Scan point added at AP '{ap.name}' location with {len(simulated_ap_data)} APs")
    
    def _clear_ap_scan_data(self, ap):
        """
        Clear scan data from a specific AP
        
        Args:
            ap (PlacedAP): The AP to clear scan data from
        """
        ap.associated_scan_data.clear()
        ap.timestamp_last_scan = None
        
        # Update status
        self.status_label.setText(f"Cleared scan data from AP '{ap.name}' (keeping AP placement)")
        
        if self.debug_mode:
            print(f"DEBUG: Cleared scan data from AP '{ap.name}' while keeping placement")
    
    def _offer_immediate_scan(self, ap):
        """
        Offer to scan immediately after placing an AP
        
        Args:
            ap (PlacedAP): The newly placed AP
        """
        reply = QMessageBox.question(
            self, 
            "Scan at New AP",
            f"AP '{ap.name}' placed successfully!\n\nWould you like to run a scan at this location now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes  # Default to Yes
        )
        
        if reply == QMessageBox.Yes:
            # Run scan at the AP location
            self._scan_at_ap(ap)
        else:
            # Update status to show AP was placed but not scanned
            self.status_label.setText(f"AP '{ap.name}' placed at ({int(ap.map_x)}, {int(ap.map_y)}) - no scan performed")
    
    def _has_scan_data(self, ap):
        """
        Check if an AP has any scan data (either scan points nearby or associated scan data)
        
        Args:
            ap (PlacedAP): The AP to check
            
        Returns:
            bool: True if AP has scan data, False otherwise
        """
        # Check if AP has associated scan data
        if ap.associated_scan_data and len(ap.associated_scan_data) > 0:
            return True
        
        # Check if there are any scan points at or very near the AP location (within 10 pixels)
        for scan_point in self.current_floor.scan_points:
            distance = ((ap.map_x - scan_point.map_x) ** 2 + (ap.map_y - scan_point.map_y) ** 2) ** 0.5
            if distance <= 10:  # Very close to AP location
                return True
        
        return False