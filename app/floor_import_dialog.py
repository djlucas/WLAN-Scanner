# app/floor_import_dialog.py

import os
import sys
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QProgressBar, QGroupBox, QGraphicsProxyWidget, QGraphicsPathItem
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize, QProcess, QTimer, QTemporaryDir, QRect
from PyQt5.QtGui import QPixmap, QPen, QColor, QBrush, QImage, QPainter, QPainterPath


# Local imports from the 'app' package
from .i18n_manager import I18nManager
from .config_manager import ConfigManager


class FloorImportDialog(QDialog):
    """
    A dialog for importing floor plan images (JPG, PNG, PDF),
    allowing for cropping, and resizing to a consistent 1920x1080 resolution.
    Handles PDF conversion using Poppler.
    """
    def __init__(self, config_manager, i18n_manager, temp_project_dir_path, debug_mode=False, parent=None):
        """
        Initializes the FloorImportDialog.

        Args:
            config_manager (ConfigManager): An instance of ConfigManager.
            i18n_manager (I18nManager): An instance of I18nManager for translation.
            temp_project_dir_path (str): The path to the main window's temporary project directory.
            debug_mode (bool): If True, enables extensive debug logging.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n_manager
        self.temp_project_dir_path = temp_project_dir_path # Store the path from MainWindow
        self.debug_mode = debug_mode # Store debug mode
        if self.debug_mode:
            print("DEBUG: FloorImportDialog initialized in DEBUG_MODE.")

        self.setWindowTitle(self.i18n.get_string("floor_import_title"))
        self.setMinimumSize(800, 600)
        self.setModal(True)

        self.initial_loaded_pixmap = None # Stores the very first loaded pixmap (or converted PDF page)
        self.current_display_pixmap = None # Stores the pixmap currently displayed and manipulated

        self.crop_rect_item = None        # QGraphicsRectItem for the cropping selection
        self.shading_item = None          # QGraphicsPathItem for the unified shading
        self.start_point = QPointF()      # Start point for drawing crop rectangle
        self.end_point = QPointF()        # End point for drawing crop rectangle
        self.is_drawing = False           # Flag for drawing a NEW crop rectangle
        self.resize_mode = None           # Stores "top_left", "bottom_right", etc. if resizing
        self.drag_start_rect = None       # Stores the rect at the start of a resize operation

        self.cropped_image_data = None    # Stores QImage of the cropped area (intermediate)
        self.intermediate_cropped_image_path = None # Path to the saved cropped image (before 1920x1080 scaling)
        self.final_scaled_image_path = None # Path where the final 1920x1080 image will be saved by this dialog

        self.poppler_process = None # QProcess for Poppler execution
        self.pdf_temp_dir = None # Persistent temporary directory for PDF conversion output

        self._init_ui()
        self._reset_all_dialog_state() # Initial full reset

        # Connect dialog's finished signal to clean up PDF temp dir if it was used
        self.finished.connect(self._cleanup_pdf_temp_dir)


    def _init_ui(self):
        """
        Sets up the user interface elements and layout for the dialog.
        """
        if self.debug_mode:
            print("DEBUG: _init_ui called.")
        main_layout = QVBoxLayout(self)

        # --- File Selection and Floor Number ---
        file_selection_group = QGroupBox(self.i18n.get_string("file_selection_group"))
        file_selection_layout = QFormLayout()

        self.floor_number_input = QLineEdit()
        self.floor_number_input.setPlaceholderText(self.i18n.get_string("floor_number_placeholder"))
        file_selection_layout.addRow(self.i18n.get_string("floor_number_label"), self.floor_number_input)

        self.file_path_input = QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.browse_file_btn = QPushButton(self.i18n.get_string("browse_button"))
        self.browse_file_btn.clicked.connect(self._browse_file)

        file_path_h_layout = QHBoxLayout()
        file_path_h_layout.addWidget(self.file_path_input)
        file_path_h_layout.addWidget(self.browse_file_btn)
        file_selection_layout.addRow(self.i18n.get_string("image_file_label"), file_path_h_layout)

        file_selection_group.setLayout(file_selection_layout)
        main_layout.addWidget(file_selection_group)

        # --- Image Display and Cropping Area ---
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setAlignment(Qt.AlignCenter)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.graphics_view.setDragMode(QGraphicsView.NoDrag) # Default to no drag, enable for panning later

        # Connect mouse events for cropping
        self.graphics_view.mousePressEvent = self._mouse_press_event
        self.graphics_view.mouseMoveEvent = self._mouse_move_event
        self.graphics_view.mouseReleaseEvent = self._mouse_release_event

        main_layout.addWidget(self.graphics_view)

        # --- Control Buttons ---
        control_buttons_layout = QHBoxLayout()
        self.crop_button = QPushButton(self.i18n.get_string("crop_button"))
        self.crop_button.clicked.connect(self._perform_crop)
        self.crop_button.setEnabled(False) # Disabled until image is loaded and selection made

        self.reset_crop_button = QPushButton(self.i18n.get_string("reset_crop_button"))
        self.reset_crop_button.clicked.connect(self._reset_crop)
        self.reset_crop_button.setEnabled(False)

        self.next_button = QPushButton(self.i18n.get_string("next_button"))
        self.next_button.clicked.connect(self._validate_and_accept)
        self.next_button.setEnabled(False) # Disabled until image is processed

        self.cancel_button = QPushButton(self.i18n.get_string("cancel_button"))
        self.cancel_button.clicked.connect(self.reject)

        control_buttons_layout.addWidget(self.crop_button)
        control_buttons_layout.addWidget(self.reset_crop_button)
        control_buttons_layout.addStretch(1)
        control_buttons_layout.addWidget(self.next_button)
        control_buttons_layout.addWidget(self.cancel_button)
        main_layout.addLayout(control_buttons_layout)

        # Progress bar for PDF conversion
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat(self.i18n.get_string("pdf_conversion_progress_format"))
        self.progress_bar.setVisible(False) # Hidden by default
        main_layout.addWidget(self.progress_bar)

    def _clear_image_display_and_crop_state(self):
        """
        Clears only the image display, cropping state, and related variables.
        Does NOT clear floor number or file path input fields.
        """
        if self.debug_mode:
            print("DEBUG: _clear_image_display_and_crop_state called.")
        # self.initial_loaded_pixmap = None # Keep this, as it's the true original
        self.current_display_pixmap = None
        self.graphics_scene.clear()
        self.crop_rect_item = None
        self.shading_item = None
        self.start_point = QPointF()
        self.end_point = QPointF()
        self.is_drawing = False
        self.resize_mode = None
        self.drag_start_rect = None
        self.cropped_image_data = None
        self.intermediate_cropped_image_path = None
        self.final_scaled_image_path = None

        self.crop_button.setEnabled(False)
        self.reset_crop_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.progress_bar.setVisible(False)

        # Add a placeholder label if the scene is empty
        has_label = False
        for item in self.graphics_scene.items():
            if isinstance(item, QGraphicsProxyWidget) and isinstance(item.widget(), QLabel):
                has_label = True
                break
        if not has_label:
            placeholder_label = QLabel(self.i18n.get_string("no_image_loaded_message"))
            placeholder_label.setAlignment(Qt.AlignCenter)
            proxy_widget = self.graphics_scene.addWidget(placeholder_label)
            self.graphics_view.setSceneRect(proxy_widget.boundingRect())
            self.graphics_view.fitInView(proxy_widget, Qt.KeepAspectRatio)
        if self.debug_mode:
            print("DEBUG: Image display and crop state cleared.")


    def _reset_all_dialog_state(self):
        """
        Resets the entire dialog to its initial state, clearing all inputs and image display.
        This is for a full dialog reset.
        """
        if self.debug_mode:
            print("DEBUG: _reset_all_dialog_state called.")

        self.floor_number_input.clear()
        self.file_path_input.clear()
        self.initial_loaded_pixmap = None # Clear initial loaded pixmap on full reset

        self._clear_image_display_and_crop_state() # Clear image related state

        # Ensure PDF temp dir is cleaned up if a new file is loaded or dialog reset
        self._cleanup_pdf_temp_dir()
        if self.debug_mode:
            print("DEBUG: Dialog reset complete.")


    def _cleanup_pdf_temp_dir(self):
        """
        Cleans up the temporary directory used for PDF conversion.
        Called when the dialog is finished or reset.
        """
        if self.pdf_temp_dir and self.pdf_temp_dir.isValid():
            self.pdf_temp_dir.remove()
            if self.debug_mode:
                print(f"DEBUG: Cleaned up PDF conversion temporary directory: {self.pdf_temp_dir.path()}")
            self.pdf_temp_dir = None
        elif self.debug_mode:
            print("DEBUG: No PDF temporary directory to clean up.")


    def _browse_file(self):
        """
        Opens a file dialog to select an image or PDF file.
        """
        if self.debug_mode:
            print("DEBUG: _browse_file called.")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.i18n.get_string("select_image_file_title"),
            "", # Default directory
            self.i18n.get_string("image_file_filter")
        )
        if file_path:
            self.file_path_input.setText(file_path)
            self._load_image_or_pdf(file_path)
        elif self.debug_mode:
            print("DEBUG: File selection cancelled.")

    def _load_image_or_pdf(self, file_path):
        """
        Loads the selected file. If it's a PDF, converts it using Poppler.
        This method now calls _clear_image_display_and_crop_state() instead of _reset_all_dialog_state().
        """
        if self.debug_mode:
            print(f"DEBUG: _load_image_or_pdf called for: {file_path}")
        self._clear_image_display_and_crop_state() # Clear image display but keep floor number
        self.file_path_input.setText(file_path) # Ensure file path is set immediately

        if file_path.lower().endswith(".pdf"):
            if self.debug_mode:
                print("DEBUG: File is PDF, attempting conversion.")
            self._convert_pdf_to_image(file_path)
        else:
            if self.debug_mode:
                print("DEBUG: File is image (PNG/JPG), loading directly.")
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, self.i18n.get_string("error_title"),
                                    self.i18n.get_string("image_load_error_message").format(file_path=file_path))
                self._clear_image_display_and_crop_state() # Clear image display if load fails
                if self.debug_mode:
                    print(f"ERROR: Failed to load image from {file_path} (Pixmap is null).")
                return
            self.initial_loaded_pixmap = pixmap # Set the initial loaded pixmap
            self._display_image(pixmap) # Display it (which sets current_display_pixmap)

    def _display_image(self, pixmap_to_show):
        """
        Displays the given QPixmap in the QGraphicsView, scaling it to fit.
        """
        if self.debug_mode:
            print(f"DEBUG: _display_image called with pixmap size: {pixmap_to_show.size()}")
        self.current_display_pixmap = pixmap_to_show # Set current_display_pixmap to the pixmap being shown

        self.graphics_scene.clear()
        self.crop_rect_item = None # Explicitly clear reference
        self.shading_item = None    # Explicitly clear reference

        pixmap_item = QGraphicsPixmapItem(self.current_display_pixmap)
        self.graphics_scene.addItem(pixmap_item)
        pixmap_item.setZValue(0) # Ensure image is at the bottom layer
        self.graphics_scene.setSceneRect(pixmap_item.boundingRect())
        self.graphics_view.fitInView(pixmap_item, Qt.KeepAspectRatio)
        self.graphics_view.setSceneRect(pixmap_item.boundingRect()) # Set scene rect after fitInView
        self.graphics_view.viewport().update() # Force repaint

        self.crop_button.setEnabled(True)
        self.reset_crop_button.setEnabled(True)
        self.next_button.setEnabled(False) # Still needs cropping/resizing

        # Remove the placeholder label if it was added
        for item in self.graphics_scene.items():
            if isinstance(item, QGraphicsProxyWidget) and isinstance(item.widget(), QLabel):
                if item.widget().text() == self.i18n.get_string("no_image_loaded_message"):
                    self.graphics_scene.removeItem(item)
                    break
        if self.debug_mode:
            print("DEBUG: Image displayed in graphics view.")


    def _convert_pdf_to_image(self, pdf_path):
        """
        Converts a PDF file to a PNG image using Poppler's pdftoppm.
        """
        if self.debug_mode:
            print(f"DEBUG: _convert_pdf_to_image called for {pdf_path}")
        poppler_path = self.config_manager.get("poppler_path")
        if not poppler_path or not os.path.exists(poppler_path):
            QMessageBox.warning(self, self.i18n.get_string("poppler_not_configured_title"),
                                self.i18n.get_string("poppler_not_configured_message"))
            self._clear_image_display_and_crop_state() # Clear image display if Poppler not configured
            if self.debug_mode:
                print("ERROR: Poppler path not configured.")
            return

        pdftoppm_executable = "pdftoppm"
        if sys.platform.startswith('win'):
            pdftoppm_executable = os.path.join(poppler_path, "pdftoppm.exe")
        else:
            # For Linux/Mac, assume pdftoppm is in PATH or specified poppler_path
            # Check if it's directly executable from poppler_path
            if os.path.exists(os.path.join(poppler_path, "pdftoppm")):
                pdftoppm_executable = os.path.join(poppler_path, "pdftoppm")
            # Else, rely on it being in system PATH, which is less reliable for specific versions

        if not os.path.exists(pdftoppm_executable) and not self._is_command_available(pdftoppm_executable):
             QMessageBox.warning(self, self.i18n.get_string("poppler_executable_not_found_title"),
                                 self.i18n.get_string("poppler_executable_not_found_message").format(exe=pdftoppm_executable))
             self._clear_image_display_and_crop_state() # Clear image display if Poppler executable not found
             if self.debug_mode:
                print(f"ERROR: Poppler executable not found: {pdftoppm_executable}")
             return

        # Create a persistent temporary directory for PDF conversion output
        self._cleanup_pdf_temp_dir() # Ensure any old one is gone
        self.pdf_temp_dir = QTemporaryDir()
        if not self.pdf_temp_dir.isValid():
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("temp_dir_error_message"))
            self._clear_image_display_and_crop_state() # Clear image display if temp dir fails
            if self.debug_mode:
                print("ERROR: Failed to create persistent PDF temporary directory.")
            return
        temp_image_prefix = os.path.join(self.pdf_temp_dir.path(), "temp_floor_plan")
        if self.debug_mode:
            print(f"DEBUG: PDF conversion temp dir created: {self.pdf_temp_dir.path()}")

        # Command to convert PDF page 1 to PNG
        # -png: output PNG. -singlefile: only output a single file (for single page).
        # -f 1 -l 1: process only page 1
        command = [pdftoppm_executable, "-png", "-singlefile", "-f", "1", "-l", "1", pdf_path, temp_image_prefix]

        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.progress_bar.setFormat(self.i18n.get_string("pdf_conversion_progress_format"))
        self.progress_bar.setVisible(True)

        self.poppler_process = QProcess(self)
        # Pass output_image_path to the slot
        self.poppler_process.finished.connect(lambda exitCode, exitStatus: self._handle_pdf_conversion_finished(exitCode, exitStatus, temp_image_prefix + ".png"))
        self.poppler_process.errorOccurred.connect(self._handle_poppler_error)

        try:
            self.poppler_process.start(command[0], command[1:])
            if self.debug_mode:
                print(f"DEBUG: Poppler process started: {' '.join(command)}")
        except Exception as e:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("poppler_process_start_error").format(error=str(e)))
            self._clear_image_display_and_crop_state() # Clear image display if process fails to start
            self.progress_bar.setVisible(False)
            if self.debug_mode:
                print(f"ERROR: Poppler process failed to start: {e}")


    def _is_command_available(self, command_name):
        """Checks if a command is available in the system's PATH."""
        return any(
            os.access(os.path.join(path, command_name), os.X_OK)
            for path in os.environ["PATH"].split(os.pathsep)
        )

    def _handle_pdf_conversion_finished(self, exit_code, exit_status, output_image_path):
        """
        Handles the completion of the PDF conversion process.
        """
        if self.debug_mode:
            print(f"DEBUG: PDF conversion finished. Exit Code: {exit_code}, Exit Status: {exit_status}")
        self.progress_bar.setVisible(False)
        if exit_status == QProcess.NormalExit and exit_code == 0:
            if os.path.exists(output_image_path):
                pixmap = QPixmap(output_image_path)
                if pixmap.isNull():
                    QMessageBox.warning(self, self.i18n.get_string("error_title"),
                                        self.i18n.get_string("converted_image_load_error").format(path=output_image_path))
                    self._clear_image_display_and_crop_state() # Clear image display if converted image is null
                    if self.debug_mode:
                        print(f"ERROR: Converted image is null: {output_image_path}")
                else:
                    self.initial_loaded_pixmap = pixmap # Set the initial loaded pixmap (from converted PDF)
                    self._display_image(pixmap) # Display it (which sets current_display_pixmap)
                    if self.debug_mode:
                        print(f"DEBUG: PDF converted successfully and displayed: {output_image_path}")
            else:
                QMessageBox.warning(self, self.i18n.get_string("error_title"),
                                    self.i18n.get_string("pdf_output_file_missing").format(path=output_image_path))
                self._clear_image_display_and_crop_state() # Clear image display if output file is missing
                if self.debug_mode:
                    print(f"ERROR: PDF output file missing: {output_image_path}")
        else:
            error_output = self.poppler_process.readAllStandardError().data().decode(sys.stderr.encoding or 'utf-8')
            QMessageBox.critical(self, self.i18n.get_string("pdf_conversion_failed_title"),
                                 self.i18n.get_string("pdf_conversion_failed_message").format(
                                     exit_code=exit_code,
                                     error_output=error_output
                                 ))
            self._clear_image_display_and_crop_state() # Clear image display if conversion fails
            if self.debug_mode:
                print(f"ERROR: PDF conversion failed. Exit code: {exit_code}, Error: {error_output}")

        # The self.pdf_temp_dir will be cleaned up by closeEvent or _reset_all_dialog_state
        self.poppler_process = None

    def _handle_poppler_error(self, error):
        """
        Handles errors that occur during the Poppler process startup.
        """
        if self.debug_mode:
            print(f"DEBUG: Poppler process error occurred: {error}")
        self.progress_bar.setVisible(False)
        error_message = self.i18n.get_string("poppler_process_error")
        if error == QProcess.FailedToStart:
            error_message = self.i18n.get_string("poppler_failed_to_start")
        elif error == QProcess.Crashed:
            error_message = self.i18n.get_string("poppler_crashed")
        elif error == QProcess.Timedout:
            error_message = self.i18n.get_string("poppler_timed_out")
        elif error == QProcess.ReadError:
            error_message = self.i18n.get_string("poppler_read_error")
        elif error == QProcess.WriteError:
            error_message = self.i18n.get_string("poppler_write_error")
        elif error == QProcess.UnknownError:
            error_message = self.i18n.get_string("poppler_unknown_error")

        QMessageBox.critical(self, self.i18n.get_string("error_title"), error_message)
        self._clear_image_display_and_crop_state() # Clear image display on Poppler error
        if self.debug_mode:
            print(f"ERROR: Poppler process error: {error_message}")

    def _get_corner_handle(self, point):
        """
        Checks if the given point is near a corner of the current crop_rect_item.
        Returns a string indicating the corner ("top_left", "bottom_right", etc.) or None.
        """
        if not self.crop_rect_item:
            return None

        rect = self.crop_rect_item.rect()
        tolerance = 10 # Pixels within which a click is considered "near" a corner

        handles = {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight()
        }

        for mode, corner_point in handles.items():
            handle_rect = QRectF(corner_point.x() - tolerance, corner_point.y() - tolerance, 2 * tolerance, 2 * tolerance)
            if handle_rect.contains(point):
                return mode
        return None

    def _mouse_press_event(self, event):
        """Handles mouse press event for starting crop selection or resizing."""
        if self.current_display_pixmap is None:
            if self.debug_mode:
                print("DEBUG: _mouse_press_event: current_display_pixmap is None. Ignoring.")
            return
        if event.button() == Qt.LeftButton:
            scene_pos = self.graphics_view.mapToScene(event.pos())
            if self.debug_mode:
                print(f"DEBUG: _mouse_press_event: Clicked at scene pos {scene_pos}")

            # Check if we are starting a resize operation
            self.resize_mode = self._get_corner_handle(scene_pos)
            if self.resize_mode and self.crop_rect_item:
                self.drag_start_rect = self.crop_rect_item.rect() # Store the initial rect for calculation
                self.start_point = scene_pos # Store the mouse press point
                self.is_drawing = False # Not drawing a new rect
                self.graphics_view.setCursor(Qt.SizeFDiagCursor if self.resize_mode in ["top_left", "bottom_right"] else Qt.SizeBDiagCursor)
                if self.debug_mode:
                    print(f"DEBUG: Starting resize mode: {self.resize_mode}")
            else:
                # Start drawing a new rectangle
                self.is_drawing = True
                self.start_point = scene_pos
                self.end_point = self.start_point
                self.resize_mode = None
                self.drag_start_rect = None
                self.graphics_view.setCursor(Qt.CrossCursor)
                if self.debug_mode:
                    print("DEBUG: Starting new drawing mode.")
                self._update_crop_rect() # Initial draw of empty rect / clear old

    def _mouse_move_event(self, event):
        """Handles mouse move event for updating crop selection or resizing."""
        if self.current_display_pixmap is None:
            return

        current_scene_pos = self.graphics_view.mapToScene(event.pos())

        if self.is_drawing:
            self.end_point = current_scene_pos
            self._update_crop_rect()
        elif self.resize_mode and self.drag_start_rect:
            # Calculate the delta movement
            delta_x = current_scene_pos.x() - self.start_point.x()
            delta_y = current_scene_pos.y() - self.start_point.y()

            new_rect = QRectF(self.drag_start_rect) # Start with the original rect

            # Adjust the rectangle based on the resize mode
            if self.resize_mode == "top_left":
                new_rect.setTopLeft(self.drag_start_rect.topLeft() + QPointF(delta_x, delta_y))
            elif self.resize_mode == "top_right":
                new_rect.setTopRight(self.drag_start_rect.topRight() + QPointF(delta_x, delta_y))
            elif self.resize_mode == "bottom_left":
                new_rect.setBottomLeft(self.drag_start_rect.bottomLeft() + QPointF(delta_x, delta_y))
            elif self.resize_mode == "bottom_right":
                new_rect.setBottomRight(self.drag_start_rect.bottomRight() + QPointF(delta_x, delta_y))

            # Ensure the new rectangle is valid (positive width/height)
            if new_rect.width() < 0:
                new_rect.setLeft(new_rect.right())
            if new_rect.height() < 0:
                new_rect.setTop(new_rect.bottom())

            # Update crop_rect_item and redraw
            self.crop_rect_item.setRect(new_rect.normalized())
            self._update_shading(new_rect.normalized()) # Update shading based on the new rect
        else:
            # Update cursor when hovering over handles if not currently dragging
            if self.crop_rect_item:
                hover_mode = self._get_corner_handle(current_scene_pos)
                if hover_mode:
                    self.graphics_view.setCursor(Qt.SizeFDiagCursor if hover_mode in ["top_left", "bottom_right"] else Qt.SizeBDiagCursor)
                else:
                    self.graphics_view.setCursor(Qt.ArrowCursor) # Default cursor
            else:
                self.graphics_view.setCursor(Qt.ArrowCursor)


    def _mouse_release_event(self, event):
        """Handles mouse release event for finalizing crop selection or resizing."""
        if self.current_display_pixmap is None:
            return

        self.graphics_view.setCursor(Qt.ArrowCursor) # Reset cursor

        if self.is_drawing:
            self.is_drawing = False
            self.end_point = self.graphics_view.mapToScene(event.pos())
            self._update_crop_rect() # Final update after drawing
            if self.debug_mode:
                # Check if crop_rect_item exists before accessing its rect()
                if self.crop_rect_item:
                    print(f"DEBUG: Drawing finished. Final crop rect: {self.crop_rect_item.rect().normalized()}")
                else: # Added this else block
                    print("DEBUG: Drawing finished. No crop rect item (was too small or not drawn).") # Updated message
        elif self.resize_mode:
            self.resize_mode = None
            self.drag_start_rect = None
            if self.debug_mode:
                # Check if crop_rect_item exists before accessing its rect()
                if self.crop_rect_item:
                    print(f"DEBUG: Resizing finished. Final crop rect: {self.crop_rect_item.rect().normalized()}")
                else: # Added this else block
                    print("DEBUG: Resizing finished. No crop rect item (became too small or not drawn).") # Updated message
            # The crop_rect_item and shading are already updated in mouseMoveEvent,
            # but we can ensure the button state is correct here.
            self.crop_button.setEnabled(self.crop_rect_item is not None and not self.crop_rect_item.rect().isEmpty())


    def _update_crop_rect(self):
        """
        Updates or creates the QGraphicsRectItem for cropping and the shading overlay.
        This method is used for initial drawing. For resizing, _update_shading is called directly.
        """
        if self.current_display_pixmap is None:
            return

        # Get the pixmap item that holds the image
        pixmap_items = [item for item in self.graphics_scene.items() if isinstance(item, QGraphicsPixmapItem)]
        if not pixmap_items:
            if self.debug_mode:
                print("DEBUG: _update_crop_rect: No pixmap item found in scene.")
            return
        image_pixmap_item = pixmap_items[0]
        pixmap_rect = image_pixmap_item.boundingRect() # Use the image item's own bounding rect

        # Calculate the normalized rectangle from start to end points
        rect = QRectF(self.start_point, self.end_point).normalized()

        # Ensure the rectangle is within the bounds of the image pixmap item
        rect = rect.intersected(pixmap_rect)
        if self.debug_mode:
            print(f"DEBUG: _update_crop_rect: Calculated rect: {rect}")


        # Remove old crop rectangle and shading item
        if self.crop_rect_item:
            self.graphics_scene.removeItem(self.crop_rect_item)
            self.crop_rect_item = None
            if self.debug_mode:
                print("DEBUG: _update_crop_rect: Removed old crop_rect_item.")
        if self.shading_item:
            self.graphics_scene.removeItem(self.shading_item)
            self.shading_item = None
            if self.debug_mode:
                print("DEBUG: _update_crop_rect: Removed old shading_item.")

        # Only draw the selection rectangle and shading if the rectangle has a meaningful size
        # Using a small threshold (e.g., 2 pixels) for width/height
        if not rect.isEmpty() and (rect.width() > 2 or rect.height() > 2):
            # Draw the selection rectangle with a blue border and NO fill
            self.crop_rect_item = self.graphics_scene.addRect(rect, QPen(Qt.blue, 2), QBrush(Qt.NoBrush))
            self.crop_rect_item.setZValue(1) # Ensure it's on top of the image and shading
            self._update_shading(rect) # Update shading for this newly drawn rect
            if self.debug_mode:
                print(f"DEBUG: _update_crop_rect: New crop_rect_item and shading added for rect: {rect}")
        else:
            if self.debug_mode:
                print("DEBUG: _update_crop_rect: Rect is too small or empty, not drawing.")
            # Ensure crop_rect_item is None if not drawn
            self.crop_rect_item = None # Explicitly set to None if not drawn or too small


        self.crop_button.setEnabled(self.crop_rect_item is not None and not self.crop_rect_item.rect().isEmpty())

    def _update_shading(self, current_crop_rect):
        """
        Updates the shading overlay based on the given current_crop_rect.
        This method is called by both drawing and resizing operations.
        """
        # Remove old shading item
        if self.shading_item:
            self.graphics_scene.removeItem(self.shading_item)
            self.shading_item = None
            if self.debug_mode:
                print("DEBUG: _update_shading: Removed old shading_item (from previous update).")


        # Get the pixmap item that holds the image
        pixmap_items = [item for item in self.graphics_scene.items() if isinstance(item, QGraphicsPixmapItem)]
        if not pixmap_items:
            if self.debug_mode:
                print("DEBUG: _update_shading: No pixmap item found in scene for shading.")
            return
        image_pixmap_item = pixmap_items[0]
        pixmap_rect = image_pixmap_item.boundingRect()
        if self.debug_mode:
            print(f"DEBUG: _update_shading: Image pixmap rect: {pixmap_rect}")


        # Create a single shading path
        shading_path = QPainterPath()
        shading_path.addRect(pixmap_rect) # Add the outer rectangle (image bounds)
        shading_path.addRect(current_crop_rect) # Add the inner rectangle (selection)

        # Use XOR combine mode to create a "hole"
        combined_path = shading_path.simplified()

        self.shading_item = QGraphicsPathItem(combined_path)
        self.shading_item.setBrush(QBrush(QColor(0, 0, 0, 150))) # Semi-transparent black
        self.shading_item.setPen(QPen(Qt.NoPen)) # No border for the shading
        self.shading_item.setZValue(0.5) # Above the image, below the selection rectangle
        self.graphics_scene.addItem(self.shading_item)
        if self.debug_mode:
            print(f"DEBUG: _update_shading: New shading item added for crop rect: {current_crop_rect}")


    def _reset_crop(self):
        """
        Re-sets the cropping selection and displays the original image.
        This now calls _clear_image_display_and_crop_state() to reset image related state.
        """
        if self.debug_mode:
            print("DEBUG: _reset_crop called.")
        if self.initial_loaded_pixmap: # Use initial_loaded_pixmap
            self._clear_image_display_and_crop_state() # Clear image display and crop state
            self._display_image(self.initial_loaded_pixmap) # Redisplay initial loaded image
            self.crop_button.setEnabled(False) # No selection initially
            self.reset_crop_button.setEnabled(True) # Can still reset again if needed
            self.next_button.setEnabled(False) # Needs re-cropping/resizing
        else:
            self._reset_all_dialog_state() # If no initial_loaded_pixmap, reset fully
        if self.debug_mode:
            print("DEBUG: Crop reset complete.")

    def _perform_crop(self):
        """
        Performs the cropping operation based on the selected rectangle.
        Then resizes the cropped image to 1920x1080.
        """
        if self.debug_mode:
            print("DEBUG: _perform_crop called.")
        if self.current_display_pixmap is None or self.crop_rect_item is None:
            QMessageBox.warning(self, self.i18n.get_string("warning_title"),
                                self.i18n.get_string("no_crop_selection_message"))
            if self.debug_mode:
                print("DEBUG: _perform_crop: No current_display_pixmap or crop item.")
            return

        crop_rect_scene = self.crop_rect_item.rect()
        if self.debug_mode:
            print(f"DEBUG: _perform_crop: Crop rect in scene: {crop_rect_scene}")

        # Get the QImage from the QPixmap
        # This is a potential crash point if current_display_pixmap is invalid
        try:
            original_image = self.current_display_pixmap.toImage()
            if self.debug_mode:
                print(f"DEBUG: _perform_crop: Original image from current_display_pixmap size: {original_image.size()}")
        except Exception as e:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 f"Error converting QPixmap to QImage: {e}")
            if self.debug_mode:
                print(f"ERROR: Failed to convert current_display_pixmap to QImage: {e}")
            return


        # Get the pixmap item that holds the image
        pixmap_items = [item for item in self.graphics_scene.items() if isinstance(item, QGraphicsPixmapItem)]
        if not pixmap_items:
            QMessageBox.critical(self, self.i18n.get_string("error_title"), self.i18n.get_string("image_item_not_found"))
            if self.debug_mode:
                print("DEBUG: _perform_crop: Image item not found in scene.")
            return
        pixmap_item = pixmap_items[0]

        # Map the crop rectangle from scene coordinates to the pixmap item's local coordinates
        # This gives us coordinates relative to the original image's pixels
        crop_rect_item_local = pixmap_item.mapFromScene(crop_rect_scene).boundingRect()

        # Convert to QRect for QImage.copy()
        crop_rect_pixels = crop_rect_item_local.toRect()
        if self.debug_mode:
            print(f"DEBUG: _perform_crop: Crop rect in pixels: {crop_rect_pixels}")

        # Ensure crop_rect_pixels is within the bounds of the original_image
        image_rect = original_image.rect()
        # This is another potential crash point if original_image is invalid
        try:
            cropped_image = original_image.copy(crop_rect_pixels.intersected(image_rect))
            if self.debug_mode:
                print(f"DEBUG: _perform_crop: Cropped image size: {cropped_image.size()}")
        except Exception as e:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 f"Error copying image data: {e}")
            if self.debug_mode:
                print(f"ERROR: Failed to copy image data: {e}")
            return


        if cropped_image.isNull():
            QMessageBox.warning(self, self.i18n.get_string("warning_title"),
                                self.i18n.get_string("crop_failed_message"))
            if self.debug_mode:
                print("DEBUG: _perform_crop: Cropped image is null.")
            return

        self.cropped_image_data = cropped_image # Store the QImage data

        # NEW: Save the intermediate cropped image to a temporary file
        # This path will be used for the 'cropped_image_path' in the Floor data model
        temp_cropped_filename = f"floor_cropped_temp_{os.urandom(4).hex()}.png"
        self.intermediate_cropped_image_path = os.path.join(self.temp_project_dir_path, temp_cropped_filename)
        try:
            if not self.cropped_image_data.save(self.intermediate_cropped_image_path, "PNG"):
                QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                     f"Failed to save intermediate cropped image to '{self.intermediate_cropped_image_path}'.")
                self.intermediate_cropped_image_path = None # Clear path if save fails
                if self.debug_mode:
                    print(f"ERROR: Failed to save intermediate cropped image: {self.intermediate_cropped_image_path}")
                return
            if self.debug_mode:
                print(f"DEBUG: Intermediate cropped image saved to: {self.intermediate_cropped_image_path}")
        except Exception as e:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 f"Exception saving intermediate cropped image: {e}")
            self.intermediate_cropped_image_path = None
            if self.debug_mode:
                print(f"ERROR: Exception during saving intermediate cropped image: {e}")
            return


        # Resize to 1920x1080, maintaining aspect ratio
        target_width = 1920
        target_height = 1080
        scaled_image = QImage(target_width, target_height, QImage.Format_RGB32) # Create a blank image

        # Get the color of the top-left pixel of the cropped image
        # This assumes the top-left pixel is representative of the desired background color.
        if not cropped_image.isNull() and cropped_image.width() > 0 and cropped_image.height() > 0:
            background_color = cropped_image.pixelColor(0, 0) # Get color of top-left pixel
            if self.debug_mode:
                print(f"DEBUG: Using cropped image's top-left pixel color for background: {background_color.name()}")
        else:
            background_color = Qt.white # Fallback to white if cropped image is invalid
            if self.debug_mode:
                print("DEBUG: Cropped image invalid, falling back to white background.")

        scaled_image.fill(background_color) # Fill with the determined background color

        painter = QPainter(scaled_image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Calculate scaling to fit cropped_image into 1920x1080 while maintaining aspect ratio
        img_width = cropped_image.width()
        img_height = cropped_image.height()

        # Avoid division by zero if image has zero dimensions
        if img_width == 0 or img_height == 0:
            QMessageBox.warning(self, self.i18n.get_string("warning_title"),
                                "Cropped image has zero dimensions, cannot scale.")
            if self.debug_mode:
                print("ERROR: Cropped image has zero dimensions, cannot scale.")
            return

        scale_w = target_width / img_width
        scale_h = target_height / img_height
        scale = min(scale_w, scale_h)

        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # Calculate position to center the image
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2

        # Draw the scaled cropped image onto the blank canvas
        painter.drawImage(QRect(x_offset, y_offset, new_width, new_height), cropped_image)
        painter.end()

        # Display the scaled image
        self.current_display_pixmap = QPixmap.fromImage(scaled_image) # Update current_display_pixmap
        self.graphics_scene.clear()
        self.crop_rect_item = None # Explicitly clear reference
        self.shading_item = None    # Explicitly clear reference

        pixmap_item = QGraphicsPixmapItem(self.current_display_pixmap)
        self.graphics_scene.addItem(pixmap_item)
        self.graphics_scene.setSceneRect(pixmap_item.boundingRect())
        self.graphics_view.fitInView(pixmap_item, Qt.KeepAspectRatio)
        self.graphics_view.setSceneRect(pixmap_item.boundingRect()) # Set scene rect after fitInView
        self.graphics_view.viewport().update() # Force repaint

        self.crop_button.setEnabled(False) # Cropping done for this step
        self.reset_crop_button.setEnabled(True) # Can reset to initial loaded
        self.next_button.setEnabled(True) # Ready for next step (scale lines)

        if self.debug_mode:
            print(f"DEBUG: Image cropped and resized to 1920x1080. New current_display_pixmap size: {self.current_display_pixmap.size()}")


    def _validate_and_accept(self):
        """
        Validates the floor number and ensures an image has been processed
        before accepting the dialog.
        Also saves the final scaled image to the main window's temporary project directory.
        """
        if self.debug_mode:
            print("DEBUG: _validate_and_accept called.")
        floor_number = self.floor_number_input.text().strip()
        if not floor_number:
            QMessageBox.warning(self, self.i18n.get_string("validation_error_title"),
                                self.i18n.get_string("floor_number_mandatory_message"))
            if self.debug_mode:
                print("DEBUG: Validation failed: Floor number is empty.")
            return

        if self.current_display_pixmap is None or self.current_display_pixmap.isNull():
            QMessageBox.warning(self, self.i18n.get_string("validation_error_title"),
                                self.i18n.get_string("image_not_processed_message"))
            if self.debug_mode:
                print("DEBUG: Validation failed: No image processed.")
            return

        # Ensure intermediate_cropped_image_path exists
        if self.intermediate_cropped_image_path is None or not os.path.exists(self.intermediate_cropped_image_path):
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 "Intermediate cropped image path is missing or invalid. Please re-crop the image.")
            if self.debug_mode:
                print("ERROR: Validation failed: intermediate_cropped_image_path is missing.")
            return

        # Save the final 1920x1080 image to the main window's temporary project directory
        if not os.path.isdir(self.temp_project_dir_path):
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("temp_dir_error_message"))
            if self.debug_mode:
                print(f"ERROR: Main window temp project dir path invalid: {self.temp_project_dir_path}")
            return

        # Generate a unique filename for the floor image within the main window's temp dir
        temp_scaled_filename = f"floor_scaled_final_{os.urandom(4).hex()}.png"
        self.final_scaled_image_path = os.path.join(self.temp_project_dir_path, temp_scaled_filename)

        try:
            if not self.current_display_pixmap.save(self.final_scaled_image_path, "PNG"):
                QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                     self.i18n.get_string("image_save_error_message").format(path=self.final_scaled_image_path))
                # If saving fails, clear the path to prevent returning a bad path
                self.final_scaled_image_path = None
                if self.debug_mode:
                    print(f"ERROR: Failed to save final scaled image to: {self.final_scaled_image_path}")
                return
        except Exception as e:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 f"Error saving final image: {e}")
            self.final_scaled_image_path = None
            if self.debug_mode:
                print(f"ERROR: Exception during saving final image: {e}")
            return


        if self.debug_mode:
            print(f"DEBUG: Final scaled image saved by FloorImportDialog to: {self.final_scaled_image_path}")
        self.accept()

    def get_floor_data(self):
        """
        Returns the processed floor data (floor number, original image path,
        path to the cropped image, and the path to the scaled image).
        This method is called by the parent (e.g., MainWindow) after dialog acceptance.
        """
        if self.debug_mode:
            print(f"DEBUG: get_floor_data returning scaled_image_path: {self.final_scaled_image_path}")
            print(f"DEBUG: get_floor_data returning cropped_image_path: {self.intermediate_cropped_image_path}")
        return {
            "floor_number": self.floor_number_input.text().strip(),
            "original_image_path": self.file_path_input.text(),
            "cropped_image_path": self.intermediate_cropped_image_path, # Now includes this path
            "scaled_image_path": self.final_scaled_image_path
        }

# --- For standalone testing of the dialog (optional) ---
if __name__ == '__main__':
    # Dummy ConfigManager and I18nManager for standalone testing
    class DummyConfigManager:
        def __init__(self):
            self._config = {
                "language": "en_US",
                "poppler_path": "", # Set this to your Poppler bin directory for PDF testing
                "measurement_system": "Imperial"
            }
        def get(self, key, default=None):
            return self._config.get(key, default)
        def set(self, key, value):
            self._config[key] = value

    # Import the actual I18nManager from its new location
    from .i18n_manager import I18nManager as DummyI18nManager
    from PyQt5.QtWidgets import QApplication, QGraphicsProxyWidget

    app = QApplication(sys.argv)
    dummy_config = DummyConfigManager()
    i18n_dir_for_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'i18n')
    dummy_i18n = DummyI18nManager(i18n_dir=i18n_dir_for_test)

    # Create a dummy image for testing
    temp_test_image_path = os.path.join(i18n_dir_for_test, "dummy_floor_plan.png")
    if not os.path.exists(temp_test_image_path):
        # Create a simple 1920x1080 white image for testing
        dummy_image = QImage(1920, 1080, QImage.Format_RGB32)
        dummy_image.fill(Qt.white)
        dummy_image.save(temp_test_image_path)
        print(f"Created dummy image: {temp_test_image_path}")

    # Create dummy i18n directory and files for testing (if they don't exist)
    os.makedirs(i18n_dir_for_test, exist_ok=True)
    en_us_path = os.path.join(i18n_dir_for_test, 'en_US.txt')
    if not os.path.exists(en_us_path):
        with open(en_us_path, 'w', encoding='utf-8') as f:
            f.write("floor_import_title=Import Floor Plan\n")
            f.write("file_selection_group=File Selection\n")
            f.write("floor_number_label=Floor Number:\n")
            f.write("floor_number_placeholder=e.g., 1, Ground Floor, Basement\n")
            f.write("image_file_label=Image/PDF File:\n")
            f.write("browse_button=Browse...\n")
            f.write("select_image_file_title=Select Floor Plan Image or PDF\n")
            f.write("image_file_filter=Image Files (*.png *.jpg *.jpeg);;PDF Files (*.pdf);;All Files (*)\n")
            f.write("crop_button=Crop\n")
            f.write("reset_crop_button=Reset Crop\n")
            f.write("next_button=Next\n")
            f.write("cancel_button=Cancel\n")
            f.write("no_image_loaded_message=No image loaded. Please select an image or PDF file.\n")
            f.write("image_load_error_message=Could not load image from '{file_path}'.\n")
            f.write("poppler_not_configured_title=Poppler Not Configured\n")
            f.write("poppler_not_configured_message=Poppler binaries path is not set in Preferences. PDF conversion will not work.\n")
            f.write("poppler_executable_not_found_title=Poppler Executable Not Found\n")
            f.write("poppler_executable_not_found_message=Poppler executable '{exe}' not found. Please check your Poppler path in Preferences.\n")
            f.write("temp_dir_error_message=Failed to create temporary directory.\n")
            f.write("pdf_conversion_progress_format=Converting PDF... %p%\n")
            f.write("pdf_conversion_started=PDF conversion started...\n")
            f.write("converted_image_load_error=Could not load converted image from '{path}'.\n")
            f.write("pdf_output_file_missing=PDF conversion finished, but output file '{path}' is missing.\n")
            f.write("pdf_conversion_success=PDF converted successfully!\n")
            f.write("pdf_conversion_failed_title=PDF Conversion Failed\n")
            f.write("pdf_conversion_failed_message=PDF conversion failed.\\nExit Code: {exit_code}\\nError Output:\\n{error_output}\\n\n")
            f.write("poppler_process_start_error=Failed to start Poppler process: {error}\n")
            f.write("poppler_process_error=Poppler process error.\n")
            f.write("poppler_failed_to_start=Poppler process failed to start. Check path and permissions.\n")
            f.write("poppler_crashed=Poppler process crashed.\n")
            f.write("poppler_timed_out=Poppler process timed out.\n")
            f.write("poppler_read_error=Poppler process read error.\n")
            f.write("poppler_write_error=Poppler process write error.\n")
            f.write("poppler_unknown_error=Poppler process unknown error.\n")
            f.write("warning_title=Warning\n")
            f.write("no_crop_selection_message=Please draw a selection rectangle on the image first.\n")
            f.write("image_item_not_found=Image item not found in scene.\n")
            f.write("crop_failed_message=Cropping failed. Please try again.\n")
            f.write("info_title=Information\n")
            f.write("image_cropped_and_resized_message=Image cropped and resized to 1920x1080.\n")
            f.write("validation_error_title=Validation Error\n")
            f.write("floor_number_mandatory_message=Floor Number is a mandatory field.\n")
            f.write("image_not_processed_message=No image has been processed. Please load, crop, and resize an image.\n")
            f.write("image_save_error_message=Failed to save processed image to '{path}'.\n")
            f.write("no_floors_added_message=No floors added yet for '{site_name}'. Add the first floor via the 'Floor' menu.\n")
            f.write("current_floor_display_message=Displaying Floor {floor_number} for '{site_name}'.\n")
            f.write("no_project_for_floor_message=Please create or open a project first before adding floors.\n")
            f.write("floor_added_status=Floor {floor_number} added successfully.\n")
            f.write("floor_add_failed_status=Failed to add floor.\n")
            f.write("floor_add_cancelled_status=Floor addition cancelled.\n")
            f.write("new_project_cancelled_full_status=New project creation cancelled because no floor was added.\n")
            f.write("preferences_saved_status=Preferences saved.\n")
            f.write("scale_line_title=Set Scale Lines\n")
            f.write("scale_line_input_group=Define Scale Line\n")
            f.write("line_type_label=Line Type:\n")
            f.write("horizontal_line_type=Horizontal\n")
            f.write("vertical_line_type=Vertical\n")
            f.write("physical_dimension_label=Physical Dimension:\n")
            f.write("physical_dimension_placeholder=e.g., 40 feet, 10 meters\n")
            f.write("current_line_pixels_label=Current Line (Pixels):\n")
            f.write("pixels_label={pixels} px\n")
            f.write("calculated_scale_label=Calculated Scale:\n")
            f.write("current_scale_label={scale}\n")
            f.write("set_line_button=Set Line\n")
            f.write("unit_feet=ft\n")
            f.write("unit_meters=m\n")
            f.write("draw_line_first_message=Please draw a line on the image first.\n")
            f.write("physical_dimension_mandatory_message=Physical Dimension is a mandatory field.\n")
            f.write("horizontal_line_set_status=Horizontal scale line set to '{dim}'.\n")
            f.write("vertical_line_set_status=Vertical scale line set to '{dim}'.\n")
            f.write("at_least_one_scale_line_mandatory=Please set at least one scale line (horizontal or vertical).\n")
            f.write("select_line_type_message=Please select a line type (Horizontal or Vertical) first.\n")
            f.write("no_floor_to_set_scale_message=No floor is currently loaded to set scale lines.\n")
            f.write("scale_lines_set_status=Scale lines set for Floor {floor_number}.\n")
            f.write("scale_lines_cancelled_status=Scale line setup cancelled for Floor {floor_number}.\n")
            f.write("image_load_error_for_display=Could not load map for Floor {floor_number} of '{site_name}'.\n")
            f.write("no_map_for_current_floor_message=No map image available for Floor {floor_number} of '{site_name}'. Please add or edit the floor map.\n")

    # For standalone testing, create a dummy temporary directory
    temp_test_dir = QTemporaryDir()
    if not temp_test_dir.isValid():
        print("ERROR: Could not create temporary directory for standalone test.")
        sys.exit(1)
    temp_project_dir_path_for_test = temp_test_dir.path()
    print(f"DEBUG: Standalone test using temp dir: {temp_project_dir_path_for_test}")

    dialog = FloorImportDialog(dummy_config, dummy_i18n, temp_project_dir_path_for_test, debug_mode=True) # Pass debug_mode
    if dialog.exec_() == QDialog.Accepted:
        floor_data = dialog.get_floor_data()
        print("Floor Data Captured:")
        print(f"  Floor Number: {floor_data['floor_number']}")
        print(f"  Scaled Image Path: {floor_data['scaled_image_path']}")
        print(f"  Original Image Path: {floor_data['original_image_path']}")
        print(f"  Cropped Image Path: {floor_data['cropped_image_path']}") # New print for cropped path
    else:
        print("Floor Import Cancelled.")
    
    # Clean up the temporary directory created for standalone testing
    if temp_test_dir.isValid():
        temp_test_dir.remove()
        print(f"DEBUG: Cleaned up standalone test temporary directory: {temp_test_dir.path()}")

    sys.exit(app.exec_())
