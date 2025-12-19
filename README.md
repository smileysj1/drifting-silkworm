# Batch Transcoder (HandBrakeCLI)

A small GUI tool that batches HandBrakeCLI transcodes for files in a folder. It
processes files one at a time, invokes HandBrakeCLI for each file, and deletes
the source file after a successful encode.

## Features

- Folder selection via GUI
- Import a HandBrake presets JSON (uses HandBrakeCLI to import and list presets)
- Select a preset (combobox populated from HandBrakeCLI output) or type a preset name
- Choose output extension (default: `mp4`)
- Progress and live log output in the GUI
- Graceful stop: finishes the current file then stops

## Requirements

- Python 3.7+
- HandBrakeCLI (command-line HandBrake encoder)
   - Download from: https://handbrake.fr/downloads.php
   - On Windows you can add the executable to your PATH or point the GUI to it

## Running

1. Place `transcode_batch.py` in a folder and run:

```bash
python transcode_batch.py
```

## How presets work

- You can supply a presets JSON file using the **Presets JSON** field and click
   **Load**. The app runs `HandBrakeCLI --preset-import-file <file> --preset-list`
   to import the file and read available preset names. The combobox will be
   populated with preset names found in HandBrakeCLI's output.
- The app prefers a preset selected in the combobox (`Preset (from JSON)`). If
   no preset is provided and no presets were loaded, the app will refuse to
   start and ask you to enter or load a preset name. (A blank preset is not
   accepted unless a preset list is available and a value is selected.)

## Usage

1. Click **Browse** next to "Folder" to select the directory containing video files.
2. If HandBrakeCLI isn't on your PATH, click **Browse** next to "HandBrakeCLI Path"
    to point to the executable; otherwise leaving it set to `HandBrakeCLI` will
    attempt to use the PATH lookup.
3. Optionally choose a presets JSON file and click **Load** to populate the
    preset combobox. Select a preset or type a preset name (exact match required
    for HandBrakeCLI's `-Z` option).
4. Set the output extension (default `mp4`).
5. Click **Start** to begin processing. Files are processed sequentially.
6. Click **Stop** to request a graceful stop — the app will finish the current
    file and then stop.

## Output naming and behavior

- Output files are written into the same folder as the source file and are
   named `<original_stem>_transcoded.<ext>` (for example `movie_transcoded.mp4`).
- If the output filename already exists, a numeric suffix is added
   (e.g. `movie_transcoded_1.mp4`, `movie_transcoded_2.mp4`, ...).
- On successful transcode the source file is removed. If HandBrakeCLI fails,
   the partial output is removed when possible and the error is logged.

## Supported input formats

The script looks for files with the following extensions: `.mp4`, `.mkv`,
`.avi`, `.mov`, `.wmv`, `.flv`, `.m4v`, `.webm`.

## Notes

- The app uses HandBrakeCLI to import and list presets; it does not parse the
   JSON itself for preset names beyond a best-effort default lookup when loading
   the JSON file.
- Be sure the preset name you select or type exactly matches a HandBrakeCLI
   preset name (case-insensitive matching is attempted when selecting defaults,
   but HandBrakeCLI's `-Z` option will be used with the provided text).

