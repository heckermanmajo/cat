# Deployment Guide

This document describes how to build and deploy the application.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions CI/CD                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Linux     │  │   Windows    │  │    macOS     │          │
│  │   (ubuntu)   │  │  (latest)    │  │   (latest)   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └────────────┬────┴────┬────────────┘                   │
│                      ▼         ▼                                │
│              ┌───────────────────────┐                          │
│              │   Artifacts per OS    │                          │
│              │  - CatKnows binary    │                          │
│              │  - Launcher binary    │                          │
│              └───────────┬───────────┘                          │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Deploy    │  │   Release   │  │  Artifacts  │             │
│  │  (Server)   │  │  (GitHub)   │  │  (Storage)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Build Process

### 1. Python Backend (Nuitka)

```bash
cd myversion
python build.py
```

This runs:
```bash
python -m nuitka \
    --onefile \
    --output-dir=dist \
    --output-filename=catknows \
    --include-data-dir=static=static \
    --include-data-dir=src=src \
    --enable-plugin=anti-bloat \
    app.py
```

Output: `myversion/dist/catknows` (or `catknows.exe` on Windows)

### 2. Launcher (Nuitka)

```bash
cd launcher
python build.py
```

Output: `launcher/dist/CatKnowsLauncher`

### 3. Electron App (electron-builder)

```bash
cd electron-fetcher
npm install
npm run build
```

The Python binary is copied into `electron-fetcher/python/` before build.

Output varies by platform:
- Linux: `dist/*.AppImage`
- Windows: `dist/*.exe`
- macOS: `dist/*.zip`

## Local Development

### Start Development Server

```bash
./start.sh
```

This script:
1. Activates Python venv
2. Starts Flask server (finds free port 3000-3100)
3. Writes port to `.port` file
4. Starts Electron pointing to Flask server
5. Kills Flask when Electron closes

### Manual Development

Terminal 1 - Backend:
```bash
source venv/bin/activate
cd myversion
python app.py
```

Terminal 2 - Frontend:
```bash
cd electron-fetcher
npm start
```

## CI/CD Pipeline (GitHub Actions)

### Trigger

```yaml
on:
  workflow_dispatch:
    inputs:
      deploy: boolean      # Deploy to production server
      release: boolean     # Create GitHub Release
      version: string      # Version number (e.g. "1.0.0")
```

### Build Matrix

```yaml
strategy:
  matrix:
    include:
      - os: ubuntu-latest
        platform: linux
        python_binary: catknows
        app_name: CatKnows.AppImage
      - os: windows-latest
        platform: windows
        python_binary: catknows.exe
        app_name: CatKnows.exe
      - os: macos-latest
        platform: macos
        python_binary: catknows
        app_name: CatKnows.zip
```

### Build Steps per Platform

1. **Setup Python 3.13** + install requirements
2. **Build Python with Nuitka** → `catknows` binary
3. **Build Launcher with Nuitka** → `CatKnowsLauncher`
4. **Copy Python binary** into `electron-fetcher/python/`
5. **Build Electron App** → Platform-specific package
6. **Create distribution package**:
   ```
   dist-package/
   ├── CatKnows.AppImage    # Main app
   ├── CatKnowsLauncher     # Launcher
   └── version.txt          # Version
   ```

### Deployment (Optional)

When `deploy: true`:

1. Download all build artifacts
2. Create deployment ZIPs:
   - `CatKnows-linux.zip` (full package)
   - `CatKnows-windows.zip`
   - `CatKnows-macos.zip`
   - Plus standalone apps for auto-updater
3. Deploy via SSH/SCP to production server

```bash
scp web.zip user@server:path/
ssh user@server "cd path && unzip -o web.zip"
```

### GitHub Release (Optional)

When `release: true`:

1. Update `version.txt`
2. Create and push git tag `v{version}`
3. Create GitHub Release with:
   - `CatKnows-linux.zip`
   - `CatKnows-windows.zip`
   - `CatKnows-macos.zip`

## Server Structure

### License Server (webserver/)

```
webserver/
├── index.php           # Landing page
├── core.php            # ORM + utilities
├── downloads/          # Built binaries
│   ├── version.txt
│   ├── CatKnows-linux.zip
│   ├── CatKnows-windows.zip
│   └── CatKnows-macos.zip
└── plugin/             # Browser extension
    └── popup.html
```

### Auto-Update Flow

1. Launcher reads local `version.txt`
2. Fetches `downloads/version.txt` from server
3. If newer version available:
   - Downloads new `CatKnows-{platform}.*`
   - Replaces local binary
4. Starts main application

## Environment Variables

### CI/CD Secrets

```
SSH_PRIVATE_KEY    # For server deployment
```

### Local Development

No environment variables required - all config is in SQLite database.

## File Structure After Build

```
project/
├── myversion/
│   └── dist/
│       └── catknows           # Compiled Python binary
├── launcher/
│   └── dist/
│       └── CatKnowsLauncher   # Compiled launcher
├── electron-fetcher/
│   ├── python/
│   │   └── catknows           # Copy for packaging
│   └── dist/
│       └── CatKnows.AppImage  # Final packaged app
└── dist-package/              # Distribution ready
    ├── CatKnows.AppImage
    ├── CatKnowsLauncher
    └── version.txt
```

## Testing

### Run Tests

```bash
# Fast (against Python directly)
./test_fast.sh

# Full (with Nuitka build)
./test.sh
```

Tests are in `tests/` directory. See `tests/testing.md` for details.
