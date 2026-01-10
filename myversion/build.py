#!/usr/bin/env python3
"""
Build-Script für CatKnows mit Nuitka
Erzeugt eine Single Binary für die aktuelle Plattform
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
    binary_name = 'catknows.exe' if system == 'windows' else 'catknows'

    cmd = [
        sys.executable, '-m', 'nuitka',
        '--onefile',
        f'--output-dir={dist_dir}',
        f'--output-filename={binary_name}',
        '--include-data-dir=static=static',
        '--include-data-dir=src=src',
        '--assume-yes-for-downloads',
        '--remove-output',
        '--enable-plugin=anti-bloat',
        '--nofollow-import-to=pytest',
        '--nofollow-import-to=setuptools',
        'app.py'
    ]

    print(f'Building CatKnows for {system}...')
    print(f'Command: {" ".join(cmd)}')

    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode == 0:
        output_path = dist_dir / binary_name
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f'\nBuild erfolgreich! {output_path} ({size_mb:.1f} MB)')
        else:
            print(f'\nBuild abgeschlossen, Binary-Pfad prüfen.')
    else:
        print(f'\nBuild fehlgeschlagen (exit code {result.returncode})')
        sys.exit(1)

if __name__ == '__main__':
    main()
