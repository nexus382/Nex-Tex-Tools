"""
Nex Tex Tools - Tkinter Version
A utility for processing video game textures with various operations.
"""

#==============================================================================
# IMPORTS SECTION
#==============================================================================
import os
import sys
import shutil
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
import queue
import time
import webbrowser

#==============================================================================
# CONSTANTS AND CONFIGURATION
#==============================================================================
# Application version
VERSION = "0.6.0"

# Create a queue for thread communication
output_queue = queue.Queue()

# Theme colors
THEME_BG = "#151e21"  # Darker gray/teal (25% darker than before)
THEME_FG = "#ffffff"  # White text
THEME_ACCENT = "#2a4c54"  # Slightly lighter teal for accents
THEME_HIGHLIGHT = "#3e7783"  # Highlight color for buttons, etc.

# Ko-fi donation URL
DONATION_URL = "https://ko-fi.com/RomRevival"  

# Discord and Reddit URLs
DISCORD_URL = "https://discord.gg/G33xPYV9CE"
REDDIT_URL = "https://reddit.com/r/flycast_texture_packs"

# Color definitions for transparency fill tool
FILL_COLORS = {
    '1': {'name': 'Magenta', 'rgb': (255, 0, 255, 255)},
    '2': {'name': 'Neon Green', 'rgb': (0, 255, 0, 255)},
    '3': {'name': 'Cyan', 'rgb': (0, 255, 255, 255)},
    '4': {'name': 'Hot Pink', 'rgb': (255, 105, 180, 255)},
    '5': {'name': 'Bright Yellow', 'rgb': (255, 255, 0, 255)}
}

# Tool descriptions for display
TOOL_DESCRIPTIONS = {
    "1": """Move Images with Alpha Channel:
This tool scans through PNG files in the source directory and identifies images that 
have transparency (alpha channel). It then moves these files to the destination directory, 
leaving non-transparent images in the source directory.

Required: 
- Source Directory: Folder containing PNG images to scan
- Destination Directory: Folder where transparent images will be moved""",

    "2": """Flip Images Vertically:
This tool flips all PNG images in the specified folder upside down (vertically).
Useful for games where textures are stored in a flipped orientation.

Required:
- Source Directory: Folder containing PNG images to flip""",

    "3": """Remove Duplicate Files:
This tool identifies files that exist in both the source and destination directories
(based on filename) and removes the duplicate files from the destination directory.

Required:
- Source Directory: Primary folder with original files
- Destination Directory: Folder to check for and remove duplicates""",

    "4": """Detect PS2 Textures with Variable Alpha:
This tool identifies PS2 textures with variable alpha transparency (not just 128 values).
When found, these files are moved from the source to the destination folder.

Required:
- Source Directory: Folder containing PNG textures to scan
- Destination Directory: Folder where variable alpha textures will be moved""",

    "5": """Make Alpha 128 Solid:
This tool changes semi-transparent pixels (alpha=128) to fully opaque (alpha=255).
Useful for fixing semi-transparent textures in games where semi-transparency isn't needed.

Required:
- Source Directory: Folder containing PNG images to process""",

    "6": """Restore Alpha to 50%:
This tool changes fully opaque pixels (alpha=255) to semi-transparent (alpha=128).
This is the opposite of "Make Alpha 128 Solid" tool.

Required:
- Source Directory: Folder containing PNG images to process""",

    "7": """Fill Transparent Areas:
This tool fills completely transparent areas (alpha=0).
Useful for visualizing the shape of textures or checking for unwanted transparency.

Required:
- Source Directory: Folder containing PNG images to process
- Fill Color: Color to use for filling transparent areas""",

    "8": """Find and Replace:
This tool finds PNG files in the source directory that don't exist in the destination 
directory and copies only those new files to the destination directory. Useful when
integrating new texture dumps with existing collections.

Required:
- Source Directory: Folder containing new files to check
- Destination Directory: Existing folder to copy new files into""",

    "9": """BKP File Remover:
This tool removes all PNG files that start with 'BKP_' in the specified directory.
Useful for cleaning up backup files created during texture editing.

Required:
- Source Directory: Folder containing BKP_ files to remove""",

    "10": """Compare and Move:
This tool compares files between source and destination directories and copies files
from source to destination if they have matching filenames (overwriting in destination).
Only copies files that already exist in the destination directory. Useful for replacing
original textures with upscaled versions.

Required:
- Source Directory: Folder with modified/upscaled images
- Destination Directory: Target folder where matching files will be replaced"""
}

#==============================================================================
# UTILITY FUNCTIONS
#==============================================================================
def validate_directory(path, create=False):
    """Validates that a directory exists or creates it if requested"""
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    if create:
        if not os.path.exists(path):
            try:
                os.makedirs(path)
                print(f"Created directory: {path}")
                return path
            except Exception as e:
                print(f"Error creating directory {path}: {e}")
                return None
    if not os.path.exists(path):
        print(f"Error: Directory does not exist: {path}")
        return None
    if not os.path.isdir(path):
        print(f"Error: Path is not a directory: {path}")
        return None
    return path

def has_alpha(image_path):
    """Checks if an image has transparency (alpha channel)"""
    try:
        with Image.open(image_path) as img:
            if img.mode == 'RGBA':
                extrema = img.getextrema()
                if len(extrema) == 4:
                    return extrema[3][0] < 255
            return False
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return False

def process_directory_batch(input_dir, process_func, **kwargs):
    """Process all PNG files in a directory using the specified function"""
    input_dir = validate_directory(input_dir)
    if not input_dir:
        return False
    png_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                if f.lower().endswith('.png')]
    if not png_files:
        print(f"\nNo PNG files found in {input_dir}")
        return False
    processed = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_func, f, **kwargs) for f in png_files]
        for future in futures:
            if future.result():
                processed += 1
            else:
                errors += 1
    print(f"\nProcessing complete!")
    print(f"Total files processed: {processed}")
    print(f"Files with errors: {errors}")
    return True

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - CORE OPERATIONS
#==============================================================================
def process_alpha(image_path, make_solid=True):
    """
    Process alpha channel in an image
    If make_solid=True: Change alpha 128 to 255 (make semi-transparent solid)
    If make_solid=False: Change alpha 255 to 128 (make solid semi-transparent)
    """
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA':
                return
            data = list(img.getdata())
            new_data = []
            for r, g, b, a in data:
                if a == 0:
                    new_data.append((r, g, b, 0))
                elif make_solid and a == 128:
                    new_data.append((r, g, b, 255))
                elif not make_solid and a == 255:
                    new_data.append((r, g, b, 128))
                else:
                    new_data.append((r, g, b, a))
            img.putdata(new_data)
            img.save(image_path, 'PNG')
            return True
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return False

def fill_transparency(image_path, color_rgb, restore=False):
    """
    Fill transparent pixels with color or restore transparency
    If restore=False: Fill transparent pixels (alpha=0) with the specified color
    If restore=True: Change pixels of the specified color back to transparent
    """
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA':
                return
            data = list(img.getdata())
            new_data = []
            if not restore:
                for r, g, b, a in data:
                    if a == 0:
                        new_data.append(color_rgb)
                    else:
                        new_data.append((r, g, b, a))
            else:
                for r, g, b, a in data:
                    if (r, g, b, a) == color_rgb:
                        new_data.append((0, 0, 0, 0))
                    else:
                        new_data.append((r, g, b, a))
            img.putdata(new_data)
            img.save(image_path, 'PNG')
            return True
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return False

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 1: MOVE ALPHA PNGS
#==============================================================================
def move_alpha_pngs(source_dir, destination_dir):
    """
    Move all PNG files with alpha channel from source to destination directory
    """
    source_dir = validate_directory(source_dir)
    if not source_dir:
        return False
    destination_dir = validate_directory(destination_dir, create=True)
    if not destination_dir:
        return False
    total_files = 0
    moved_files = 0
    error_files = 0
    try:
        png_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.png')]
        if not png_files:
            print(f"\nNo PNG files found in {source_dir}")
            return False
        with ThreadPoolExecutor(max_workers=8) as executor:
            for filename in png_files:
                total_files += 1
                file_path = os.path.join(source_dir, filename)
                try:
                    if has_alpha(file_path):
                        dest_path = os.path.join(destination_dir, filename)
                        shutil.move(file_path, dest_path)
                        print(f"Moved {filename} to {destination_dir}")
                        moved_files += 1
                    else:
                        print(f"Skipped {filename} (no alpha channel)")
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    error_files += 1
        print(f"\nSummary:")
        print(f"Total PNG files found: {total_files}")
        print(f"Files moved (with alpha): {moved_files}")
        print(f"Files skipped (without alpha): {total_files - moved_files - error_files}")
        print(f"Files with errors: {error_files}")
        return True
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        return False

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 2: FLIP IMAGES
#==============================================================================
def flip_images(folder_path):
    """
    Flip all PNG images in the folder vertically (top to bottom)
    """
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' not found")
        return
    png_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                if f.lower().endswith('.png')]
    if not png_files:
        print("No PNG files found in the folder")
        return
    with ThreadPoolExecutor(max_workers=8) as executor:
        def flip_single(filepath):
            try:
                with Image.open(filepath) as img:
                    flipped_img = img.transpose(Image.FLIP_TOP_BOTTOM)
                    flipped_img.save(filepath)
                print(f"Flipped: {os.path.basename(filepath)}")
                return True
            except Exception as e:
                print(f"Error processing {os.path.basename(filepath)}: {str(e)}")
                return False
        list(executor.map(flip_single, png_files))

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 3: REMOVE DUPLICATE FILES
#==============================================================================
def list_duplicate_files(source_dir, dest_dir):
    """
    Find files that exist in both source and destination directories
    """
    source_files = set(file.name for file in source_dir.iterdir() if file.is_file())
    dest_files = [file for file in dest_dir.iterdir() if file.is_file() and file.name in source_files]
    return dest_files

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 4: DETECT PS2 TEXTURES
#==============================================================================
def process_single_image(args):
    """
    Helper function for detect_ps2_alpha - processes a single image
    """
    file_path, output_dir = args
    try:
        with Image.open(file_path) as img:
            if img.mode != 'RGBA':
                return None
            alpha = img.split()[3]
            alpha_values = set(alpha.getdata())
            if any(x != 128 for x in alpha_values):
                filename = os.path.basename(file_path)
                dest_path = os.path.join(output_dir, filename)
                shutil.move(file_path, dest_path)
                return filename
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return None

def detect_ps2_alpha(input_dir, output_dir):
    """
    Detect PS2 textures with variable alpha values and move them
    """
    print("\nStarting PS2 texture detection with multi-threading...")
    input_dir = validate_directory(input_dir)
    if not input_dir:
        return False
    output_dir = validate_directory(output_dir, create=True)
    if not output_dir:
        return False
    png_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                if f.lower().endswith('.png')]
    if not png_files:
        print(f"\nNo PNG files found in {input_dir}")
        return False
    total_files = len(png_files)
    print(f"\nFound {total_files} PNG files to process...")
    work_items = [(f, output_dir) for f in png_files]
    moved_files = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(process_single_image, work_items))
        moved_files = sum(1 for r in results if r is not None)
        for filename in (r for r in results if r is not None):
            print(f"Moved shaped texture: {filename}")
    print(f"\nProcessing complete!")
    print(f"Total PNG files processed: {total_files}")
    print(f"Files moved (with variable alpha): {moved_files}")
    print(f"Files skipped: {total_files - moved_files}")
    return True

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 8: FIND AND REPLACE
#==============================================================================
def find_and_replace(source_dir, dest_dir):
    """
    Find files in source directory that don't exist in destination directory
    and copy only those new files to the destination directory.
    """
    source_dir = validate_directory(source_dir)
    if not source_dir:
        return False
    dest_dir = validate_directory(dest_dir)
    if not dest_dir:
        return False
    
    # Get list of PNG files in source directory (new dump)
    source_files = [f for f in os.listdir(source_dir) 
                   if f.lower().endswith('.png') and os.path.isfile(os.path.join(source_dir, f))]
    
    total_files = len(source_files)
    if not source_files:
        print(f"\nNo PNG files found in source directory {source_dir}")
        return False
    
    # Get set of filenames that already exist in destination directory (old dump)
    existing_files = set(f for f in os.listdir(dest_dir) 
                      if f.lower().endswith('.png') and os.path.isfile(os.path.join(dest_dir, f)))
    
    print(f"\nFound {total_files} PNG files in source directory...")
    print(f"Found {len(existing_files)} PNG files in destination directory...")
    
    # Find new files (in source but not in destination)
    new_files = [f for f in source_files if f not in existing_files]
    print(f"Found {len(new_files)} new files to copy...")
    
    if not new_files:
        print("No new files to copy. Operation complete!")
        return True
    
    copied_files = 0
    error_files = 0
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        def copy_file(filename):
            try:
                source_path = os.path.join(source_dir, filename)
                dest_path = os.path.join(dest_dir, filename)
                
                # Copy the new file to destination
                shutil.copy2(source_path, dest_path)
                
                print(f"Copied: {filename} (new file)")
                return "copied"
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                return "error"
        
        results = list(executor.map(copy_file, new_files))
        
    copied_files = sum(1 for r in results if r == "copied")
    error_files = sum(1 for r in results if r == "error")
    
    print(f"\nOperation complete!")
    print(f"Total files in source: {total_files}")
    print(f"New files found: {len(new_files)}")
    print(f"Files copied: {copied_files}")
    print(f"Files with errors: {error_files}")
    
    return True

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 9: BKP FILE REMOVER
#==============================================================================
def remove_bkp_files(directory):
    """
    Remove all PNG files in the specified directory that have filenames
    starting with 'BKP_'.
    """
    directory = validate_directory(directory)
    if not directory:
        return False
    
    # Get list of PNG files in the directory that start with BKP_
    bkp_files = [f for f in os.listdir(directory) 
                if f.lower().endswith('.png') and f.startswith('BKP_') and os.path.isfile(os.path.join(directory, f))]
    
    total_bkp_files = len(bkp_files)
    if not bkp_files:
        print(f"\nNo BKP_ PNG files found in {directory}")
        return False
    
    print(f"\nFound {total_bkp_files} BKP_ PNG files to remove...")
    
    deleted_files = 0
    error_files = 0
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        def delete_file(filename):
            try:
                file_path = os.path.join(directory, filename)
                os.remove(file_path)
                print(f"Deleted: {filename}")
                return True
            except Exception as e:
                print(f"Error deleting {filename}: {e}")
                return False
        
        results = list(executor.map(delete_file, bkp_files))
        
        for result in results:
            if result:
                deleted_files += 1
            else:
                error_files += 1
    
    print(f"\nOperation complete!")
    print(f"Total BKP_ PNG files found: {total_bkp_files}")
    print(f"Files deleted: {deleted_files}")
    print(f"Files with errors: {error_files}")
    
    return True

#==============================================================================
# IMAGE PROCESSING FUNCTIONS - TOOL 10: COMPARE AND MOVE
#==============================================================================
def compare_and_move(source_dir, dest_dir):
    """
    Compare files between source directory (upscaled images) and destination 
    directory (new dump). Copies files from source to destination if they have
    matching filenames, overwriting in destination.
    """
    source_dir = validate_directory(source_dir)
    if not source_dir:
        return False
    dest_dir = validate_directory(dest_dir)
    if not dest_dir:
        return False
    
    # Get list of PNG files in source directory (upscaled images)
    source_files = {f: os.path.join(source_dir, f) for f in os.listdir(source_dir) 
                   if f.lower().endswith('.png') and os.path.isfile(os.path.join(source_dir, f))}
    
    # Get list of PNG files in destination directory (new dump)
    dest_files = {f: os.path.join(dest_dir, f) for f in os.listdir(dest_dir) 
                 if f.lower().endswith('.png') and os.path.isfile(os.path.join(dest_dir, f))}
    
    total_source = len(source_files)
    total_dest = len(dest_files)
    
    if not source_files:
        print(f"\nNo PNG files found in source directory {source_dir}")
        return False
    if not dest_files:
        print(f"\nNo PNG files found in destination directory {dest_dir}")
        return False
    
    print(f"\nFound {total_source} PNG files in source directory (upscaled images)...")
    print(f"Found {total_dest} PNG files in destination directory (new dump)...")
    
    # Find matching files (in both source and destination)
    matching_files = [f for f in dest_files if f in source_files]
    print(f"Found {len(matching_files)} matching files to replace...")
    
    if not matching_files:
        print("No matching files to replace. Operation complete!")
        return True
    
    copied_files = 0
    error_files = 0
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        def copy_replace_file(filename):
            try:
                source_path = os.path.join(source_dir, filename)
                dest_path = os.path.join(dest_dir, filename)
                
                # Copy the upscaled file to destination, overwriting the existing one
                shutil.copy2(source_path, dest_path)
                
                print(f"Replaced: {filename}")
                return "copied"
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                return "error"
        
        results = list(executor.map(copy_replace_file, matching_files))
    
    copied_files = sum(1 for r in results if r == "copied")
    error_files = sum(1 for r in results if r == "error")
    
    print(f"\nOperation complete!")
    print(f"Total files in source: {total_source}")
    print(f"Total files in destination: {total_dest}")
    print(f"Matching files found: {len(matching_files)}")
    print(f"Files replaced: {copied_files}")
    print(f"Files with errors: {error_files}")
    
    return True

#==============================================================================
# ADD NEW IMAGE PROCESSING FUNCTIONS HERE
#==============================================================================
# Copy the structure of one of the existing functions and modify it
# Remember to add an entry in the TOOL_DESCRIPTIONS dictionary at the top
# Then add a new radio button in the UI section
# Finally, add a case in the run_selected_tool method

#==============================================================================
# TKINTER GUI CLASS
#==============================================================================
class ImageToolsApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Nex Tex Tools v{VERSION}")
        self.root.geometry("900x700")
        
        # Apply dark theme colors
        self.apply_theme()
        
        # Create main frame with dark background
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Set background colors
        root.configure(bg=THEME_BG)
        
        # Title and version
        title_frame = ttk.Frame(self.main_frame)
        title_frame.pack(fill="x", pady=10)
        
        ttk.Label(
            title_frame, 
            text="Nex Tex Tools", 
            font=("Helvetica", 20, "bold")
        ).pack(side="left", pady=5)
        
        ttk.Label(
            title_frame, 
            text=f"v{VERSION}", 
            font=("Helvetica", 12)
        ).pack(side="left", padx=10, pady=5)
        
        ttk.Separator(self.main_frame, orient="horizontal").pack(fill="x", pady=10)
        
        # Create horizontal layout
        self.horizontal_layout = ttk.Frame(self.main_frame)
        self.horizontal_layout.pack(fill="both", expand=True)
        
        # Left panel - Tool selection
        self.left_panel = ttk.Frame(self.horizontal_layout)
        self.left_panel.pack(side="left", fill="y", padx=(0, 10))
        
        tool_frame = ttk.LabelFrame(self.left_panel, text="Select Tool")
        tool_frame.pack(fill="x", pady=5)
        
        # Radio buttons for tool selection
        self.selected_tool = tk.StringVar(value="1")
        tools = [
            ("Move Images with Alpha Channel", "1"),
            ("Flip Images Vertically", "2"),
            ("Remove Duplicate Files", "3"),
            ("Detect PS2 Textures with Variable Alpha", "4"),
            ("Make Alpha 128 Solid", "5"),
            ("Restore Alpha to 50%", "6"),
            ("Fill Transparent Areas", "7"),
            ("Find and Replace", "8"),
            ("BKP File Remover", "9"),
            ("Compare and Move", "10")
            # Add new tools here following the same pattern
        ]
        
        for i, (text, value) in enumerate(tools):
            ttk.Radiobutton(
                tool_frame, 
                text=text, 
                variable=self.selected_tool, 
                value=value,
                command=self.update_display
            ).pack(anchor="w", padx=10, pady=3)
        
        # Right panel - Tool details and inputs
        self.right_panel = ttk.Frame(self.horizontal_layout)
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # Tool description area
        self.description_frame = ttk.LabelFrame(self.right_panel, text="Tool Description:")
        self.description_frame.pack(fill="x", pady=5)
        
        self.description_text = tk.Text(self.description_frame, height=6, wrap="word", 
                                   bg=THEME_ACCENT, fg=THEME_FG)
        self.description_text.pack(fill="x", padx=5, pady=5)
        self.description_text.config(state="disabled")
        
        # Input options frame (removed title as requested)
        self.input_frame = ttk.Frame(self.right_panel)
        self.input_frame.pack(fill="x", pady=10)
        
        # Source directory
        self.source_dir_frame = ttk.Frame(self.input_frame)
        self.source_dir_frame.pack(fill="x", pady=5)
        ttk.Label(self.source_dir_frame, text="Source Directory:", width=15).pack(side="left")
        self.source_dir = tk.StringVar()
        ttk.Entry(self.source_dir_frame, textvariable=self.source_dir, width=50).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(self.source_dir_frame, text="Browse", command=self.browse_source).pack(side="left")
        
        # Destination directory
        self.dest_dir_frame = ttk.Frame(self.input_frame)
        self.dest_dir_frame.pack(fill="x", pady=5)
        ttk.Label(self.dest_dir_frame, text="Destination Directory:", width=15).pack(side="left")
        self.dest_dir = tk.StringVar()
        ttk.Entry(self.dest_dir_frame, textvariable=self.dest_dir, width=50).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(self.dest_dir_frame, text="Browse", command=self.browse_dest).pack(side="left")
        
        # Fill color dropdown (initially hidden)
        self.fill_color_frame = ttk.Frame(self.input_frame)
        self.fill_color = tk.StringVar(value="Magenta")
        ttk.Label(self.fill_color_frame, text="Fill Color:", width=15).pack(side="left")
        self.color_dropdown = ttk.Combobox(
            self.fill_color_frame, 
            textvariable=self.fill_color,
            values=["Magenta", "Neon Green", "Cyan", "Hot Pink", "Bright Yellow"],
            state="readonly",
            width=20
        )
        self.color_dropdown.pack(side="left", padx=5)
        
        # Add community buttons to the bottom of the left panel
        donation_frame = ttk.Frame(self.left_panel)
        donation_frame.pack(side="bottom", fill="x", pady=20)
        
        # Style for all community buttons
        style = ttk.Style()
        style.configure("Donation.TButton", font=("Helvetica", 10, "bold"))
        
        # Ko-fi button
        donation_button = ttk.Button(
            donation_frame,
            text="Support Me Please On Ko-Fi\nSo I Can Keep Bringing Us Tools!",
            command=self.open_donation_link,
            style="Donation.TButton"
        )
        donation_button.pack(fill="x", padx=10, pady=5)
        
        # Discord button
        discord_button = ttk.Button(
            donation_frame,
            text="Join Our Discord Server\nJust Ping Nexus222!",
            command=self.open_discord_link,
            style="Donation.TButton"
        )
        discord_button.pack(fill="x", padx=10, pady=5)
        
        # Reddit button
        reddit_button = ttk.Button(
            donation_frame,
            text="Check Out Our Texture Packs\nOn Reddit!",
            command=self.open_reddit_link,
            style="Donation.TButton"
        )
        reddit_button.pack(fill="x", padx=10, pady=5)
        
        # Action buttons
        button_frame = ttk.Frame(self.right_panel)
        button_frame.pack(fill="x", pady=10)
        ttk.Button(
            button_frame, 
            text="Run Tool", 
            command=self.run_selected_tool
        ).pack(side="left", padx=5)
        ttk.Button(
            button_frame, 
            text="About", 
            command=self.show_about
        ).pack(side="left", padx=5)
        ttk.Button(
            button_frame, 
            text="Exit", 
            command=root.destroy
        ).pack(side="left", padx=5)
        
        # Output area
        output_frame = ttk.LabelFrame(self.right_panel, text="Output:")
        output_frame.pack(fill="both", expand=True, pady=5)
        
        self.output_text = tk.Text(output_frame, height=10, width=80, wrap="word",
                              bg=THEME_ACCENT, fg=THEME_FG)
        self.output_text.pack(fill="both", expand=True, side="left")
        
        output_scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        output_scrollbar.pack(side="right", fill="y")
        self.output_text.config(yscrollcommand=output_scrollbar.set)
        self.output_text.config(state="disabled")
        
        # Progress bar
        self.progress_frame = ttk.Frame(self.right_panel)
        self.progress_frame.pack(fill="x", pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill="x")
        
        # Set initial state
        self.update_display()
        
        # Start polling queue for output messages
        self.check_queue()
    
    def apply_theme(self):
        """Apply dark theme colors to the UI elements"""
        # Configure colors for text widgets that need it
        self.root.option_add("*Text*Background", THEME_BG)
        self.root.option_add("*Text*Foreground", THEME_FG)
        
        # Configure the root window background
        self.root.configure(background=THEME_BG)
    
    def open_donation_link(self):
        """Open the Ko-fi donation page in a web browser"""
        webbrowser.open(DONATION_URL)
    
    def open_discord_link(self):
        """Open the Discord server invite link in a web browser"""
        webbrowser.open(DISCORD_URL)

    def open_reddit_link(self):
        """Open the Reddit subreddit in a web browser"""
        webbrowser.open(REDDIT_URL)
    
    def show_about(self):
        """Show the about dialog with information about the tool"""
        about_text = f"""Nex Tex Tools v{VERSION}
        
A texture processing utility for video game modding.

This tool helps with processing and managing texture files 
for PlayStation 1, Dreamcast, PS2, and GameCube era games.

Created by: RomRevival
Support: {DONATION_URL}
"""
        messagebox.showinfo("About Nex Tex Tools", about_text)
    
    def browse_source(self):
        """Browse for source directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.source_dir.set(directory)
    
    def browse_dest(self):
        """Browse for destination directory"""
        directory = filedialog.askdirectory()
        if directory:
            self.dest_dir.set(directory)
    
    def update_display(self):
        """Update the description and input options based on the selected tool"""
        tool_num = self.selected_tool.get()
        
        # Update description text
        self.description_text.config(state="normal")
        self.description_text.delete('1.0', tk.END)
        if tool_num in TOOL_DESCRIPTIONS:
            self.description_text.insert('1.0', TOOL_DESCRIPTIONS[tool_num])
        self.description_text.config(state="disabled")
        
        # Reset visibility
        self.fill_color_frame.pack_forget()
        
        # Two directory inputs
        if tool_num in ["1", "4", "8", "10"]:
            self.source_dir_frame.pack(fill="x", pady=5)
            self.dest_dir_frame.pack(fill="x", pady=5)
        # Single directory input
        elif tool_num in ["2", "5", "6", "9"]:
            self.source_dir_frame.pack(fill="x", pady=5)
            self.dest_dir_frame.pack_forget()
        # Fill transparent areas (needs color selection)
        elif tool_num == "7":
            self.source_dir_frame.pack(fill="x", pady=5)
            self.dest_dir_frame.pack_forget()
            self.fill_color_frame.pack(fill="x", pady=5)
        # Remove duplicate files (uses source/dest)
        elif tool_num == "3":
            self.source_dir_frame.pack(fill="x", pady=5)
            self.dest_dir_frame.pack(fill="x", pady=5)
    
    def print_to_output(self, message):
        """Append text to the output area"""
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, message + '\n')
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")
    
    def clear_output(self):
        """Clear the output area"""
        self.output_text.config(state="normal")
        self.output_text.delete('1.0', tk.END)
        self.output_text.config(state="disabled")
    
    def check_queue(self):
        """Check the output queue for messages from threads"""
        try:
            while True:
                message_type, message = output_queue.get_nowait()
                
                if message_type == 'DONE':
                    self.print_to_output("Operation completed successfully!")
                    # Update the progress bar to 100%
                    self.progress_bar["value"] = 100
                elif message_type == 'ERROR':
                    self.print_to_output(f"Error: {message}")
                    messagebox.showerror("Error", f"An error occurred: {message}")
                elif message_type == 'INFO':
                    self.print_to_output(message)
                elif message_type == 'PROGRESS':
                    # Update progress bar
                    self.progress_bar["value"] = message
                
                output_queue.task_done()
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.check_queue)
    
    def run_selected_tool(self):
        """Run the selected tool with provided inputs"""
        # Clear output
        self.clear_output()
        
        # Reset progress bar
        self.progress_bar["value"] = 0
        
        # Get tool number
        tool_num = self.selected_tool.get()
        
        # Setup function and arguments based on selected tool
        function = None
        args = []
        kwargs = {}
        
        # Get directory paths
        source_dir = self.source_dir.get()
        dest_dir = self.dest_dir.get()
        
        # Validate paths as needed
        if not source_dir:
            messagebox.showerror("Error", "Please select a source directory")
            return
            
        if tool_num in ["1", "3", "4", "8", "10"] and not dest_dir:
            messagebox.showerror("Error", "Please select a destination directory")
            return
        
        if not os.path.exists(source_dir):
            if messagebox.askyesno("Directory Missing", "Source directory doesn't exist. Create it?"):
                try:
                    os.makedirs(source_dir)
                    self.print_to_output(f"Created source directory: {source_dir}")
                except Exception as e:
                    messagebox.showerror("Error", f"Error creating directory: {e}")
                    return
            else:
                return
        
        if tool_num in ["1", "4", "8", "10"] and not os.path.exists(dest_dir):
            # Create destination directory if needed
            if messagebox.askyesno("Directory Missing", "Destination directory doesn't exist. Create it?"):
                try:
                    os.makedirs(dest_dir)
                    self.print_to_output(f"Created destination directory: {dest_dir}")
                except Exception as e:
                    messagebox.showerror("Error", f"Error creating directory: {e}")
                    return
            else:
                return
        
        # Set up the function call based on selected tool
        if tool_num == "1":  # Move Images with Alpha Channel
            function = move_alpha_pngs
            args = [source_dir, dest_dir]
        elif tool_num == "2":  # Flip Images Vertically
            function = flip_images
            args = [source_dir]
        elif tool_num == "3":  # Remove Duplicate Files
            # Special handling for deduplication
            self.run_deduplication(source_dir, dest_dir)
            return
        elif tool_num == "4":  # Detect PS2 Textures
            function = detect_ps2_alpha
            args = [source_dir, dest_dir]
        elif tool_num == "5":  # Make Alpha 128 Solid
            function = lambda dir: process_directory_batch(dir, process_alpha, make_solid=True)
            args = [source_dir]
        elif tool_num == "6":  # Restore Alpha to 50%
            function = lambda dir: process_directory_batch(dir, process_alpha, make_solid=False)
            args = [source_dir]
        elif tool_num == "7":  # Fill Transparent Areas
            # Get the color selection
            color_name = self.fill_color.get()
            color_index = list(FILL_COLORS.keys())[['Magenta', 'Neon Green', 'Cyan', 'Hot Pink', 'Bright Yellow'].index(color_name)]
            function = lambda dir: process_directory_batch(dir, fill_transparency, color_rgb=FILL_COLORS[color_index]['rgb'], restore=False)
            args = [source_dir]
        elif tool_num == "8":  # Find and Replace
            function = find_and_replace
            args = [source_dir, dest_dir]
        elif tool_num == "9":  # BKP File Remover
            function = remove_bkp_files
            args = [source_dir]
        elif tool_num == "10":  # Compare and Move
            function = compare_and_move
            args = [source_dir, dest_dir]
        # Add new tool cases here
        
        # Redirect print output to GUI
        original_print = print
        def print_redirect(*args, **kwargs):
            message = " ".join(map(str, args))
            output_queue.put(('INFO', message))
        
        # Override built-in print
        import builtins
        builtins.print = print_redirect
        
        # Start the operation in a thread
        if function:
            self.print_to_output(f"Starting operation...")
            threading.Thread(target=self.long_operation_thread, 
                           args=(function, args, kwargs), 
                           daemon=True).start()
    
    def long_operation_thread(self, function, args, kwargs):
        """Run operations in a separate thread to keep GUI responsive"""
        try:
            result = function(*args, **kwargs)
            output_queue.put(('DONE', result))
        except Exception as e:
            output_queue.put(('ERROR', str(e)))
        
        # Reset print after thread completes
        import builtins
        builtins.print = __builtins__.__dict__['print']
    
    def run_deduplication(self, source_dir, dest_dir):
        """Special handler for deduplication which needs more interaction"""
        try:
            source_path = Path(source_dir).resolve()
            dest_path = Path(dest_dir).resolve()
            
            if not source_path.exists() or not source_path.is_dir():
                self.print_to_output("Invalid source directory")
                return
            
            if not dest_path.exists() or not dest_path.is_dir():
                self.print_to_output("Invalid destination directory")
                return
            
            duplicates = list_duplicate_files(source_path, dest_path)
            
            if not duplicates:
                self.print_to_output("No duplicate filenames found. Nothing to delete.")
                return
            
            # Show the duplicates
            self.print_to_output("The following files will be deleted from the destination directory:")
            for file in duplicates:
                self.print_to_output(f"- {file.name}")
            
            # Ask for confirmation via a popup
            if messagebox.askyesno("Confirm Deletion", 
                               f"Are you sure you want to delete these {len(duplicates)} files from {dest_dir}?"):
                
                # Process deletions in a thread
                threading.Thread(target=self.process_deletions_thread, 
                               args=(duplicates,), 
                               daemon=True).start()
            else:
                self.print_to_output("Operation cancelled.")
        
        except Exception as e:
            self.print_to_output(f"Error: {str(e)}")
    
    def process_deletions_thread(self, duplicates):
        """Process file deletions in a separate thread"""
        deleted = 0
        errors = []
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            def delete_file(file):
                try:
                    file.unlink()
                    return True, None
                except Exception as e:
                    return False, (file.name, str(e))
            
            results = list(executor.map(delete_file, duplicates))
            
        for success, error in results:
            if success:
                deleted += 1
            elif error:
                errors.append(error)
        
        # Update the UI with results
        output_queue.put(('INFO', f"Operation completed: {deleted} file(s) deleted successfully"))
        
        if errors:
            output_queue.put(('INFO', f"{len(errors)} error(s) occurred:"))
            for filename, error in errors:
                output_queue.put(('INFO', f"  - Failed to delete '{filename}': {error}"))

#==============================================================================
# PROGRAM ENTRY POINT
#==============================================================================
def main():
    # Create a console window for error messages on Windows
    if sys.platform.startswith('win'):
        try:
            import ctypes
            ctypes.windll.kernel32.AllocConsole()
            sys.stdout = open('CONOUT$', 'w')
        except:
            pass
    
    try:
        # Run the tkinter application
        root = tk.Tk()
        app = ImageToolsApp(root)
        root.mainloop()
    except Exception as e:
        # Try to show error in GUI
        try:
            messagebox.showerror("Critical Error", f"Critical Error:\n{str(e)}\n\nThe application will now close.")
        except:
            # Fallback to console
            print(f"Critical Error: {e}")
        
        # Wait for input to keep window open
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()