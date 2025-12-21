<?php
/**
 * CatKnows Download API
 *
 * Serves the appropriate binary based on the requested platform.
 * Direct access to the downloads folder is blocked via .htaccess
 */

header('Content-Type: application/json');

// Available binaries mapping
$binaries = [
    'macos-arm64' => [
        'file' => 'catknows-macos-arm64',
        'mime' => 'application/octet-stream',
        'name' => 'catknows-macos-arm64'
    ],
    'macos-amd64' => [
        'file' => 'catknows-macos-amd64',
        'mime' => 'application/octet-stream',
        'name' => 'catknows-macos-amd64'
    ],
    'windows-amd64' => [
        'file' => 'catknows-windows-amd64.exe',
        'mime' => 'application/vnd.microsoft.portable-executable',
        'name' => 'catknows-windows-amd64.exe'
    ],
    'linux-amd64' => [
        'file' => 'catknows-linux-amd64',
        'mime' => 'application/octet-stream',
        'name' => 'catknows-linux-amd64'
    ]
];

// Get the requested platform
$platform = $_GET['platform'] ?? null;

// Handle info request - returns available platforms
if (isset($_GET['info'])) {
    echo json_encode([
        'available_platforms' => array_keys($binaries),
        'detect_endpoint' => '/api/download.php?detect',
        'download_endpoint' => '/api/download.php?platform={platform}'
    ]);
    exit;
}

// Handle OS detection request - returns detected platform from User-Agent
if (isset($_GET['detect'])) {
    $userAgent = $_SERVER['HTTP_USER_AGENT'] ?? '';
    $detected = detectPlatform($userAgent);

    echo json_encode([
        'detected_os' => $detected['os'],
        'detected_arch' => $detected['arch'],
        'recommended_platform' => $detected['platform'],
        'user_agent' => $userAgent
    ]);
    exit;
}

// Validate platform parameter for download
if (!$platform) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing platform parameter. Use ?detect to auto-detect or ?info for available platforms.']);
    exit;
}

if (!isset($binaries[$platform])) {
    http_response_code(400);
    echo json_encode([
        'error' => 'Invalid platform',
        'available' => array_keys($binaries)
    ]);
    exit;
}

// Get binary info
$binary = $binaries[$platform];
$filePath = __DIR__ . '/../downloads/' . $binary['file'];

// Check if file exists
if (!file_exists($filePath)) {
    http_response_code(404);
    echo json_encode(['error' => 'Binary not found. Please run the build script first.']);
    exit;
}

// Serve the file
header('Content-Type: ' . $binary['mime']);
header('Content-Disposition: attachment; filename="' . $binary['name'] . '"');
header('Content-Length: ' . filesize($filePath));
header('Cache-Control: no-cache, must-revalidate');

readfile($filePath);
exit;

/**
 * Detect platform from User-Agent string
 */
function detectPlatform(string $userAgent): array {
    $os = 'unknown';
    $arch = 'amd64'; // Default to amd64
    $platform = 'linux-amd64'; // Default fallback

    // Detect OS
    if (stripos($userAgent, 'Windows') !== false) {
        $os = 'windows';
        $platform = 'windows-amd64';
    } elseif (stripos($userAgent, 'Mac') !== false || stripos($userAgent, 'Macintosh') !== false) {
        $os = 'macos';
        // Try to detect Apple Silicon vs Intel
        // Note: Browser UA doesn't reliably indicate ARM, so we check for indicators
        if (stripos($userAgent, 'ARM') !== false ||
            stripos($userAgent, 'arm64') !== false ||
            // Safari on Apple Silicon sometimes has different indicators
            (stripos($userAgent, 'Safari') !== false && stripos($userAgent, 'Chrome') === false && stripos($userAgent, 'Version/17') !== false)) {
            $arch = 'arm64';
            $platform = 'macos-arm64';
        } else {
            $arch = 'amd64';
            $platform = 'macos-amd64';
        }
    } elseif (stripos($userAgent, 'Linux') !== false) {
        $os = 'linux';
        // Check for ARM Linux
        if (stripos($userAgent, 'aarch64') !== false || stripos($userAgent, 'arm64') !== false) {
            $arch = 'arm64';
            // We don't have Linux ARM build yet, fall back to amd64
            $platform = 'linux-amd64';
        } else {
            $platform = 'linux-amd64';
        }
    }

    return [
        'os' => $os,
        'arch' => $arch,
        'platform' => $platform
    ];
}
