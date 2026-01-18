# Update Server Guide

This document describes how the update/download server works and how the auto-update system functions.

## Overview

The update server serves two purposes:
1. **Download Portal** - Landing page for new users to download the app
2. **Version API** - Endpoint for the launcher to check for updates

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Update Flow                                 │
│                                                                      │
│   User's Machine                         Server (webserver/)         │
│   ┌─────────────────┐                   ┌──────────────────────────┐│
│   │                 │                   │                          ││
│   │  ┌───────────┐  │  1. Check version │  ┌────────────────────┐  ││
│   │  │ Launcher  │──┼──────────────────▶│  │   version.php      │  ││
│   │  │           │  │                   │  │   {version, urls}  │  ││
│   │  │           │◀─┼───────────────────│  └────────────────────┘  ││
│   │  └─────┬─────┘  │  JSON response    │                          ││
│   │        │        │                   │  ┌────────────────────┐  ││
│   │        │ newer? │  2. Download      │  │   downloads/       │  ││
│   │        │        │                   │  │   ├─ version.txt   │  ││
│   │        ▼        │                   │  │   ├─ CatKnows-*.exe│  ││
│   │  ┌───────────┐  │──────────────────▶│  │   ├─ CatKnows-*.zip│  ││
│   │  │ Download  │  │                   │  │   └─ ...           │  ││
│   │  │ & Replace │◀─┼───────────────────│  └────────────────────┘  ││
│   │  └─────┬─────┘  │  Binary file      │                          ││
│   │        │        │                   │  ┌────────────────────┐  ││
│   │        ▼        │                   │  │   index.php        │  ││
│   │  ┌───────────┐  │                   │  │   (download page)  │  ││
│   │  │ CatKnows  │  │                   │  └────────────────────┘  ││
│   │  │   .exe    │  │                   │                          ││
│   │  └───────────┘  │                   └──────────────────────────┘│
│   └─────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Server Structure

```
webserver/
├── core.php           # Shared ORM + utilities (for license management)
├── index.php          # Download landing page
├── version.php        # Version API for auto-updater
├── downloads/         # Binary files
│   ├── version.txt    # Current version (e.g. "1.2.3")
│   ├── CatKnows-win.exe       # Windows standalone (for updates)
│   ├── CatKnows-mac.zip       # macOS standalone (for updates)
│   ├── CatKnows-linux.AppImage # Linux standalone (for updates)
│   ├── CatKnows-windows.zip   # Full package (with launcher)
│   ├── CatKnows-macos.zip     # Full package (with launcher)
│   └── CatKnows-linux.zip     # Full package (with launcher)
└── plugin/            # Browser extension (optional)
```

## Components

### Download Page (`index.php`)

Landing page for new users:

```php
<?php
// Detect platform from User-Agent
function detectPlatform(): string {
    $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
    if(stripos($ua, 'Windows') !== false) return 'windows';
    if(stripos($ua, 'Mac') !== false) return 'mac';
    if(stripos($ua, 'Linux') !== false) return 'linux';
    return 'unknown';
}

// Download files per platform (full distribution with launcher)
const DOWNLOADS = [
    'windows' => ['file' => 'CatKnows-windows.zip', 'label' => 'Windows'],
    'mac'     => ['file' => 'CatKnows-macos.zip', 'label' => 'macOS'],
    'linux'   => ['file' => 'CatKnows-linux.zip', 'label' => 'Linux'],
];

// Handle download
if(isset($_GET['download']) && isset(DOWNLOADS[$_GET['download']])) {
    $dl = DOWNLOADS[$_GET['download']];
    $path = __DIR__ . '/downloads/' . $dl['file'];
    if(file_exists($path)) {
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . $dl['file'] . '"');
        readfile($path);
        exit;
    }
}
?>
<!-- HTML download page with platform detection -->
```

Features:
- Auto-detects user's platform
- Shows primary download button for detected platform
- Lists other platforms as secondary options

### Version API (`version.php`)

JSON endpoint for launcher to check versions:

```php
<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$versionFile = __DIR__ . '/downloads/version.txt';
$version = file_exists($versionFile)
    ? trim(file_get_contents($versionFile))
    : '0.0.0';

$baseUrl = 'https://' . $_SERVER['HTTP_HOST'] . '/downloads';

echo json_encode([
    'version' => $version,
    'windows' => $baseUrl . '/CatKnows-win.exe',
    'mac'     => $baseUrl . '/CatKnows-mac.zip',
    'linux'   => $baseUrl . '/CatKnows-linux.AppImage',
]);
```

Response format:
```json
{
    "version": "1.2.3",
    "windows": "https://example.com/downloads/CatKnows-win.exe",
    "mac": "https://example.com/downloads/CatKnows-mac.zip",
    "linux": "https://example.com/downloads/CatKnows-linux.AppImage"
}
```

## Launcher (Client Side)

### Location

```
launcher/
├── launcher.py    # Main launcher script
└── build.py       # Nuitka build script
```

### Update Flow

```python
def main():
    app_dir = get_app_dir()
    local_version = read_local_version(app_dir)  # from version.txt

    # 1. Fetch remote version
    remote = fetch_remote_version()  # GET /version.php
    if remote is None:
        launch_app(app_dir)  # Offline - just start
        return

    remote_version = remote.get('version', '0.0.0')

    # 2. Compare versions
    if not compare_versions(local_version, remote_version):
        launch_app(app_dir)  # Up to date
        return

    # 3. Download update
    download_url = remote.get(get_platform())  # windows/mac/linux
    temp_file = download_file(download_url)

    # 4. Replace executable
    exe_path = app_dir / get_executable_name()
    exe_path.unlink()
    shutil.move(temp_file, exe_path)
    write_local_version(app_dir, remote_version)

    # 5. Launch
    launch_app(app_dir)
```

### Version Comparison

Simple semantic versioning:

```python
def compare_versions(local: str, remote: str) -> bool:
    """Return True if remote is newer than local."""
    def parse(v: str) -> tuple:
        return tuple(int(x) for x in v.split('.') if x.isdigit())
    return parse(remote) > parse(local)

# Examples:
compare_versions("1.0.0", "1.0.1")  # True (update available)
compare_versions("1.0.1", "1.0.0")  # False (already newer)
compare_versions("1.0.0", "1.0.0")  # False (same version)
```

### GUI vs Headless

```python
def main():
    platform = get_platform()
    has_display = os.environ.get('DISPLAY') or platform in ('windows', 'mac')

    if has_display:
        run_with_gui()     # tkinter progress bar
    else:
        run_headless()     # console output
```

## Distribution Packages

### Full Package (for new users)

Downloaded from landing page, contains:

```
CatKnows-windows.zip/
├── CatKnowsLauncher.exe   # Small launcher (~5MB)
├── CatKnows.exe           # Main app (~50MB)
└── version.txt            # Current version
```

User runs `CatKnowsLauncher.exe` which:
1. Checks for updates
2. Downloads new `CatKnows.exe` if needed
3. Launches main app

### Standalone (for updates)

Downloaded by launcher, replaces only the main app:
- `CatKnows-win.exe` - Windows portable
- `CatKnows-mac.zip` - macOS app bundle
- `CatKnows-linux.AppImage` - Linux AppImage

## Deployment (CI/CD)

### File Generation

GitHub Actions builds and uploads:

```yaml
# Prepare deployment package
- name: Prepare deployment package
  run: |
    mkdir -p webserver/downloads

    # Version file
    cp version.txt webserver/downloads/

    # Standalone apps for auto-updater
    cp electron-fetcher/dist/*.exe webserver/downloads/CatKnows-win.exe
    cp electron-fetcher/dist/*.zip webserver/downloads/CatKnows-mac.zip
    cp electron-fetcher/dist/*.AppImage webserver/downloads/CatKnows-linux.AppImage

    # Full distribution ZIPs (with launcher)
    cd artifacts/catknows-windows && zip -r ../../webserver/downloads/CatKnows-windows.zip ./*
    cd artifacts/catknows-macos && zip -r ../../webserver/downloads/CatKnows-macos.zip ./*
    cd artifacts/catknows-linux && zip -r ../../webserver/downloads/CatKnows-linux.zip ./*
```

### Upload to Server

```yaml
- name: Deploy to production server
  run: |
    scp web.zip user@server:/path/
    ssh user@server "cd /path && unzip -o web.zip"
```

## Reproducing This Pattern

### 1. Version API

Create `version.php`:

```php
<?php
header('Content-Type: application/json');
$version = trim(file_get_contents('downloads/version.txt'));
echo json_encode([
    'version' => $version,
    'windows' => 'https://yoursite.com/downloads/App-win.exe',
    'mac'     => 'https://yoursite.com/downloads/App-mac.zip',
    'linux'   => 'https://yoursite.com/downloads/App-linux.AppImage',
]);
```

### 2. Launcher

Create Python launcher:

```python
import urllib.request
import json

VERSION_URL = "https://yoursite.com/version.php"

def check_update():
    with urllib.request.urlopen(VERSION_URL) as resp:
        remote = json.loads(resp.read())

    local = read_version_file()

    if parse_version(remote['version']) > parse_version(local):
        download_and_replace(remote[get_platform()])
        write_version_file(remote['version'])

    launch_main_app()
```

### 3. Build Launcher

```python
# build.py
subprocess.run([
    'python', '-m', 'nuitka',
    '--onefile',
    '--output-filename=AppLauncher',
    'launcher.py'
])
```

### 4. Package Distribution

```
MyApp/
├── AppLauncher.exe    # Small, checks updates
├── MyApp.exe          # Main app, replaceable
└── version.txt        # Local version
```

## Security Considerations

- **HTTPS required** - All downloads over HTTPS
- **No code signing** (optional) - Consider signing for production
- **Server validation** - Launcher trusts server completely
- **Rollback** - No automatic rollback on failed update

## Troubleshooting

### Update not detected
- Check `version.txt` on server matches build version
- Verify `version.php` returns correct JSON

### Download fails
- Check file permissions on server
- Verify file paths in `version.php`

### App won't start after update
- Binary permissions (Linux: needs `chmod +x`)
- Quarantine (macOS: may need user approval)
