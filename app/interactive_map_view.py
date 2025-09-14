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
# import random  # Removed - no longer needed without simulation fallback
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QInputDialog, QMenu, QAction, QDialog, QScrollArea, QPushButton, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QFont, QMouseEvent
from .data_models import PlacedAP, ScanPoint
# from .scan_simulator import ScanSimulator  # Removed for V1, will be used in V2 for predictive heatmaps
from .wifi_scanner import WiFiScanner, WiFiScanError
from .heatmap_generator import HeatmapGenerator

class InteractiveMapView(QWidget):
    """
    Interactive map view widget for displaying floor plans and placing APs
    """

    # Signals
    ap_placed = pyqtSignal(object)  # Emitted when an AP is placed
    scan_point_added = pyqtSignal(object)  # Emitted when a scan point is added
    status_message = pyqtSignal(str)  # Emitted to update main window status bar

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
        self.left_click_mode = None  # None, "place_ap", or "live_scan" - for menu-triggered left-click modes
        self.dragging_ap = None
        self.drag_offset = QPoint(0, 0)
        self.right_click_position = QPoint(0, 0)  # Store right-click position for context menu

        # Zoom functionality
        self.zoom_level = 1.0  # 1.0 = 100%, 0.5 = 50%, 2.0 = 200%
        self.min_zoom = 0.25   # 25% minimum zoom
        self.max_zoom = 4.0    # 400% maximum zoom
        self.zoom_step = 0.25  # 25% zoom increments


        # WiFi Scanner for live scanning only
        self.wifi_scanner = WiFiScanner()
        self.use_live_scanning = self.wifi_scanner.is_available()

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        # Remove the layout - make this widget just contain the label directly
        # Main map display label
        self.map_label = QLabel(self)
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setStyleSheet("QLabel { border: 1px solid #ccc; background-color: #f0f0f0; }")
        self.map_label.setMinimumSize(800, 600)
        self.map_label.mousePressEvent = self._map_mouse_press
        self.map_label.mouseMoveEvent = self._map_mouse_move
        self.map_label.mouseReleaseEvent = self._map_mouse_release

        # Position the label to fill this widget
        self.map_label.move(0, 0)

        # Set the widget size to match the label size
        self.setMinimumSize(800, 600)

    def set_floor(self, floor):
        """
        Set the current floor to display

        Args:
            floor (Floor): Floor object to display
        """
        self.current_floor = floor
        self._load_floor_image()

        # Floor data updated - ready for live WiFi scanning

        self._render_map()


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

        # Ensure the pixmap is valid before painting
        if self.display_pixmap.isNull():
            return

        painter = QPainter(self.display_pixmap)

        # Check if painter is valid
        if not painter.isActive():
            return

        try:
            # Draw heatmap overlay if enabled
            if self.heatmap_enabled:
                self._draw_heatmap_overlay(painter)

            # Draw placed APs
            self._draw_placed_aps(painter)

            # Draw scan points
            self._draw_scan_points(painter)
        finally:
            # Ensure painter is always properly ended
            if painter.isActive():
                painter.end()

        # Scale to actual zoom level, not to fit label
        original_size = self.base_pixmap.size()
        zoom_size = original_size * self.zoom_level
        scaled_pixmap = self.display_pixmap.scaled(
            zoom_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Resize widget and label to match zoom
        self.map_label.setFixedSize(zoom_size)
        self.setFixedSize(zoom_size)

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

        for i, scan_point in enumerate(self.current_floor.scan_points):
            x, y = int(scan_point.map_x), int(scan_point.map_y)

            # Draw scan point marker (small green circle)
            painter.setPen(QPen(QColor(0, 150, 0), 2))
            painter.setBrush(QBrush(QColor(0, 200, 0, 150)))
            painter.drawEllipse(x - 6, y - 6, 12, 12)

            # Draw sequential scan point number (1-based)
            scan_number = i + 1
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawText(x - 10, y + 20, 20, 10, Qt.AlignCenter, str(scan_number))

    def _draw_heatmap_overlay(self, painter):
        """Draw heatmap overlay on the map"""
        if not self.current_floor or not self.current_floor.scan_points:
            return

        # Only generate heatmap if we don't have one yet
        if not self.heatmap_pixmap or self.heatmap_pixmap.isNull():
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

        # Generate heatmap with progress indication
        # Show status for heatmap generation
        self._update_status("Generating signal strength heatmap...")

        # Force UI update to show status message immediately
        QApplication.processEvents()

        # Let the "Generating heatmap..." message show for 1 second
        import time
        time.sleep(1.0)

        self.heatmap_pixmap = self.heatmap_generator.generate_heatmap(
            self.current_floor.scan_points,
            target_network=self.current_heatmap_network,
            floor=self.current_floor,
            status_callback=self._heatmap_progress_callback
        )

        # Clear progress message - show completion
        network_display = self.current_heatmap_network or "unknown network"
        completion_message = self.i18n.get_string("heatmap_progress_completed").format(network=network_display)
        self._update_status(completion_message)

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

    def set_heatmap_network_and_enable(self, network_ssid: str = None, enabled: bool = True):
        """Set both heatmap network and enabled state in a single operation to avoid double generation"""
        network_changed = self.current_heatmap_network != network_ssid
        enabled_changed = self.heatmap_enabled != enabled

        # Update both states
        self.current_heatmap_network = network_ssid
        self.heatmap_enabled = enabled

        # Only generate heatmap once if either changed and heatmap is now enabled
        if (network_changed or enabled_changed) and self.heatmap_enabled:
            self._update_heatmap()
            self._render_map()

        if self.debug_mode:
            network_name = network_ssid if network_ssid else "Strongest Signal"
            print(f"DEBUG: Heatmap network set to: {network_name}, enabled: {enabled}")

    def set_left_click_mode(self, mode: str = None):
        """Set the left-click mode for menu-triggered placement"""
        self.left_click_mode = mode
        if self.debug_mode:
            print(f"DEBUG: Left-click mode set to: {mode}")

    def wheelEvent(self, event):
        """Handle mouse wheel events for Ctrl+wheel zoom"""
        # Only zoom if Ctrl is held down
        if event.modifiers() & Qt.ControlModifier:
            # Get wheel delta (positive = zoom in, negative = zoom out)
            delta = event.angleDelta().y()

            if delta > 0:
                self._zoom_in_at_cursor(event.pos())
            elif delta < 0:
                self._zoom_out_at_cursor(event.pos())

            event.accept()
        else:
            # Let parent handle normal scrolling
            super().wheelEvent(event)

    def zoom_in(self):
        """Zoom in (called from menu)"""
        if self.zoom_level < self.max_zoom:
            self.zoom_level = min(self.max_zoom, self.zoom_level + self.zoom_step)
            self._apply_zoom()
            self._emit_zoom_changed()

    def zoom_out(self):
        """Zoom out (called from menu)"""
        if self.zoom_level > self.min_zoom:
            self.zoom_level = max(self.min_zoom, self.zoom_level - self.zoom_step)
            self._apply_zoom()
            self._emit_zoom_changed()

    def _zoom_in_at_cursor(self, cursor_pos):
        """Zoom in at cursor position"""
        if self.zoom_level < self.max_zoom:
            self.zoom_level = min(self.max_zoom, self.zoom_level + self.zoom_step)
            self._apply_zoom()
            self._emit_zoom_changed()

    def _zoom_out_at_cursor(self, cursor_pos):
        """Zoom out at cursor position"""
        if self.zoom_level > self.min_zoom:
            self.zoom_level = max(self.min_zoom, self.zoom_level - self.zoom_step)
            self._apply_zoom()
            self._emit_zoom_changed()

    def _apply_zoom(self):
        """Apply current zoom level to the display"""
        if not self.base_pixmap:
            return

        # Calculate the actual size based on zoom level
        original_size = self.base_pixmap.size()
        new_size = original_size * self.zoom_level

        # Resize both the label and the container widget
        self.map_label.setFixedSize(new_size)
        self.setFixedSize(new_size)  # Resize the container widget too

        # Scale the display_pixmap to the actual zoom size (no fitting)
        if self.display_pixmap and not self.display_pixmap.isNull():
            # Scale to actual zoom size, not to fit label
            scaled_pixmap = self.display_pixmap.scaled(
                new_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.map_label.setPixmap(scaled_pixmap)
        else:
            # If no display_pixmap exists, render the map once
            self._render_map()

    def _emit_zoom_changed(self):
        """Emit zoom level change to update status bar"""
        zoom_percent = int(self.zoom_level * 100)

        # Find the main window to update zoom display
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'update_zoom_display'):
                parent.update_zoom_display(zoom_percent)
                break
            parent = parent.parent()

        if self.debug_mode:
            print(f"DEBUG: Zoom level changed to {zoom_percent}%")

    def fit_to_window(self, window_size):
        """Fit the map to the specified window size"""
        if not self.base_pixmap:
            return

        # Calculate zoom level to fit the image within the window
        original_size = self.base_pixmap.size()

        # Calculate scale factors for both width and height
        width_scale = window_size.width() / original_size.width()
        height_scale = window_size.height() / original_size.height()

        # Use the smaller scale to ensure entire image fits
        fit_zoom = min(width_scale, height_scale)

        # Clamp to zoom limits
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, fit_zoom))

        self._apply_zoom()
        self._emit_zoom_changed()

        if self.debug_mode:
            print(f"DEBUG: Fit to window - zoom level set to {int(self.zoom_level * 100)}%")

    def _update_status(self, message):
        """Emit status message to main window"""
        self.status_message.emit(message)

    def get_available_networks(self):
        """Get list of networks available for heatmap display"""
        if not self.current_floor or not self.current_floor.scan_points:
            return []

        return self.heatmap_generator.get_connected_networks(self.current_floor.scan_points)

    def get_strongest_network_ssid(self):
        """Get the SSID of the strongest network from scan data"""
        if not self.current_floor or not self.current_floor.scan_points:
            return None

        # Find the SSID with the strongest signal strength
        strongest_signal = -999
        strongest_ssid = None

        for scan_point in self.current_floor.scan_points:
            if not scan_point.ap_list:
                continue

            for ap in scan_point.ap_list:
                if ap.signal_strength > strongest_signal:
                    strongest_signal = ap.signal_strength
                    strongest_ssid = ap.ssid

        return strongest_ssid

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

            # Check if we're in a special left-click mode from menu
            if self.left_click_mode == 'place_ap':
                self._place_ap_at_position(x, y)
                return
            elif self.left_click_mode == 'live_scan':
                self._add_scan_point_at_position(x, y)
                return

            # Check if clicking on an existing AP for dragging
            clicked_ap = self._get_ap_at_position(x, y)
            if clicked_ap:
                self.dragging_ap = clicked_ap
                self.drag_offset = QPoint(x - int(clicked_ap.map_x), y - int(clicked_ap.map_y))
                return

            # Left-click on empty space does nothing - use right-click for placement

    def _map_mouse_move(self, event):
        """Handle mouse move events (for dragging and hover)"""
        if not self.base_pixmap:
            return

        map_pos = self._label_to_map_coords(event.pos())
        if not map_pos:
            return

        # Handle AP dragging
        if self.dragging_ap:
            # Update AP position
            self.dragging_ap.map_x = map_pos.x() - self.drag_offset.x()
            self.dragging_ap.map_y = map_pos.y() - self.drag_offset.y()

            # Re-render the map
            self._render_map()

    def _map_mouse_release(self, event):
        """Handle mouse release events"""
        if self.dragging_ap:

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

        # Check if right-clicking on an existing AP or scan point
        clicked_ap = self._get_ap_at_position(self.right_click_position.x(), self.right_click_position.y())
        clicked_scan_point = self._get_scan_point_at_position(self.right_click_position.x(), self.right_click_position.y())

        if clicked_ap:
            # Menu options for existing AP
            context_menu.addAction(self.i18n.get_string("edit_ap_properties"), lambda: self._edit_ap_properties(clicked_ap))

            # Scan options - always show rescan, plus additional options if has data
            context_menu.addAction(self.i18n.get_string("rescan_at_this_ap"), lambda: self._scan_at_ap(clicked_ap))

            if self._has_scan_data(clicked_ap):
                context_menu.addAction(self.i18n.get_string("clear_this_ap_scan_data"), lambda: self._clear_ap_scan_data(clicked_ap))
                context_menu.addSeparator()
                context_menu.addAction(self.i18n.get_string("show_scan_data"), lambda: self._show_ap_scan_data(clicked_ap))

            context_menu.addSeparator()
            context_menu.addAction(self.i18n.get_string("remove_ap"), lambda: self._remove_ap(clicked_ap))
            context_menu.addSeparator()

        elif clicked_scan_point:
            # Menu options for existing scan point
            scan_point_index = self.current_floor.scan_points.index(clicked_scan_point) + 1
            networks_count = len(clicked_scan_point.ap_list) if clicked_scan_point.ap_list else 0
            context_menu.addAction(f"Scan Point {scan_point_index} ({networks_count} networks)", lambda: None).setEnabled(False)  # Info only
            context_menu.addAction(self.i18n.get_string("rescan_at_this_location"), lambda: self._rescan_scan_point(clicked_scan_point))
            context_menu.addAction(self.i18n.get_string("show_scan_data"), lambda: self._show_scan_point_data(clicked_scan_point))
            context_menu.addSeparator()
            context_menu.addAction(self.i18n.get_string("remove_this_scan_point"), lambda: self._remove_scan_point(clicked_scan_point))
            context_menu.addSeparator()

        else:
            # Only show placement and scan options when clicking on empty space
            place_ap_action = QAction(self.i18n.get_string("place_access_point_here"), self)
            place_ap_action.triggered.connect(lambda: self._place_ap_at_position(
                self.right_click_position.x(),
                self.right_click_position.y()
            ))
            context_menu.addAction(place_ap_action)

            scan_label = self.i18n.get_string("run_live_scan_here") if self.use_live_scanning else self.i18n.get_string("run_scan_here_simulated")
            scan_here_action = QAction(scan_label, self)
            scan_here_action.triggered.connect(lambda: self._add_scan_point_at_position(
                self.right_click_position.x(),
                self.right_click_position.y()
            ))
            context_menu.addAction(scan_here_action)

        context_menu.addSeparator()

        # Bulk operations
        context_menu.addSeparator()

        if self.current_floor.scan_points or any(self._has_scan_data(ap) for ap in self.current_floor.placed_aps):
            context_menu.addAction(self.i18n.get_string("clear_all_scan_data"), self._clear_all_scan_data)

        if self.current_floor.placed_aps:
            context_menu.addAction(self.i18n.get_string("remove_all_aps"), self._remove_all_aps)

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
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("ap_renamed_status").format(old_name=old_name, ap_name=ap.name))

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
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("ap_removed_status").format(ap_name=ap.name))

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

    def _get_scan_point_at_position(self, x, y, tolerance=20):
        """
        Get scan point at the specified position

        Args:
            x, y (int): Position coordinates
            tolerance (int): Search tolerance in pixels

        Returns:
            ScanPoint or None: The scan point at that position
        """
        if not self.current_floor or not self.current_floor.scan_points:
            return None

        for scan_point in self.current_floor.scan_points:
            distance = ((x - scan_point.map_x) ** 2 + (y - scan_point.map_y) ** 2) ** 0.5
            if distance <= tolerance:
                return scan_point

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

        # AP locations updated - ready for scanning

        # Re-render map
        self._render_map()

        # Emit signal
        self.ap_placed.emit(new_ap)

        if self.debug_mode:
            print(f"DEBUG: Placed AP '{ap_name}' at ({x}, {y})")

        # Immediately offer to scan at the new AP location
        self._offer_immediate_scan(new_ap)

    def _add_scan_point_at_position(self, x, y, replace_existing=False):
        """
        Add a scan point with live or simulated data at the specified position

        Args:
            x, y (int): Map coordinates
            replace_existing (bool): If True, remove existing scan point at this location first
        """
        # Remove existing scan point if replacing
        if replace_existing:
            existing_point = self._get_scan_point_at_position(x, y, tolerance=5)
            if existing_point:
                self.current_floor.scan_points.remove(existing_point)

        # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("scanning_at_location_status").format(x=x, y=y))

        try:
            if self.use_live_scanning:
                # Perform live WiFi scan
                print(f"Performing live WiFi scan at ({x}, {y})...")
                ap_data_list = self.wifi_scanner.scan(timeout=30)
                scan_type = "Live"
            else:
                # No fallback - show error if WiFi scanning not available
                QMessageBox.warning(self, "WiFi Scanner Error", "WiFi scanning is not available on this system.")
                return

            # Create scan point
            scan_point = ScanPoint(
                map_x=x,
                map_y=y,
                timestamp=datetime.datetime.now(),
                ap_list=ap_data_list
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
            # Update status with scan completion
            self._update_status(f"Live scan completed at ({x}, {y}) - {len(ap_data_list)} access points detected")

            if self.debug_mode:
                print(f"DEBUG: Added {scan_type.lower()} scan point at ({x}, {y}) with {len(ap_data_list)} APs")

        except WiFiScanError as e:
            # Handle scan errors gracefully
            error_msg = f"WiFi scan failed at ({x}, {y}): {e}"
            print(f"ERROR: {error_msg}")
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("scan_failed_status").format(x=x, y=y))

            # Show error to user - no fallback
            QMessageBox.warning(self, "WiFi Scan Error",
                              f"Live WiFi scanning failed:\n{e}")
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error during scan at ({x}, {y}): {e}"
            print(f"ERROR: {error_msg}")
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("scan_error_status").format(x=x, y=y))
            QMessageBox.critical(self, "Scan Error", error_msg)

    def set_placement_mode(self, mode):
        """
        Set the placement mode (legacy method - now placement is only via right-click)

        Args:
            mode (str): "ap" or "scan_point" (for compatibility)
        """
        self.placement_mode = mode  # Keep for legacy compatibility
        # Show scanning status in the label
        scan_status = "Live WiFi" if self.use_live_scanning else "Not Available"
        # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("status_legend").format(scan_status=scan_status))

        if self.debug_mode:
            print(f"DEBUG: Placement mode set to: {mode} (but all placement now via right-click)")

    def clear_all_aps(self):
        """Remove all placed APs from the current floor"""
        if self.current_floor:
            self.current_floor.placed_aps.clear()
            self._render_map()
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("all_aps_cleared_status"))

    def clear_all_scan_points(self):
        """Remove all scan points from the current floor"""
        if self.current_floor:
            self.current_floor.scan_points.clear()
            # Update heatmap if enabled (scan data cleared)
            if self.heatmap_enabled:
                self._update_heatmap()
            self._render_map()
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("all_scan_points_cleared_status"))


    def _clear_all_scan_data(self):
        """
        Clear ALL scan data: removes all scan points and clears AP scan data (making APs orange)
        """
        cleared_scan_points = len(self.current_floor.scan_points) if self.current_floor.scan_points else 0
        cleared_ap_data = 0

        # Clear all scan points
        if self.current_floor.scan_points:
            self.current_floor.scan_points.clear()

        # Clear scan data from all APs
        if self.current_floor.placed_aps:
            for ap in self.current_floor.placed_aps:
                if ap.associated_scan_data:
                    ap.associated_scan_data.clear()
                    ap.timestamp_last_scan = None
                    cleared_ap_data += 1

        # Update heatmap if enabled (all scan data cleared)
        if self.heatmap_enabled:
            self._update_heatmap()

        # Re-render map
        self._render_map()

        # Update status
        parts = []
        if cleared_scan_points > 0:
            parts.append(f"{cleared_scan_points} scan points")
        if cleared_ap_data > 0:
            parts.append(f"scan data from {cleared_ap_data} APs")

        if parts:
            # Status updates now handled by main window
            # self.status_label.setText(self.i18n.get_string("cleared_scan_data_status").format(parts=' and '.join(parts)))
            pass
        else:
            # Status updates now handled by main window
            # self.status_label.setText(self.i18n.get_string("no_scan_data_to_clear_status"))
            pass

        if self.debug_mode:
            print(f"DEBUG: Cleared {cleared_scan_points} scan points and scan data from {cleared_ap_data} APs")

    def _scan_at_ap(self, ap):
        """
        Add a scan point at a specific AP location with live or simulated data

        Args:
            ap (PlacedAP): The AP to scan at
        """
        # Update status for AP scanning
        self._update_status(f"Scanning at AP '{ap.name}'...")

        try:
            if self.use_live_scanning:
                # Perform live WiFi scan
                print(f"Performing live WiFi scan at AP '{ap.name}' ({ap.map_x}, {ap.map_y})...")
                ap_data_list = self.wifi_scanner.scan(timeout=30)
                scan_type = "Live"
            else:
                # No fallback - show error if WiFi scanning not available
                QMessageBox.warning(self, "WiFi Scanner Error", "WiFi scanning is not available on this system.")
                return

            # Create scan point at AP location
            scan_point = ScanPoint(
                map_x=ap.map_x,
                map_y=ap.map_y,
                timestamp=datetime.datetime.now(),
                ap_list=ap_data_list
            )

            self.current_floor.scan_points.append(scan_point)

            # Update heatmap if enabled (new scan data available)
            if self.heatmap_enabled:
                self._update_heatmap()

            # Re-render map
            self._render_map()

            # Update status
            # Update status with AP scan completion
            self._update_status(f"Live scan at AP '{ap.name}' completed - {len(ap_data_list)} access points detected")

            if self.debug_mode:
                print(f"DEBUG: Added {scan_type.lower()} scan point at AP '{ap.name}' ({ap.map_x}, {ap.map_y}) with {len(ap_data_list)} APs")

        except WiFiScanError as e:
            # Handle scan errors gracefully
            error_msg = f"WiFi scan failed at AP '{ap.name}': {e}"
            print(f"ERROR: {error_msg}")
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("ap_scan_failed_status").format(ap_name=ap.name))

            # Show error to user - no fallback
            QMessageBox.warning(self, "WiFi Scan Error",
                              f"Live WiFi scanning failed:\n{e}")
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error during scan at AP '{ap.name}': {e}"
            print(f"ERROR: {error_msg}")
            # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("ap_scan_error_status").format(ap_name=ap.name))
            QMessageBox.critical(self, "Scan Error", error_msg)

    def _clear_ap_scan_data(self, ap):
        """
        Clear scan data from a specific AP

        Args:
            ap (PlacedAP): The AP to clear scan data from
        """
        ap.associated_scan_data.clear()
        ap.timestamp_last_scan = None

        # Update status
        # Status updates now handled by main window
        # self.status_label.setText(self.i18n.get_string("ap_scan_data_cleared_status").format(ap_name=ap.name))

        if self.debug_mode:
            print(f"DEBUG: Cleared scan data from AP '{ap.name}' while keeping placement")

    def _remove_scan_point(self, scan_point):
        """
        Remove a specific scan point from the floor

        Args:
            scan_point (ScanPoint): The scan point to remove
        """
        if scan_point in self.current_floor.scan_points:
            scan_point_index = self.current_floor.scan_points.index(scan_point) + 1
            networks_count = len(scan_point.ap_list) if scan_point.ap_list else 0

            self.current_floor.scan_points.remove(scan_point)

            # Update heatmap if enabled (scan data removed)
            if self.heatmap_enabled:
                self._update_heatmap()

            # Re-render map
            self._render_map()

            # Status updates now handled by main window
        # self.status_label.setText(f"Scan Point {scan_point_index} removed ({networks_count} networks)")

            if self.debug_mode:
                print(f"DEBUG: Removed scan point at ({scan_point.map_x}, {scan_point.map_y}) with {networks_count} networks")

    def _remove_all_aps(self):
        """
        Remove all APs and clear all scan data (comprehensive cleanup)
        """
        if not self.current_floor:
            return

        ap_count = len(self.current_floor.placed_aps) if self.current_floor.placed_aps else 0
        scan_point_count = len(self.current_floor.scan_points) if self.current_floor.scan_points else 0

        # Clear everything
        if self.current_floor.placed_aps:
            self.current_floor.placed_aps.clear()
        if self.current_floor.scan_points:
            self.current_floor.scan_points.clear()

        # Update heatmap if enabled (all data cleared)
        if self.heatmap_enabled:
            self._update_heatmap()

        # Re-render map
        self._render_map()

        # Update status
        parts = []
        if ap_count > 0:
            parts.append(f"{ap_count} APs")
        if scan_point_count > 0:
            parts.append(f"{scan_point_count} scan points")

        if parts:
            # Status updates now handled by main window
            # self.status_label.setText(self.i18n.get_string("removed_items_status").format(parts=' and '.join(parts)))
            pass
        else:
            # Status updates now handled by main window
            # self.status_label.setText(self.i18n.get_string("no_aps_to_remove_status"))
            pass

        if self.debug_mode:
            print(f"DEBUG: Removed {ap_count} APs and {scan_point_count} scan points - full cleanup")

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
            # Status updates now handled by main window
            # self.status_label.setText(self.i18n.get_string("ap_placed_no_scan_status").format(ap_name=ap.name, x=int(ap.map_x), y=int(ap.map_y)))
            pass

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

    def _heatmap_progress_callback(self, percent, network_name):
        """Callback for heatmap generation progress updates"""
        # Format progress message using i18n
        network_display = network_name or "unknown network"
        progress_message = self.i18n.get_string("heatmap_progress_generating").format(
            network=network_display,
            percent=percent
        )
        self._update_status(progress_message)
        QApplication.processEvents()  # Force UI update to show progress immediately

    def _rescan_scan_point(self, scan_point):
        """Rescan at an existing scan point location"""
        if not scan_point:
            return

        # Perform new scan at the scan point location
        self._add_scan_point_at_position(scan_point.map_x, scan_point.map_y, replace_existing=True)

    def _show_ap_scan_data(self, ap):
        """Show scrollable scan data dialog for an AP with all measurements"""
        if not ap:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Scan Data - {ap.name}")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Header info
        header_label = QLabel(f"AP: {ap.name}\nLocation: ({int(ap.map_x)}, {int(ap.map_y)})")
        header_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(header_label)

        # Scrollable area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Find scan points near this AP
        nearby_scan_points = []
        tolerance = 50  # pixels

        for scan_point in self.current_floor.scan_points:
            distance = ((scan_point.map_x - ap.map_x) ** 2 + (scan_point.map_y - ap.map_y) ** 2) ** 0.5
            if distance <= tolerance:
                nearby_scan_points.append(scan_point)

        if nearby_scan_points:
            # Show ALL measurements from ALL nearby scan points
            for i, scan_point in enumerate(nearby_scan_points):
                # Scan point header
                sp_label = QLabel(f"Scan Point {i+1} - Location: ({int(scan_point.map_x)}, {int(scan_point.map_y)})")
                sp_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; margin-top: 5px; font-weight: bold;")
                scroll_layout.addWidget(sp_label)

                # All networks from this scan point
                sorted_networks = sorted(scan_point.ap_list, key=lambda x: x.signal_strength, reverse=True)
                for network in sorted_networks:
                    ssid = network.ssid if network.ssid else "{Hidden}"
                    network_info = f"• {ssid}\n  BSSID: {network.bssid}\n  RSSI: {network.signal_strength} dBm\n  Band: {network.band}"

                    net_label = QLabel(network_info)
                    net_label.setStyleSheet("padding: 5px; margin-left: 10px; border-left: 2px solid #ccc;")
                    net_label.setWordWrap(True)
                    scroll_layout.addWidget(net_label)
        else:
            no_data_label = QLabel("No scan data available near this AP")
            no_data_label.setStyleSheet("padding: 20px; font-style: italic; color: #666;")
            scroll_layout.addWidget(no_data_label)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec_()

    def _show_scan_point_data(self, scan_point):
        """Show scrollable scan data dialog for a scan point"""
        if not scan_point:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Scan Point Data")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Get scan point number
        scan_point_index = self.current_floor.scan_points.index(scan_point) + 1

        # Header info
        header_label = QLabel(f"Scan Point {scan_point_index}\nLocation: ({int(scan_point.map_x)}, {int(scan_point.map_y)})\nNetworks detected: {len(scan_point.ap_list) if scan_point.ap_list else 0}")
        header_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(header_label)

        # Scrollable area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        if scan_point.ap_list:
            # Sort networks by signal strength (strongest first)
            sorted_networks = sorted(scan_point.ap_list, key=lambda x: x.signal_strength, reverse=True)

            for network in sorted_networks:
                ssid = network.ssid if network.ssid else "{Hidden}"
                network_info = f"• {ssid}\n  BSSID: {network.bssid}\n  RSSI: {network.signal_strength} dBm\n  Band: {network.band}"

                net_label = QLabel(network_info)
                net_label.setStyleSheet("padding: 8px; margin: 2px; border: 1px solid #ddd; border-radius: 4px; background-color: #fafafa;")
                net_label.setWordWrap(True)
                scroll_layout.addWidget(net_label)
        else:
            no_data_label = QLabel("No networks detected at this scan point")
            no_data_label.setStyleSheet("padding: 20px; font-style: italic; color: #666;")
            scroll_layout.addWidget(no_data_label)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec_()