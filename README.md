# Hidden Geometry Removal (Compatible with Blender 4.0+)
### A Blender Add-on for Optimizing 3D Models

![Blender Version](https://img.shields.io/badge/Blender-4.0%2B-orange)
![Version](https://img.shields.io/badge/Version-0.1.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

Hidden Geometry Removal is a powerful Blender add-on that automatically identifies and removes geometry that cannot be seen from any viewing angle. This tool is perfect for optimizing 3D models for real-time applications, game engines, or web-based 3D viewers.

![image](https://github.com/user-attachments/assets/4b47e745-d773-4dda-b784-c1d36a6bfae0)


## Features

- 🎥 Intelligent camera placement using spherical distribution
- 🔄 Customizable number of viewing angles
- ⚡ High-precision geometry analysis
- 🎯 Support for both deletion and selection modes
- 🛠️ User-friendly interface

## Installation

1. Download the latest release (`HiddenGeometryRemoval.py`)
2. Open Blender and go to `Edit > Preferences > Add-ons`
3. Click `Install` and select the downloaded file
4. Enable the add-on by checking the box

## Usage

1. Select your mesh object in the 3D viewport
2. Open the sidebar (`N` key) and find the "Hidden Removal" tab
3. Adjust the settings:
   - **Number of Rows**: Controls the number of vertical camera splines around the object
   - **Cameras per Row**: Sets how many cameras are placed along each spline
   - **Camera Distance**: Adjusts how far cameras are from the object's center
   - **Delete/Select Mode**: Choose between removing hidden geometry or selecting visible faces
   - **Precision**: Toggle between high and low precision analysis
4. Click "Remove Hidden Geometry" to process your mesh

## How It Works

The add-on creates a spherical distribution of cameras around your object using:
- Vertical splines (rows) evenly distributed around the object
- Multiple camera positions along each spline
- Automatic camera positioning and targeting
- Ray-casting for visibility checks

## Settings Explained

### Camera Distribution
- **Rows**: More rows = more thorough horizontal coverage
  - Minimum: 2
  - Maximum: 12
  - Default: 4

- **Cameras per Row**: More cameras = better vertical coverage
  - Minimum: 2
  - Maximum: 12
  - Default: 4
  - Must be even number

### Processing Options
- **High Precision**: Checks vertices and edge midpoints (slower but more accurate)
- **Low Precision**: Only checks face centers (faster but less precise)

## Best Practices

1. **Camera Distance**: Set it larger than your object's maximum dimension
2. **Number of Cameras**: Start with default values and increase if needed
3. **Precision Mode**: Use 'High' for final processing, 'Low' for testing
4. **Backup**: Always save your file before processing large models

## Performance Tips

- Start with lower settings for large meshes
- Use 'Outer Select' mode to preview what will be removed
- Increase camera count gradually until desired results are achieved

## Limitations

- Works best with manifold geometry
- Processing time increases with camera count and mesh complexity
- Very small details might require higher camera counts to detect

## Feedback

Feel free to submit issues.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Seungwoo Lee
