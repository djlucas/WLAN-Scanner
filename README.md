# 📡 WLAN Scanner

NOTE: This project is only just geting started, I haven't even gotten to AP placement and storing scan data yet. I'll update this readme when the time comes.

A desktop application built with Python and PyQt5 for conducting Wi-Fi site surveys. Visualize network data directly on your floor plans, manage multi-floor projects, and generate professional reports.

## ✨ Features
-   **Project Management**: Create, load, and save multi-floor survey projects.
-   **Interactive Map**: Place, move, and visualize Access Point (AP) scan data on your floor plan images.
-   **Data Collection**: Run platform-specific scripts (`scan_win.ps1` for Windows, `scan_unix.sh` for Linux/Mac) to collect wireless network data.
-   **Report Generation**: Export a comprehensive PDF report of your site survey.
-   **Internationalization (i18n)**: Supports multiple languages with easily editable text files.
-   **User Feedback**: Provides real-time status updates and uses a custom message box for a consistent UI.
-   **Robust Error Handling**: Gracefully handles script execution, JSON parsing, and file I/O errors.

## 🛠️ Prerequisites

Before running the application, ensure you have the following installed:

-   **Python 3.x**: The application is built with modern Python.
-   **Poppler**: A PDF rendering library. You must configure the path to its binaries in the application's preferences.
-   **PyQt5**: The GUI framework.

You can install the Python dependencies using `pip` with the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## 🚀 Installation and Setup

1.  **Clone the repository**:

    ```bash
    git clone [https://github.com/djlucas/WLAN-Scanner.git]
    cd WLAN-Scanner
    ```

2.  **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Poppler**:
    The application needs the path to the `poppler` binaries (e.g., `pdftoppm.exe`). You will be prompted to set this path in the Preferences dialog upon the first launch.

4.  **Place Scan Scripts**:
    Ensure the platform-specific scan scripts (`scan_win.ps1` and `scan_unix.sh`) are in the root directory and are executable.

## ▶️ Usage

To start the application, simply run the main Python script:

```bash
python main.py
```

## 🤝 Contributing

I welcome contributions! Please feel free to fork the repository, open an issue, or submit a pull request.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

