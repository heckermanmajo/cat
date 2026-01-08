<?php
require_once __DIR__ . '/core.php';

// Download-Handler
if(isset($_GET['platform'])) {
    $platform = $_GET['platform'];
    $files = [
        'macos-arm64'   => 'catknows-macos-arm64.zip',
        'macos-amd64'   => 'catknows-macos-amd64.zip',
        'windows-amd64' => 'catknows-windows-amd64.zip',
        'linux-amd64'   => 'catknows-linux-amd64.zip',
    ];

    if(!isset($files[$platform])) {
        http_response_code(404);
        die('Unbekannte Plattform');
    }

    $file = __DIR__ . '/releases/' . $files[$platform];

    if(!file_exists($file)) {
        http_response_code(404);
        die('Datei nicht gefunden: ' . $files[$platform]);
    }

    header('Content-Type: application/zip');
    header('Content-Disposition: attachment; filename="' . $files[$platform] . '"');
    header('Content-Length: ' . filesize($file));
    readfile($file);
    exit;
}
?>
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<title>Download - CatKnows</title>
<style><?= css() ?></style>
</head><body>

<h1>CatKnows Download</h1>

<div class="card">
    <div class="card-header">Download</div>
    <div class="card-body">
        <p id="detected" style="margin-bottom:20px">Erkenne Betriebssystem...</p>

        <p><a href="#" id="download-btn" class="btn">Download</a></p>

        <hr style="margin:20px 0;border:none;border-top:1px solid #ddd">

        <p><strong>Andere Plattformen:</strong></p>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
            <a href="?platform=macos-arm64" class="btn btn-outline btn-sm" data-platform="macos-arm64">macOS (Apple Silicon)</a>
            <a href="?platform=macos-amd64" class="btn btn-outline btn-sm" data-platform="macos-amd64">macOS (Intel)</a>
            <a href="?platform=windows-amd64" class="btn btn-outline btn-sm" data-platform="windows-amd64">Windows (64-bit)</a>
            <a href="?platform=linux-amd64" class="btn btn-outline btn-sm" data-platform="linux-amd64">Linux (64-bit)</a>
        </div>
    </div>
</div>

<script>
let platform = 'linux-amd64';
let osName = 'Linux';

const ua = navigator.userAgent;
if(ua.includes('Windows')) {
    platform = 'windows-amd64';
    osName = 'Windows';
} else if(ua.includes('Mac')) {
    osName = 'macOS';
    // Versuche Apple Silicon zu erkennen
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl');
        if(gl) {
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if(dbg) {
                const renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                if(renderer && (renderer.includes('Apple M') || renderer.includes('Apple GPU'))) {
                    platform = 'macos-arm64';
                    osName = 'macOS (Apple Silicon)';
                } else {
                    platform = 'macos-amd64';
                    osName = 'macOS (Intel)';
                }
            } else {
                platform = 'macos-arm64'; // Default zu ARM für neuere Macs
            }
        }
    } catch(e) {
        platform = 'macos-amd64';
    }
} else if(ua.includes('Linux')) {
    platform = 'linux-amd64';
    osName = 'Linux';
}

document.getElementById('detected').innerHTML = 'Erkannt: <strong>' + osName + '</strong>';
document.getElementById('download-btn').href = '?platform=' + platform;
document.getElementById('download-btn').textContent = 'Download fuer ' + osName;

// Aktive Plattform markieren
document.querySelectorAll('[data-platform]').forEach(el => {
    if(el.dataset.platform === platform) {
        el.classList.remove('btn-outline');
    }
});
</script>

</body></html>
