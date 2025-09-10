# 📡 WLAN Scanner

A desktop application built with Python and PyQt5 for conducting Wi-Fi site surveys. Visualize network data directly on your floor plans, manage multi-floor projects, and generate professional reports.

## 🚧 Development Status

**Current Status: Foundation Phase (~40% Complete)**

This project has a solid foundation with core UI components implemented, but WiFi scanning functionality is still in development.

### ✅ **Implemented Features**
- **Application Framework**: Complete PyQt5 application with debug modes
- **Configuration System**: Persistent settings with JSON storage
- **Internationalization**: Multi-language support with English translations
- **Project Creation**: Site information collection and new project workflow
- **Floor Plan Import**: Advanced PDF support with Poppler integration
- **Image Processing**: Automatic cropping, scaling to 1920x1080, aspect ratio handling  
- **Scale Line Management**: Intelligent line detection and physical dimension mapping
- **Data Models**: Complete object model for projects, floors, APs, and scan points
- **User Interface**: Full menu system, dialogs, and preferences management

### 🟡 **Partially Implemented**
- **Floor Management**: Can import and display floors, multi-floor navigation pending
- **Project Management**: New project creation works, save/load functionality is placeholder

### ❌ **Missing Core Features**
- **WiFi Scanning**: No actual wireless network scanning capability yet
- **Interactive Maps**: Cannot place or manage AP markers on floor plans
- **Scan Point Placement**: No ability to record survey points
- **Data Visualization**: No AP list tables or heatmap generation  
- **Project Persistence**: Cannot save/load complete projects
- **Report Generation**: PDF reporting system not implemented

### 📋 **Planned Features**
- **Project Management**: Create, load, and save multi-floor survey projects
- **Interactive Map**: Place, move, and visualize Access Point (AP) scan data on floor plans
- **Data Collection**: Run platform-specific scripts for collecting wireless network data
- **Report Generation**: Export comprehensive PDF reports of site surveys
- **User Feedback**: Real-time status updates with consistent UI messaging
- **Robust Error Handling**: Comprehensive error handling for all operations

### 🎯 **Next Development Priorities**
1. Interactive map markers and AP placement (`map_view.py`, `ap_manager.py`)
2. WiFi scanning implementation (`scan_manager.py`)
3. Project save/load functionality (`project_exporter.py`)
4. PDF report generation (`report_generator.py`)

**Current State**: The application can create projects, import floor plans, and set scale lines, but cannot yet perform actual WiFi surveys.

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

