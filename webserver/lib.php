<?php
/**
 * CatKnows Webserver Library
 *
 * Zentrale Library mit allen wiederverwendbaren Funktionen:
 * - Datenbank-Verbindung
 * - Kryptographie (Ed25519)
 * - Session/Auth
 * - Lizenz-Generierung
 */

// ============================================================================
// Datenbank
// ============================================================================

define('DB_HOST', getenv('DB_HOST') ?: 'localhost');
define('DB_NAME', getenv('DB_NAME') ?: 'catknows_license');
define('DB_USER', getenv('DB_USER') ?: 'catknows');
define('DB_PASS', getenv('DB_PASS') ?: 'CHANGE_ME_IN_PRODUCTION');

function getDBConnection(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $dsn = sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', DB_HOST, DB_NAME);
        $pdo = new PDO($dsn, DB_USER, DB_PASS, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
    }
    return $pdo;
}

// ============================================================================
// Kryptographie (Ed25519 Lizenzsignierung)
// ============================================================================

define('LICENSE_PRIVATE_KEY', getenv('LICENSE_PRIVATE_KEY') ?: '');
define('LICENSE_PUBLIC_KEY', getenv('LICENSE_PUBLIC_KEY') ?: '');

function keysConfigured(): bool {
    return strlen(LICENSE_PRIVATE_KEY) === 128 && strlen(LICENSE_PUBLIC_KEY) === 64;
}

function getPrivateKey(): string {
    if (!keysConfigured()) {
        throw new Exception('Kryptographische Keys nicht konfiguriert!');
    }
    return sodium_hex2bin(LICENSE_PRIVATE_KEY);
}

function getPublicKey(): string {
    if (!keysConfigured()) {
        throw new Exception('Kryptographische Keys nicht konfiguriert!');
    }
    return sodium_hex2bin(LICENSE_PUBLIC_KEY);
}

/**
 * Generiert ein neues Ed25519 Schlüsselpaar
 * @return array ['private' => hex, 'public' => hex]
 */
function generateKeyPair(): array {
    if (!function_exists('sodium_crypto_sign_keypair')) {
        throw new Exception('PHP sodium extension nicht verfügbar!');
    }
    $keypair = sodium_crypto_sign_keypair();
    return [
        'private' => sodium_bin2hex(sodium_crypto_sign_secretkey($keypair)),
        'public' => sodium_bin2hex(sodium_crypto_sign_publickey($keypair))
    ];
}

// ============================================================================
// Admin Session/Auth
// ============================================================================

define('ADMIN_USERNAME', getenv('ADMIN_USERNAME') ?: 'admin');
define('ADMIN_PASSWORD', getenv('ADMIN_PASSWORD') ?: 'admin123');
define('SESSION_LIFETIME', 3600);

function verifyAdminPassword(string $password): bool {
    return $password === ADMIN_PASSWORD;
}

function isLoggedIn(): bool {
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    return isset($_SESSION['admin_logged_in']) && $_SESSION['admin_logged_in'] === true;
}

function requireLogin(): void {
    if (!isLoggedIn()) {
        header('Location: admin-login.php');
        exit;
    }
}

function getCurrentPage(): string {
    return basename($_SERVER['PHP_SELF'], '.php');
}

// ============================================================================
// Lizenz-Generierung
// ============================================================================

/**
 * Generiert einen kryptographisch sicheren Lizenzschlüssel
 * Format: XXXX-XXXX-XXXX-XXXX (ohne verwechselbare Zeichen 0/O, 1/I/L)
 */
function generateLicenseKey(): string {
    $chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
    $parts = [];
    for ($i = 0; $i < 4; $i++) {
        $part = '';
        for ($j = 0; $j < 4; $j++) {
            $part .= $chars[random_int(0, strlen($chars) - 1)];
        }
        $parts[] = $part;
    }
    return implode('-', $parts);
}

// ============================================================================
// API Response Helpers
// ============================================================================

function jsonResponse(array $data, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function jsonError(string $error, int $status = 400): void {
    jsonResponse(['error' => $error], $status);
}

// ============================================================================
// Lizenz-Signierung (für API)
// ============================================================================

function createLicensePayload(
    bool $valid,
    ?string $expiresAt,
    string $nonce,
    ?string $error = null,
    string $product = 'catknows',
    array $features = []
): array {
    $payload = [
        'valid' => $valid,
        'expires_at' => $expiresAt ?? '',
        'nonce' => $nonce,
        'timestamp' => time(),
        'product' => $product,
        'features' => $features,
    ];
    if ($error) {
        $payload['error'] = $error;
    }
    return $payload;
}

function signLicenseResponse(array $payload): array {
    $privateKey = getPrivateKey();
    $payloadJson = json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    $signature = sodium_crypto_sign_detached($payloadJson, $privateKey);
    return [
        'payload' => $payload,
        'signature' => sodium_bin2hex($signature),
    ];
}

// ============================================================================
// Admin Template Helpers
// ============================================================================

function adminHeader(): void {
    $currentPage = getCurrentPage();
    ?>
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatKnows Admin</title>
    <link rel="stylesheet" href="admin-style.css">
</head>
<body>
    <div class="admin-layout">
        <aside class="sidebar">
            <div class="sidebar-header">
                <h1>CatKnows</h1>
                <span>Admin Panel</span>
            </div>
            <nav>
                <ul class="sidebar-nav">
                    <li><a href="admin-dashboard.php" class="<?= $currentPage === 'admin-dashboard' ? 'active' : '' ?>"><span class="icon">&#x1F4CA;</span> Dashboard</a></li>
                    <li><a href="admin-licenses.php" class="<?= in_array($currentPage, ['admin-licenses', 'admin-license-edit']) ? 'active' : '' ?>"><span class="icon">&#x1F511;</span> Lizenzen</a></li>
                    <li><a href="admin-activations.php" class="<?= $currentPage === 'admin-activations' ? 'active' : '' ?>"><span class="icon">&#x1F4BB;</span> Aktivierungen</a></li>
                    <li><a href="admin-audit.php" class="<?= $currentPage === 'admin-audit' ? 'active' : '' ?>"><span class="icon">&#x1F4DD;</span> Audit Log</a></li>
                </ul>
            </nav>
            <div class="sidebar-footer">
                <a href="admin-logout.php">&#x1F6AA; Abmelden</a>
            </div>
        </aside>
        <main class="main-content">
    <?php
}

function adminFooter(): void {
    ?>
        </main>
    </div>
</body>
</html>
    <?php
}

// ============================================================================
// CSRF Protection
// ============================================================================

function generateCsrfToken(): string {
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function csrfField(): string {
    return '<input type="hidden" name="csrf_token" value="' . htmlspecialchars(generateCsrfToken()) . '">';
}

function verifyCsrfToken(): bool {
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    $token = $_POST['csrf_token'] ?? '';
    return !empty($token) && hash_equals($_SESSION['csrf_token'] ?? '', $token);
}

function requireCsrf(): void {
    if (!verifyCsrfToken()) {
        http_response_code(403);
        die('CSRF-Token ungueltig. Bitte Seite neu laden.');
    }
}

// ============================================================================
// Audit Log
// ============================================================================

function logAudit(PDO $db, ?int $licenseId, string $action, array $details = [], ?string $machineId = null): void {
    $stmt = $db->prepare("
        INSERT INTO license_audit_log (license_id, action, machine_id, ip_address, details)
        VALUES (?, ?, ?, ?, ?)
    ");
    $stmt->execute([
        $licenseId,
        $action,
        $machineId,
        $_SERVER['REMOTE_ADDR'] ?? null,
        json_encode($details)
    ]);
}
