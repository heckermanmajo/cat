<?php
/**
 * CatKnows Download API
 *
 * GET /download.php?platform=macos-arm64
 * GET /download.php?info
 * GET /download.php?detect
 */

require_once __DIR__ . '/lib.php';

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

// Info-Request
if (isset($_GET['info'])) {
    jsonResponse([
        'available_platforms' => array_keys($binaries),
        'detect_endpoint' => '/download.php?detect',
        'download_endpoint' => '/download.php?platform={platform}'
    ]);
}

// OS-Detection-Request
if (isset($_GET['detect'])) {
    $userAgent = $_SERVER['HTTP_USER_AGENT'] ?? '';
    $detected = detectPlatform($userAgent);
    jsonResponse([
        'detected_os' => $detected['os'],
        'detected_arch' => $detected['arch'],
        'recommended_platform' => $detected['platform'],
        'user_agent' => $userAgent
    ]);
}

// Download
$platform = $_GET['platform'] ?? null;

if (!$platform) {
    jsonError('Missing platform parameter. Use ?detect to auto-detect or ?info for available platforms.');
}

if (!isset($binaries[$platform])) {
    jsonResponse(['error' => 'Invalid platform', 'available' => array_keys($binaries)], 400);
}

$binary = $binaries[$platform];
$filePath = __DIR__ . '/downloads/' . $binary['file'];

if (!file_exists($filePath)) {
    jsonError('Binary not found. Please run the build script first.', 404);
}

// Serve the file
header('Content-Type: ' . $binary['mime']);
header('Content-Disposition: attachment; filename="' . $binary['name'] . '"');
header('Content-Length: ' . filesize($filePath));
header('Cache-Control: no-cache, must-revalidate');
readfile($filePath);
exit;

function detectPlatform(string $userAgent): array {
    $os = 'unknown';
    $arch = 'amd64';
    $platform = 'linux-amd64';

    if (stripos($userAgent, 'Windows') !== false) {
        $os = 'windows';
        $platform = 'windows-amd64';
    } elseif (stripos($userAgent, 'Mac') !== false || stripos($userAgent, 'Macintosh') !== false) {
        $os = 'macos';
        if (stripos($userAgent, 'ARM') !== false || stripos($userAgent, 'arm64') !== false ||
            (stripos($userAgent, 'Safari') !== false && stripos($userAgent, 'Chrome') === false && stripos($userAgent, 'Version/17') !== false)) {
            $arch = 'arm64';
            $platform = 'macos-arm64';
        } else {
            $platform = 'macos-amd64';
        }
    } elseif (stripos($userAgent, 'Linux') !== false) {
        $os = 'linux';
        $platform = 'linux-amd64';
    }

    return ['os' => $os, 'arch' => $arch, 'platform' => $platform];
}
