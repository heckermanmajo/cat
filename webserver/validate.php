<?php
/**
 * Lizenz-Validierung API
 *
 * POST /validate.php
 *
 * Request:
 * {
 *   "license_key": "ABC-123-XYZ",
 *   "nonce": "random_hex_string",
 *   "machine_id": "hashed_hardware_id"
 * }
 *
 * Response (signiert):
 * {
 *   "payload": { ... },
 *   "signature": "hex_encoded_ed25519_signature"
 * }
 */

require_once __DIR__ . '/lib.php';

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Preflight für CORS
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Nur POST erlaubt
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    jsonError('method_not_allowed', 405);
}

// Input parsen
$input = json_decode(file_get_contents('php://input'), true);
if (!$input) {
    jsonError('invalid_json');
}

$licenseKey = $input['license_key'] ?? '';
$nonce = $input['nonce'] ?? '';
$machineId = $input['machine_id'] ?? '';

// Validierung
if (empty($licenseKey) || empty($nonce)) {
    jsonError('missing_parameters');
}

// Nonce-Format prüfen (64 hex chars = 32 bytes)
if (!preg_match('/^[a-f0-9]{64}$/i', $nonce)) {
    jsonError('invalid_nonce_format');
}

try {
    $pdo = getDBConnection();

    // Lizenz in DB suchen
    $stmt = $pdo->prepare('
        SELECT id, license_key, customer_email, product, valid_until,
               is_active, max_activations, current_activations, features
        FROM licenses
        WHERE license_key = ?
    ');
    $stmt->execute([$licenseKey]);
    $license = $stmt->fetch();

    if (!$license) {
        $payload = createLicensePayload(false, null, $nonce, 'invalid_license');
        echo json_encode(signLicenseResponse($payload));
        exit;
    }

    if (!$license['is_active']) {
        $payload = createLicensePayload(false, $license['valid_until'], $nonce, 'license_deactivated');
        echo json_encode(signLicenseResponse($payload));
        exit;
    }

    // Ablaufdatum prüfen
    $expiresAt = new DateTime($license['valid_until']);
    $now = new DateTime();

    if ($expiresAt < $now) {
        $payload = createLicensePayload(false, $license['valid_until'], $nonce, 'license_expired');
        echo json_encode(signLicenseResponse($payload));
        exit;
    }

    // Last-Check updaten
    $pdo->prepare('UPDATE licenses SET last_check = NOW() WHERE id = ?')
        ->execute([$license['id']]);

    // Machine-Aktivierung tracken
    if (!empty($machineId)) {
        $stmt = $pdo->prepare('
            INSERT INTO activations (license_id, machine_id, activated_at, last_seen)
            VALUES (?, ?, NOW(), NOW())
            ON DUPLICATE KEY UPDATE last_seen = NOW()
        ');
        $stmt->execute([$license['id'], $machineId]);
    }

    // Features parsen
    $features = [];
    if (!empty($license['features'])) {
        $features = json_decode($license['features'], true) ?: [];
    }

    // Erfolgreiche Validierung
    $payload = createLicensePayload(
        true,
        $license['valid_until'],
        $nonce,
        null,
        $license['product'] ?? 'catknows',
        $features
    );

    echo json_encode(signLicenseResponse($payload));

} catch (Exception $e) {
    error_log('License validation error: ' . $e->getMessage());
    jsonError('server_error', 500);
}
