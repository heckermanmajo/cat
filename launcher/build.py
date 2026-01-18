#!/usr/bin/env python3
"""
Build-Script for CatKnows Launcher with Nuitka
Creates a small single binary for the current platform
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

def main():
    project_dir = Path(__file__).parent
    dist_dir = project_dir / 'dist'
    dist_dir.mkdir(exist_ok=True)

    system = platform.system().lower()
    binary_name = 'CatKnowsLauncher.exe' if system == 'windows' else 'CatKnowsLauncher'

    cmd = [
        sys.executable, '-m', 'nuitka',
        '--onefile',
        f'--output-dir={dist_dir}',
        f'--output-filename={binary_name}',
        '--assume-yes-for-downloads',
        '--remove-output',
        '--enable-plugin=anti-bloat',
        '--enable-plugin=tk-inter',
        '--nofollow-import-to=pytest',
        '--nofollow-import-to=setuptools',
        '--nofollow-import-to=pip',
        'launcher.py'
    ]

    # Windows: hide console window
    if system == 'windows':
        cmd.insert(-1, '--windows-console-mode=disable')

    print(f'Building CatKnows Launcher for {system}...')
    print(f'Command: {" ".join(cmd)}')

    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode == 0:
        output_path = dist_dir / binary_name
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f'\nBuild successful! {output_path} ({size_mb:.1f} MB)')
        else:
            print(f'\nBuild completed, check binary path.')
    else:
        print(f'\nBuild failed (exit code {result.returncode})')
        sys.exit(1)

if __name__ == '__main__':
    main()
