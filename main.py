#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# main.py
#
# Description:
# Main entry point for the WLAN Scanner application. Initializes the
# application, loads configuration, sets up internationalization, and
# starts the main window.
# -----------------------------------------------------------------------------

import sys
import os
import platform
from PyQt5.QtWidgets import QApplication, QMessageBox

# Ensure the 'app' directory is in the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.main_window import MainWindow
from app.config_manager import ConfigManager
from app.i18n_manager import I18nManager

def main():
    """
    Main entry point for the WLAN Scanner application.
    Initializes the application, loads configuration, sets up i18n,
    and starts the main window.
    """
    app = QApplication(sys.argv)

    # --- Determine Debug Mode from Environment Variable ---
    # Set WLAN_SCANNER_DEBUG=1 (or True/true) in your environment to enable debug logging.
    debug_mode = os.environ.get("WLAN_SCANNER_DEBUG", "0").lower() in ("1", "true")
    if debug_mode:
        print("DEBUG: WLAN_SCANNER_DEBUG environment variable detected. Debug mode is ON.")
    # ----------------------------------------------------

    # Determine the configuration file path
    # For cross-platform compatibility, use a hidden directory in the user's home
    home_dir = os.path.expanduser("~")
    app_config_dir = os.path.join(home_dir, ".WLAN-Scanner")
    config_file_name = "config.json"
    config_file_path = os.path.join(app_config_dir, config_file_name)
    if debug_mode:
        print(f"DEBUG: Configuration file path: {config_file_path}")

    # Initialize ConfigManager with the config file path
    config_manager = ConfigManager(config_file_path)

    # Initialize I18nManager
    # Determine the path to the i18n directory dynamically
    i18n_dir = os.path.join(os.path.dirname(__file__), 'i18n')
    i18n_manager = I18nManager(i18n_dir=i18n_dir)

    # Load initial language from config, default to en_US
    initial_language = config_manager.get("language", "en_US")
    i18n_manager.set_language(initial_language)
    if debug_mode: # Use the dynamically determined debug_mode
        # Corrected attribute name from .current_language to .lang_code
        print(f"DEBUG: I18nManager initialized with language: {i18n_manager.lang_code} from {i18n_manager.i18n_dir}")


    # Check for initial setup completion (e.g., Poppler path)
    # This logic can be expanded as more mandatory settings are identified
    poppler_path = config_manager.get("poppler_path")
    
    # Auto-detect poppler if not configured
    if not poppler_path or not os.path.exists(poppler_path):
        detected_path = None
        
        if platform.system() == "Windows":
            # Check for poppler/ subdirectory in project root
            project_root = os.path.dirname(__file__)
            
            # First check simple poppler/Library/bin structure
            local_poppler_path = os.path.join(project_root, "poppler", "Library", "bin")
            if os.path.exists(local_poppler_path) and os.path.exists(os.path.join(local_poppler_path, "pdftoppm.exe")):
                detected_path = local_poppler_path
            else:
                # Check for versioned poppler directories: poppler/poppler-*/Library/bin
                poppler_base_dir = os.path.join(project_root, "poppler")
                if os.path.exists(poppler_base_dir):
                    import glob
                    versioned_dirs = glob.glob(os.path.join(poppler_base_dir, "poppler-*", "Library", "bin"))
                    for versioned_path in versioned_dirs:
                        if os.path.exists(os.path.join(versioned_path, "pdftoppm.exe")):
                            detected_path = versioned_path
                            break
                
        elif platform.system() == "Linux":
            # Check common system paths for pdftoppm
            common_paths = ["/usr/bin", "/usr/local/bin", "/bin"]
            for path in common_paths:
                if os.path.exists(os.path.join(path, "pdftoppm")):
                    detected_path = path
                    break
                    
        elif platform.system() == "Darwin":  # macOS
            # Check common Homebrew paths
            homebrew_paths = [
                "/opt/homebrew/bin",  # Apple Silicon Macs
                "/usr/local/bin",     # Intel Macs
                "/usr/bin"            # System default
            ]
            for path in homebrew_paths:
                if os.path.exists(os.path.join(path, "pdftoppm")):
                    detected_path = path
                    break
        
        if detected_path:
            # Auto-configure the detected poppler path
            config_manager.set("poppler_path", detected_path)
            poppler_path = detected_path
            print(f"Auto-detected Poppler at: {detected_path}")
    
    if not poppler_path or not os.path.exists(poppler_path):
        # If Poppler path is still not set, MainWindow will prompt if needed
        pass

    # Create and show the main window, passing the debug mode
    main_window = MainWindow(config_manager, i18n_manager, debug_mode=debug_mode)
    main_window.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
