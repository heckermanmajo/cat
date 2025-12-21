<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatKnows - Download</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 16px;
            padding: 48px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            text-align: center;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 16px;
        }

        h1 {
            color: #1a1a2e;
            font-size: 32px;
            margin-bottom: 8px;
        }

        .tagline {
            color: #666;
            font-size: 16px;
            margin-bottom: 32px;
        }

        .detected-os {
            background: #f0f4ff;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            font-size: 14px;
            color: #4a5568;
        }

        .detected-os strong {
            color: #667eea;
        }

        .download-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 16px 32px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            width: 100%;
            margin-bottom: 16px;
        }

        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }

        .download-btn:active {
            transform: translateY(0);
        }

        .download-btn svg {
            width: 24px;
            height: 24px;
        }

        .other-platforms {
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid #e2e8f0;
        }

        .other-platforms h3 {
            color: #4a5568;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 12px;
        }

        .platform-links {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }

        .platform-link {
            color: #667eea;
            text-decoration: none;
            font-size: 13px;
            padding: 6px 12px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            transition: all 0.2s;
        }

        .platform-link:hover {
            background: #f0f4ff;
            border-color: #667eea;
        }

        .platform-link.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }

        .loading {
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🐱</div>
        <h1>CatKnows</h1>
        <p class="tagline">Lokale Analyse-Software</p>

        <div class="detected-os" id="detected-os">
            <span class="loading">Erkenne Betriebssystem...</span>
        </div>

        <a href="#" class="download-btn" id="download-btn" onclick="downloadForPlatform(); return false;">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span id="download-btn-text">Download</span>
        </a>

        <div class="other-platforms">
            <h3>Andere Plattformen</h3>
            <div class="platform-links" id="platform-links">
                <a href="/api/download.php?platform=macos-arm64" class="platform-link" data-platform="macos-arm64">macOS (Apple Silicon)</a>
                <a href="/api/download.php?platform=macos-amd64" class="platform-link" data-platform="macos-amd64">macOS (Intel)</a>
                <a href="/api/download.php?platform=windows-amd64" class="platform-link" data-platform="windows-amd64">Windows (64-bit)</a>
                <a href="/api/download.php?platform=linux-amd64" class="platform-link" data-platform="linux-amd64">Linux (64-bit)</a>
            </div>
        </div>
    </div>

    <script>
        // Platform detection based on browser metadata
        let detectedPlatform = 'linux-amd64';
        let detectedOsName = 'Linux';

        function detectPlatform() {
            const ua = navigator.userAgent;
            const platform = navigator.platform || '';

            // Detect OS
            if (ua.includes('Windows')) {
                detectedPlatform = 'windows-amd64';
                detectedOsName = 'Windows';
            } else if (ua.includes('Mac') || ua.includes('Macintosh')) {
                detectedOsName = 'macOS';
                // Try to detect Apple Silicon
                // Check for ARM indicators
                if (platform === 'MacIntel') {
                    // Could be either Intel or Rosetta 2 on Apple Silicon
                    // We'll try to detect via other means
                    try {
                        // Check for WebGL renderer which might indicate Apple Silicon
                        const canvas = document.createElement('canvas');
                        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        if (gl) {
                            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                            if (debugInfo) {
                                const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                                if (renderer && (renderer.includes('Apple M') || renderer.includes('Apple GPU'))) {
                                    detectedPlatform = 'macos-arm64';
                                    detectedOsName = 'macOS (Apple Silicon)';
                                } else {
                                    detectedPlatform = 'macos-amd64';
                                    detectedOsName = 'macOS (Intel)';
                                }
                            } else {
                                // Default to Apple Silicon for newer Macs
                                detectedPlatform = 'macos-arm64';
                                detectedOsName = 'macOS';
                            }
                        }
                    } catch (e) {
                        // Fallback to Intel
                        detectedPlatform = 'macos-amd64';
                        detectedOsName = 'macOS';
                    }
                } else if (platform.includes('arm') || platform.includes('ARM')) {
                    detectedPlatform = 'macos-arm64';
                    detectedOsName = 'macOS (Apple Silicon)';
                } else {
                    detectedPlatform = 'macos-amd64';
                    detectedOsName = 'macOS (Intel)';
                }
            } else if (ua.includes('Linux')) {
                detectedOsName = 'Linux';
                if (ua.includes('aarch64') || ua.includes('arm64')) {
                    // No ARM Linux build available, default to amd64
                    detectedPlatform = 'linux-amd64';
                    detectedOsName = 'Linux (ARM - using x64)';
                } else {
                    detectedPlatform = 'linux-amd64';
                }
            }

            updateUI();
        }

        function updateUI() {
            // Update detected OS display
            document.getElementById('detected-os').innerHTML =
                'Erkannt: <strong>' + detectedOsName + '</strong>';

            // Update download button text
            const osShort = detectedPlatform.split('-')[0];
            const osNames = {
                'macos': 'macOS',
                'windows': 'Windows',
                'linux': 'Linux'
            };
            document.getElementById('download-btn-text').textContent =
                'Download für ' + (osNames[osShort] || osShort);

            // Highlight active platform in links
            document.querySelectorAll('.platform-link').forEach(link => {
                link.classList.remove('active');
                if (link.dataset.platform === detectedPlatform) {
                    link.classList.add('active');
                }
            });
        }

        function downloadForPlatform() {
            window.location.href = '/api/download.php?platform=' + detectedPlatform;
        }

        // Run detection on page load
        detectPlatform();
    </script>
</body>
</html>
