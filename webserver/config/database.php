<?php
/**
 * Datenbank-Konfiguration für Lizenz-Server
 *
 * WICHTIG: In Produktion diese Werte aus Environment-Variablen laden!
 */

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
