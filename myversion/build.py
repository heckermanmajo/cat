#!/usr/bin/env python3
"""
Build-Script für CatKnows mit Nuitka
Erzeugt Standalone-Builds für die aktuelle Plattform

Windows: --standalone + zip (AV-freundlicher als onefile)
Linux: --standalone + tar.gz (kein FUSE nötig)
"""

import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

# Build-Konfiguration
VERSION = '1.0.0.0'
COPYRIGHT = '© 2025 CatKnows'


def build_linux(project_dir: Path, dist_dir: Path):
    """Linux: standalone build + tar.gz packaging"""
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--standalone',
        f'--output-dir={dist_dir}',
        '--include-data-dir=static=static',
        '--include-data-dir=src=src',
        '--assume-yes-for-downloads',
        '--remove-output',
        '--enable-plugin=anti-bloat',
        '--nofollow-import-to=pytest',
        '--nofollow-import-to=setuptools',
        'app.py'
    ]

    print('Building CatKnows for linux (standalone)...')
    print(f'Command: {" ".join(cmd)}')

    result = subprocess.run(cmd, cwd=project_dir)
    if result.returncode != 0:
        print(f'\nBuild fehlgeschlagen (exit code {result.returncode})')
        sys.exit(1)

    # Nuitka erzeugt app.dist Ordner
    standalone_dir = dist_dir / 'app.dist'
    if not standalone_dir.exists():
        print(f'\nFehler: {standalone_dir} nicht gefunden')
        sys.exit(1)

    # Umbenennen zu catknows
    final_dir = dist_dir / 'catknows'
    if final_dir.exists():
        shutil.rmtree(final_dir)
    standalone_dir.rename(final_dir)

    # Binary umbenennen
    binary = final_dir / 'app'
    if binary.exists():
        binary.rename(final_dir / 'catknows')

    # Als tar.gz packen
    tarball = dist_dir / 'catknows-linux.tar.gz'
    print(f'\nPacke als {tarball}...')
    with tarfile.open(tarball, 'w:gz') as tar:
        tar.add(final_dir, arcname='catknows')

    size_mb = tarball.stat().st_size / (1024 * 1024)
    print(f'\nBuild erfolgreich! {tarball} ({size_mb:.1f} MB)')
    print(f'Entpacken mit: tar -xzf {tarball.name}')
    print(f'Starten mit: ./catknows/catknows')


def build_windows(project_dir: Path, dist_dir: Path):
    """Windows: standalone build + zip packaging (AV-freundlicher als onefile)"""
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--standalone',
        f'--output-dir={dist_dir}',
        '--include-data-dir=static=static',
        '--include-data-dir=src=src',
        '--assume-yes-for-downloads',
        '--remove-output',
        '--enable-plugin=anti-bloat',
        '--nofollow-import-to=pytest',
        '--nofollow-import-to=setuptools',
        # Windows-Metadaten (reduziert AV false positives)
        '--windows-icon-from-ico=icon.ico',
        '--windows-company-name=CatKnows',
        '--windows-product-name=CatKnows',
        f'--windows-file-version={VERSION}',
        f'--windows-product-version={VERSION}',
        '--windows-file-description=Skool Community Analyzer',
        f'--windows-copyright={COPYRIGHT}',
        '--windows-console-mode=disable',
        'app.py'
    ]

    print('Building CatKnows for windows (standalone)...')
    print(f'Command: {" ".join(cmd)}')

    result = subprocess.run(cmd, cwd=project_dir)
    if result.returncode != 0:
        print(f'\nBuild fehlgeschlagen (exit code {result.returncode})')
        sys.exit(1)

    # Nuitka erzeugt app.dist Ordner
    standalone_dir = dist_dir / 'app.dist'
    if not standalone_dir.exists():
        print(f'\nFehler: {standalone_dir} nicht gefunden')
        sys.exit(1)

    # Umbenennen zu catknows
    final_dir = dist_dir / 'catknows'
    if final_dir.exists():
        shutil.rmtree(final_dir)
    standalone_dir.rename(final_dir)

    # Binary umbenennen
    binary = final_dir / 'app.exe'
    if binary.exists():
        binary.rename(final_dir / 'catknows.exe')

    # Als zip packen
    zip_path = dist_dir / 'catknows-windows.zip'
    print(f'\nPacke als {zip_path}...')
    shutil.make_archive(str(dist_dir / 'catknows-windows'), 'zip', dist_dir, 'catknows')

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f'\nBuild erfolgreich! {zip_path} ({size_mb:.1f} MB)')
    print(f'Entpacken und starten mit: catknows\\catknows.exe')


def main():
    project_dir = Path(__file__).parent
    dist_dir = project_dir / 'dist'
    dist_dir.mkdir(exist_ok=True)

    system = platform.system().lower()

    if system == 'linux':
        build_linux(project_dir, dist_dir)
    elif system == 'windows':
        build_windows(project_dir, dist_dir)
    else:
        print(f'Unsupported platform: {system}')
        sys.exit(1)


if __name__ == '__main__':
    main()
