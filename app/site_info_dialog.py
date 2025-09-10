#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/site_info_dialog.py
#
# Description:
# Dialog for entering and editing site-specific information including
# site name, contact details, and complete address information.
# -----------------------------------------------------------------------------

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt

# Corrected to use relative imports for modules within the 'app' package
from .data_models import SiteInfo
# Import the actual I18nManager from its new location for the standalone test block
# For the main class, i18n_manager is passed in, so no direct import needed here.
# from .i18n_manager import I18nManager # This would be used if I18nManager was not passed in

class SiteInformationDialog(QDialog):
    """
    A dialog for entering and editing site-specific information, including
    name, contact, telephone, and detailed address fields.
    """
    def __init__(self, site_info, i18n_manager, parent=None):
        """
        Initializes the SiteInformationDialog.

        Args:
            site_info (SiteInfo): The SiteInfo object to populate and update.
            i18n_manager: An instance of I18nManager for translation.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.site_info = site_info
        self.i18n = i18n_manager
        self.setWindowTitle(self.i18n.get_string("site_info_title"))
        self.setMinimumWidth(400)
        self.setModal(True) # Make it a modal dialog

        self._init_ui()
        self._load_site_info()

    def _init_ui(self):
        """
        Sets up the user interface elements and layout for the site information dialog.
        """
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Site Name (Mandatory)
        self.site_name_input = QLineEdit()
        self.site_name_input.setPlaceholderText(self.i18n.get_string("site_name_placeholder"))
        form_layout.addRow(self.i18n.get_string("site_name_label"), self.site_name_input)

        # Contact
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText(self.i18n.get_string("contact_placeholder"))
        form_layout.addRow(self.i18n.get_string("contact_label"), self.contact_input)

        # Telephone
        self.telephone_input = QLineEdit()
        self.telephone_input.setPlaceholderText(self.i18n.get_string("telephone_placeholder"))
        form_layout.addRow(self.i18n.get_string("telephone_label"), self.telephone_input)

        # --- Address Fields ---
        # Street
        self.street_input = QLineEdit()
        self.street_input.setPlaceholderText(self.i18n.get_string("street_placeholder"))
        form_layout.addRow(self.i18n.get_string("street_label"), self.street_input)

        # City
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText(self.i18n.get_string("city_placeholder"))
        form_layout.addRow(self.i18n.get_string("city_label"), self.city_input)

        # State/Province
        self.state_province_input = QLineEdit()
        self.state_province_input.setPlaceholderText(self.i18n.get_string("state_province_placeholder"))
        form_layout.addRow(self.i18n.get_string("state_province_label"), self.state_province_input)

        # Postal Code
        self.postal_code_input = QLineEdit()
        self.postal_code_input.setPlaceholderText(self.i18n.get_string("postal_code_placeholder"))
        form_layout.addRow(self.i18n.get_string("postal_code_label"), self.postal_code_input)

        # Country
        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText(self.i18n.get_string("country_placeholder"))
        form_layout.addRow(self.i18n.get_string("country_label"), self.country_input)

        main_layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton(self.i18n.get_string("ok_button"))
        self.ok_button.clicked.connect(self._validate_and_accept)
        self.cancel_button = QPushButton(self.i18n.get_string("cancel_button"))
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1) # Push buttons to the right
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def _load_site_info(self):
        """
        Loads the current SiteInfo object's data into the UI fields.
        """
        self.site_name_input.setText(self.site_info.site_name)
        self.contact_input.setText(self.site_info.contact)
        self.telephone_input.setText(self.site_info.telephone)
        self.street_input.setText(self.site_info.street)
        self.city_input.setText(self.site_info.city)
        self.state_province_input.setText(self.site_info.state_province)
        self.postal_code_input.setText(self.site_info.postal_code)
        self.country_input.setText(self.site_info.country)

    def _save_site_info(self):
        """
        Reads data from the UI fields and updates the SiteInfo object.
        """
        self.site_info.site_name = self.site_name_input.text().strip()
        self.site_info.contact = self.contact_input.text().strip()
        self.site_info.telephone = self.telephone_input.text().strip()
        self.site_info.street = self.street_input.text().strip()
        self.site_info.city = self.city_input.text().strip()
        self.site_info.state_province = self.state_province_input.text().strip()
        self.site_info.postal_code = self.postal_code_input.text().strip()
        self.site_info.country = self.country_input.text().strip()

    def _validate_and_accept(self):
        """
        Validates mandatory fields before accepting the dialog.
        """
        if not self.site_name_input.text().strip():
            QMessageBox.warning(self, self.i18n.get_string("validation_error_title"),
                                self.i18n.get_string("site_name_mandatory_message"))
            return

        self._save_site_info()
        self.accept()

# --- For standalone testing of the dialog (optional) ---
if __name__ == '__main__':
    import sys
    # Corrected to use relative imports for dummy classes in standalone test
    from .data_models import SiteInfo as DummySiteInfo # Alias to avoid name conflict
    from .i18n_manager import I18nManager as DummyI18nManager # Import from the actual i18n_manager.py

    app = QApplication(sys.argv)
    dummy_site_info = DummySiteInfo(site_name="Example Site", city="Anytown")
    # For standalone testing, I18nManager needs the correct path to i18n directory
    # This path is relative to the current file (app/site_info_dialog.py)
    # It needs to go up one level (..) to 'WLAN-Scanner/' then find 'i18n/'
    i18n_dir_for_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'i18n')
    dummy_i18n = DummyI18nManager(i18n_dir=i18n_dir_for_test)

    # Create dummy i18n directory and files for testing (if they don't exist)
    os.makedirs(i18n_dir_for_test, exist_ok=True)
    en_us_path = os.path.join(i18n_dir_for_test, 'en_US.txt')
    if not os.path.exists(en_us_path):
        with open(en_us_path, 'w', encoding='utf-8') as f:
            f.write("site_info_title=Site Information\n")
            f.write("site_name_label=Site Name (Mandatory):\n")
            f.write("site_name_placeholder=Enter site name\n")
            f.write("contact_label=Contact Person:\n")
            f.write("contact_placeholder=Enter contact person's name\n")
            f.write("telephone_label=Telephone Number:\n")
            f.write("telephone_placeholder=Enter telephone number\n")
            f.write("street_label=Street Address:\n")
            f.write("street_placeholder=Enter street address\n")
            f.write("city_label=City:\n")
            f.write("city_placeholder=Enter city\n")
            f.write("state_province_label=State/Province:\n")
            f.write("state_province_placeholder=Enter state or province\n")
            f.write("postal_code_label=Postal Code:\n")
            f.write("postal_code_placeholder=Enter postal code\n")
            f.write("country_label=Country:\n")
            f.write("country_placeholder=Enter country\n")
            f.write("ok_button=OK\n")
            f.write("cancel_button=Cancel\n")
            f.write("validation_error_title=Validation Error\n")
            f.write("site_name_mandatory_message=Site Name is a mandatory field.\n")


    dialog = SiteInformationDialog(dummy_site_info, dummy_i18n)
    if dialog.exec_() == QDialog.Accepted:
        print("Site Info Saved:")
        print(f"  Site Name: {dummy_site_info.site_name}")
        print(f"  Contact: {dummy_site_info.contact}")
        print(f"  Telephone: {dummy_site_info.telephone}")
        print(f"  Street: {dummy_site_info.street}")
        print(f"  City: {dummy_site_info.city}")
        print(f"  State/Province: {dummy_site_info.state_province}")
        print(f"  Postal Code: {dummy_site_info.postal_code}")
        print(f"  Country: {dummy_site_info.country}")
    else:
        print("Site Info Cancelled.")
    sys.exit(app.exec_())
