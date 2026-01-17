<?php
declare(strict_types = 1);

// Plattform-Erkennung via User-Agent
function detectPlatform(): string {
    $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
    if(stripos($ua, 'Windows') !== false) return 'windows';
    if(stripos($ua, 'Mac') !== false) return 'mac';
    if(stripos($ua, 'Linux') !== false) return 'linux';
    return 'unknown';
}

// Download-Dateien pro Plattform
const DOWNLOADS_APP = [
    'windows' => ['file' => 'catknows-win.exe', 'label' => 'Windows'],
    'mac'     => ['file' => 'catknows-mac.zip', 'label' => 'macOS'],
    'linux'   => ['file' => 'catknows-linux.tar.gz', 'label' => 'Linux'],
];

const DOWNLOADS_FETCHER = [
    'windows' => ['file' => 'fetcher-win.exe', 'label' => 'Windows'],
    'mac'     => ['file' => 'fetcher-mac.zip', 'label' => 'macOS'],
    'linux'   => ['file' => 'fetcher-linux.AppImage', 'label' => 'Linux'],
];

$platform = detectPlatform();
$downloadApp = DOWNLOADS_APP[$platform] ?? null;
$downloadFetcher = DOWNLOADS_FETCHER[$platform] ?? null;

// Download-Action: App
if(isset($_GET['download']) && isset(DOWNLOADS_APP[$_GET['download']])) {
    $dl = DOWNLOADS_APP[$_GET['download']];
    $path = __DIR__ . '/downloads/' . $dl['file'];
    if(file_exists($path)) {
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . $dl['file'] . '"');
        header('Content-Length: ' . filesize($path));
        readfile($path);
        exit;
    }
    $error = "Datei nicht gefunden: {$dl['file']}";
}

// Download-Action: Fetcher
if(isset($_GET['fetcher']) && isset(DOWNLOADS_FETCHER[$_GET['fetcher']])) {
    $dl = DOWNLOADS_FETCHER[$_GET['fetcher']];
    $path = __DIR__ . '/downloads/' . $dl['file'];
    if(file_exists($path)) {
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . $dl['file'] . '"');
        header('Content-Length: ' . filesize($path));
        readfile($path);
        exit;
    }
    $error = "Datei nicht gefunden: {$dl['file']}";
}

// Download-Action: Plugin (Legacy - dynamisch gezippt)
if(isset($_GET['plugin'])) {
    $pluginDir = __DIR__ . '/plugin';
    if(!is_dir($pluginDir)) { $error = "Plugin-Ordner nicht gefunden"; }
    else {
        $zip = new ZipArchive();
        $tmpFile = tempnam(sys_get_temp_dir(), 'plugin') . '.zip';
        if($zip->open($tmpFile, ZipArchive::CREATE) === true) {
            foreach(glob($pluginDir . '/*') as $file) {
                $zip->addFile($file, basename($file));
            }
            $zip->close();
            header('Content-Type: application/zip');
            header('Content-Disposition: attachment; filename="catknows-plugin.zip"');
            header('Content-Length: ' . filesize($tmpFile));
            readfile($tmpFile);
            unlink($tmpFile);
            exit;
        }
        $error = "ZIP-Erstellung fehlgeschlagen";
    }
}
?>
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatKnows Download</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { text-align: center; padding: 2rem; max-width: 600px; }
        h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        h2 { font-size: 1.3rem; margin-bottom: 0.5rem; color: #ccc; }
        .subtitle { color: #888; margin-bottom: 2rem; }
        .info { color: #888; font-size: 0.9rem; margin-bottom: 1rem; }
        .download-section { background: #252545; padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; }
        .download-btn { display: inline-block; background: #4a6cf7; color: #fff; padding: 1rem 2.5rem; border-radius: 8px; text-decoration: none; font-size: 1.1rem; font-weight: 600; transition: background 0.2s; }
        .download-btn:hover { background: #3a5cd7; }
        .download-btn.secondary { background: #555; }
        .download-btn.secondary:hover { background: #666; }
        .platform { font-size: 0.9rem; color: #888; margin-top: 1rem; }
        .other-platforms { margin-top: 1rem; }
        .other-platforms a { color: #4a6cf7; margin: 0 0.8rem; text-decoration: none; font-size: 0.9rem; }
        .other-platforms a:hover { text-decoration: underline; }
        .error { background: #f44; color: #fff; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
        .warning { background: #f80; color: #fff; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-size: 0.9rem; }
        .plugin-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #333; }
        .plugin-section p { color: #666; margin-bottom: 0.5rem; font-size: 0.85rem; }
        .plugin-link { color: #666; text-decoration: none; font-size: 0.85rem; }
        .plugin-link:hover { text-decoration: underline; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <h1>CatKnows</h1>
        <p class="subtitle">Skool Community Analyzer</p>

        <div class="warning">Beta-Version - Software noch in Entwicklung</div>

        <?php if(isset($error)): ?>
            <div class="error"><?= htmlspecialchars($error) ?></div>
        <?php endif; ?>

        <!-- Fetcher Download (Hauptdownload) -->
        <div class="download-section">
            <h2>1. Fetcher herunterladen</h2>
            <p class="info">Die Fetcher-App holt Daten von Skool</p>
            <?php if($downloadFetcher): ?>
                <a href="?fetcher=<?= $platform ?>" class="download-btn">Fetcher für <?= $downloadFetcher['label'] ?></a>
            <?php endif; ?>
            <div class="other-platforms">
                <?php foreach(DOWNLOADS_FETCHER as $key => $dl): ?>
                    <?php if($key !== $platform): ?>
                        <a href="?fetcher=<?= $key ?>"><?= $dl['label'] ?></a>
                    <?php endif; ?>
                <?php endforeach; ?>
            </div>
        </div>

        <!-- App Download -->
        <div class="download-section">
            <h2>2. Analyzer herunterladen</h2>
            <p class="info">Die Analyzer-App wertet die Daten aus</p>
            <?php if($downloadApp): ?>
                <a href="?download=<?= $platform ?>" class="download-btn secondary">Analyzer für <?= $downloadApp['label'] ?></a>
            <?php endif; ?>
            <div class="other-platforms">
                <?php foreach(DOWNLOADS_APP as $key => $dl): ?>
                    <?php if($key !== $platform): ?>
                        <a href="?download=<?= $key ?>"><?= $dl['label'] ?></a>
                    <?php endif; ?>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="platform">Erkannte Plattform: <?= $downloadApp['label'] ?? 'Unbekannt' ?></p>

        <div class="plugin-section">
            <p>Alternative: Browser-Extension (Legacy)</p>
            <a href="?plugin" class="plugin-link">Plugin herunterladen</a>
        </div>
    </div>
</body>
</html>
