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
const DOWNLOADS = [
    'windows' => ['file' => 'catknows-win.exe', 'label' => 'Windows'],
    'mac'     => ['file' => 'catknows-mac.zip', 'label' => 'macOS'],
    'linux'   => ['file' => 'catknows-linux.tar.gz', 'label' => 'Linux'],
];

$platform = detectPlatform();
$download = DOWNLOADS[$platform] ?? null;

// Download-Action: App
if(isset($_GET['download']) && isset(DOWNLOADS[$_GET['download']])) {
    $dl = DOWNLOADS[$_GET['download']];
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

// Download-Action: Plugin (dynamisch gezippt)
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
        .container { text-align: center; padding: 2rem; }
        h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        .subtitle { color: #888; margin-bottom: 2rem; }
        .download-btn { display: inline-block; background: #4a6cf7; color: #fff; padding: 1rem 2.5rem; border-radius: 8px; text-decoration: none; font-size: 1.2rem; font-weight: 600; transition: background 0.2s; }
        .download-btn:hover { background: #3a5cd7; }
        .platform { font-size: 0.9rem; color: #888; margin-top: 1rem; }
        .other-platforms { margin-top: 2rem; }
        .other-platforms a { color: #4a6cf7; margin: 0 1rem; text-decoration: none; }
        .other-platforms a:hover { text-decoration: underline; }
        .error { background: #f44; color: #fff; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
        .warning { background: #f80; color: #fff; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-size: 0.9rem; }
        .plugin-section { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid #333; }
        .plugin-section p { color: #888; margin-bottom: 0.5rem; font-size: 0.9rem; }
        .plugin-link { color: #4a6cf7; text-decoration: none; }
        .plugin-link:hover { text-decoration: underline; }
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

        <?php if($download): ?>
            <a href="?download=<?= $platform ?>" class="download-btn">Download für <?= $download['label'] ?></a>
            <p class="platform">Erkannte Plattform: <?= $download['label'] ?></p>
        <?php else: ?>
            <p>Plattform nicht erkannt. Bitte wähle:</p>
        <?php endif; ?>

        <div class="other-platforms">
            <?php foreach(DOWNLOADS as $key => $dl): ?>
                <?php if($key !== $platform): ?>
                    <a href="?download=<?= $key ?>"><?= $dl['label'] ?></a>
                <?php endif; ?>
            <?php endforeach; ?>
        </div>

        <div class="plugin-section">
            <p>Browser-Extension für Skool-Datenexport:</p>
            <a href="?plugin" class="plugin-link">Plugin herunterladen</a>
        </div>
    </div>
</body>
</html>
