#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/i18n_manager.py
#
# Description:
# Internationalization manager for the WLAN Scanner application.
# Handles loading and retrieving translated strings from language files.
# -----------------------------------------------------------------------------

import os
import locale

class I18nManager:
    """
    Manages application internationalization by loading translations from text files.
    """
    def __init__(self, lang_code=None, i18n_dir=""):
        """
        Initializes the I18nManager with a specific language code and directory.
        If no lang_code is provided, detects from system environment.

        Args:
            lang_code (str, optional): The language code (e.g., "en_US", "es_ES").
                                     If None, auto-detects from system.
            i18n_dir (str): The absolute path to the directory containing translation files.
        """
        self.lang_code = lang_code or self._detect_system_language()
        self.i18n_dir = i18n_dir
        self.translations = {}
        self._load_translations()
        print(f"I18nManager initialized with language: {self.lang_code} from {self.i18n_dir}")

    def _detect_system_language(self):
        """
        Detects the system language from environment variables.

        Returns:
            str: The detected language code, defaults to 'en_US'.
        """
        # Try various environment variables in order of preference
        for env_var in ['LANG', 'LC_ALL', 'LC_MESSAGES', 'LANGUAGE']:
            lang = os.environ.get(env_var)
            if lang:
                # Extract language code (e.g., 'en_US.UTF-8' -> 'en_US')
                lang = lang.split('.')[0].split('@')[0]
                if '_' in lang:
                    return lang
                elif '-' in lang:
                    # Convert 'en-US' to 'en_US'
                    return lang.replace('-', '_')
                else:
                    # Just language code like 'en' -> 'en_US'
                    return f"{lang}_US" if lang == 'en' else f"{lang}_{lang.upper()}"

        # Fallback: try Python's locale detection
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                return system_locale
        except:
            pass

        # Final fallback
        return "en_US"

    def _load_translations(self):
        """
        Loads translations from the specified language's text file.
        Each line in the file should be in 'key=value' format.
        Lines starting with '#' are treated as comments.
        Falls back to en_US if the preferred language file doesn't exist.
        """
        # Try to load the preferred language
        filepath = os.path.join(self.i18n_dir, f"{self.lang_code}.txt")

        if os.path.exists(filepath):
            self._load_translation_file(filepath)
        elif self.lang_code != "en_US":
            # Fallback to en_US if preferred language doesn't exist
            print(f"Warning: Translation file not found: {filepath}")
            fallback_path = os.path.join(self.i18n_dir, "en_US.txt")
            if os.path.exists(fallback_path):
                print(f"Falling back to en_US translations")
                self._load_translation_file(fallback_path)
                self.lang_code = "en_US"  # Update to reflect actual loaded language
            else:
                print(f"Error: No translation files found in {self.i18n_dir}")
        else:
            print(f"Error: en_US translation file not found: {filepath}")

    def _load_translation_file(self, filepath):
        """
        Loads translations from a specific file path.

        Args:
            filepath (str): Path to the translation file to load.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        self.translations[key.strip()] = value.strip()
            print(f"Loaded translations from: {filepath}")
        except Exception as e:
            print(f"Error loading translations from {filepath}: {e}")

    def get_string(self, key):
        """
        Retrieves a translated string for the given key.

        Args:
            key (str): The key of the string to translate.

        Returns:
            str: The translated string, or the key itself if no translation is found.
        """
        return self.translations.get(key, key) # Return key itself if translation not found

    def set_language(self, new_lang_code):
        """
        Changes the current language and reloads translations.

        Args:
            new_lang_code (str): The new language code to set.
        """
        if self.lang_code != new_lang_code:
            self.lang_code = new_lang_code
            self.translations = {} # Clear old translations
            self._load_translations()
            print(f"Language changed to: {self.lang_code}")
