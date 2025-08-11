# app/config_manager.py

import json
import os

class ConfigManager:
    """
    Manages application configuration, including loading from and saving to a JSON file.
    It also handles default values and checks for initial setup requirements.
    """
    def __init__(self, config_file_path):
        """
        Initializes the ConfigManager with the path to the configuration file.

        Args:
            config_file_path (str): The absolute path to the configuration JSON file.
        """
        self.config_file_path = config_file_path
        self.config = {}
        self._load_config()

    def _load_config(self):
        """
        Loads the configuration from the JSON file. If the file does not exist
        or is malformed, it initializes with an empty dictionary.
        """
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Configuration file '{self.config_file_path}' is malformed. Initializing with empty config.")
                self.config = {}
            except Exception as e:
                print(f"Error loading config file '{self.config_file_path}': {e}")
                self.config = {}
        else:
            print(f"Info: Configuration file '{self.config_file_path}' not found. Initializing with empty config.")
            self.config = {}

    def _save_config(self):
        """
        Saves the current configuration dictionary to the JSON file.
        Ensures the directory for the config file exists.
        """
        os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config file '{self.config_file_path}': {e}")

    def get(self, key, default=None):
        """
        Retrieves a configuration value by its key.

        Args:
            key (str): The key of the configuration setting.
            default: The default value to return if the key is not found.

        Returns:
            The value associated with the key, or the default value if not found.
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """
        Sets a configuration value and immediately saves the updated configuration.

        Args:
            key (str): The key of the configuration setting.
            value: The value to set for the key.
        """
        self.config[key] = value
        self._save_config()

    def is_initial_setup_needed(self):
        """
        Checks if essential configuration settings are missing, indicating
        that an initial setup (e.g., via a preferences dialog) is required.
        Scan script paths are now hardcoded and not checked here.

        Returns:
            bool: True if initial setup is needed, False otherwise.
        """
        # Removed 'scan_scripts_win' and 'scan_scripts_unix' from required_settings
        required_settings = [
            "language",
            "poppler_path",
            "measurement_system"
        ]
        for setting in required_settings:
            if self.get(setting) is None:
                return True
        return False

    def get_all_config(self):
        """
        Returns a copy of the entire configuration dictionary.

        Returns:
            dict: A copy of the current configuration.
        """
        return self.config.copy()
