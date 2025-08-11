# app/i18n_manager.py

import os

class I18nManager:
    """
    Manages application internationalization by loading translations from text files.
    """
    def __init__(self, lang_code="en_US", i18n_dir=""):
        """
        Initializes the I18nManager with a specific language code and directory.

        Args:
            lang_code (str): The language code (e.g., "en_US", "es_ES").
            i18n_dir (str): The absolute path to the directory containing translation files.
        """
        self.lang_code = lang_code
        self.i18n_dir = i18n_dir
        self.translations = {}
        self._load_translations()
        print(f"I18nManager initialized with language: {self.lang_code} from {self.i18n_dir}")

    def _load_translations(self):
        """
        Loads translations from the specified language's text file.
        Each line in the file should be in 'key=value' format.
        Lines starting with '#' are treated as comments.
        """
        filepath = os.path.join(self.i18n_dir, f"{self.lang_code}.txt")
        if os.path.exists(filepath):
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
        else:
            print(f"Warning: Translation file not found: {filepath}")

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
