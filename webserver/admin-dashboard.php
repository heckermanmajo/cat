<?php
/**
 * Admin Dashboard
 * - Statistiken
 * - Key-Generierung (ehemals scripts/generate-keys.php)
 */
require_once __DIR__ . '/lib.php';
requireLogin();

$db = getDBConnection();
$generatedKeys = null;
$keyError = null;

// Key-Generierung
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['generate_keys'])) {
    requireCsrf();
    try {
        $generatedKeys = generateKeyPair();
    } catch (Exception $e) {
        $keyError = $e->getMessage();
    }
}

// Statistiken laden
$stats = ['total' => 0, 'active' => 0, 'expired' => 0, 'activations' => 0];
try {
    $stats['total'] = $db->query("SELECT COUNT(*) FROM licenses")->fetchColumn();
    $stats['active'] = $db->query("SELECT COUNT(*) FROM licenses WHERE is_active = 1 AND valid_until >= CURDATE()")->fetchColumn();
    $stats['expired'] = $db->query("SELECT COUNT(*) FROM licenses WHERE valid_until < CURDATE()")->fetchColumn();
    $stats['activations'] = $db->query("SELECT COUNT(*) FROM activations")->fetchColumn();
} catch (PDOException $e) {
    // DB noch nicht initialisiert
}

// Letzte Lizenzen
$recentLicenses = [];
try {
    $stmt = $db->query("
        SELECT l.*, (SELECT COUNT(*) FROM activations a WHERE a.license_id = l.id) as activation_count
        FROM licenses l ORDER BY l.created_at DESC LIMIT 5
    ");
    $recentLicenses = $stmt->fetchAll();
} catch (PDOException $e) {}

// Letzte Aktivitaeten
$recentActivity = [];
try {
    $stmt = $db->query("
        SELECT la.*, l.license_key FROM license_audit_log la
        LEFT JOIN licenses l ON la.license_id = l.id
        ORDER BY la.created_at DESC LIMIT 10
    ");
    $recentActivity = $stmt->fetchAll();
} catch (PDOException $e) {}

adminHeader();
?>

<div class="page-header">
    <h2>Dashboard</h2>
    <a href="admin-license-edit.php" class="btn btn-primary">+ Neue Lizenz</a>
</div>

<!-- Stats -->
<div class="stats-grid">
    <div class="stat-card">
        <div class="label">Lizenzen gesamt</div>
        <div class="value"><?= $stats['total'] ?></div>
    </div>
    <div class="stat-card success">
        <div class="label">Aktive Lizenzen</div>
        <div class="value"><?= $stats['active'] ?></div>
    </div>
    <div class="stat-card danger">
        <div class="label">Abgelaufene Lizenzen</div>
        <div class="value"><?= $stats['expired'] ?></div>
    </div>
    <div class="stat-card">
        <div class="label">Geraete-Aktivierungen</div>
        <div class="value"><?= $stats['activations'] ?></div>
    </div>
</div>

<!-- Key Generation -->
<div class="card">
    <div class="card-header">
        <h3>Ed25519 Schluessel generieren</h3>
    </div>
    <div class="card-body">
        <?php if ($keyError): ?>
            <div class="alert alert-error"><?= htmlspecialchars($keyError) ?></div>
        <?php endif; ?>

        <?php if ($generatedKeys): ?>
            <div class="alert alert-success">Schluessel erfolgreich generiert!</div>
            <div class="key-label">Private Key (GEHEIM - nur auf Server):</div>
            <div class="key-display"><?= htmlspecialchars($generatedKeys['private']) ?></div>
            <div class="key-label">Public Key (in Go-Client einbetten):</div>
            <div class="key-display"><?= htmlspecialchars($generatedKeys['public']) ?></div>
            <p style="margin-top: 16px; color: var(--gray-500); font-size: 14px;">
                <strong>Environment-Variablen setzen:</strong><br>
                <code>export LICENSE_PRIVATE_KEY="<?= htmlspecialchars($generatedKeys['private']) ?>"</code><br>
                <code>export LICENSE_PUBLIC_KEY="<?= htmlspecialchars($generatedKeys['public']) ?>"</code>
            </p>
        <?php else: ?>
            <p style="color: var(--gray-600); margin-bottom: 16px;">
                Generiere ein neues Ed25519 Schluessel-Paar fuer die Lizenzsignierung.
                <?php if (keysConfigured()): ?>
                    <span class="badge badge-success">Keys konfiguriert</span>
                <?php else: ?>
                    <span class="badge badge-warning">Keine Keys konfiguriert</span>
                <?php endif; ?>
            </p>
            <form method="POST">
                <?= csrfField() ?>
                <button type="submit" name="generate_keys" class="btn btn-secondary">Neues Schluessel-Paar generieren</button>
            </form>
        <?php endif; ?>
    </div>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
    <!-- Recent Licenses -->
    <div class="card">
        <div class="card-header">
            <h3>Neueste Lizenzen</h3>
            <a href="admin-licenses.php" class="btn btn-sm btn-secondary">Alle anzeigen</a>
        </div>
        <div class="card-body">
            <?php if (empty($recentLicenses)): ?>
                <div class="empty-state"><p>Noch keine Lizenzen vorhanden</p></div>
            <?php else: ?>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Lizenz</th><th>Kunde</th><th>Status</th></tr></thead>
                        <tbody>
                            <?php foreach ($recentLicenses as $license): ?>
                                <?php
                                $isExpired = strtotime($license['valid_until']) < time();
                                $isActive = $license['is_active'] && !$isExpired;
                                ?>
                                <tr>
                                    <td><a href="admin-license-edit.php?id=<?= $license['id'] ?>"><code><?= htmlspecialchars($license['license_key']) ?></code></a></td>
                                    <td><?= htmlspecialchars($license['customer_name'] ?: $license['customer_email']) ?></td>
                                    <td>
                                        <?php if ($isActive): ?>
                                            <span class="badge badge-success">Aktiv</span>
                                        <?php elseif ($isExpired): ?>
                                            <span class="badge badge-danger">Abgelaufen</span>
                                        <?php else: ?>
                                            <span class="badge badge-warning">Deaktiviert</span>
                                        <?php endif; ?>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </div>
    </div>

    <!-- Recent Activity -->
    <div class="card">
        <div class="card-header">
            <h3>Letzte Aktivitaeten</h3>
            <a href="admin-audit.php" class="btn btn-sm btn-secondary">Alle anzeigen</a>
        </div>
        <div class="card-body">
            <?php if (empty($recentActivity)): ?>
                <div class="empty-state"><p>Noch keine Aktivitaeten</p></div>
            <?php else: ?>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Zeit</th><th>Aktion</th><th>Lizenz</th></tr></thead>
                        <tbody>
                            <?php foreach ($recentActivity as $activity): ?>
                                <tr>
                                    <td><?= date('d.m. H:i', strtotime($activity['created_at'])) ?></td>
                                    <td><span class="badge badge-info"><?= htmlspecialchars($activity['action']) ?></span></td>
                                    <td><code><?= htmlspecialchars($activity['license_key'] ?? 'N/A') ?></code></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </div>
    </div>
</div>

<?php adminFooter(); ?>
