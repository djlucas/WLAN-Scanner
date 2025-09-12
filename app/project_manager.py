#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/project_manager.py
#
# Description:
# Project file management for the WLAN Scanner application. Handles saving and
# loading projects in ZIP-based .wls format with JSON metadata and embedded
# image files.
# -----------------------------------------------------------------------------

import os
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .data_models import MapProject


class ProjectManager:
    """
    Manages saving and loading of WLAN Scanner projects in .wls format.
    
    The .wls file is a ZIP archive containing:
    - project.json: JSON serialized MapProject data
    - images/: Directory containing all floor plan images
        - original/: Original imported images  
        - cropped/: Cropped versions of images
        - scaled/: Final scaled (1920x1080) images for display
    """
    
    @staticmethod
    def save_project(project: MapProject, file_path: str, temp_dir: Optional[str] = None) -> bool:
        """
        Save a MapProject to a .wls file.
        
        Args:
            project: The MapProject to save
            file_path: Path where to save the .wls file
            temp_dir: Temporary directory containing project files (optional)
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Ensure file has .wls extension
            if not file_path.lower().endswith('.wls'):
                file_path += '.wls'
                
            # Create a temporary directory for building the archive
            with tempfile.TemporaryDirectory() as build_dir:
                
                # Create directory structure
                images_dir = os.path.join(build_dir, 'images')
                original_dir = os.path.join(images_dir, 'original')
                cropped_dir = os.path.join(images_dir, 'cropped') 
                scaled_dir = os.path.join(images_dir, 'scaled')
                
                os.makedirs(original_dir, exist_ok=True)
                os.makedirs(cropped_dir, exist_ok=True)
                os.makedirs(scaled_dir, exist_ok=True)
                
                # Copy image files and update paths in project data
                project_data = project.to_dict()
                
                for floor_idx, floor_data in enumerate(project_data['floors']):
                    floor_num = floor_data['floor_number']
                    
                    # Copy and update original image path
                    if floor_data['original_image_path'] and os.path.exists(floor_data['original_image_path']):
                        original_filename = f"floor_{floor_num}_original{Path(floor_data['original_image_path']).suffix}"
                        original_dest = os.path.join(original_dir, original_filename)
                        shutil.copy2(floor_data['original_image_path'], original_dest)
                        floor_data['original_image_path'] = f"images/original/{original_filename}"
                    
                    # Copy and update cropped image path
                    if floor_data['cropped_image_path'] and os.path.exists(floor_data['cropped_image_path']):
                        cropped_filename = f"floor_{floor_num}_cropped{Path(floor_data['cropped_image_path']).suffix}"
                        cropped_dest = os.path.join(cropped_dir, cropped_filename)
                        shutil.copy2(floor_data['cropped_image_path'], cropped_dest)
                        floor_data['cropped_image_path'] = f"images/cropped/{cropped_filename}"
                    
                    # Copy and update scaled image path
                    if floor_data['scaled_image_path'] and os.path.exists(floor_data['scaled_image_path']):
                        scaled_filename = f"floor_{floor_num}_scaled{Path(floor_data['scaled_image_path']).suffix}"
                        scaled_dest = os.path.join(scaled_dir, scaled_filename)
                        shutil.copy2(floor_data['scaled_image_path'], scaled_dest)
                        floor_data['scaled_image_path'] = f"images/scaled/{scaled_filename}"
                
                # Save project JSON
                project_json_path = os.path.join(build_dir, 'project.json')
                with open(project_json_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)
                
                # Create ZIP file
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(build_dir):
                        for file in files:
                            file_path_full = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path_full, build_dir)
                            zipf.write(file_path_full, arc_name)
                
                return True
                
        except Exception as e:
            print(f"Error saving project: {e}")
            return False
    
    @staticmethod
    def load_project(file_path: str, extract_dir: Optional[str] = None) -> Tuple[Optional[MapProject], Optional[str]]:
        """
        Load a MapProject from a .wls file.
        
        Args:
            file_path: Path to the .wls file to load
            extract_dir: Directory to extract project files to (creates temp if None)
            
        Returns:
            Tuple[MapProject, str]: Loaded project and extraction directory path,
                                   or (None, None) if loading failed
        """
        try:
            if not os.path.exists(file_path):
                print(f"Project file not found: {file_path}")
                return None, None
            
            # Create extraction directory
            if extract_dir is None:
                extract_dir = tempfile.mkdtemp(prefix='wls_project_')
            else:
                os.makedirs(extract_dir, exist_ok=True)
            
            # Extract ZIP file
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.extractall(extract_dir)
            
            # Load project JSON
            project_json_path = os.path.join(extract_dir, 'project.json')
            if not os.path.exists(project_json_path):
                print("project.json not found in .wls file")
                return None, None
            
            with open(project_json_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Convert relative paths to absolute paths
            for floor_data in project_data['floors']:
                if floor_data['original_image_path']:
                    floor_data['original_image_path'] = os.path.join(extract_dir, floor_data['original_image_path'])
                if floor_data['cropped_image_path']:
                    floor_data['cropped_image_path'] = os.path.join(extract_dir, floor_data['cropped_image_path'])
                if floor_data['scaled_image_path']:
                    floor_data['scaled_image_path'] = os.path.join(extract_dir, floor_data['scaled_image_path'])
            
            # Create MapProject from data
            project = MapProject.from_dict(project_data)
            
            return project, extract_dir
            
        except Exception as e:
            print(f"Error loading project: {e}")
            return None, None
    
    @staticmethod
    def is_valid_project_file(file_path: str) -> bool:
        """
        Check if a file is a valid .wls project file.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            bool: True if file appears to be a valid .wls project
        """
        try:
            if not file_path.lower().endswith('.wls') or not os.path.exists(file_path):
                return False
                
            with zipfile.ZipFile(file_path, 'r') as zipf:
                # Check if required files exist
                file_list = zipf.namelist()
                if 'project.json' not in file_list:
                    return False
                
                # Try to parse project.json
                with zipf.open('project.json') as f:
                    project_data = json.load(f)
                    
                # Basic structure validation
                required_keys = ['site_info', 'floors', 'current_floor_index']
                if not all(key in project_data for key in required_keys):
                    return False
                    
                return True
                
        except Exception:
            return False
    
    @staticmethod
    def get_project_info(file_path: str) -> Optional[dict]:
        """
        Get basic project information without fully loading the project.
        
        Args:
            file_path: Path to .wls file
            
        Returns:
            dict: Project info with site_name, floor_count, etc. or None if failed
        """
        try:
            if not ProjectManager.is_valid_project_file(file_path):
                return None
                
            with zipfile.ZipFile(file_path, 'r') as zipf:
                with zipf.open('project.json') as f:
                    project_data = json.load(f)
                
                return {
                    'site_name': project_data['site_info'].get('site_name', 'Unnamed Site'),
                    'floor_count': len(project_data['floors']),
                    'current_floor_index': project_data.get('current_floor_index', 0),
                    'file_size': os.path.getsize(file_path)
                }
                
        except Exception:
            return None