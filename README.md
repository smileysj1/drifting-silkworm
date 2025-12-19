# Batch Transcoder (HandBrakeCLI)

A simple GUI application for batch-transcoding videos using HandBrakeCLI presets. Processes videos one-at-a-time, automatically deleting source files after successful encoding.

## Features

- **Folder Selection**: Browse and select a folder containing video files
- **Preset Support**: Specify a HandBrakeCLI preset (e.g., "Fast 1080p30", "HQ 1080p30 Surround")
- **Output Format**: Choose output file extension (mp4, mkv, etc.)
- **Auto-delete**: Source files are removed after successful transcode
- **Stop Control**: Gracefully stop processing after the current file completes
- **Live Log**: Real-time logging of all operations

## Requirements

- Python 3.7+
- **HandBrakeCLI** (command-line HandBrake encoder)
  - Download from: https://handbrake.fr/downloads.php
  - On Windows, extract to a known location or add to PATH

## Installation

1. Ensure `transcode_batch.py` is in your desired directory
2. Install/configure HandBrakeCLI on your system
3. Run the script:

```bash
python transcode_batch.py
```

## Usage

1. **Click "Browse"** next to "Folder" to select a folder with video files
2. **Locate HandBrakeCLI** (optional; leave as "HandBrakeCLI" if in PATH):
   - Click "Browse" next to "HandBrakeCLI Path" to select the executable
3. **Enter Preset Name**: Type the exact name of your HandBrake preset (e.g., "Fast 1080p30")
   - Optional; if blank, defaults encoding with no preset
4. **Output extension**: Change if needed (default: "mp4")
5. **Click "Start"** to begin batch processing
   - Files are processed one-by-one
   - Source files are deleted after successful transcode
   - Output files are named `{original_name}_transcoded.{extension}`
6. **Click "Stop"** to gracefully stop after the current file

## Supported Formats

The script recognizes: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.m4v`, `.webm`

## Notes

- Output files are saved in the same folder as the source
- If an output file already exists, a numeric suffix is added: `name_transcoded_1.mp4`
- Failed encodes are logged; the partial output is cleaned up automatically
- Use HandBrake CLI options by specifying a preset name matching your HandBrake configuration
