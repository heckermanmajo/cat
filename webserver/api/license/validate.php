<?php
/**
 * Lizenz-Validierung API
 *
 * POST /api/license/validate.php
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
 *   "payload": {
 *     "valid": true,
 *     "expires_at": "2025-12-31",
 *     "nonce": "same_as_request",
 *     "timestamp": 1702400000,
 *     "product": "catknows",
 *     "features": ["basic", "analytics"]
 *   },
 *   "signature": "hex_encoded_ed25519_signature"
 * }
 */

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
    http_response_code(405);
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}

require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../config/keys.php';

// Input parsen
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_json']);
    exit;
}

$licenseKey = $input['license_key'] ?? '';
$nonce = $input['nonce'] ?? '';
$machineId = $input['machine_id'] ?? '';

// Validierung
if (empty($licenseKey) || empty($nonce)) {
    http_response_code(400);
    echo json_encode(['error' => 'missing_parameters']);
    exit;
}

// Nonce-Format prüfen (64 hex chars = 32 bytes)
if (!preg_match('/^[a-f0-9]{64}$/i', $nonce)) {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_nonce_format']);
    exit;
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
        // Ungültige Lizenz - trotzdem signierte Antwort senden
        $payload = createPayload(false, null, $nonce, 'invalid_license');
        echo json_encode(signResponse($payload));
        exit;
    }

    if (!$license['is_active']) {
        $payload = createPayload(false, $license['valid_until'], $nonce, 'license_deactivated');
        echo json_encode(signResponse($payload));
        exit;
    }

    // Ablaufdatum prüfen
    $expiresAt = new DateTime($license['valid_until']);
    $now = new DateTime();

    if ($expiresAt < $now) {
        $payload = createPayload(false, $license['valid_until'], $nonce, 'license_expired');
        echo json_encode(signResponse($payload));
        exit;
    }

    // Last-Check und Aktivierung tracken
    updateLicenseUsage($pdo, $license['id'], $machineId);

    // Features parsen (JSON in DB)
    $features = [];
    if (!empty($license['features'])) {
        $features = json_decode($license['features'], true) ?: [];
    }

    // Erfolgreiche Validierung
    $payload = createPayload(
        true,
        $license['valid_until'],
        $nonce,
        null,
        $license['product'],
        $features
    );

    echo json_encode(signResponse($payload));

} catch (Exception $e) {
    error_log('License validation error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'server_error']);
}

/**
 * Erstellt das Payload-Objekt
 */
function createPayload(
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

/**
 * Signiert die Response mit Ed25519
 */
function signResponse(array $payload): array {
    $privateKey = getPrivateKey();

    // WICHTIG: JSON muss exakt gleich serialisiert werden wie im Go-Client!
    // Keine Pretty-Print, keine zusätzlichen Spaces
    $payloadJson = json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

    // Ed25519 Signatur erstellen
    $signature = sodium_crypto_sign_detached($payloadJson, $privateKey);

    return [
        'payload' => $payload,
        'signature' => sodium_bin2hex($signature),
    ];
}

/**
 * Aktualisiert Nutzungsdaten der Lizenz
 */
function updateLicenseUsage(PDO $pdo, int $licenseId, string $machineId): void {
    // Last-Check updaten
    $pdo->prepare('UPDATE licenses SET last_check = NOW() WHERE id = ?')
        ->execute([$licenseId]);

    // Machine-Aktivierung tracken (wenn machine_id vorhanden)
    if (!empty($machineId)) {
        $stmt = $pdo->prepare('
            INSERT INTO activations (license_id, machine_id, activated_at, last_seen)
            VALUES (?, ?, NOW(), NOW())
            ON DUPLICATE KEY UPDATE last_seen = NOW()
        ');
        $stmt->execute([$licenseId, $machineId]);
    }
}
