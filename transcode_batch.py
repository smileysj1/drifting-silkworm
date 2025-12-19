"""
Batch Transcoder - A GUI tool for transcoding multiple videos with HandBrakeCLI.

Features:
  - Select folder containing videos
  - Specify HandBrake preset and output format
  - Automatic source deletion after successful encode
  - Real-time logging and graceful stop control
"""

import os
import subprocess
import threading
import queue
import time
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json

# Supported video file extensions
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.webm'}
LOG_POLL_INTERVAL = 200  # milliseconds
HB_OUTPUT_SUFFIX = '_transcoded'


class TranscodeApp:
    """Main GUI application for batch transcoding with HandBrakeCLI."""

    def __init__(self, root):
        """Initialize the application window and UI components."""
        self.root = root
        root.title('Batch Transcoder (HandBrakeCLI)')

        # Initialize internal state
        self._stop_event = threading.Event()
        self._worker = None
        self._message_queue = queue.Queue()

        # Build UI
        self._build_ui()

        # Start polling for log messages
        self.root.after(LOG_POLL_INTERVAL, self._poll_queue)

    def _build_ui(self):
        """Construct all UI elements and layout."""
        frame = ttk.Frame(self.root, padding=10)
        frame.grid(sticky='nsew')

        # Folder selection
        self.folder_var = tk.StringVar()
        self._add_input_row(frame, 0, 'Folder:', self.folder_var, self.browse_folder)

        # HandBrakeCLI path
        self.hb_var = tk.StringVar(value='HandBrakeCLI')
        self._add_input_row(frame, 1, 'HandBrakeCLI Path:', self.hb_var, self.browse_hb)

        # Presets JSON selector (optional)
        self.presets_file_var = tk.StringVar()
        ttk.Label(frame, text='Presets JSON:').grid(row=2, column=0, sticky='w')
        ttk.Entry(frame, textvariable=self.presets_file_var, width=50).grid(row=2, column=1, sticky='we')
        presets_btn_frame = ttk.Frame(frame)
        presets_btn_frame.grid(row=2, column=2)
        ttk.Button(presets_btn_frame, text='Browse', command=self.browse_presets_file).pack(side='left')
        ttk.Button(presets_btn_frame, text='Load', command=self.load_presets_file).pack(side='left', padx=(4,0))

        # Preset selector (combobox) - populated from JSON and readonly
        self.preset_var = tk.StringVar()
        ttk.Label(frame, text='Preset (from JSON):').grid(row=3, column=0, sticky='w')
        self.preset_combo = ttk.Combobox(frame, textvariable=self.preset_var, width=48, state='disabled')
        self.preset_combo.grid(row=3, column=1, sticky='we')

        # Output extension
        ext_frame = ttk.Frame(frame)
        ext_frame.grid(row=4, column=1, columnspan=2, sticky='w')
        ttk.Label(frame, text='Output extension:').grid(row=4, column=0, sticky='w')
        self.ext_var = tk.StringVar(value='mp4')
        ttk.Entry(ext_frame, textvariable=self.ext_var, width=10).pack(side='left')

        # Control buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.start_btn = ttk.Button(button_frame, text='Start', command=self.start)
        self.start_btn.pack(side='left', padx=(0, 5))
        self.stop_btn = ttk.Button(button_frame, text='Stop', command=self.stop, state='disabled')
        self.stop_btn.pack(side='left')

        # Log display
        ttk.Label(frame, text='Log:').grid(row=5, column=0, sticky='nw')
        self.log_widget = tk.Text(frame, width=80, height=20, state='disabled')
        self.log_widget.grid(row=5, column=1, columnspan=2, sticky='we')

        # Progress bar for batch
        progress_frame = ttk.Frame(frame)
        progress_frame.grid(row=6, column=0, columnspan=3, sticky='we', pady=(8, 0))
        ttk.Label(progress_frame, text='Progress:').pack(side='left')
        self.progress_text_var = tk.StringVar(value='')
        ttk.Label(progress_frame, textvariable=self.progress_text_var, width=8).pack(side='left', padx=(6, 8))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', length=400, mode='determinate', variable=self.progress_var, maximum=100.0)
        self.progress_bar.pack(side='left', fill='x', expand=True)

        frame.columnconfigure(1, weight=1)

    def _add_input_row(self, parent, row, label_text, var, browse_command):
        """Add a labeled input row with optional browse button."""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky='w')
        ttk.Entry(parent, textvariable=var, width=50).grid(row=row, column=1, sticky='we')
        if browse_command:
            ttk.Button(parent, text='Browse', command=browse_command).grid(row=row, column=2)

    # ============================================================================
    # Presets JSON loading
    # ============================================================================

    def browse_presets_file(self):
        """Browse for a presets JSON file."""
        path = filedialog.askopenfilename(title='Select presets JSON', filetypes=[('JSON files','*.json'), ('All files','*.*')])
        if path:
            self.presets_file_var.set(path)
            self._log(f'Presets file selected: {path}')

    def load_presets_file(self):
        """Load presets from the selected JSON file and populate the combobox."""
        path = self.presets_file_var.get().strip()
        if not path:
            messagebox.showwarning('No file', 'Please select a presets JSON file to load.')
            return
        # Do not parse the JSON here. HandBrakeCLI will import the presets
        # JSON directly. Validate the file exists and enable the preset name
        # entry so the user can type/select the preset to use with -Z.
        if not os.path.exists(path):
            self._log(f'Presets JSON file not found: {path}', 'error')
            messagebox.showerror('File not found', 'The specified presets JSON file does not exist.')
            return

        self._log(f'Attempting to load presets via HandBrakeCLI from: {path}')
        hb_path = self._resolve_hb_path()

        # Build command to list presets; import file first so imported presets appear
        cmd = [hb_path, '--preset-list']
        if path:
            cmd = [hb_path, '--preset-import-file', path, '--preset-list']

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError:
            self._log('HandBrakeCLI not found when attempting to list presets.', 'error')
            messagebox.showerror('HandBrakeCLI not found', 'Could not find HandBrakeCLI executable to list presets.')
            return
        except Exception as e:
            self._log(f'Error running HandBrakeCLI: {e}', 'error')
            messagebox.showerror('Error', f'Failed to run HandBrakeCLI: {e}')
            return

        output = proc.stdout or ''
        presets = []
        for line in output.splitlines():
            # Skip empty lines and category headers (which end with ':')
            if not line.strip():
                continue
            stripped = line.strip()
            if stripped.endswith(':'):
                continue
            # Heuristic: preset names are typically indented under categories
            if line.startswith(' ') or line.startswith('\t'):
                presets.append(stripped)

        # Fallback: if none found, try extracting any non-header lines
        if not presets:
            for line in output.splitlines():
                s = line.strip()
                if s and 'preset' not in s.lower() and 'handbrake' not in s.lower():
                    presets.append(s)

        if not presets:
            self._log('No presets found via HandBrakeCLI output.', 'error')
            messagebox.showinfo('No presets', 'HandBrakeCLI did not return any presets.')
            return

        # Try to get a default preset name from the JSON contents and prefer it
        default_name = self._get_default_preset_from_json(path)

        # Populate combobox and select default (preferred) or first preset
        self._log(f'Loaded {len(presets)} presets via HandBrakeCLI')
        # If default_name matches one of the presets, use that exact value (preserve case)
        selected = None
        if default_name:
            for p in presets:
                if p.strip().lower() == default_name.strip().lower():
                    selected = p
                    break
        if not selected:
            # If default_name provided but not found, insert it at top and use it
            if default_name:
                presets.insert(0, default_name)
                selected = default_name
            else:
                selected = presets[0]

        self.preset_combo['values'] = presets
        self.preset_var.set(selected)
        self.preset_combo.config(state='readonly')
        messagebox.showinfo('Presets loaded', f'Loaded {len(presets)} presets from HandBrakeCLI.')

    # NOTE: preset extraction from JSON removed. We now pass the JSON file
    # directly to HandBrakeCLI via --preset-import-file and the user must
    # supply the preset name to use with -Z.

    # ============================================================================
    # Event Handlers (UI interactions)
    # ============================================================================

    def browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def browse_hb(self):
        """Open file browser for HandBrakeCLI executable."""
        path = filedialog.askopenfilename(title='Locate HandBrakeCLI executable')
        if path:
            self.hb_var.set(path)

    def start(self):
        """Validate inputs and start transcoding in background thread."""
        # Validate folder
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror('Error', 'Please select a valid folder.')
            return

        # Require a preset selected from the loaded JSON; if none explicitly selected,
        # fall back to the first loaded value in the combobox (if any).
        preset = self.preset_var.get().strip()
        if not preset:
            vals = list(self.preset_combo['values']) if self.preset_combo['values'] else []
            if vals:
                preset = vals[0]
                self.preset_var.set(preset)
                self._log(f'No preset explicitly selected; using first loaded preset: {preset}', 'info')
            else:
                messagebox.showerror('No preset', 'Please enter a preset name before starting. Optionally load a presets JSON to import.')
                return

        # Resolve HandBrakeCLI path
        hb_path = self._resolve_hb_path()

        # Disable UI and start worker thread
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self._stop_event.clear()

        # Reset progress UI
        try:
            self.progress_var.set(0.0)
            self.progress_text_var.set('')
        except Exception:
            pass

        # Determine preset: prefer combobox selection (preset_var)
        preset = self.preset_var.get().strip()

        output_ext = self.ext_var.get().lstrip('.')
        self._worker = threading.Thread(
            target=self._process_folder,
            args=(folder, hb_path, preset, output_ext),
            daemon=True
        )
        self._worker.start()

    def stop(self):
        """Request graceful stop after current file."""
        self._log('Stop requested — will finish current file then stop.', 'info')
        self._stop_event.set()
        self.stop_btn.config(state='disabled')

    # ============================================================================
    # Logging and Queue Management
    # ============================================================================

    def _poll_queue(self):
        """Poll message queue for log updates from worker thread."""
        try:
            while True:
                msg_type, message = self._message_queue.get_nowait()
                # Handle progress updates separately from log messages
                if msg_type == 'progress':
                    try:
                        val = float(message)
                    except Exception:
                        val = 0.0
                    # Clip value between 0 and 100
                    val = max(0.0, min(100.0, val))
                    self.progress_var.set(val)
                elif msg_type == 'progress_text':
                    try:
                        self.progress_text_var.set(str(message))
                    except Exception:
                        pass
                else:
                    self._append_log(message, msg_type)
        except queue.Empty:
            pass
        self.root.after(LOG_POLL_INTERVAL, self._poll_queue)

    def _log(self, message, msg_type='info'):
        """Queue a log message to be displayed in UI."""
        self._message_queue.put((msg_type, message))

    def _append_log(self, message, msg_type='info'):
        """Append a message to the log display with timestamp."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.log_widget.config(state='normal')
        self.log_widget.insert('end', f'[{timestamp}] {message}\n')
        self.log_widget.see('end')
        self.log_widget.config(state='disabled')

    # ============================================================================
    # Worker Thread - Main Processing Logic
    # ============================================================================

    def _resolve_hb_path(self):
        """Resolve the HandBrakeCLI executable path."""
        user_input = self.hb_var.get()
        # If user entered just the name, try to find it in PATH
        if os.path.basename(user_input) == 'HandBrakeCLI':
            return shutil.which('HandBrakeCLI') or 'HandBrakeCLI'
        return user_input

    def _process_folder(self, folder, hb_path, preset, output_ext):
        """Main worker thread: scan folder and transcode each video file."""
        self._log(f'Scanning folder: {folder}')
        video_files = self._find_video_files(folder)

        if not video_files:
            self._log('No video files found in folder.', 'error')
            self._mark_done()
            return

        total_files = len(video_files)
        # Initialize progress UI (0%)
        try:
            self._message_queue.put(('progress', 0.0))
            self._message_queue.put(('progress_text', f'0/{total_files}'))
        except Exception:
            pass

        # Process each video file
        for idx, source_file in enumerate(video_files, start=1):
            if self._stop_event.is_set():
                self._log('Stopping before next file.')
                break

            self._process_single_file(source_file, hb_path, preset, output_ext, idx, len(video_files))

            # Report progress after processing this file
            try:
                pct = (idx / total_files) * 100.0 if total_files else 100.0
                self._message_queue.put(('progress', pct))
                self._message_queue.put(('progress_text', f'{idx}/{total_files}'))
            except Exception:
                pass

        self._mark_done()

    def _find_video_files(self, folder):
        """Find all video files in folder, sorted by name."""
        folder_path = Path(folder)
        video_files = [
            f for f in sorted(folder_path.iterdir())
            if f.is_file() and f.suffix.lower() in VIDEO_EXTS
        ]
        return video_files

    def _process_single_file(self, source_file, hb_path, preset, output_ext, file_num, total_files):
        """Transcode a single file, then delete the source."""
        self._log(f'[{file_num}/{total_files}] Processing: {source_file.name}')

        # Determine output path (avoid overwriting)
        output_file = self._get_output_path(source_file, output_ext)

        # Build and execute HandBrakeCLI command
        command = self._build_hb_command(hb_path, preset, source_file, output_file)
        self._log(f'Running: {" ".join(command)}', 'debug')

        # Run transcode
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode == 0:
                self._log(f'Success: {source_file.name} -> {output_file.name}')
                self._delete_source(source_file)
            else:
                self._handle_transcode_failure(source_file, output_file, result)
        except FileNotFoundError as e:
            self._log(f'HandBrakeCLI executable not found: {e}', 'error')
        except Exception as e:
            self._log(f'Processing failed for {source_file.name}: {e}', 'error')

    def _get_output_path(self, source_file, output_ext):
        """Generate unique output filename."""
        base_name = source_file.stem
        output_name = f'{base_name}{HB_OUTPUT_SUFFIX}.{output_ext}'
        output_path = source_file.with_name(output_name)

        # Ensure unique filename
        counter = 1
        while output_path.exists():
            output_name = f'{base_name}{HB_OUTPUT_SUFFIX}_{counter}.{output_ext}'
            output_path = source_file.with_name(output_name)
            counter += 1

        return output_path

    def _build_hb_command(self, hb_path, preset, source_file, output_file):
        """Build the HandBrakeCLI command."""
        command = [hb_path] if (hb_path and os.path.exists(hb_path)) else ['HandBrakeCLI']
        # If a presets JSON file was provided, import it so HandBrake can use
        # presets defined inside the file.
        presets_path = self.presets_file_var.get().strip()
        if presets_path:
            command.extend(['--preset-import-file', presets_path])
        if preset:
            command.extend(['-Z', preset])
        command.extend(['-i', str(source_file), '-o', str(output_file)])
        return command

    def _get_default_preset_from_json(self, path):
        """Attempt to read a sensible default preset name from the JSON file.

        Heuristics: look for keys like 'preset', 'preset_name', 'name', or the
        first string found in lists/dicts. Returns None if nothing found.
        """
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as e:
            self._log(f'Could not read presets JSON for default name: {e}', 'debug')
            return None

        def search(obj):
            if isinstance(obj, str) and obj.strip():
                return obj.strip()
            if isinstance(obj, dict):
                for key in ('preset', 'preset_name', 'name', 'PresetName', 'Name', 'Preset'):
                    if key in obj and isinstance(obj[key], str) and obj[key].strip():
                        return obj[key].strip()
                for v in obj.values():
                    res = search(v)
                    if res:
                        return res
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
                    res = search(item)
                    if res:
                        return res
            return None

        return search(data)

    def _delete_source(self, source_file):
        """Delete source file after successful transcode."""
        try:
            os.remove(source_file)
            self._log(f'Deleted source: {source_file.name}')
        except Exception as e:
            self._log(f'Failed to delete source {source_file.name}: {e}', 'error')

    def _handle_transcode_failure(self, source_file, output_file, process_result):
        """Handle transcode failure: log error and clean up partial output."""
        self._log(f'HandBrakeCLI failed for {source_file.name} (code {process_result.returncode}).', 'error')
        self._log(process_result.stdout, 'debug')

        # Clean up partial output file
        try:
            if output_file.exists():
                output_file.unlink()
        except Exception:
            pass

    def _mark_done(self):
        """Mark processing as complete and re-enable UI."""
        self._log('Processing finished.')
        # Ensure progress shows complete on UI
        try:
            self._message_queue.put(('progress', 100.0))
            self._message_queue.put(('progress_text', 'Done'))
        except Exception:
            pass
        # Re-enable controls
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

# ============================================================================
# Application Entry Point
# ============================================================================


def main():
    """Launch the application."""
    root = tk.Tk()
    app = TranscodeApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
