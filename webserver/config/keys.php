<?php
/**
 * Kryptographische Schlüssel für Lizenz-Signierung
 *
 * WICHTIG: Private Key NIEMALS committen oder teilen!
 * In Produktion aus Environment-Variable oder Secret-Manager laden.
 *
 * Keys generieren mit: php scripts/generate-keys.php
 */

// Private Key - NUR auf dem Server, NIEMALS teilen!
// Lädt aus Environment oder Fallback für Entwicklung
define('LICENSE_PRIVATE_KEY', getenv('LICENSE_PRIVATE_KEY') ?: '');

// Public Key - kann öffentlich sein, wird in Go-Client eingebettet
define('LICENSE_PUBLIC_KEY', getenv('LICENSE_PUBLIC_KEY') ?: '');

/**
 * Prüft ob gültige Keys konfiguriert sind
 */
function keysConfigured(): bool {
    return strlen(LICENSE_PRIVATE_KEY) === 128 && strlen(LICENSE_PUBLIC_KEY) === 64;
}

/**
 * Gibt den Private Key als Binary zurück
 */
function getPrivateKey(): string {
    if (!keysConfigured()) {
        throw new Exception('Kryptographische Keys nicht konfiguriert! Führe scripts/generate-keys.php aus.');
    }
    return sodium_hex2bin(LICENSE_PRIVATE_KEY);
}

/**
 * Gibt den Public Key als Binary zurück
 */
function getPublicKey(): string {
    if (!keysConfigured()) {
        throw new Exception('Kryptographische Keys nicht konfiguriert!');
    }
    return sodium_hex2bin(LICENSE_PUBLIC_KEY);
}
