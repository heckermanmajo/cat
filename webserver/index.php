<?php
declare(strict_types = 1);

// Platform detection via User-Agent
function detectPlatform(): string {
    $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
    if(stripos($ua, 'Windows') !== false) return 'windows';
    if(stripos($ua, 'Mac') !== false) return 'mac';
    if(stripos($ua, 'Linux') !== false) return 'linux';
    return 'unknown';
}

// Download files per platform (full distribution with launcher)
const DOWNLOADS = [
    'windows' => ['file' => 'CatKnows-windows.zip', 'label' => 'Windows', 'icon' => '🪟'],
    'mac'     => ['file' => 'CatKnows-macos.zip', 'label' => 'macOS', 'icon' => '🍎'],
    'linux'   => ['file' => 'CatKnows-linux.zip', 'label' => 'Linux', 'icon' => '🐧'],
];

$platform = detectPlatform();
$download = DOWNLOADS[$platform] ?? null;

// Download action
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
    $error = "File not found: {$dl['file']}";
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatKnows - Download</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            padding: 2rem;
            max-width: 500px;
        }
        .logo {
            width: 100px;
            height: 100px;
            margin-bottom: 20px;
            border-radius: 20px;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #fff, #a5b4fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: #888;
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }
        .warning {
            background: linear-gradient(90deg, #f59e0b, #d97706);
            color: #fff;
            padding: 0.8rem 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            font-size: 0.9rem;
            font-weight: 500;
        }
        .download-btn {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            background: linear-gradient(90deg, #4f46e5, #6366f1);
            color: #fff;
            padding: 1rem 2.5rem;
            border-radius: 12px;
            text-decoration: none;
            font-size: 1.2rem;
            font-weight: 600;
            transition: all 0.2s;
            box-shadow: 0 4px 15px rgba(79, 70, 229, 0.4);
        }
        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5);
        }
        .download-btn .icon {
            font-size: 1.5rem;
        }
        .platform {
            font-size: 0.85rem;
            color: #666;
            margin-top: 1rem;
        }
        .other-platforms {
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #333;
        }
        .other-platforms p {
            color: #666;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }
        .other-platforms a {
            color: #6366f1;
            margin: 0 1rem;
            text-decoration: none;
            font-size: 0.95rem;
        }
        .other-platforms a:hover {
            text-decoration: underline;
        }
        .error {
            background: #dc2626;
            color: #fff;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }
        .features {
            margin-top: 3rem;
            text-align: left;
            background: rgba(255,255,255,0.05);
            padding: 1.5rem;
            border-radius: 12px;
        }
        .features h3 {
            font-size: 1rem;
            margin-bottom: 1rem;
            color: #a5b4fc;
        }
        .features ul {
            list-style: none;
            font-size: 0.9rem;
            color: #999;
        }
        .features li {
            padding: 0.4rem 0;
        }
        .features li::before {
            content: "✓ ";
            color: #22c55e;
        }
    </style>
</head>
<body>
    <div class="container">
        <img src="icon.png" class="logo" alt="CatKnows" onerror="this.style.display='none'">
        <h1>CatKnows</h1>
        <p class="subtitle">Skool Community Analyzer</p>

        <div class="warning">Beta Version - Software in development</div>

        <?php if(isset($error)): ?>
            <div class="error"><?= htmlspecialchars($error) ?></div>
        <?php endif; ?>

        <?php if($download): ?>
            <a href="?download=<?= $platform ?>" class="download-btn">
                <span class="icon"><?= $download['icon'] ?></span>
                <span>Download for <?= $download['label'] ?></span>
            </a>
            <p class="platform">Detected platform: <?= $download['label'] ?></p>
        <?php else: ?>
            <p style="color: #888; margin-bottom: 1rem;">Platform not detected. Please select:</p>
            <div>
                <?php foreach(DOWNLOADS as $key => $dl): ?>
                    <a href="?download=<?= $key ?>" class="download-btn" style="margin: 0.5rem; padding: 0.8rem 1.5rem; font-size: 1rem;">
                        <span class="icon"><?= $dl['icon'] ?></span>
                        <span><?= $dl['label'] ?></span>
                    </a>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>

        <div class="other-platforms">
            <p>Other platforms:</p>
            <?php foreach(DOWNLOADS as $key => $dl): ?>
                <?php if($key !== $platform): ?>
                    <a href="?download=<?= $key ?>"><?= $dl['icon'] ?> <?= $dl['label'] ?></a>
                <?php endif; ?>
            <?php endforeach; ?>
        </div>

        <div class="features">
            <h3>What's included:</h3>
            <ul>
                <li>Community member analysis</li>
                <li>Post & engagement tracking</li>
                <li>Skool data fetcher (built-in)</li>
                <li>Local data storage</li>
                <li>No account required</li>
            </ul>
        </div>
    </div>
</body>
</html>
