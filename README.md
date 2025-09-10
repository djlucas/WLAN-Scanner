# 📡 WLAN Scanner

A desktop application built with Python and PyQt5 for conducting Wi-Fi site surveys. Visualize network data directly on your floor plans, manage multi-floor projects, and generate professional reports.

## 🚧 Development Status

**Current Status: Interactive Survey Phase (~70% Complete)**

The application now features a fully interactive map interface for AP placement and simulated scanning. Core survey functionality is operational with professional-grade workflow features.

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
- **🆕 Interactive Map Interface**: Right-click context menus for AP placement and scanning
- **🆕 AP Management**: Visual AP placement with drag-and-drop repositioning
- **🆕 Scan Point System**: Add simulated scan points with network detection data
- **🆕 Smart Workflow**: Immediate scan offers after AP placement with visual status indicators
- **🆕 Scan Data Management**: Clear and refresh scan data while preserving AP layouts
- **🆕 Simulated Scanning**: Realistic WiFi data generation matching actual scan script format

### 🟡 **Partially Implemented**
- **Floor Management**: Can import and display floors, multi-floor navigation pending
- **Project Management**: New project creation works, save/load functionality is placeholder

### ❌ **Missing Core Features**
- **Live WiFi Scanning**: Integration with actual wireless network scanning (simulated scanning works)
- **Data Visualization**: No AP list tables or heatmap generation  
- **Project Persistence**: Cannot save/load complete projects
- **Report Generation**: PDF reporting system not implemented

### 🎯 **Next Development Priorities**
1. **Live WiFi Integration**: Connect simulated scanning with actual `get-wlans.ps1`/`get-wlans.sh` scripts
2. **Data Visualization**: AP lists, signal strength tables, and coverage heatmaps
3. **Project Persistence**: Save/load complete projects with all AP and scan data
4. **Report Generation**: Professional PDF reports with maps, data tables, and recommendations

### 🎮 **Interactive Features Guide**

#### **AP Placement & Management:**
- **🔵 Blue APs** = Have scan data (surveyed)
- **🟠 Orange APs** = Need scanning (newly placed or data cleared)
- **Right-click empty space** → "Place Access Point Here" 
- **Right-click existing AP** → Smart context menu (Edit, Scan/Rescan, Clear data, Remove)
- **Left-click & drag** → Move APs to new positions

#### **Scanning Workflow:**
1. Right-click to place AP → Enter name → Choose to scan immediately
2. For existing APs: Right-click → "Scan at This AP" or "Rescan at This AP"  
3. Bulk operations: "Scan at All AP Locations" or "Clear All AP Scan Data"
4. Visual feedback: Scan points show as green circles with detected AP counts

#### **Site Survey Management:**
- **Initial Survey**: Place APs and scan each location
- **Site Refresh**: "Clear All AP Scan Data" → Re-scan locations for updated data
- **Flexible Layout**: Keep AP positions while refreshing scan data as needed

**Current State**: The application provides a complete interactive survey interface with simulated scanning. Ready for live WiFi integration.

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

4.  **Scan Scripts**:
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
   - Use "Scan at All AP Locations" for bulk scanning
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

