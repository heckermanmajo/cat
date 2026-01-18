<?php
declare(strict_types = 1);

/**
 * Version API for CatKnows Launcher
 * Returns current version and download URLs for all platforms
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// Version file contains just the version number (e.g., "1.0.0")
$versionFile = __DIR__ . '/downloads/version.txt';
$version = file_exists($versionFile) ? trim(file_get_contents($versionFile)) : '0.0.0';

// Base URL for downloads
$baseUrl = 'https://' . $_SERVER['HTTP_HOST'] . dirname($_SERVER['SCRIPT_NAME']) . '/downloads';

echo json_encode([
    'version' => $version,
    'windows' => $baseUrl . '/CatKnows-win.exe',
    'mac'     => $baseUrl . '/CatKnows-mac.zip',
    'linux'   => $baseUrl . '/CatKnows-linux.AppImage',
], JSON_UNESCAPED_SLASHES);
