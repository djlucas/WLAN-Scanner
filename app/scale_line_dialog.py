# app/scale_line_dialog.py

import os
import sys
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsLineItem,
    QGroupBox, QComboBox, QStatusBar
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize, QLineF
from PyQt5.QtGui import QPixmap, QPen, QColor, QPainter, QBrush, QImage # Import QImage for pixel access

# Local imports from the 'app' package
from .i18n_manager import I18nManager
from .config_manager import ConfigManager
from .data_models import ScaleLine # Import the ScaleLine class


class ScaleLineDialog(QDialog):
    """
    A dialog for setting scale lines on a floor plan image.
    Automatically places default horizontal and vertical lines based on image content,
    allowing the user to adjust their positions/lengths and define physical dimensions.
    """
    def __init__(self, image_path, config_manager, i18n_manager, debug_mode=False, parent=None):
        """
        Initializes the ScaleLineDialog.

        Args:
            image_path (str): The path to the 1920x1080 scaled floor plan image.
            config_manager (ConfigManager): An instance of ConfigManager.
            i18n_manager (I18nManager): An instance of I18nManager for translation.
            debug_mode (bool): If True, enables extensive debug logging.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.image_path = image_path
        self.config_manager = config_manager
        self.i18n = i18n_manager
        self.debug_mode = debug_mode
        if self.debug_mode:
            print("DEBUG: ScaleLineDialog initialized in DEBUG_MODE.")

        self.setWindowTitle(self.i18n.get_string("scale_line_title"))
        self.setMinimumSize(800, 600)
        self.setModal(True)

        self.current_pixmap = QPixmap(self.image_path)
        if self.current_pixmap.isNull():
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("image_load_error_for_display").format(
                                     floor_number="current", site_name="current project" # Placeholder, actual values not available here
                                 ))
            if self.debug_mode:
                print(f"ERROR: Failed to load image for ScaleLineDialog: {self.image_path}")
            self.reject()
            return

        self.current_line_item = None # The QGraphicsLineItem currently being displayed/edited (main line segment)
        self.start_point_drag = QPointF() # Stores initial mouse position for dragging
        self.original_drag_line_p1 = QPointF() # Original line start point before drag
        self.original_drag_line_p2 = QPointF() # Original line end point before drag
        self.is_dragging_handle = False
        self.dragged_handle = None # "start" or "end"

        self.horizontal_line_data = None # Stores ScaleLine object for horizontal
        self.vertical_line_data = None   # Stores ScaleLine object for vertical

        self._init_ui()
        self._display_image() # Displays image and calls _redraw_all_lines

        # Automatically place initial horizontal line if none exists
        if not self.horizontal_line_data:
            self._auto_place_initial_horizontal_line()

        # Update UI based on initial state (after auto-placement)
        self._update_ok_button_state()

    def _init_ui(self):
        """
        Sets up the user interface elements and layout for the dialog.
        """
        if self.debug_mode:
            print("DEBUG: _init_ui called.")
        main_layout = QVBoxLayout(self)

        # Graphics View for image display and line drawing
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setAlignment(Qt.AlignCenter)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.graphics_view.setDragMode(QGraphicsView.NoDrag) # Disable default drag mode

        # Connect mouse events for dragging line handles
        self.graphics_view.mousePressEvent = self._mouse_press_event
        self.graphics_view.mouseMoveEvent = self._mouse_move_event
        self.graphics_view.mouseReleaseEvent = self._mouse_release_event

        main_layout.addWidget(self.graphics_view)

        # Scale Line Input Group
        scale_input_group = QGroupBox(self.i18n.get_string("scale_line_input_group"))
        scale_input_layout = QFormLayout()

        self.line_type_combo = QComboBox()
        self.line_type_combo.addItem(self.i18n.get_string("horizontal_line_type"))
        self.line_type_combo.addItem(self.i18n.get_string("vertical_line_type"))
        self.line_type_combo.currentIndexChanged.connect(self._line_type_changed)
        scale_input_layout.addRow(self.i18n.get_string("line_type_label"), self.line_type_combo)

        self.physical_dimension_input = QLineEdit()
        self.physical_dimension_input.setPlaceholderText(self.i18n.get_string("physical_dimension_placeholder"))
        self.physical_dimension_input.textChanged.connect(self._update_calculated_scale)
        scale_input_layout.addRow(self.i18n.get_string("physical_dimension_label"), self.physical_dimension_input)

        self.current_line_pixels_label = QLabel(self.i18n.get_string("pixels_label").format(pixels=0))
        scale_input_layout.addRow(self.i18n.get_string("current_line_pixels_label"), self.current_line_pixels_label)

        self.calculated_scale_label = QLabel(self.i18n.get_string("current_scale_label").format(scale="N/A"))
        scale_input_layout.addRow(self.i18n.get_string("calculated_scale_label"), self.calculated_scale_label)

        self.set_line_button = QPushButton(self.i18n.get_string("set_line_button"))
        self.set_line_button.clicked.connect(self._set_line)
        self.set_line_button.setEnabled(False) # Disabled until a line is valid

        scale_input_layout.addRow(self.set_line_button)
        scale_input_group.setLayout(scale_input_layout)
        main_layout.addWidget(scale_input_group)

        # OK and Cancel Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton(self.i18n.get_string("ok_button"))
        self.ok_button.clicked.connect(self._validate_and_accept)
        self.ok_button.setEnabled(False) # Enabled when at least one line is set

        self.cancel_button = QPushButton(self.i18n.get_string("cancel_button"))
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        # Status Bar
        self._status_bar = QStatusBar()
        main_layout.addWidget(self._status_bar)

    def _detect_lines_and_get_coords(self, min_line_length=300):
        """
        Analyzes the current pixmap to detect the topmost horizontal line and
        the leftmost/rightmost vertical lines based on black pixels.
        Returns (topmost_y, leftmost_x, rightmost_x).
        If no lines are detected, falls back to default positions.
        """
        image = self.current_pixmap.toImage()
        image_width = image.width()
        image_height = image.height()

        topmost_y = -1
        leftmost_x = image_width # Initialize to max to find min
        rightmost_x = -1 # Initialize to min to find max

        COLOR_TOLERANCE = 10 # Tolerance for near-black

        def is_near_black(color):
            return color.red() < COLOR_TOLERANCE and \
                   color.green() < COLOR_TOLERANCE and \
                   color.blue() < COLOR_TOLERANCE

        # Find topmost horizontal line
        for y in range(image_height):
            consecutive_black_pixels = 0
            for x in range(image_width):
                pixel_color = QColor(image.pixel(x, y))
                if is_near_black(pixel_color):
                    consecutive_black_pixels += 1
                else:
                    consecutive_black_pixels = 0 # Reset count if not black
                
                if consecutive_black_pixels >= min_line_length:
                    topmost_y = y
                    if self.debug_mode:
                        print(f"DEBUG: Detected topmost horizontal line at Y: {topmost_y} (length >= {min_line_length} pixels)")
                    break # Found a sufficiently long horizontal line in this row
            if topmost_y != -1:
                break # Found the topmost line, no need to check further rows

        # If no line detected, fall back to default placement (e.g., 10% from top)
        if topmost_y == -1:
            topmost_y = int(image_height * 0.1)
            if self.debug_mode:
                print("DEBUG: No distinct topmost horizontal line detected. Defaulting topmost_y placement.")

        # Find leftmost and rightmost vertical lines
        # Iterate through columns
        for x_coord in range(image_width): # Renamed to x_coord to avoid conflict with loop variable x
            consecutive_black_pixels = 0
            found_vertical_line_in_column = False
            for y_coord in range(image_height): # Renamed to y_coord
                pixel_color = QColor(image.pixel(x_coord, y_coord))
                if is_near_black(pixel_color):
                    consecutive_black_pixels += 1
                else:
                    consecutive_black_pixels = 0
                
                if consecutive_black_pixels >= min_line_length:
                    # Found a sufficiently long vertical line segment in this column
                    if x_coord < leftmost_x: # Update leftmost_x if this is further left
                        leftmost_x = x_coord
                    if x_coord > rightmost_x: # Update rightmost_x if this is further right
                        rightmost_x = x_coord
                    found_vertical_line_in_column = True
                    # Do not break here, continue to find the extent of this vertical line
            # After checking all pixels in a column, if a vertical line was found
            if found_vertical_line_in_column:
                if self.debug_mode:
                    print(f"DEBUG: Found vertical line segment in column X: {x_coord} (length >= {min_line_length} pixels)")


        # If no vertical lines detected, fall back to default
        if leftmost_x == image_width: # Still at initial max value, means no lines found
            leftmost_x = int(image_width * 0.1)
            if self.debug_mode:
                print("DEBUG: No distinct leftmost vertical line detected. Defaulting leftmost_x placement.")
        else:
            if self.debug_mode:
                print(f"DEBUG: Final detected leftmost vertical line at X: {leftmost_x}")

        if rightmost_x == -1: # Still at initial min value, means no lines found
            rightmost_x = int(image_width * 0.9)
            if self.debug_mode:
                print("DEBUG: No distinct rightmost vertical line detected. Defaulting rightmost_x placement.")
        else:
            if self.debug_mode:
                print(f"DEBUG: Final detected rightmost vertical line at X: {rightmost_x}")

        return topmost_y, leftmost_x, rightmost_x


    def _auto_place_initial_horizontal_line(self):
        """
        Automatically places a default horizontal line on the map,
        75px above the topmost detected line, spanning leftmost to rightmost detected vertical lines.
        """
        topmost_detected_y, leftmost_detected_x, rightmost_detected_x = self._detect_lines_and_get_coords()
        
        # Calculate the Y position for the horizontal scale line (75px above the detected line)
        # Ensure it doesn't go off the top of the image
        horizontal_line_y = max(0, topmost_detected_y - 75)
        
        # Use detected X coordinates for start and end points
        x1 = leftmost_detected_x
        x2 = rightmost_detected_x
        y = horizontal_line_y # Both points have the same Y for a horizontal line

        # Create a ScaleLine object for initial display
        # We use a placeholder physical dimension, user will input real value
        # The physical dimension value here is a default in meters, as per data_models.py
        self.horizontal_line_data = ScaleLine(x1, y, x2, y, 30.48, True, "m") # Default to 100ft (30.48m)
        
        # Redraw all lines to display this new horizontal line with its style and tick marks
        self._redraw_all_lines()
        
        # Update UI fields for this pre-placed line
        self.line_type_combo.setCurrentText(self.i18n.get_string("horizontal_line_type"))
        # DO NOT set text here, rely on placeholder for initial display
        # self.physical_dimension_input.setText(self._format_physical_dimension_for_display(self.horizontal_line_data.physical_dimension_value, self.horizontal_line_data.physical_dimension_unit))
        self._update_calculated_scale() # This will update labels
        self._status_bar.showMessage(self.i18n.get_string("enter_horizontal_dimension_message"))
        if self.debug_mode:
            print(f"DEBUG: Auto-placed initial horizontal line: {self.horizontal_line_data.to_dict()}")


    def _display_image(self):
        """
        Displays the floor plan image in the QGraphicsView.
        """
        if self.debug_mode:
            print("DEBUG: _display_image called.")
        self.graphics_scene.clear()
        pixmap_item = QGraphicsPixmapItem(self.current_pixmap)
        self.graphics_scene.addItem(pixmap_item)
        self.graphics_scene.setSceneRect(pixmap_item.boundingRect())
        self.graphics_view.fitInView(pixmap_item, Qt.KeepAspectRatio)
        self.graphics_view.setSceneRect(pixmap_item.boundingRect()) # Set scene rect after fitInView
        self.graphics_view.viewport().update() # Force repaint

        self._redraw_all_lines() # Redraw any existing lines

    def _draw_scale_marker(self, scale_line_obj, is_current_selection=False):
        """
        Draws a scale line (horizontal or vertical) with its tick marks on the scene.
        If is_current_selection is True, it also sets self.current_line_item to the main line.
        """
        if not scale_line_obj:
            return [] # Return list of items added

        items_added = []

        # Both horizontal and vertical lines should be dashed black
        main_pen = QPen(Qt.black, 3, Qt.DashLine) 

        # Draw the main line
        main_line = QLineF(scale_line_obj.x1, scale_line_obj.y1, scale_line_obj.x2, scale_line_obj.y2)
        line_item = self.graphics_scene.addLine(main_line, main_pen)
        line_item.setZValue(1)
        items_added.append(line_item)

        if is_current_selection:
            self.current_line_item = line_item # Set this as the draggable item

        # Draw tick marks (75px total length, 37.5px on each side of the endpoint)
        tick_length = 75.0
        half_tick = tick_length / 2.0
        tick_pen = QPen(Qt.black, 1, Qt.SolidLine) # Thin black solid line for ticks

        # Start point tick
        if scale_line_obj.is_horizontal:
            tick1 = QLineF(scale_line_obj.x1, scale_line_obj.y1 - half_tick,
                           scale_line_obj.x1, scale_line_obj.y1 + half_tick)
        else: # Vertical
            tick1 = QLineF(scale_line_obj.x1 - half_tick, scale_line_obj.y1,
                           scale_line_obj.x1 + half_tick, scale_line_obj.y1)
        tick_item1 = self.graphics_scene.addLine(tick1, tick_pen)
        tick_item1.setZValue(1)
        items_added.append(tick_item1)

        # End point tick
        if scale_line_obj.is_horizontal:
            tick2 = QLineF(scale_line_obj.x2, scale_line_obj.y2 - half_tick,
                           scale_line_obj.x2, scale_line_obj.y2 + half_tick)
        else: # Vertical
            tick2 = QLineF(scale_line_obj.x2 - half_tick, scale_line_obj.y2,
                           scale_line_obj.x2 + half_tick, scale_line_obj.y2)
        tick_item2 = self.graphics_scene.addLine(tick2, tick_pen)
        tick_item2.setZValue(1)
        items_added.append(tick_item2)

        return items_added


    def _redraw_all_lines(self):
        """Redraws horizontal and vertical lines with their specific styles and tick marks."""
        # Remove all non-pixmap items (lines, ticks)
        items_to_remove = [item for item in self.graphics_scene.items() if not isinstance(item, QGraphicsPixmapItem)]
        for item in items_to_remove:
            self.graphics_scene.removeItem(item)
        self.current_line_item = None # Reset current line item reference

        # Redraw horizontal line if data exists
        if self.horizontal_line_data:
            is_current_h = (self.line_type_combo.currentText() == self.i18n.get_string("horizontal_line_type"))
            self._draw_scale_marker(self.horizontal_line_data, is_current_selection=is_current_h)

        # Redraw vertical line if data exists
        if self.vertical_line_data:
            is_current_v = (self.line_type_combo.currentText() == self.i18n.get_string("vertical_line_type"))
            self._draw_scale_marker(self.vertical_line_data, is_current_selection=is_current_v)

        self._update_calculated_scale() # Update scale display based on current selection


    def _line_type_changed(self):
        """Handles changes in the line type combo box."""
        if self.debug_mode:
            print(f"DEBUG: Line type changed to: {self.line_type_combo.currentText()}")
        
        # Clear current line item from scene to avoid ghosting, it will be redrawn by _redraw_all_lines
        # No need to remove specific items here, _redraw_all_lines handles clearing all non-pixmap items.
        self.current_line_item = None

        # Update UI and status based on selected line type
        if self.line_type_combo.currentText() == self.i18n.get_string("horizontal_line_type"):
            self._status_bar.showMessage(self.i18n.get_string("edit_horizontal_dimension_message"))
            if self.horizontal_line_data:
                # Convert from meters (internal storage) to display unit based on config
                display_value = self.horizontal_line_data.physical_dimension_value
                display_unit = self.horizontal_line_data.physical_dimension_unit # This is 'm'
                if self.config_manager.get("measurement_system", "Imperial") == "Imperial":
                    display_value = ScaleLine.convert_to_feet(display_value)
                    display_unit = "ft"
                self.physical_dimension_input.setText(self._format_physical_dimension_for_display(display_value, display_unit))
            else:
                self.physical_dimension_input.clear()
        else: # Vertical line type
            self._status_bar.showMessage(self.i18n.get_string("edit_vertical_dimension_message"))
            if self.vertical_line_data:
                # Convert from meters (internal storage) to display unit based on config
                display_value = self.vertical_line_data.physical_dimension_value
                display_unit = self.vertical_line_data.physical_dimension_unit # This is 'm'
                if self.config_manager.get("measurement_system", "Imperial") == "Imperial":
                    display_value = ScaleLine.convert_to_feet(display_value)
                    display_unit = "ft"
                self.physical_dimension_input.setText(self._format_physical_dimension_for_display(display_value, display_unit))
            else:
                self.physical_dimension_input.clear()

        self._redraw_all_lines() # This will set self.current_line_item and update labels
        self._update_ok_button_state()


    def _get_handle_at_pos(self, line_item, scene_pos):
        """
        Checks if scene_pos is near the start or end handle of a line_item.
        Returns "start", "end", or None.
        """
        if not line_item:
            return None
        line = line_item.line()
        tolerance = 10 # pixels
        start_rect = QRectF(line.p1().x() - tolerance, line.p1().y() - tolerance, 2*tolerance, 2*tolerance)
        end_rect = QRectF(line.p2().x() - tolerance, line.p2().y() - tolerance, 2*tolerance, 2*tolerance)

        if start_rect.contains(scene_pos):
            return "start"
        elif end_rect.contains(scene_pos):
            return "end"
        return None

    def _mouse_press_event(self, event):
        """Handles mouse press event for starting line dragging."""
        if event.button() == Qt.LeftButton:
            scene_pos = self.graphics_view.mapToScene(event.pos())
            if self.debug_mode:
                print(f"DEBUG: _mouse_press_event: Clicked at scene pos {scene_pos}")

            if self.current_line_item:
                self.dragged_handle = self._get_handle_at_pos(self.current_line_item, scene_pos)
                if self.dragged_handle:
                    self.is_dragging_handle = True
                    self.start_point_drag = scene_pos # Store initial mouse position for drag calculation
                    # Store the original line points to calculate new position relative to drag start
                    current_line = self.current_line_item.line()
                    self.original_drag_line_p1 = current_line.p1()
                    self.original_drag_line_p2 = current_line.p2()
                    self._status_bar.showMessage(self.i18n.get_string("edit_scale_lines_message"))
                    if self.debug_mode:
                        print(f"DEBUG: Starting drag for handle: {self.dragged_handle}")
                    return
            # If no handle is dragged, do nothing (no drawing from scratch)

    def _mouse_move_event(self, event):
        """Handles mouse move event for updating line dragging."""
        if self.current_pixmap.isNull():
            return

        if self.is_dragging_handle and self.dragged_handle and self.current_line_item:
            scene_pos = self.graphics_view.mapToScene(event.pos())
            # Constrain scene_pos to image bounds
            image_rect = self.graphics_scene.itemsBoundingRect()
            scene_pos.setX(max(image_rect.left(), min(image_rect.right(), scene_pos.x())))
            scene_pos.setY(max(image_rect.top(), min(image_rect.bottom(), scene_pos.y())))

            delta_x = scene_pos.x() - self.start_point_drag.x()
            delta_y = scene_pos.y() - self.start_point_drag.y()

            new_p1 = QPointF(self.original_drag_line_p1)
            new_p2 = QPointF(self.original_drag_line_p2)

            if self.dragged_handle == "start":
                new_p1 += QPointF(delta_x, delta_y)
            elif self.dragged_handle == "end":
                new_p2 += QPointF(delta_x, delta_y)

            # Constrain to horizontal/vertical if applicable
            if self.line_type_combo.currentText() == self.i18n.get_string("horizontal_line_type"):
                new_p1.setY(self.original_drag_line_p1.y()) # Keep Y of start point fixed
                new_p2.setY(self.original_drag_line_p2.y()) # Keep Y of end point fixed
            else: # Vertical
                new_p1.setX(self.original_drag_line_p1.x()) # Keep X of start point fixed
                new_p2.setX(self.original_drag_line_p2.x()) # Keep X of end point fixed

            self.current_line_item.setLine(QLineF(new_p1, new_p2))
            self._update_calculated_scale() # Update display as line is dragged

    def _mouse_release_event(self, event):
        """Handles mouse release event for finalizing line dragging."""
        if self.current_pixmap.isNull():
            return

        if self.is_dragging_handle:
            self.is_dragging_handle = False
            self.dragged_handle = None
            
            if self.current_line_item:
                current_line = self.current_line_item.line()
                physical_value = None
                physical_unit = None

                if self.line_type_combo.currentText() == self.i18n.get_string("horizontal_line_type") and self.horizontal_line_data:
                    physical_value = self.horizontal_line_data.physical_dimension_value
                    physical_unit = self.horizontal_line_data.physical_dimension_unit
                    # Update the stored ScaleLine object with the new coordinates
                    self.horizontal_line_data = ScaleLine(current_line.x1(), current_line.y1(),
                                                          current_line.x2(), current_line.y2(),
                                                          physical_value, True, physical_unit)
                    if self.debug_mode:
                        print(f"DEBUG: Horizontal line updated after drag: {self.horizontal_line_data.to_dict()}")
                elif self.line_type_combo.currentText() == self.i18n.get_string("vertical_line_type") and self.vertical_line_data:
                    physical_value = self.vertical_line_data.physical_dimension_value
                    physical_unit = self.vertical_line_data.physical_dimension_unit
                    # Update the stored ScaleLine object with the new coordinates
                    self.vertical_line_data = ScaleLine(current_line.x1(), current_line.y1(),
                                                        current_line.x2(), current_line.y2(),
                                                        physical_value, False, physical_unit)
                    if self.debug_mode:
                        print(f"DEBUG: Vertical line updated after drag: {self.vertical_line_data.to_dict()}")
            self._status_bar.showMessage(self.i18n.get_string("edit_scale_lines_message"))

        self._update_calculated_scale() # Ensure scale is updated after release
        self._update_ok_button_state()


    def _update_calculated_scale(self):
        """
        Calculates and updates the displayed scale based on the current line and
        entered physical dimension.
        """
        if self.debug_mode:
            print("DEBUG: _update_calculated_scale called.")

        current_line_pixels = 0
        if self.current_line_item:
            current_line_pixels = self.current_line_item.line().length()
        self.current_line_pixels_label.setText(self.i18n.get_string("pixels_label").format(pixels=f"{current_line_pixels:.2f}"))

        physical_dimension_text = self.physical_dimension_input.text().strip()
        physical_value, physical_unit = ScaleLine.parse_physical_dimension_input(physical_dimension_text)

        if physical_value is not None and current_line_pixels > 0:
            scale_per_pixel = physical_value / current_line_pixels
            # Convert to feet if Imperial system is preferred for display, otherwise meters
            display_unit = physical_unit
            if self.config_manager.get("measurement_system", "Imperial") == "Imperial":
                # Convert from meters (internal storage) to feet for display
                scale_per_pixel = ScaleLine.convert_to_feet(scale_per_pixel)
                display_unit = "ft"
            # No else needed, as physical_unit is already "m" if metric

            self.calculated_scale_label.setText(self.i18n.get_string("current_scale_label").format(scale=f"1 px = {scale_per_pixel:.2f} {display_unit}"))
            if self.debug_mode:
                print(f"DEBUG: Scale calculated: 1 px = {scale_per_pixel:.2f} {display_unit}")
        else:
            self.calculated_scale_label.setText(self.i18n.get_string("current_scale_label").format(scale="N/A"))
            if self.debug_mode:
                print("DEBUG: Scale calculation skipped (no physical dimension or zero pixels).")

        # Enable set_line_button if there's a valid line and physical dimension
        self.set_line_button.setEnabled(physical_value is not None and current_line_pixels > 0)
        self._update_ok_button_state() # Update OK button state after any change

    def _set_line(self):
        """
        Sets the currently displayed line's data.
        Automatically proposes a vertical line after horizontal is set.
        """
        if self.debug_mode:
            print("DEBUG: _set_line called.")
        
        # Ensure there's a current line item being displayed
        if self.current_line_item is None or self.current_line_item.line().length() == 0:
            QMessageBox.warning(self, self.i18n.get_string("warning_title"),
                                self.i18n.get_string("no_line_to_set_message"))
            if self.debug_mode:
                print("DEBUG: Set line failed: No line displayed or zero length.")
            return

        physical_dimension_text = self.physical_dimension_input.text().strip()
        physical_value, physical_unit = ScaleLine.parse_physical_dimension_input(physical_dimension_text)

        if physical_value is None:
            QMessageBox.warning(self, self.i18n.get_string("validation_error_title"),
                                self.i18n.get_string("physical_dimension_mandatory_message"))
            if self.debug_mode:
                print("DEBUG: Set line failed: Physical dimension invalid.")
            return

        current_line_geometry = self.current_line_item.line()
        
        if self.line_type_combo.currentText() == self.i18n.get_string("horizontal_line_type"):
            # Update horizontal_line_data with current geometry and physical dimension
            # physical_value is already in meters from parse_physical_dimension_input
            self.horizontal_line_data = ScaleLine(current_line_geometry.x1(), current_line_geometry.y1(),
                                                  current_line_geometry.x2(), current_line_geometry.y2(),
                                                  physical_value, True, "m") # Store as 'm' internally
            self._status_bar.showMessage(self.i18n.get_string("horizontal_line_set_status").format(dim=physical_dimension_text))
            if self.debug_mode:
                print(f"DEBUG: Horizontal scale line set to: {self.horizontal_line_data.to_dict()}")

            # --- Automatically propose and draw vertical line if horizontal is set ---
            if self.horizontal_line_data and not self.vertical_line_data:
                h_line_pixels = self.horizontal_line_data.pixel_length
                h_line_physical_value = self.horizontal_line_data.physical_dimension_value # This is in meters
                h_line_physical_unit = self.horizontal_line_data.physical_dimension_unit # This is 'm'

                # Calculate coordinates for a vertical line of the same pixel length
                # Position it on the left side, centered vertically
                image_width = self.current_pixmap.width()
                image_height = self.current_pixmap.height()
                
                x_pos = image_width * 0.05 # 5% from left edge
                y_center = image_height / 2
                y1_v = y_center - (h_line_pixels / 2)
                y2_v = y_center + (h_line_pixels / 2)

                # Ensure coordinates are within image bounds
                y1_v = max(0.0, y1_v)
                y2_v = min(float(image_height), y2_v)

                self.vertical_line_data = ScaleLine(
                    x_pos, y1_v, x_pos, y2_v, h_line_physical_value, False, h_line_physical_unit
                )
                self._redraw_all_lines() # Redraw both lines, ensuring vertical is drawn

                # Update UI to reflect the newly proposed vertical line
                self.line_type_combo.setCurrentText(self.i18n.get_string("vertical_line_type"))
                # Format the physical dimension text for display in the input field
                # Convert from meters (h_line_physical_value) to display unit based on config
                display_value = h_line_physical_value
                display_unit = "m"
                if self.config_manager.get("measurement_system", "Imperial") == "Imperial":
                    display_value = ScaleLine.convert_to_feet(display_value)
                    display_unit = "ft"
                
                physical_text_for_input = self._format_physical_dimension_for_display(display_value, display_unit)
                
                self.physical_dimension_input.setText(physical_text_for_input)
                self._update_calculated_scale() # Recalculate and display scale for vertical line
                self._status_bar.showMessage(self.i18n.get_string("auto_vertical_line_proposed_status").format(dim=physical_text_for_input))
                if self.debug_mode:
                    print(f"DEBUG: Auto-proposed vertical line. Data: {self.vertical_line_data.to_dict()}")

        else: # Vertical line type
            # Update vertical_line_data with current geometry and physical dimension
            # physical_value is already in meters from parse_physical_dimension_input
            self.vertical_line_data = ScaleLine(current_line_geometry.x1(), current_line_geometry.y1(),
                                                current_line_geometry.x2(), current_line_geometry.y2(),
                                                physical_value, False, "m") # Store as 'm' internally
            self._status_bar.showMessage(self.i18n.get_string("vertical_line_set_status").format(dim=physical_dimension_text))
            if self.debug_mode:
                print(f"DEBUG: Vertical scale line set to: {self.vertical_line_data.to_dict()}")

        self._redraw_all_lines() # Ensure lines are drawn correctly after setting
        self._update_ok_button_state()

    def _format_physical_dimension_for_display(self, value, unit):
        """
        Helper to format physical dimension for display in QLineEdit,
        handling feet and inches if applicable.
        This function now expects 'value' to be in the 'unit' it's displaying.
        """
        if unit == "ft":
            feet_part = int(value)
            inches_part = round((value - feet_part) * 12)
            if inches_part == 0:
                return f"{feet_part}'"
            elif inches_part == 12: # If it rounds up to next foot
                return f"{feet_part + 1}'"
            else:
                return f"{feet_part}' {inches_part}\""
        elif unit == "m":
            if value == int(value):
                return f"{int(value)} m"
            return f"{value:.2f} m" # Format meters to 2 decimal places
        return f"{value} {unit}"


    def _update_ok_button_state(self):
        """
        Enables the OK button only if at least one scale line (horizontal or vertical)
        has been set. Also updates status bar messages.
        """
        is_ok_enabled = (self.horizontal_line_data is not None) or \
                        (self.vertical_line_data is not None)
        self.ok_button.setEnabled(is_ok_enabled)
        if self.debug_mode:
            print(f"DEBUG: OK button enabled: {is_ok_enabled}")
            
        # Update status bar messages based on state
        if not self.horizontal_line_data:
            self._status_bar.showMessage(self.i18n.get_string("enter_horizontal_dimension_message"))
        elif not self.vertical_line_data:
            # Display the auto-proposed vertical line dimension based on the horizontal line's physical value
            # Convert from meters (h_line_physical_value) to display unit based on config
            display_value = self.horizontal_line_data.physical_dimension_value
            display_unit = "m"
            if self.config_manager.get("measurement_system", "Imperial") == "Imperial":
                display_value = ScaleLine.convert_to_feet(display_value)
                display_unit = "ft"

            self._status_bar.showMessage(self.i18n.get_string("auto_vertical_line_proposed_status").format(
                dim=self._format_physical_dimension_for_display(display_value, display_unit)
            ))
        elif self.horizontal_line_data and self.vertical_line_data:
            self._status_bar.showMessage(self.i18n.get_string("edit_scale_lines_message"))


    def _validate_and_accept(self):
        """
        Validates that at least one scale line has been set before accepting the dialog.
        """
        if self.debug_mode:
            print("DEBUG: _validate_and_accept called.")
        if self.horizontal_line_data is None and self.vertical_line_data is None:
            QMessageBox.warning(self, self.i18n.get_string("validation_error_title"),
                                self.i18n.get_string("at_least_one_scale_line_mandatory"))
            if self.debug_mode:
                print("DEBUG: Validation failed: No scale lines set.")
            return
        self.accept()

    def get_scale_lines(self):
        """
        Returns the set horizontal and vertical scale line data.
        """
        if self.debug_mode:
            print(f"DEBUG: get_scale_lines returning H: {self.horizontal_line_data}, V: {self.vertical_line_data}")
        return self.horizontal_line_data, self.vertical_line_data

# --- For standalone testing of the dialog (optional) ---
if __name__ == '__main__':
    # Dummy ConfigManager and I18nManager for standalone testing
    class DummyConfigManager:
        def __init__(self):
            self._config = {
                "language": "en_US",
                "poppler_path": "", # Set this to your Poppler bin directory for PDF testing
                "measurement_system": "Imperial" # Or "Metric"
            }
        def get(self, key, default=None):
            return self._config.get(key, default)
        def set(self, key, value):
            self._config[key] = value

    # Import the actual I18nManager from its new location
    from .i18n_manager import I18nManager as DummyI18nManager
    from PyQt5.QtWidgets import QApplication, QGraphicsProxyWidget
    from PyQt5.QtCore import QTimer # Import QTimer for standalone test
    from PyQt5.QtGui import QImage # Import QImage for dummy image creation

    app = QApplication(sys.argv)
    dummy_config = DummyConfigManager()
    # For standalone testing, I18nManager needs the correct path to i18n directory
    i18n_dir_for_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'i18n')
    dummy_i18n = DummyI18nManager(i18n_dir=i18n_dir_for_test)

    # Create dummy i18n directory and files for testing (if they don't exist)
    os.makedirs(i18n_dir_for_test, exist_ok=True)
    en_us_path = os.path.join(i18n_dir_for_test, 'en_US.txt')
    if not os.path.exists(en_us_path):
        with open(en_us_path, 'w', encoding='utf-8') as f:
            f.write("scale_line_title=Set Scale Lines\n")
            f.write("scale_line_input_group=Define Scale Line\n")
            f.write("line_type_label=Line Type:\n")
            f.write("horizontal_line_type=Horizontal\n")
            f.write("vertical_line_type=Vertical\n")
            f.write("physical_dimension_label=Physical Dimension:\n")
            f.write("physical_dimension_placeholder=E.g.: 40' 6\"; 40 ft 6 in; 40.5 feet; 12.34m; 12.34 meters\n")
            f.write("current_line_pixels_label=Current Line (Pixels):\n")
            f.write("pixels_label={pixels} px\n")
            f.write("calculated_scale_label=Calculated Scale:\n")
            f.write("current_scale_label={scale}\n")
            f.write("set_line_button=Set Line\n")
            f.write("unit_feet=ft\n")
            f.write("unit_meters=m\n")
            f.write("no_line_to_set_message=No line is currently displayed or it has zero length. Please adjust a line or ensure one is visible.\n")
            f.write("physical_dimension_mandatory_message=Physical Dimension is a mandatory field.\n")
            f.write("horizontal_line_set_status=Horizontal scale line set to '{dim}'.\n")
            f.write("vertical_line_set_status=Vertical line set to '{dim}'.\n")
            f.write("at_least_one_scale_line_mandatory=Please set at least one scale line (horizontal or vertical).\n")
            f.write("select_line_type_message=Please select a line type (Horizontal or Vertical) first.\n")
            f.write("no_floor_to_set_scale_message=No floor is currently loaded to set scale lines.\n")
            f.write("scale_lines_set_status=Scale lines set for Floor {floor_number}.\n")
            f.write("scale_lines_cancelled_status=Scale line setup cancelled for Floor {floor_number}.\n")
            f.write("image_load_error_for_display=Could not load map for Floor {floor_number} of '{site_name}'.\n")
            f.write("no_map_for_current_floor_message=No map image available for Floor {floor_number} of '{site_name}'. Please add or edit the floor map.\n")
            f.write("enter_horizontal_dimension_message=Step 1: Enter the physical dimension for the pre-drawn horizontal line.\n")
            f.write("edit_horizontal_dimension_message=Adjust the horizontal line by dragging its ends, then enter its physical dimension.\n")
            f.write("edit_vertical_dimension_message=Adjust the vertical line by dragging its ends, then enter its physical dimension.\n")
            f.write("edit_scale_lines_message=Scale lines set. You can adjust them by dragging the ends, or click OK.\n")
            f.write("both_scale_lines_mandatory=Please set both horizontal and vertical scale lines.\n")
            f.write("auto_vertical_line_proposed_status=Vertical line auto-proposed based on horizontal: '{dim}'. Adjust if needed.\n")


    # For standalone testing, create a dummy temporary directory
    temp_test_dir = QTemporaryDir()
    if not temp_test_dir.isValid():
        print("ERROR: Could not create temporary directory for standalone test.")
        sys.exit(1)
    temp_project_dir_path_for_test = temp_test_dir.path()
    print(f"DEBUG: Standalone test using temp dir: {temp_project_dir_path_for_test}")

    # Create a dummy image for testing that has black lines on a white background
    temp_test_image_path = os.path.join(i18n_dir_for_test, "dummy_floor_plan_1920x1080.png")
    if not os.path.exists(temp_test_image_path):
        dummy_image = QImage(1920, 1080, QImage.Format_RGB32)
        dummy_image.fill(Qt.white) # Fill with white background

        painter = QPainter(dummy_image)
        painter.setPen(QPen(Qt.black, 2)) # Black pen for drawing lines

        # Draw a topmost horizontal line (length 1700px)
        painter.drawLine(100, 200, 1800, 200) 

        # Draw leftmost and rightmost vertical lines (length 950px each)
        painter.drawLine(100, 50, 100, 1000) 
        painter.drawLine(1800, 50, 1800, 1000) 

        painter.end()
        dummy_image.save(temp_test_image_path)
        print(f"Created dummy image with lines: {temp_test_image_path}")

    dialog = ScaleLineDialog(temp_test_image_path, dummy_config, dummy_i18n, debug_mode=True) # Pass debug_mode
    if dialog.exec_() == QDialog.Accepted:
        h_line, v_line = dialog.get_scale_lines()
        print("Scale Line Data Captured:")
        print(f"  Horizontal Line: {h_line.to_dict() if h_line else 'None'}")
        print(f"  Vertical Line: {v_line.to_dict() if v_line else 'None'}")
    else:
        print("Scale Line Setup Cancelled.")

    # Clean up the temporary directory created for standalone testing
    if temp_test_dir.isValid():
        temp_test_dir.remove()
        print(f"DEBUG: Cleaned up standalone test temporary directory: {temp_test_dir.path()}")

    sys.exit(app.exec_())
