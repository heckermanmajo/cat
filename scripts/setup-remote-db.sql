-- Setup für Remote-Datenbank d045c2f8 auf frellow.de
-- Ausführen mit: mysql -h frellow.de -u d045c2f8 -p d045c2f8 < scripts/setup-remote-db.sql

-- Haupttabelle für Lizenzen
CREATE TABLE IF NOT EXISTS licenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    license_key VARCHAR(64) UNIQUE NOT NULL,
    customer_email VARCHAR(255),
    customer_name VARCHAR(255),
    product VARCHAR(50) DEFAULT 'catknows',
    valid_until DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    max_activations INT DEFAULT 3,
    current_activations INT DEFAULT 0,
    features JSON,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_check TIMESTAMP NULL,

    INDEX idx_license_key (license_key),
    INDEX idx_customer_email (customer_email),
    INDEX idx_valid_until (valid_until)
);

-- Tabelle für Geräte-Aktivierungen
CREATE TABLE IF NOT EXISTS activations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    license_id INT NOT NULL,
    machine_id VARCHAR(255) NOT NULL,
    machine_name VARCHAR(255),
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY unique_license_machine (license_id, machine_id),
    FOREIGN KEY (license_id) REFERENCES licenses(id) ON DELETE CASCADE,
    INDEX idx_machine_id (machine_id)
);

-- Tabelle für Audit-Log
CREATE TABLE IF NOT EXISTS license_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    license_id INT,
    action VARCHAR(50) NOT NULL,
    machine_id VARCHAR(255),
    ip_address VARCHAR(45),
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_license_id (license_id),
    INDEX idx_created_at (created_at)
);

-- Dev-Lizenz
INSERT INTO licenses (license_key, customer_email, customer_name, valid_until, features)
VALUES (
    'DEV-TEST-LICENSE-2024',
    'dev@catknows.local',
    'Development Team',
    DATE_ADD(CURDATE(), INTERVAL 1 YEAR),
    '["basic", "analytics", "ai", "dev"]'
) ON DUPLICATE KEY UPDATE valid_until = DATE_ADD(CURDATE(), INTERVAL 1 YEAR);

-- Hoomans Community Lizenz
INSERT INTO licenses (license_key, customer_email, customer_name, valid_until, features, notes)
VALUES (
    'HOOMANS-2025-CATKNOWS',
    'hoomans@example.com',
    'Hoomans Community',
    DATE_ADD(CURDATE(), INTERVAL 1 YEAR),
    '["basic", "analytics", "ai"]',
    'Beispiel-Lizenz für Hoomans Skool Community. Community-ID: hoomans'
) ON DUPLICATE KEY UPDATE valid_until = DATE_ADD(CURDATE(), INTERVAL 1 YEAR);

SELECT 'Setup complete!' AS status;
SELECT COUNT(*) AS license_count FROM licenses;
