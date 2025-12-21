#!/usr/bin/env php
<?php
/**
 * Generiert Ed25519 Schlüsselpaar für Lizenz-Signierung
 *
 * Ausführen mit: php scripts/generate-keys.php
 *
 * WICHTIG:
 * - Private Key NIEMALS committen oder teilen!
 * - Public Key wird in Go-Client eingebettet
 * - Keys sicher aufbewahren (z.B. in Secret-Manager)
 */

echo "=== Catknows Lizenz-Key Generator ===\n\n";

// Prüfen ob sodium extension verfügbar ist
if (!function_exists('sodium_crypto_sign_keypair')) {
    echo "ERROR: PHP sodium extension nicht verfügbar!\n";
    echo "Installieren mit: apt install php-sodium (Linux) oder in php.ini aktivieren\n";
    exit(1);
}

// Ed25519 Schlüsselpaar generieren
$keypair = sodium_crypto_sign_keypair();
$privateKey = sodium_crypto_sign_secretkey($keypair);
$publicKey = sodium_crypto_sign_publickey($keypair);

// Als Hex für einfache Handhabung
$privateKeyHex = sodium_bin2hex($privateKey);
$publicKeyHex = sodium_bin2hex($publicKey);

echo "Schlüsselpaar erfolgreich generiert!\n\n";

echo "======================================\n";
echo "PRIVATE KEY (64 bytes = 128 hex chars)\n";
echo "======================================\n";
echo "GEHEIM HALTEN! Nur auf Server speichern.\n\n";
echo $privateKeyHex . "\n\n";

echo "======================================\n";
echo "PUBLIC KEY (32 bytes = 64 hex chars)\n";
echo "======================================\n";
echo "Kann öffentlich sein. In Go-Client einbetten.\n\n";
echo $publicKeyHex . "\n\n";

echo "======================================\n";
echo "NÄCHSTE SCHRITTE\n";
echo "======================================\n\n";

echo "1. Server-Konfiguration (Environment-Variablen):\n";
echo "   export LICENSE_PRIVATE_KEY=\"$privateKeyHex\"\n";
echo "   export LICENSE_PUBLIC_KEY=\"$publicKeyHex\"\n\n";

echo "2. Go-Client (go-client/license/license.go):\n";
echo "   Ersetze den ServerPublicKey placeholder mit:\n\n";
echo "   var ServerPublicKey = mustDecodeHex(\"$publicKeyHex\")\n\n";

echo "3. Keys sicher aufbewahren:\n";
echo "   - Private Key in Secret-Manager oder .env (NICHT committen!)\n";
echo "   - Backup an sicherem Ort\n\n";

// Optional: In Datei speichern (mit Warnung)
$saveToFile = false;
if (isset($argv[1]) && $argv[1] === '--save') {
    $saveToFile = true;
}

if ($saveToFile) {
    $keysDir = __DIR__ . '/../keys';
    if (!is_dir($keysDir)) {
        mkdir($keysDir, 0700, true);
    }

    // .gitignore für keys-Ordner
    file_put_contents($keysDir . '/.gitignore', "*\n!.gitignore\n");

    // Private Key (sehr restriktive Permissions)
    $privateKeyFile = $keysDir . '/private.key';
    file_put_contents($privateKeyFile, $privateKeyHex);
    chmod($privateKeyFile, 0600);

    // Public Key
    $publicKeyFile = $keysDir . '/public.key';
    file_put_contents($publicKeyFile, $publicKeyHex);
    chmod($publicKeyFile, 0644);

    echo "Keys gespeichert in:\n";
    echo "   Private: $privateKeyFile (chmod 600)\n";
    echo "   Public:  $publicKeyFile\n\n";
    echo "WARNUNG: Stelle sicher dass keys/ in .gitignore ist!\n";
} else {
    echo "Tipp: Führe 'php scripts/generate-keys.php --save' aus um Keys in Dateien zu speichern.\n";
}

echo "\n";
