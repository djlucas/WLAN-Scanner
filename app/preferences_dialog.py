# app/preferences_dialog.py

import os
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QComboBox, QRadioButton,
    QGroupBox, QFileDialog, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt, QProcess

class PreferencesDialog(QDialog):
    """
    A dialog for configuring application preferences, including Poppler path,
    language, and measurement system. Scan script paths are now hardcoded.
    All UI labels and texts are now internationalized.
    """
    def __init__(self, config_manager, i18n_manager, parent=None):
        """
        Initializes the PreferencesDialog.

        Args:
            config_manager: An instance of ConfigManager for loading/saving settings.
            i18n_manager: An instance of I18nManager for translation.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n_manager
        self.setWindowTitle(self.i18n.get_string("preferences_title"))
        self.setMinimumWidth(500)

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """
        Sets up the user interface elements and layout for the preferences dialog.
        """
        main_layout = QVBoxLayout(self)

        # --- Paths Group Box ---
        paths_group = QGroupBox(self.i18n.get_string("preferences_paths_group"))
        paths_layout = QFormLayout()

        # Poppler Path (only path configuration remaining here)
        self.poppler_path_input = QLineEdit()
        self.poppler_browse_btn = QPushButton(self.i18n.get_string("browse_button"))
        self.poppler_browse_btn.clicked.connect(lambda: self._browse_directory_path(self.poppler_path_input))

        poppler_h_layout = QHBoxLayout()
        poppler_h_layout.addWidget(self.poppler_path_input)
        poppler_h_layout.addWidget(self.poppler_browse_btn)
        paths_layout.addRow(self.i18n.get_string("poppler_path_label"), poppler_h_layout)

        paths_group.setLayout(paths_layout)
        main_layout.addWidget(paths_group)

        # --- General Settings Group Box ---
        general_group = QGroupBox(self.i18n.get_string("preferences_general_group"))
        general_layout = QFormLayout()

        # Language Selection
        self.language_combo = QComboBox()
        self._populate_language_combo()
        general_layout.addRow(self.i18n.get_string("language_label"), self.language_combo)

        # Measurement System
        measurement_layout = QHBoxLayout()
        self.imperial_radio = QRadioButton(self.i18n.get_string("imperial_system"))
        self.metric_radio = QRadioButton(self.i18n.get_string("metric_system"))
        measurement_layout.addWidget(self.imperial_radio)
        measurement_layout.addWidget(self.metric_radio)
        measurement_layout.addStretch(1) # Push radios to the left
        general_layout.addRow(self.i18n.get_string("measurement_system_label"), measurement_layout)

        general_group.setLayout(general_layout)
        main_layout.addWidget(general_group)

        # --- Dialog Buttons ---
        button_layout = QHBoxLayout()
        self.save_button = QPushButton(self.i18n.get_string("save_button"))
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton(self.i18n.get_string("cancel_button"))
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1) # Push buttons to the right
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def _populate_language_combo(self):
        """
        Populates the language combo box by scanning the 'i18n' directory
        for .txt files (e.g., en_US.txt, es_ES.txt).
        """
        # Corrected path: go up one level from app/preferences_dialog.py to WLAN-Scanner/
        # then into i18n/
        i18n_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'i18n')
        if not os.path.exists(i18n_dir):
            print(f"Warning: i18n directory not found at {i18n_dir}")
            return

        languages = []
        for filename in os.listdir(i18n_dir):
            if filename.endswith(".txt"):
                lang_code = filename[:-4] # Remove .txt extension
                languages.append(lang_code)

        languages.sort() # Sort alphabetically
        self.language_combo.addItems(languages)

    def _load_settings(self):
        """
        Loads current settings from the ConfigManager and populates the UI fields.
        """
        # Removed loading of scan_scripts_win and scan_scripts_unix
        self.poppler_path_input.setText(self.config_manager.get("poppler_path", ""))

        # Set language combo box
        current_lang = self.config_manager.get("language", "en_US")
        index = self.language_combo.findText(current_lang)
        if index != -1:
            self.language_combo.setCurrentIndex(index)

        # Set measurement system radio buttons
        measurement_system = self.config_manager.get("measurement_system", "Imperial")
        if measurement_system == "Imperial":
            self.imperial_radio.setChecked(True)
        else:
            self.metric_radio.setChecked(True)

    def _save_settings(self):
        """
        Reads settings from the UI fields and saves them to the ConfigManager.
        """
        # Removed saving of scan_scripts_win and scan_scripts_unix
        self.config_manager.set("poppler_path", self.poppler_path_input.text())
        self.config_manager.set("language", self.language_combo.currentText())
        self.config_manager.set("measurement_system", "Imperial" if self.imperial_radio.isChecked() else "Metric")

    # Removed _browse_script_path and _test_script methods as they are no longer needed.

    def _browse_directory_path(self, line_edit):
        """
        Opens a directory dialog to select a directory (e.g., for Poppler binaries).
        """
        dir_path = QFileDialog.getExistingDirectory(
            self,
            self.i18n.get_string("select_directory_title"),
            line_edit.text() if line_edit.text() else os.path.expanduser("~")
        )
        if dir_path:
            line_edit.setText(dir_path)

    def accept(self):
        """
        Overrides QDialog.accept() to save settings before closing.
        """
        self._save_settings()
        super().accept()

    def reject(self):
        """
        Overrides QDialog.reject() to discard changes before closing.
        """
        super().reject()

# --- For standalone testing of the dialog (optional) ---
if __name__ == '__main__':
    # This block allows you to run and test preferences_dialog.py directly
    # without needing the full main.py setup.
    # It uses dummy ConfigManager and I18nManager for demonstration.
    class DummyConfigManager:
        def __init__(self):
            self._config = {
                "language": "en_US",
                "poppler_path": "",
                "measurement_system": "Imperial"
            }

        def get(self, key, default=None):
            return self._config.get(key, default)

        def set(self, key, value):
            self._config[key] = value
            print(f"Dummy Config set: {key} = {value}")

        def is_initial_setup_needed(self):
            return False

        def _save_config(self):
            print("Dummy config saved.")

    # Import the actual I18nManager from its new location
    # This path is relative to the current file (app/preferences_dialog.py)
    # It needs to go up one level (..) to 'app/' then find 'i18n_manager.py'
    from .i18n_manager import I18nManager as DummyI18nManager

    app = QApplication(sys.argv)
    dummy_config = DummyConfigManager()
    # For standalone testing, I18nManager needs the correct path to i18n directory
    # This path is relative to the current file (app/preferences_dialog.py)
    # It needs to go up one level (..) to 'app/' then up another (..) to 'WLAN-Scanner/' then find 'i18n/'
    i18n_dir_for_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'i18n')
    dummy_i18n = DummyI18nManager(i18n_dir=i18n_dir_for_test)

    # Create dummy i18n directory and files for testing language combo
    os.makedirs(i18n_dir_for_test, exist_ok=True)
    with open(os.path.join(i18n_dir_for_test, 'en_US.txt'), 'w', encoding='utf-8') as f:
        f.write("app_title_placeholder=WLAN Scanner Application\n")
        f.write("welcome_message_placeholder=Welcome to the WLAN Scanner!\n")
        f.write("initial_setup_title=Initial Setup\n")
        f.write("initial_setup_complete_message=Preferences saved. Application will now start.\n")
        f.write("initial_setup_warning_title=Setup Incomplete\n")
        f.write("initial_setup_cancel_message=Initial setup was cancelled. Some features may not work correctly.\n")
        f.write("preferences_title=Preferences\n")
        f.write("preferences_paths_group=Paths Configuration\n")
        f.write("poppler_path_label=Poppler Binaries Path:\n")
        f.write("browse_button=Browse...\n")
        f.write("preferences_general_group=General Settings\n")
        f.write("language_label=Language:\n")
        f.write("measurement_system_label=Measurement System:\n")
        f.write("imperial_system=Imperial\n")
        f.write("metric_system=Metric\n")
        f.write("save_button=Save\n")
        f.write("cancel_button=Cancel\n")
        f.write("select_directory_title=Select Directory\n")
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
        f.write("validation_error_title=Validation Error\n")
        f.write("site_name_mandatory_message=Site Name is a mandatory field.\n")
        f.write("default_measurement_system=Imperial\n") # Default measurement system
        f.write("no_project_loaded_message=No project loaded. Start a new project or open an existing one.\n")
        f.write("project_loaded_message=Project '{site_name}' loaded.\n")
        f.write("ready_status=Ready\n")
        f.write("menu_file=File\n")
        f.write("menu_file_new_project=New Project...\n")
        f.write("menu_file_open_project=Open Project...\n")
        f.write("menu_file_save_project=Save Project\n")
        f.write("menu_file_save_project_as=Save Project As...\n")
        f.write("menu_file_exit=Exit\n")
        f.write("menu_edit=Edit\n")
        f.write("menu_edit_preferences=Preferences...\n")
        f.write("menu_edit_site_info=Edit Site Info...\n")
        f.write("menu_floor=Floor\n")
        f.write("menu_floor_add_new_floor=Add New Floor...\n")
        f.write("menu_floor_edit_current_floor_map=Edit Current Floor Map...\n")
        f.write("menu_floor_set_scale_lines=Set Scale Lines...\n")
        f.write("menu_scan=Scan\n")
        f.write("menu_scan_run_scan=Run Scan (Current Location)\n")
        f.write("menu_scan_configure_scan_tools=Configure Scan Tools...\n")
        f.write("menu_report=Report\n")
        f.write("menu_report_generate_pdf_report=Generate PDF Report...\n")
        f.write("menu_view=View\n")
        f.write("menu_view_toggle_ap_list_panel=Toggle AP List Panel\n")
        f.write("menu_view_zoom_in=Zoom In\n")
        f.write("menu_view_zoom_out=Zoom Out\n")
        f.write("menu_help=Help\n")
        f.write("menu_help_about=About...\n")
        f.write("save_changes_title=Save Changes\n")
        f.write("save_changes_message=Do you want to save changes to the current project?\n")
        f.write("info_title=Information\n")
        f.write("save_not_implemented_message=Save functionality is not yet implemented.\n")
        f.write("new_project_created_status=New project '{site_name}' created.\n")
        f.write("new_project_cancelled_status=New project creation cancelled.\n")
        f.write("no_project_title=No Project\n")
        f.write("no_project_loaded_message_short=No project is currently loaded.\n")
        f.write("site_info_updated_status=Site information updated.\n")
        f.write("site_info_edit_cancelled_status=Site information edit cancelled.\n")

    with open(os.path.join(i18n_dir_for_test, 'es_ES.txt'), 'w', encoding='utf-8') as f:
        f.write("preferences_title=Preferencias\n")
        f.write("preferences_paths_group=Configuración de Rutas\n")
        f.write("poppler_path_label=Ruta Binarios Poppler:\n")
        f.write("browse_button=Examinar...\n")
        f.write("preferences_general_group=Configuración General\n")
        f.write("language_label=Idioma:\n")
        f.write("measurement_system_label=Sistema de Medida:\n")
        f.write("imperial_system=Imperial\n")
        f.write("metric_system=Métrico\n")
        f.write("save_button=Guardar\n")
        f.write("cancel_button=Cancelar\n")
        f.write("select_directory_title=Seleccionar Directorio\n")
        f.write("site_info_title=Información del Sitio\n")
        f.write("site_name_label=Nombre del Sitio (Obligatorio):\n")
        f.write("site_name_placeholder=Introduzca el nombre del sitio\n")
        f.write("contact_label=Persona de Contacto:\n")
        f.write("contact_placeholder=Introduzca el nombre de la persona de contacto\n")
        f.write("telephone_label=Número de Teléfono:\n")
        f.write("telephone_placeholder=Introduzca el número de teléfono\n")
        f.write("street_label=Dirección:\n")
        f.write("street_placeholder=Introduzca la dirección\n")
        f.write("city_label=Ciudad:\n")
        f.write("city_placeholder=Introduzca la ciudad\n")
        f.write("state_province_label=Estado/Provincia:\n")
        f.write("state_province_placeholder=Introduzca el estado o provincia\n")
        f.write("postal_code_label=Código Postal:\n")
        f.write("postal_code_placeholder=Introduzca el código postal\n")
        f.write("country_label=País:\n")
        f.write("country_placeholder=Introduzca el país\n")
        f.write("ok_button=Aceptar\n")
        f.write("validation_error_title=Error de Validación\n")
        f.write("site_name_mandatory_message=El nombre del sitio es un campo obligatorio.\n")
        f.write("default_measurement_system=Metric\n")
        f.write("no_project_loaded_message=No hay proyecto cargado. Inicie un nuevo proyecto o abra uno existente.\n")
        f.write("project_loaded_message=Proyecto '{site_name}' cargado.\n")
        f.write("ready_status=Listo\n")
        f.write("menu_file=Archivo\n")
        f.write("menu_file_new_project=Nuevo Proyecto...\n")
        f.write("menu_file_open_project=Abrir Proyecto...\n")
        f.write("menu_file_save_project=Guardar Proyecto\n")
        f.write("menu_file_save_project_as=Guardar Proyecto Como...\n")
        f.write("menu_file_exit=Salir\n")
        f.write("menu_edit=Editar\n")
        f.write("menu_edit_preferences=Preferencias...\n")
        f.write("menu_edit_site_info=Editar Información del Sitio...\n")
        f.write("menu_floor=Planta\n")
        f.write("menu_floor_add_new_floor=Añadir Nueva Planta...\n")
        f.write("menu_floor_edit_current_floor_map=Editar Mapa de Planta Actual...\n")
        f.write("menu_floor_set_scale_lines=Establecer Líneas de Escala...\n")
        f.write("menu_scan=Escanear\n")
        f.write("menu_scan_run_scan=Ejecutar Escaneo (Ubicación Actual)\n")
        f.write("menu_scan_configure_scan_tools=Configurar Herramientas de Escaneo...\n")
        f.write("menu_report=Informe\n")
        f.write("menu_report_generate_pdf_report=Generar Informe PDF...\n")
        f.write("menu_view=Ver\n")
        f.write("menu_view_toggle_ap_list_panel=Alternar Panel de Lista de PA\n")
        f.write("menu_view_zoom_in=Acercar\n")
        f.write("menu_view_zoom_out=Alejar\n")
        f.write("menu_help=Ayuda\n")
        f.write("menu_help_about=Acerca de...\n")
        f.write("save_changes_title=Guardar Cambios\n")
        f.write("save_changes_message=¿Desea guardar los cambios en el proyecto actual?\n")
        f.write("info_title=Información\n")
        f.write("save_not_implemented_message=La función de guardar aún no está implementada.\n")
        f.write("new_project_created_status=Nuevo proyecto '{site_name}' creado.\n")
        f.write("new_project_cancelled_status=Creación de nuevo proyecto cancelada.\n")
        f.write("no_project_title=Sin Proyecto\n")
        f.write("no_project_loaded_message_short=No hay ningún proyecto cargado actualmente.\n")
        f.write("site_info_updated_status=Información del sitio actualizada.\n")
        f.write("site_info_edit_cancelled_status=Edición de información del sitio cancelada.\n")

    dialog = PreferencesDialog(dummy_config, dummy_i18n)
    dialog.show()
    sys.exit(app.exec_())
