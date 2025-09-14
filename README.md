# 📡 WLAN Scanner

A desktop application built with Python and PyQt5 for conducting Wi-Fi site surveys. Visualize network data directly on your floor plans, manage multi-floor projects, and generate professional reports.

## 🚧 Development Status

**Current Status: Data Visualization Phase (~75% Complete)**

The application now features complete interactive survey functionality with project persistence, live WiFi scanning, and advanced heatmap visualization. Professional WiFi site survey workflow is fully operational with real-time signal analysis and optimized performance.

### ✅ **Recently Completed Features**
- **✨ Comprehensive AP Properties**: Full asset management with manufacturer, model, serial number, ethernet MAC address, and asset tag tracking
- **✨ Live WiFi Scanning**: Real WiFi network scanning with platform-specific scripts (Linux/Windows)
- **✨ Advanced Heatmap Engine**: Complete rewrite using AP source location estimation and signal propagation modeling
- **✨ Empirical Signal Analysis**: Uses real scan measurements to estimate AP locations and generate accurate coverage maps
- **✨ Signal Propagation Physics**: Implements path loss models (0.5 dB/ft for 2.4GHz, 0.6 dB/ft for 5GHz) based on empirical data
- **✨ Interactive Progress Feedback**: Real-time status updates during heatmap generation with multi-stage progress indication
- **✨ Enhanced Scan Point Management**: Right-click context menus for scan points with data viewing and management options
- **🐛 Zoom Performance Optimization**: Fixed QPainter segfault and eliminated heatmap recalculation during zoom operations
- **🐛 Interactive Map Stability**: Added safety checks and exception handling for painting operations
- **🚀 Performance Improvements**: Optimized heatmap generation (~5s) and eliminated double-generation issues
- **🎯 Enhanced User Experience**: Comprehensive status messaging, scroll bar navigation, and fit-to-window defaults
- **🔧 UI/UX Polish**: Custom status bar with legend, improved progress indicators, and internationalization support

### ✅ **Core Implemented Features**
- **Application Framework**: Complete PyQt5 application with debug modes
- **Configuration System**: Persistent settings with JSON storage
- **Internationalization**: Multi-language support with English translations
- **Project Creation**: Site information collection and new project workflow
- **Floor Plan Import**: Advanced PDF support with Poppler integration
- **Image Processing**: Automatic cropping, scaling to 1920x1080, aspect ratio handling  
- **Scale Line Management**: Intelligent line detection and physical dimension mapping
- **Data Models**: Complete object model for projects, floors, APs, and scan points
- **User Interface**: Full menu system, dialogs, and preferences management
- **Interactive Map Interface**: Right-click context menus for AP placement and scanning
- **AP Management**: Visual AP placement with drag-and-drop repositioning and comprehensive property tracking (manufacturer, model, serial number, ethernet MAC, asset tag)
- **Multi-Floor Navigation**: Floor selector dropdown for projects with multiple floors
- **Real-Time WiFi Scanning**: Live network detection with platform-specific optimization
- **Signal Strength Heatmaps**: Visual coverage maps with SSID-based network selection and progress tracking
- **Smart Workflow**: Immediate scan offers after AP placement with visual status indicators
- **Scan Data Management**: Clear and refresh scan data while preserving AP layouts
- **Advanced Map Controls**: Zoom with scroll bar navigation, fit-to-window defaults, and optimized rendering
- **Dual-Mode Scanning**: Empirical measurement analysis (V1) + theoretical RF prediction (V2 future)

### ❌ **Missing Core Features**
- **PDF Report Generation**: Professional reporting system with multiple output formats
  - **Executive Reports**: High-level coverage summaries with key metrics and recommendations
  - **Technical Reports**: Detailed signal analysis with AP specifications and measurement data
  - **Interference Analysis**: Channel utilization maps showing peak signal values across all channels
  - **Multi-Map Integration**: Floor plans, coverage heatmaps, and interference visualizations

### 🎯 **Next Development Priorities**
1. **Interference Map Engine**: Channel utilization analysis with peak signal aggregation across all detected networks
2. **Executive Report System**: High-level PDF reports with coverage summaries, key metrics, and professional recommendations
3. **Technical Report System**: Detailed PDF reports with comprehensive signal analysis, AP specifications, and measurement tables
4. **Multi-Map PDF Integration**: Embedding floor plans, signal heatmaps, and interference visualizations in report outputs

### 🔄 **V1/V2 Architecture**
- **V1 (Current)**: Empirical measurement-driven analysis using real scan data for accurate site assessment
- **V2 (Future)**: Theoretical RF prediction engine for AP placement optimization and "what-if" scenarios

### 🎮 **Interactive Features Guide**

#### **AP Placement & Management:**
- **🔵 Blue APs** = Have scan data (surveyed)
- **🟠 Orange APs** = Need scanning (newly placed or data cleared)
- **Right-click empty space** → "Place Access Point Here" 
- **Right-click existing AP** → Smart context menu (Edit Properties, Scan/Rescan, Clear data, Remove)
- **Left-click & drag** → Move APs to new positions

#### **Scanning Workflow:**
1. Right-click to place AP → Enter name → Choose to scan immediately
2. For existing APs: Right-click → "Scan at This AP" or "Rescan at This AP"
3. Bulk operations: "Clear All AP Scan Data" to reset survey data
4. Visual feedback: Scan points show as green circles with detected AP counts

#### **Site Survey Management:**
- **Initial Survey**: Place APs and scan each location
- **Site Refresh**: "Clear All AP Scan Data" → Re-scan locations for updated data
- **Flexible Layout**: Keep AP positions while refreshing scan data as needed

**Current State**: The application provides a complete interactive survey interface with live WiFi scanning and advanced heatmap visualization. Ready for professional site surveys.

## 🛠️ Prerequisites

Before running the application, ensure you have the following installed:

-   **Python 3.x**: The application is built with modern Python.
-   **Poppler**: A PDF rendering library. You must configure the path to its binaries in the application's preferences.
-   **PyQt5**: The GUI framework for the user interface.
-   **NumPy**: Required for heatmap mathematical operations and signal processing.
-   **SciPy**: Used for advanced interpolation and signal strength calculations.

## 🚀 Installation and Setup

1.  **Install Python 3.x**:

    **Windows Users**:
    - The recommended way to install Python is through the **[Microsoft Store](https://apps.microsoft.com/store/detail/python-310/9PJPW5LDXLZ5)**. This provides the simplest installation and setup.
    - Alternatively, you can use the installer from the [official Python website](https.www.python.org/downloads/windows/). If you use this method, ensure you **check the box that says "Add Python to PATH"** during installation.
  
    **Linux Users**:
    - Python 3 is usually pre-installed. You can check by opening a terminal and running `python3 --version`.
    - If it's not installed, use your package manager:
      - **Ubuntu/Debian**: `sudo apt update && sudo apt install python3 python3-pip`
      - **Fedora/CentOS**: `sudo dnf install python3 python3-pip`
      - **SUSE/openSUSE**: `sudo zypper install python3 python3-pip`

    **macOS Users**:
    - We recommend installing Python via [Homebrew](https://brew.sh/). If you have Homebrew installed, open a terminal and run:
      ```bash
      brew install python
      ```

2.  **Clone the repository**:

    ```bash
    git clone [https://github.com/djlucas/WLAN-Scanner.git]
    cd WLAN-Scanner
    ```

3.  **Install dependencies**:

    ** Windows and mac OS users**:
      ```
      pip install -r requirements.txt
      ```

    ** Linux Users**:
       - Review the contents of requiremnts.txt and install using your package manager.
         - Ubuntu/Debian: `sudo apt update && sudo apt install python3-pyqt5 python3-numpy python3-scipy `
         - Fedora/CentOS: `sudo dnf install python3-qt5 python3-numpy python3-scipy`
         - **SUSE/openSUSE**: `sudo zypper install python3-PyQt5 python3-numpy python3-scipy`

4.  **Configure Poppler**:
    The application needs the `poppler` binaries for PDF floor plan processing.
    
    **Windows Users**: Download and extract Poppler from:
    https://github.com/oschwartz10612/poppler-windows/releases
    
    Extract the contents to the `poppler/` subdirectory in your WLAN-Scanner folder. The application will automatically detect the binaries in either:
    - `poppler/Library/bin/pdftoppm.exe` (direct extraction)
    - `poppler/poppler-*/Library/bin/pdftoppm.exe` (versioned directories)
    
    Alternatively, extract to any location and set the path manually in Preferences.
    
    **Linux Users**: Install poppler through your package manager:
    - Ubuntu/Debian: `sudo apt update && sudo apt install poppler-utils`
    - Fedora/CentOS: `sudo dnf install poppler-utils`
    - **SUSE/openSUSE**: `sudo zypper install poppler-tools`
    - The application will automatically detect poppler if installed in system paths.
    
    **macOS Users**: Install poppler through Homebrew:
    - `brew install poppler`
    - The application will automatically detect poppler in Homebrew paths (`/opt/homebrew/bin` for Apple Silicon or `/usr/local/bin` for Intel Macs).

5.  **Scan Scripts**:
    The platform-specific scan scripts (`get-wlans.ps1` and `get-wlans.sh`) are included in the `scripts/` directory.

## ▶️ Usage

### Quick Start

```bash
python main.py
```

### Basic Survey Workflow

1. **Create New Project**: 
   - File → New Project → Enter site information
   - Import floor plan (PDF or image) → Crop and scale to 1920x1080
   - Set scale lines for accurate measurements

2. **Place Access Points**:
   - Right-click on floor plan → "Place Access Point Here"  
   - Enter AP name → Choose "Yes" to scan immediately
   - AP appears blue (scanned) or orange (needs scanning)

3. **Manage Scans**:
   - Right-click existing APs for context menu options
   - "Clear All AP Scan Data" to refresh survey data

4. **Interactive Navigation**:
   - Drag APs to reposition them on the floor plan
   - Green scan points show detected network counts
   - Status bar provides visual legend for AP colors

## 🤝 Contributing

I welcome contributions! Please feel free to fork the repository, open an issue, or submit a pull request.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the `LICENSE` file for details.

**Note**: This project uses PyQt5, which requires GPL v3 licensing for non-commercial applications under Qt's licensing terms.

