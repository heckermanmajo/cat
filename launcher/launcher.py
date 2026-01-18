#!/usr/bin/env python3
"""
CatKnows Launcher - Auto-updater and application launcher
Downloads new versions from server if available, then launches main app.
"""

import os
import sys
import json
import platform
import subprocess
import urllib.request
import urllib.error
import tempfile
import shutil
from pathlib import Path

# Configuration
VERSION_URL = "https://testing.cat-knows.com/version.php"
CONNECT_TIMEOUT = 5

def get_app_dir() -> Path:
    """Get directory where launcher is running from."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_platform() -> str:
    """Get current platform identifier."""
    system = platform.system().lower()
    if system == 'windows': return 'windows'
    if system == 'darwin': return 'mac'
    return 'linux'

def get_executable_name() -> str:
    """Get main app executable name for current platform."""
    plat = get_platform()
    if plat == 'windows': return 'CatKnows.exe'
    if plat == 'mac': return 'CatKnows.app'
    return 'CatKnows.AppImage'

def read_local_version(app_dir: Path) -> str:
    """Read local version from version.txt."""
    version_file = app_dir / 'version.txt'
    if version_file.exists():
        return version_file.read_text().strip()
    return '0.0.0'

def write_local_version(app_dir: Path, version: str) -> None:
    """Write version to version.txt."""
    version_file = app_dir / 'version.txt'
    version_file.write_text(version)

def fetch_remote_version() -> dict | None:
    """Fetch version info from server. Returns None on error."""
    try:
        req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'CatKnowsLauncher'})
        with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None

def compare_versions(local: str, remote: str) -> bool:
    """Return True if remote is newer than local."""
    def parse(v: str) -> tuple:
        return tuple(int(x) for x in v.split('.') if x.isdigit())
    try:
        return parse(remote) > parse(local)
    except ValueError:
        return False

def download_file(url: str, dest: Path, progress_callback=None) -> bool:
    """Download file from URL to destination. Returns success."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CatKnowsLauncher'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            with open(dest, 'wb') as f:
                while chunk := resp.read(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)
        return True
    except Exception:
        return False

def launch_app(app_dir: Path) -> None:
    """Launch the main application."""
    exe_name = get_executable_name()
    exe_path = app_dir / exe_name

    if not exe_path.exists():
        show_error(f"Application not found: {exe_name}")
        sys.exit(1)

    plat = get_platform()
    if plat == 'windows':
        os.startfile(exe_path)
    elif plat == 'mac':
        subprocess.Popen(['open', str(exe_path)])
    else:
        os.chmod(exe_path, 0o755)
        subprocess.Popen([str(exe_path)])

def show_error(message: str) -> None:
    """Show error message (GUI if available, else console)."""
    print(f"ERROR: {message}", file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("CatKnows Launcher", message)
        root.destroy()
    except ImportError:
        pass

def run_with_gui() -> None:
    """Run launcher with tkinter GUI for progress."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        run_headless()
        return

    app_dir = get_app_dir()
    local_version = read_local_version(app_dir)

    # Create simple window
    root = tk.Tk()
    root.title("CatKnows")
    root.geometry("300x100")
    root.resizable(False, False)

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 300) // 2
    y = (root.winfo_screenheight() - 100) // 2
    root.geometry(f"300x100+{x}+{y}")

    label = tk.Label(root, text="Checking for updates...", pady=10)
    label.pack()

    progress = ttk.Progressbar(root, length=250, mode='indeterminate')
    progress.pack(pady=10)
    progress.start(10)

    def check_and_update():
        remote = fetch_remote_version()

        if remote is None:
            label.config(text="Starting CatKnows...")
            root.after(500, lambda: finish(root, app_dir))
            return

        remote_version = remote.get('version', '0.0.0')

        if not compare_versions(local_version, remote_version):
            label.config(text="Starting CatKnows...")
            root.after(500, lambda: finish(root, app_dir))
            return

        # Update available
        plat = get_platform()
        download_url = remote.get(plat)

        if not download_url:
            label.config(text="Starting CatKnows...")
            root.after(500, lambda: finish(root, app_dir))
            return

        label.config(text=f"Downloading update {remote_version}...")
        progress.stop()
        progress.config(mode='determinate', value=0)

        def update_progress(downloaded, total):
            pct = (downloaded / total) * 100
            progress['value'] = pct
            root.update_idletasks()

        # Download to temp file
        exe_name = get_executable_name()
        temp_file = Path(tempfile.gettempdir()) / f"catknows_update_{exe_name}"

        if download_file(download_url, temp_file, update_progress):
            # Replace executable
            exe_path = app_dir / exe_name
            try:
                if exe_path.exists():
                    exe_path.unlink()
                shutil.move(str(temp_file), str(exe_path))
                write_local_version(app_dir, remote_version)
                label.config(text="Update complete!")
            except Exception as e:
                label.config(text="Update failed, starting anyway...")
        else:
            label.config(text="Download failed, starting anyway...")

        root.after(500, lambda: finish(root, app_dir))

    def finish(root, app_dir):
        root.destroy()
        launch_app(app_dir)

    root.after(100, check_and_update)
    root.mainloop()

def run_headless() -> None:
    """Run launcher without GUI."""
    app_dir = get_app_dir()
    local_version = read_local_version(app_dir)

    print(f"CatKnows Launcher - Local version: {local_version}")
    print("Checking for updates...")

    remote = fetch_remote_version()

    if remote is None:
        print("Could not reach update server, starting app...")
        launch_app(app_dir)
        return

    remote_version = remote.get('version', '0.0.0')

    if not compare_versions(local_version, remote_version):
        print(f"Already up to date (v{local_version})")
        launch_app(app_dir)
        return

    plat = get_platform()
    download_url = remote.get(plat)

    if not download_url:
        print(f"No download available for {plat}")
        launch_app(app_dir)
        return

    print(f"Downloading update {remote_version}...")

    exe_name = get_executable_name()
    temp_file = Path(tempfile.gettempdir()) / f"catknows_update_{exe_name}"

    def print_progress(downloaded, total):
        pct = (downloaded / total) * 100
        print(f"\rProgress: {pct:.1f}%", end='', flush=True)

    if download_file(download_url, temp_file, print_progress):
        print("\nInstalling update...")
        exe_path = app_dir / exe_name
        try:
            if exe_path.exists():
                exe_path.unlink()
            shutil.move(str(temp_file), str(exe_path))
            write_local_version(app_dir, remote_version)
            print("Update complete!")
        except Exception as e:
            print(f"Update failed: {e}")
    else:
        print("\nDownload failed")

    launch_app(app_dir)

def main():
    # Use GUI on Windows/Mac, headless on Linux (unless display available)
    plat = get_platform()
    has_display = os.environ.get('DISPLAY') or plat in ('windows', 'mac')

    if has_display:
        run_with_gui()
    else:
        run_headless()

if __name__ == '__main__':
    main()
