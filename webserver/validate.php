<?php
require_once __DIR__ . '/core.php';
setupDB();

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true) ?: [];
$key = $input['license_key'] ?? '';
$nonce = $input['nonce'] ?? '';
$machineId = $input['machine_id'] ?? '';

if(!$key || !$nonce) {
    echo json_encode(['error' => 'missing_parameters']);
    exit;
}

$licenses = Model::getList(License::class, "SELECT * FROM license WHERE license_key = ?", [$key]);
$license = $licenses[0] ?? null;

$payload = ['valid' => false, 'nonce' => $nonce, 'timestamp' => time()];

if(!$license) {
    $payload['error'] = 'invalid_license';
} elseif(!$license->is_active) {
    $payload['error'] = 'license_deactivated';
} elseif($license->isExpired()) {
    $payload['error'] = 'license_expired';
} else {
    $payload['valid'] = true;
    $payload['expires_at'] = date('Y-m-d', $license->valid_until);
    $payload['features'] = $license->getFeatures();

    $license->last_check = time();
    Model::save($license);

    if($machineId) {
        $existing = Model::getList(Activation::class, "SELECT * FROM activation WHERE license_id = ? AND machine_id = ?", [$license->id, $machineId]);
        if($existing) {
            $existing[0]->last_seen = time();
            Model::save($existing[0]);
        } else {
            $a = new Activation();
            $a->license_id = $license->id;
            $a->machine_id = $machineId;
            $a->last_seen = time();
            Model::save($a);
        }
    }
}

// Sign response if keys configured
if(strlen(LICENSE_PRIVATE_KEY) === 128) {
    $payloadJson = json_encode($payload);
    $signature = sodium_crypto_sign_detached($payloadJson, sodium_hex2bin(LICENSE_PRIVATE_KEY));
    echo json_encode(['payload' => $payload, 'signature' => sodium_bin2hex($signature)]);
} else {
    echo json_encode($payload);
}
