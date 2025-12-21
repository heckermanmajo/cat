#!/usr/bin/env php
<?php
/**
 * Erstellt eine neue Lizenz in der Datenbank
 *
 * Verwendung:
 *   php scripts/create-license.php --email="kunde@example.com" --name="Max Mustermann" --months=12
 *
 * Optionen:
 *   --email     Kunden-Email (required)
 *   --name      Kundenname (optional)
 *   --months    Gültigkeit in Monaten (default: 12)
 *   --features  Komma-getrennte Features (default: basic)
 *   --max-act   Maximale Aktivierungen (default: 3)
 */

require_once __DIR__ . '/../config/database.php';

// Argumente parsen
$options = getopt('', ['email:', 'name:', 'months:', 'features:', 'max-act:']);

if (empty($options['email'])) {
    echo "Verwendung: php create-license.php --email=\"kunde@example.com\" [--name=\"Name\"] [--months=12] [--features=\"basic,analytics\"]\n";
    exit(1);
}

$email = $options['email'];
$name = $options['name'] ?? '';
$months = (int)($options['months'] ?? 12);
$featuresStr = $options['features'] ?? 'basic';
$maxActivations = (int)($options['max-act'] ?? 3);

// Features als Array
$features = array_map('trim', explode(',', $featuresStr));

// Lizenzschlüssel generieren (Format: XXXX-XXXX-XXXX-XXXX)
$licenseKey = generateLicenseKey();

// Ablaufdatum berechnen
$validUntil = (new DateTime())->modify("+{$months} months")->format('Y-m-d');

try {
    $pdo = getDBConnection();

    $stmt = $pdo->prepare('
        INSERT INTO licenses (license_key, customer_email, customer_name, valid_until, max_activations, features)
        VALUES (?, ?, ?, ?, ?, ?)
    ');

    $stmt->execute([
        $licenseKey,
        $email,
        $name,
        $validUntil,
        $maxActivations,
        json_encode($features)
    ]);

    echo "=== Lizenz erfolgreich erstellt ===\n\n";
    echo "Lizenzschlüssel: $licenseKey\n";
    echo "Kunde:           $email\n";
    echo "Name:            $name\n";
    echo "Gültig bis:      $validUntil\n";
    echo "Features:        " . implode(', ', $features) . "\n";
    echo "Max. Geräte:     $maxActivations\n";
    echo "\n";

} catch (Exception $e) {
    echo "Fehler: " . $e->getMessage() . "\n";
    exit(1);
}

/**
 * Generiert einen kryptographisch sicheren Lizenzschlüssel
 * Format: XXXX-XXXX-XXXX-XXXX (nur Großbuchstaben und Zahlen, ohne verwechselbare Zeichen)
 */
function generateLicenseKey(): string {
    // Zeichen ohne verwechselbare (0/O, 1/I/L)
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
