#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/main_window.py
#
# Description:
# Main application window for the WLAN Scanner. Handles the primary UI layout,
# menu bar actions, project management, and coordinates interactions between
# different dialogs and components.
# -----------------------------------------------------------------------------

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QAction, QMessageBox,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDialog, QComboBox, QFileDialog, QActionGroup, QScrollArea
)
from PyQt5.QtCore import Qt, QTemporaryDir, QTimer
from PyQt5.QtGui import QPixmap

# Local imports from the 'app' package using relative imports
from .preferences_dialog import PreferencesDialog
from .site_info_dialog import SiteInformationDialog
from .floor_import_dialog import FloorImportDialog
from .scale_line_dialog import ScaleLineDialog
from .interactive_map_view import InteractiveMapView
from .data_models import MapProject, SiteInfo, Floor
from .project_manager import ProjectManager


class MainWindow(QMainWindow):
    """
    The main application window for the WLAN Scanner.
    Handles the main UI layout, menu bar actions, and orchestrates
    interactions with other dialogs and managers.
    """
    def __init__(self, config_manager, i18n_manager, debug_mode=False, parent=None):
        """
        Initializes the MainWindow.

        Args:
            config_manager: An instance of ConfigManager.
            i18n_manager: An instance of I18nManager for translations.
            debug_mode (bool): If True, enables extensive debug logging.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n_manager
        self.debug_mode = debug_mode
        if self.debug_mode:
            print("DEBUG: MainWindow initialized in DEBUG_MODE.")

        self.current_project = None # MapProject object
        self.project_temp_dir = None # Persistent QTemporaryDir for the project
        self.current_project_file_path = None # Path to the currently opened/saved .wls file
        self.project_modified = False # Track if project has unsaved changes

        self.setWindowTitle(self.i18n.get_string("app_title_placeholder"))
        self.setMinimumSize(1024, 768)

        self._init_ui()
        self._create_menus()
        self._check_initial_setup()

    def _init_ui(self):
        """
        Initializes the main user interface components and layout.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove main layout margins
        main_layout.setSpacing(0)  # Remove spacing between main widgets

        # Interactive map view wrapped in scroll area
        self.map_view = InteractiveMapView(self.i18n, debug_mode=self.debug_mode, parent=self)
        self.map_view.ap_placed.connect(self._on_ap_placed)
        self.map_view.scan_point_added.connect(self._on_scan_point_added)
        self.map_view.status_message.connect(self._on_status_update)
        self.map_view.request_instruction_update.connect(self._show_next_user_instruction)

        # Wrap map view in a scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.map_view)
        self.scroll_area.setWidgetResizable(False)  # Don't auto-resize the widget
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignCenter)  # Center the widget when smaller than scroll area
        main_layout.addWidget(self.scroll_area)

        # Custom status bar at bottom
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        status_layout.setSpacing(0)  # Remove spacing between widgets

        # Status message area (takes remaining space)
        self.status_label = QLabel(self.i18n.get_string("ready_status"))
        self.status_label.setStyleSheet("QLabel { padding: 4px 8px; }")
        self.status_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.status_label.setSizePolicy(self.status_label.sizePolicy().horizontalPolicy(), self.status_label.sizePolicy().Fixed)
        status_layout.addWidget(self.status_label, 1)  # stretch factor 1

        # Legend/Key area (fixed width)
        self.legend_label = QLabel("🔵 Scanned • 🟠 Need Scanning")
        self.legend_label.setStyleSheet("QLabel { padding: 4px 8px; border-left: 1px solid #ccc; color: #666; }")
        self.legend_label.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        self.legend_label.setMinimumWidth(160)
        self.legend_label.setSizePolicy(self.legend_label.sizePolicy().Fixed, self.legend_label.sizePolicy().Fixed)
        status_layout.addWidget(self.legend_label, 0)  # no stretch

        # Zoom display area (fixed width)
        self.zoom_label = QLabel(f"{self.i18n.get_string('zoom_label')} 100%")
        self.zoom_label.setStyleSheet("QLabel { padding: 4px 8px; border-left: 1px solid #ccc; }")
        self.zoom_label.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(80)
        self.zoom_label.setSizePolicy(self.zoom_label.sizePolicy().Fixed, self.zoom_label.sizePolicy().Fixed)
        status_layout.addWidget(self.zoom_label, 0)  # no stretch

        # Create status bar widget
        self.status_widget = QWidget()
        self.status_widget.setLayout(status_layout)
        self.status_widget.setStyleSheet("QWidget { border-top: 1px solid #ccc; background-color: #f0f0f0; }")
        self.status_widget.setFixedHeight(28)  # Use fixed height instead of min/max
        main_layout.addWidget(self.status_widget)

        # Floor selector
        self.floor_selector = QComboBox()
        self.floor_selector.setVisible(False)
        self.floor_selector.currentIndexChanged.connect(self._floor_selected)
        main_layout.addWidget(self.floor_selector)

    def _create_menus(self):
        """
        Creates the application's menu bar and populates it with actions.
        """
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu(self.i18n.get_string("menu_file"))
        new_project_action = QAction(self.i18n.get_string("menu_file_new_project"), self)
        new_project_action.triggered.connect(self._new_project)
        file_menu.addAction(new_project_action)

        open_project_action = QAction(self.i18n.get_string("menu_file_open_project"), self)
        open_project_action.triggered.connect(self._open_project)
        file_menu.addAction(open_project_action)

        save_project_action = QAction(self.i18n.get_string("menu_file_save_project"), self)
        save_project_action.triggered.connect(self._save_project)
        file_menu.addAction(save_project_action)

        save_project_as_action = QAction(self.i18n.get_string("menu_file_save_project_as"), self)
        save_project_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_project_as_action)

        file_menu.addSeparator()
        exit_action = QAction(self.i18n.get_string("menu_file_exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu(self.i18n.get_string("menu_edit"))
        preferences_action = QAction(self.i18n.get_string("menu_edit_preferences"), self)
        preferences_action.triggered.connect(self._open_preferences)
        edit_menu.addAction(preferences_action)

        edit_site_info_action = QAction(self.i18n.get_string("menu_edit_site_info"), self)
        edit_site_info_action.triggered.connect(self._edit_site_info)
        edit_menu.addAction(edit_site_info_action)

        # Floor Menu
        floor_menu = menu_bar.addMenu(self.i18n.get_string("menu_floor"))
        add_new_floor_action = QAction(self.i18n.get_string("menu_floor_add_new_floor"), self)
        add_new_floor_action.triggered.connect(lambda: self._add_new_floor(is_first_floor=False))
        floor_menu.addAction(add_new_floor_action)

        edit_current_floor_map_action = QAction(self.i18n.get_string("menu_floor_edit_current_floor_map"), self)
        edit_current_floor_map_action.triggered.connect(self._edit_current_floor_map)
        floor_menu.addAction(edit_current_floor_map_action)

        set_scale_lines_action = QAction(self.i18n.get_string("menu_floor_set_scale_lines"), self)
        set_scale_lines_action.triggered.connect(lambda: self._set_scale_lines_for_current_floor(is_first_floor_setup=False))
        floor_menu.addAction(set_scale_lines_action)

        # Scan Menu
        scan_menu = menu_bar.addMenu(self.i18n.get_string("menu_scan"))

        info_action = QAction("Place APs and Scan Points (Right-click on map)", self)
        info_action.setEnabled(False)  # Just informational
        scan_menu.addAction(info_action)

        scan_menu.addSeparator()

        # Left-click placement modes
        place_ap_action = QAction("Place AP (Left-click mode)", self)
        place_ap_action.setCheckable(True)
        place_ap_action.triggered.connect(self._toggle_place_ap_mode)
        scan_menu.addAction(place_ap_action)

        run_live_scan_action = QAction("Run Live Scan (Left-click mode)", self)
        run_live_scan_action.setCheckable(True)
        run_live_scan_action.triggered.connect(self._toggle_run_live_scan_mode)
        scan_menu.addAction(run_live_scan_action)

        scan_menu.addSeparator()
        clear_scan_data_action = QAction(self.i18n.get_string("clear_all_scan_data"), self)
        clear_scan_data_action.triggered.connect(lambda: self.map_view._clear_all_scan_data())
        scan_menu.addAction(clear_scan_data_action)

        # Store references to these actions for later use
        self.place_ap_action = place_ap_action
        self.run_live_scan_action = run_live_scan_action

        # Report Menu
        report_menu = menu_bar.addMenu(self.i18n.get_string("menu_report"))
        generate_pdf_report_action = QAction(self.i18n.get_string("menu_report_generate_pdf_report"), self)
        generate_pdf_report_action.triggered.connect(self._generate_pdf_report)
        report_menu.addAction(generate_pdf_report_action)

        export_map_image_action = QAction(self.i18n.get_string("menu_report_export_map_image"), self)
        export_map_image_action.triggered.connect(self._export_map_image)
        report_menu.addAction(export_map_image_action)

        # View Menu
        view_menu = menu_bar.addMenu(self.i18n.get_string("menu_view"))

        # Heatmap toggle
        self.heatmap_toggle_action = QAction("Show Signal Strength Heatmap", self)
        self.heatmap_toggle_action.setCheckable(True)
        self.heatmap_toggle_action.setChecked(False)
        self.heatmap_toggle_action.triggered.connect(self._toggle_heatmap)
        view_menu.addAction(self.heatmap_toggle_action)

        # Heatmap network selection submenu
        self.heatmap_network_menu = view_menu.addMenu("Select Heatmap Network")
        self.heatmap_network_menu.setEnabled(False)  # Disabled by default
        self._update_heatmap_network_menu()

        view_menu.addSeparator()

        zoom_in_action = QAction(self.i18n.get_string("menu_view_zoom_in"), self)
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction(self.i18n.get_string("menu_view_zoom_out"), self)
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)

        fit_to_window_action = QAction("Zoom: Fit to Window", self)
        fit_to_window_action.triggered.connect(self._fit_to_window)
        view_menu.addAction(fit_to_window_action)

        # Help Menu
        help_menu = menu_bar.addMenu(self.i18n.get_string("menu_help"))
        about_action = QAction(self.i18n.get_string("menu_help_about"), self)
        about_action.triggered.connect(self._about_dialog)
        help_menu.addAction(about_action)

    def _check_initial_setup(self):
        """
        Checks if initial application setup (preferences) is needed.
        If so, it opens the preferences dialog.
        """
        if self.config_manager.is_initial_setup_needed():
            QMessageBox.information(self, self.i18n.get_string("initial_setup_title"),
                                    self.i18n.get_string("initial_setup_complete_message"))
            self._open_preferences(is_initial_setup=True)

    def _open_preferences(self, is_initial_setup=False):
        """
        Opens the preferences dialog.
        """
        dialog = PreferencesDialog(self.config_manager, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            # Settings saved, update i18n manager if language changed
            self.i18n.set_language(self.config_manager.get("language", "en_US"))
            self.status_label.setText(self.i18n.get_string("ready_status"))
            if self.debug_mode:
                print("DEBUG: Preferences saved.")
        else:
            if is_initial_setup:
                QMessageBox.warning(self, self.i18n.get_string("initial_setup_warning_title"),
                                    self.i18n.get_string("initial_setup_cancel_message"))
            self.status_label.setText(self.i18n.get_string("ready_status"))
            if self.debug_mode:
                print("DEBUG: Preferences cancelled.")

    def _new_project(self):
        """
        Starts a new project by prompting for site information and then the first floor.
        """
        if self.debug_mode:
            print("DEBUG: Starting new project creation.")

        # 1. Get Site Information
        self.status_label.setText(self.i18n.get_string("collecting_site_info_status"))

        # Create a new SiteInfo object for the new project
        new_site_info = SiteInfo()
        site_info_dialog = SiteInformationDialog(new_site_info, self.i18n, parent=self)
        if site_info_dialog.exec_() == QDialog.Accepted:
            # Site info collected, proceed to add first floor
            self.status_label.setText(self.i18n.get_string("creating_project_status").format(site_name=new_site_info.site_name))

            self.current_project = MapProject(site_info=new_site_info)
            self.project_temp_dir = QTemporaryDir()
            self.project_modified = True  # New project needs to be saved
            self._update_window_title()
            self.status_label.setText(self.i18n.get_string("new_project_created_status").format(site_name=self.current_project.site_info.site_name))
            if self.debug_mode:
                print(f"DEBUG: New project created with site info: {self.current_project.site_info.to_dict()}")
            self._add_new_floor(is_first_floor=True)
        else:
            self.current_project = None # Ensure no partial project is created
            self.status_label.setText(self.i18n.get_string("new_project_cancelled_status"))
            if self.debug_mode:
                print("DEBUG: New project creation cancelled by user.")

    def _open_project(self):
        """
        Opens an existing project from a .wls file.
        """
        # Check if current project needs to be saved
        if not self._check_save_current_project():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open WLAN Scanner Project",
            "",
            "WLAN Scanner Projects (*.wls);;All Files (*)"
        )

        if not file_path:
            if self.debug_mode:
                print("DEBUG: Open project cancelled by user.")
            return

        if self.debug_mode:
            print(f"DEBUG: Attempting to open project: {file_path}")

        # Load the project
        project, extract_dir = ProjectManager.load_project(file_path)

        if project is None:
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                self.i18n.get_string("failed_load_project_message").format(file_path=file_path))
            if self.debug_mode:
                print(f"DEBUG: Failed to load project from {file_path}")
            return

        # Clean up old project temp directory if it exists
        if self.project_temp_dir and self.project_temp_dir.isValid():
            del self.project_temp_dir

        # Set up the new project
        self.current_project = project
        self.project_temp_dir = QTemporaryDir()
        if self.project_temp_dir.isValid():
            # Copy extracted files to our managed temp directory
            import shutil
            shutil.copytree(extract_dir, self.project_temp_dir.path(), dirs_exist_ok=True)

        self.current_project_file_path = file_path
        self.project_modified = False

        # Update UI
        self._update_floor_selector()
        self._display_current_floor_map()
        self._fit_to_window()  # Default to fit-to-window view when loading projects
        self._update_window_title()

        self.status_label.setText(f"Project '{self.current_project.site_info.site_name}' loaded successfully.")
        if self.debug_mode:
            print(f"DEBUG: Project loaded successfully from {file_path}")
            print(f"DEBUG: Site: {self.current_project.site_info.site_name}, Floors: {len(self.current_project.floors)}")

    def _save_project(self):
        """
        Saves the current project to its existing file, or prompts for location if new.
        """
        if self.current_project is None:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_project_to_save_message"))
            if self.debug_mode:
                print("DEBUG: Cannot save - no project loaded.")
            return

        # If no file path exists, use Save As
        if self.current_project_file_path is None:
            self._save_project_as()
            return

        if self.debug_mode:
            print(f"DEBUG: Saving project to {self.current_project_file_path}")

        # Save to existing file
        success = ProjectManager.save_project(
            self.current_project,
            self.current_project_file_path,
            self.project_temp_dir.path() if self.project_temp_dir and self.project_temp_dir.isValid() else None
        )

        if success:
            self.project_modified = False
            self._update_window_title()
            self.status_label.setText(f"Project '{self.current_project.site_info.site_name}' saved successfully.")
            if self.debug_mode:
                print(f"DEBUG: Project saved successfully to {self.current_project_file_path}")
        else:
            QMessageBox.critical(self, self.i18n.get_string("save_error_title"),
                                self.i18n.get_string("failed_save_project_message").format(file_path=self.current_project_file_path))
            if self.debug_mode:
                print(f"DEBUG: Failed to save project to {self.current_project_file_path}")

    def _save_project_as(self):
        """
        Saves the current project to a new location.
        """
        if self.current_project is None:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_project_to_save_message"))
            if self.debug_mode:
                print("DEBUG: Cannot save as - no project loaded.")
            return

        # Suggest default filename based on site name
        default_filename = self.current_project.site_info.site_name.replace(' ', '_')
        if not default_filename:
            default_filename = "WLAN_Survey"
        default_filename += ".wls"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save WLAN Scanner Project",
            default_filename,
            "WLAN Scanner Projects (*.wls);;All Files (*)"
        )

        if not file_path:
            if self.debug_mode:
                print("DEBUG: Save As cancelled by user.")
            return

        if self.debug_mode:
            print(f"DEBUG: Saving project as {file_path}")

        # Save to new file
        success = ProjectManager.save_project(
            self.current_project,
            file_path,
            self.project_temp_dir.path() if self.project_temp_dir and self.project_temp_dir.isValid() else None
        )

        if success:
            self.current_project_file_path = file_path
            self.project_modified = False
            self._update_window_title()
            self.status_label.setText(f"Project '{self.current_project.site_info.site_name}' saved to '{file_path}'.")
            if self.debug_mode:
                print(f"DEBUG: Project saved as {file_path}")
        else:
            QMessageBox.critical(self, self.i18n.get_string("save_error_title"),
                                self.i18n.get_string("failed_save_project_message").format(file_path=file_path))
            if self.debug_mode:
                print(f"DEBUG: Failed to save project as {file_path}")

    def _edit_site_info(self):
        """
        Opens the site information dialog to edit the current project's site info.
        """
        if self.current_project is None:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_project_loaded_message_short"))
            if self.debug_mode:
                print("DEBUG: Attempted to edit site info, but no project loaded.")
            return

        dialog = SiteInformationDialog(self.current_project.site_info, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self._mark_project_modified()
            self.status_label.setText(self.i18n.get_string("site_info_updated_status"))
            if self.debug_mode:
                print(f"DEBUG: Site information updated: {self.current_project.site_info.to_dict()}")
        else:
            self.status_label.setText(self.i18n.get_string("site_info_edit_cancelled_status"))
            if self.debug_mode:
                print("DEBUG: Site information edit cancelled.")

    def _add_new_floor(self, is_first_floor=False):
        """
        Adds a new floor to the current project.
        """
        if self.current_project is None:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_project_for_floor_message"))
            if self.debug_mode:
                print("DEBUG: Cannot add floor: No project loaded.")
            return

        if not self.project_temp_dir or not self.project_temp_dir.isValid():
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("temp_dir_error_message"))
            if self.debug_mode:
                print("ERROR: Project temporary directory is not valid.")
            return

        # Update status to indicate floor import is starting
        if is_first_floor:
            self.status_label.setText(self.i18n.get_string("importing_first_floor_status"))
        else:
            self.status_label.setText(self.i18n.get_string("importing_floor_status"))

        dialog = FloorImportDialog(self.config_manager, self.i18n, self.project_temp_dir.path(), debug_mode=self.debug_mode, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            floor_data = dialog.get_floor_data()
            if floor_data:
                new_floor = Floor(
                    floor_number=floor_data['floor_number'],
                    original_image_path=floor_data['original_image_path'],
                    cropped_image_path=floor_data['cropped_image_path'],
                    scaled_image_path=floor_data['scaled_image_path']
                )
                self.current_project.floors.append(new_floor)
                self.current_project.current_floor_index = len(self.current_project.floors) - 1
                self._mark_project_modified()
                self._update_floor_selector()
                self._display_current_floor_map()
                self._fit_to_window()  # Default to fit-to-window view for new floors
                self.status_label.setText(self.i18n.get_string("floor_added_status").format(floor_number=new_floor.floor_number))
                if self.debug_mode:
                    print(f"DEBUG: Floor {new_floor.floor_number} added to project. Original: {new_floor.original_image_path}, Cropped: {new_floor.cropped_image_path}, Scaled: {new_floor.scaled_image_path}")

                # After adding the floor, immediately open the ScaleLineDialog
                if new_floor.scaled_image_path and os.path.exists(new_floor.scaled_image_path):
                    self.status_label.setText(self.i18n.get_string("setting_scale_lines_status").format(floor_description=new_floor.floor_number))
                    self._set_scale_lines_for_current_floor(is_first_floor_setup=is_first_floor)
                else:
                    QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                        self.i18n.get_string("no_map_for_current_floor_message").format(
                                            floor_number=new_floor.floor_number,
                                            site_name=self.current_project.site_info.site_name
                                        ))
                    if self.debug_mode:
                        print(f"DEBUG: Cannot set scale lines: Scaled image not found for floor {new_floor.floor_number}.")
            else:
                self.status_label.setText(self.i18n.get_string("floor_add_failed_status"))
                if self.debug_mode:
                    print("DEBUG: Floor data not returned from dialog.")
                if is_first_floor:
                    # If it was the first floor setup and it failed, cancel project creation
                    self.current_project = None
                    self.status_label.setText(self.i18n.get_string("new_project_cancelled_full_status"))
        else:
            self.status_label.setText(self.i18n.get_string("floor_add_cancelled_status"))
            if self.debug_mode:
                print("DEBUG: Floor addition cancelled by user.")
            if is_first_floor:
                # If it was the first floor setup and it was cancelled, cancel project creation
                self.current_project = None
                self.status_label.setText(self.i18n.get_string("new_project_cancelled_full_status"))


    def _edit_current_floor_map(self):
        """
        Re-opens the FloorImportDialog for the current floor to allow editing its map.
        """
        if self.current_project is None or not self.current_project.floors:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_map_for_current_floor_message").format(
                                    floor_number="current", site_name="current project"
                                ))
            if self.debug_mode:
                print("DEBUG: Cannot edit floor map: No project or no floors loaded.")
            return

        current_floor = self.current_project.floors[self.current_project.current_floor_index]

        if not self.project_temp_dir or not self.project_temp_dir.isValid():
            QMessageBox.critical(self, self.i18n.get_string("error_title"),
                                 self.i18n.get_string("temp_dir_error_message"))
            if self.debug_mode:
                print("ERROR: Project temporary directory is not valid.")
            return

        # Pass existing image paths to the dialog for pre-filling/re-editing
        dialog = FloorImportDialog(
            self.config_manager, self.i18n, self.project_temp_dir.path(),
            debug_mode=self.debug_mode, parent=self,
            initial_floor_number=current_floor.floor_number,
            initial_original_image_path=current_floor.original_image_path
        )
        if dialog.exec_() == QDialog.Accepted:
            floor_data = dialog.get_floor_data()
            if floor_data:
                # Update the existing floor object with new data
                current_floor.floor_number = floor_data['floor_number']
                current_floor.original_image_path = floor_data['original_image_path']
                current_floor.cropped_image_path = floor_data['cropped_image_path']
                current_floor.scaled_image_path = floor_data['scaled_image_path']
                self._mark_project_modified()
                self._display_current_floor_map()
                self.status_label.setText(self.i18n.get_string("floor_added_status").format(floor_number=current_floor.floor_number)) # Re-using status message
                if self.debug_mode:
                    print(f"DEBUG: Floor {current_floor.floor_number} map updated. Original: {current_floor.original_image_path}, Cropped: {current_floor.cropped_image_path}, Scaled: {current_floor.scaled_image_path}")
            else:
                self.status_label.setText(self.i18n.get_string("floor_add_failed_status")) # Re-using status message
                if self.debug_mode:
                    print("DEBUG: Floor data not returned from dialog during edit.")
        else:
            self.status_label.setText(self.i18n.get_string("floor_add_cancelled_status")) # Re-using status message
            if self.debug_mode:
                print("DEBUG: Floor map edit cancelled by user.")


    def _set_scale_lines_for_current_floor(self, is_first_floor_setup):
        """
        Opens the ScaleLineDialog for the current floor.
        """
        if self.debug_mode:
            print(f"DEBUG: Calling _set_scale_lines_for_current_floor. is_first_floor_setup={is_first_floor_setup}")

        if self.current_project is None or not self.current_project.floors:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_floor_to_set_scale_message"))
            if self.debug_mode:
                print("DEBUG: Cannot set scale lines: No project or no floors loaded.")
            return

        current_floor = self.current_project.floors[self.current_project.current_floor_index]

        if not current_floor.scaled_image_path or not os.path.exists(current_floor.scaled_image_path):
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_map_for_current_floor_message").format(
                                    floor_number=current_floor.floor_number,
                                    site_name=self.current_project.site_info.site_name
                                ))
            if self.debug_mode:
                print(f"DEBUG: Cannot set scale lines: Scaled image not found for floor {current_floor.floor_number}.")
            return

        scale_line_dialog = ScaleLineDialog(current_floor.scaled_image_path, self.config_manager, self.i18n, debug_mode=self.debug_mode, parent=self)
        if scale_line_dialog.exec_() == QDialog.Accepted:
            h_line, v_line = scale_line_dialog.get_scale_lines()
            current_floor.scale_line_horizontal = h_line
            current_floor.scale_line_vertical = v_line
            self._mark_project_modified()
            self.status_label.setText(self.i18n.get_string("scale_lines_set_status").format(floor_number=current_floor.floor_number))

            # After a brief delay, show AP placement instruction
            QTimer.singleShot(2000, self._show_next_user_instruction)
            if self.debug_mode:
                print(f"DEBUG: Scale lines set for Floor {current_floor.floor_number}. H: {h_line.to_dict() if h_line else 'None'}, V: {v_line.to_dict() if v_line else 'None'}")
        else:
            self.status_label.setText(self.i18n.get_string("scale_lines_cancelled_status").format(floor_number=current_floor.floor_number))
            if self.debug_mode:
                print(f"DEBUG: Scale line setup cancelled for Floor {current_floor.floor_number}.")

    def _update_floor_selector(self):
        """Updates the floor selector dropdown with the current floors."""
        self.floor_selector.clear()
        if self.current_project and len(self.current_project.floors) > 1:
            for floor in self.current_project.floors:
                self.floor_selector.addItem(floor.floor_number)
            self.floor_selector.setCurrentIndex(self.current_project.current_floor_index)
            self.floor_selector.setVisible(True)
        else:
            self.floor_selector.setVisible(False)

    def _floor_selected(self, index):
        """Handles floor selection from the dropdown."""
        if self.current_project and index >= 0:
            self.current_project.current_floor_index = index
            self._display_current_floor_map()


    def _display_current_floor_map(self):
        """
        Displays the current floor in the interactive map view.
        """
        if self.current_project and self.current_project.floors:
            current_floor = self.current_project.floors[self.current_project.current_floor_index]
            self.map_view.set_floor(current_floor)
            self.status_label.setText(
                self.i18n.get_string("current_floor_display_message").format(
                    floor_number=current_floor.floor_number,
                    site_name=self.current_project.site_info.site_name
                )
            )
            if self.debug_mode:
                print(f"DEBUG: Displaying interactive map for Floor {current_floor.floor_number}.")
        else:
            self.map_view.set_floor(None)
            self.status_label.setText(self.i18n.get_string("ready_status"))
            if self.debug_mode:
                print("DEBUG: No project or no floors to display.")

    def resizeEvent(self, event):
        """
        Handles window resize events.
        """
        super().resizeEvent(event)

    def closeEvent(self, event):
        """
        Handles application close event with save check.
        """
        if self._check_save_current_project():
            event.accept()
        else:
            event.ignore()

    # Placeholder methods for other menu actions
    def _run_scan(self):
        QMessageBox.information(self, self.i18n.get_string("info_title"),
                                self.i18n.get_string("run_scan_not_implemented_message"))
        if self.debug_mode:
            print("DEBUG: Run Scan functionality called (not implemented).")

    def _configure_scan_tools(self):
        QMessageBox.information(self, self.i18n.get_string("info_title"),
                                self.i18n.get_string("configure_scan_tools_not_implemented_message"))
        if self.debug_mode:
            print("DEBUG: Configure Scan Tools functionality called (not implemented).")

    def _generate_pdf_report(self):
        QMessageBox.information(self, self.i18n.get_string("info_title"),
                                self.i18n.get_string("generate_pdf_report_not_implemented_message"))
        if self.debug_mode:
            print("DEBUG: Generate PDF Report functionality called (not implemented).")

    def _export_map_image(self):
        """Export the current map view as a PNG image"""
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtCore import QStandardPaths
        import os

        if self.current_project is None or not hasattr(self, 'map_view'):
            QMessageBox.warning(self, self.i18n.get_string("no_map_title"),
                                self.i18n.get_string("no_project_with_map_message"))
            return

        # Get the current map display pixmap from the map view
        current_pixmap = self.map_view.display_pixmap
        if not current_pixmap or current_pixmap.isNull():
            QMessageBox.warning(self, self.i18n.get_string("no_map_image_title"),
                                self.i18n.get_string("no_map_image_available_message"))
            return

        # Get default export location (Documents folder)
        documents_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        site_name = self.current_project.site_info.site_name if self.current_project else "map"
        default_filename = f"{site_name}_map_export.png"
        default_path = os.path.join(documents_path, default_filename)

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Map as Image",
            default_path,
            "PNG Images (*.png);;All Files (*)"
        )

        if file_path:
            try:
                # Save the pixmap as PNG
                success = current_pixmap.save(file_path, "PNG")
                if success:
                    QMessageBox.information(self, self.i18n.get_string("export_successful_title"),
                                            self.i18n.get_string("map_exported_message").format(file_path=file_path))
                    if self.debug_mode:
                        print(f"DEBUG: Map exported successfully to {file_path}")
                else:
                    QMessageBox.critical(self, self.i18n.get_string("export_failed_title"),
                                        self.i18n.get_string("failed_save_map_image_message"))
                    if self.debug_mode:
                        print(f"DEBUG: Failed to export map to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, self.i18n.get_string("export_error_title"),
                                    self.i18n.get_string("error_exporting_map_message").format(error=str(e)))
                if self.debug_mode:
                    print(f"DEBUG: Export error: {e}")

    def _toggle_heatmap(self):
        """Toggle heatmap display on/off"""
        if self.current_project is None:
            QMessageBox.warning(self, self.i18n.get_string("no_project_title"),
                                self.i18n.get_string("no_project_with_scan_data_message"))
            self.heatmap_toggle_action.setChecked(False)
            return

        # Get the checked state and toggle heatmap
        heatmap_enabled = self.heatmap_toggle_action.isChecked()

        if heatmap_enabled:
            # Get strongest network first
            strongest_ssid = self.map_view.get_strongest_network_ssid()

            # Set both network and enabled state in a single operation to avoid double generation
            self.map_view.set_heatmap_network_and_enable(strongest_ssid, True)

            if strongest_ssid:
                self.status_label.setText(f"Heatmap showing: {strongest_ssid}")
            else:
                self.status_label.setText("No scan data available for heatmap")

            self._update_heatmap_network_menu()
        else:
            # Disable heatmap
            self.map_view.set_heatmap_enabled(heatmap_enabled)
            self.status_label.setText("Signal strength heatmap disabled")

        # Enable/disable network selection menu
        self.heatmap_network_menu.setEnabled(heatmap_enabled)

        if self.debug_mode:
            print(f"DEBUG: Heatmap {status}")

    def _update_heatmap_network_menu(self):
        """Update the heatmap network selection menu with available networks"""
        self.heatmap_network_menu.clear()

        if not self.current_project:
            return

        # Get current network and available networks
        current_network = self.map_view.current_heatmap_network
        strongest_ssid = self.map_view.get_strongest_network_ssid()

        # Get available networks from current map
        available_networks = self.map_view.get_available_networks()

        if available_networks:
            # Create action group for radio button behavior
            self.heatmap_network_group = QActionGroup(self)

            for network in available_networks:
                action = QAction(network, self)  # Just show SSID, no "Network:" prefix
                action.setCheckable(True)
                action.triggered.connect(lambda checked, ssid=network: self._set_heatmap_network(ssid))

                # Block signals while setting initial checked state to avoid triggering during setup
                action.blockSignals(True)
                action.setChecked(network == current_network)  # Check if this is currently selected
                action.blockSignals(False)

                self.heatmap_network_group.addAction(action)
                self.heatmap_network_menu.addAction(action)

        if self.debug_mode:
            print(f"DEBUG: Updated heatmap network menu with {len(available_networks)} networks")

    def _set_heatmap_network(self, network_ssid):
        """Set the target network for heatmap display"""
        self.map_view.set_heatmap_network(network_ssid)

        network_name = network_ssid if network_ssid else "Strongest Signal"
        self.status_label.setText(f"Heatmap showing: {network_name}")

        if self.debug_mode:
            print(f"DEBUG: Heatmap network set to: {network_name}")

    def _toggle_place_ap_mode(self):
        """Toggle left-click AP placement mode"""
        is_checked = self.place_ap_action.isChecked()

        if is_checked:
            # Disable the other mode
            self.run_live_scan_action.setChecked(False)
            self.map_view.set_left_click_mode('place_ap')
            self.status_label.setText("Left-click AP placement mode enabled")
        else:
            self.map_view.set_left_click_mode(None)
            self.status_label.setText("Left-click AP placement mode disabled")

        if self.debug_mode:
            print(f"DEBUG: Place AP mode {'enabled' if is_checked else 'disabled'}")

    def _toggle_run_live_scan_mode(self):
        """Toggle left-click live scan mode"""
        is_checked = self.run_live_scan_action.isChecked()

        if is_checked:
            # Disable the other mode
            self.place_ap_action.setChecked(False)
            self.map_view.set_left_click_mode('live_scan')
            self.status_label.setText("Left-click live scan mode enabled")
        else:
            self.map_view.set_left_click_mode(None)
            self.status_label.setText("Left-click live scan mode disabled")

        if self.debug_mode:
            print(f"DEBUG: Live scan mode {'enabled' if is_checked else 'disabled'}")

    def _zoom_in(self):
        """Zoom in the map view"""
        if self.map_view:
            self.map_view.zoom_in()
        if self.debug_mode:
            print("DEBUG: Zoom In functionality called.")

    def _zoom_out(self):
        """Zoom out the map view"""
        if self.map_view:
            self.map_view.zoom_out()
        if self.debug_mode:
            print("DEBUG: Zoom Out functionality called.")

    def _fit_to_window(self):
        """Fit the map to the current window size"""
        if self.map_view:
            self.map_view.fit_to_window(self.scroll_area.size())
        if self.debug_mode:
            print("DEBUG: Fit to Window functionality called.")

    def update_zoom_display(self, zoom_percent):
        """Update the zoom level display in the status bar"""
        self.zoom_label.setText(f"{self.i18n.get_string('zoom_label')} {zoom_percent}%")

    def _about_dialog(self):
        QMessageBox.information(self, self.i18n.get_string("menu_help_about"), self.i18n.get_string("about_application_message"))
        if self.debug_mode:
            print("DEBUG: About dialog called.")

    def _on_ap_placed(self, placed_ap):
        """
        Handle signal when an AP is placed on the map

        Args:
            placed_ap (PlacedAP): The placed AP object
        """
        if self.debug_mode:
            print(f"DEBUG: AP '{placed_ap.name}' placed at ({placed_ap.map_x}, {placed_ap.map_y})")

        # Mark project as modified
        self._mark_project_modified()

        # Update status
        self.status_label.setText(f"Access Point '{placed_ap.name}' placed successfully")

        # After a brief delay, show next instruction
        QTimer.singleShot(2000, self._show_next_user_instruction)

    def _on_scan_point_added(self, scan_point):
        """
        Handle signal when a scan point is added to the map

        Args:
            scan_point (ScanPoint): The scan point object
        """
        if self.debug_mode:
            print(f"DEBUG: Scan point added at ({scan_point.map_x}, {scan_point.map_y}) with {len(scan_point.ap_list)} APs")

        # Mark project as modified
        self._mark_project_modified()

        # Update heatmap network menu if heatmap is enabled
        if hasattr(self, 'heatmap_toggle_action') and self.heatmap_toggle_action.isChecked():
            self._update_heatmap_network_menu()

        # Update status
        ap_count = len(scan_point.ap_list)
        self.status_label.setText(f"Scan point added - {ap_count} access points detected")

        # After a brief delay, show next instruction
        QTimer.singleShot(2000, self._show_next_user_instruction)

    def _on_status_update(self, message):
        """Handle status message updates from map view"""
        self.status_label.setText(message)

    def _check_save_current_project(self):
        """
        Check if the current project needs to be saved before proceeding.

        Returns:
            bool: True to proceed, False to cancel the operation
        """
        if self.current_project is None or not self.project_modified:
            return True

        reply = QMessageBox.question(
            self,
            "Save Changes?",
            f"The project '{self.current_project.site_info.site_name}' has unsaved changes.\n"
            "Do you want to save them before proceeding?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )

        if reply == QMessageBox.Save:
            self._save_project()
            return not self.project_modified  # Only proceed if save was successful
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def _update_window_title(self):
        """Update the main window title to reflect current project status."""
        base_title = self.i18n.get_string("app_title_placeholder")

        if self.current_project is None:
            self.setWindowTitle(base_title)
        else:
            site_name = self.current_project.site_info.site_name or "Unnamed Site"
            modified_indicator = "*" if self.project_modified else ""
            self.setWindowTitle(f"{base_title} - {site_name}{modified_indicator}")

    def _mark_project_modified(self):
        """Mark the current project as having unsaved changes."""
        if not self.project_modified:
            self.project_modified = True
            self._update_window_title()

    def _show_next_user_instruction(self):
        """Shows progressive instructions to guide user through the mapping process."""
        if not self.current_project or not self.current_project.floors:
            return

        current_floor = self.current_project.floors[self.current_project.current_floor_index]
        placed_aps = len(current_floor.placed_aps) if current_floor.placed_aps else 0
        scan_points = len(current_floor.scan_points) if current_floor.scan_points else 0

        if placed_aps == 0:
            # No APs placed yet - instruct user to place first AP
            self.status_label.setText(self.i18n.get_string("place_first_ap_instruction"))
        elif placed_aps == 1 and scan_points == 0:
            # First AP placed but no scan data - instruct to scan at AP or place scan points
            aps_without_data = self._count_aps_without_scan_data(current_floor)
            if aps_without_data > 0:
                self.status_label.setText(self.i18n.get_string("scan_at_ap_instruction"))
            else:
                self.status_label.setText(self.i18n.get_string("place_more_aps_instruction"))
        else:
            # Multiple APs or scan points exist - check status
            aps_without_data = self._count_aps_without_scan_data(current_floor)
            if aps_without_data > 0:
                self.status_label.setText(self.i18n.get_string("aps_need_scan_data_instruction").format(count=aps_without_data))
            else:
                self.status_label.setText(self.i18n.get_string("add_more_aps_or_scan_points_instruction"))

    def _count_aps_without_scan_data(self, floor):
        """Count APs that don't have scan data associated with them."""
        if not floor.placed_aps:
            return 0

        count = 0
        for ap in floor.placed_aps:
            # Check if there's a scan point at exactly this AP location
            has_scan_data = False
            if floor.scan_points:
                for scan_point in floor.scan_points:
                    # Scan data exists if coordinates match exactly
                    if scan_point.map_x == ap.map_x and scan_point.map_y == ap.map_y:
                        has_scan_data = True
                        break
            if not has_scan_data:
                count += 1
        return count

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

    # Ensure i18n directory exists for testing
    os.makedirs(i18n_dir_for_test, exist_ok=True)

    # Check if translation file exists - if not, the I18nManager will handle the fallback
    en_us_path = os.path.join(i18n_dir_for_test, 'en_US.txt')
    if not os.path.exists(en_us_path):
        print(f"Warning: Translation file not found at {en_us_path}")
        print("Please ensure the i18n/en_US.txt file exists in the project directory")
        print("The application will use the key names as fallback strings")

    # For standalone testing, create a dummy temporary directory
    temp_test_dir = QTemporaryDir()
    if not temp_test_dir.isValid():
        print("ERROR: Could not create temporary directory for standalone test.")
        sys.exit(1)
    temp_project_dir_path_for_test = temp_test_dir.path()
    print(f"DEBUG: Standalone test using temp dir: {temp_project_dir_path_for_test}")

    # Create a dummy image for testing that has black lines on a white background
    temp_test_image_path = os.path.join(temp_project_dir_path_for_test, "dummy_floor_plan_1920x1080.png")
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

    main_window = MainWindow(dummy_config, dummy_i18n, debug_mode=True)
    main_window.show()
    sys.exit(app.exec_())
