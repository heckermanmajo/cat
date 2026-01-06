<?php
/**
 * Admin Lizenz bearbeiten/erstellen
 */
require_once __DIR__ . '/lib.php';
requireLogin();

$db = getDBConnection();
$id = $_GET['id'] ?? null;
$license = null;
$error = '';
$isNew = !$id;

$availableFeatures = ['basic', 'analytics', 'ai', 'dev'];

// Lizenz laden
if ($id) {
    $stmt = $db->prepare("SELECT * FROM licenses WHERE id = ?");
    $stmt->execute([$id]);
    $license = $stmt->fetch();
    if (!$license) {
        header('Location: admin-licenses.php?msg=Lizenz nicht gefunden');
        exit;
    }
}

// Formular verarbeiten
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();
    $licenseKey = trim($_POST['license_key'] ?? '');
    $customerEmail = trim($_POST['customer_email'] ?? '');
    $customerName = trim($_POST['customer_name'] ?? '');
    $validUntil = $_POST['valid_until'] ?? '';
    $isActive = isset($_POST['is_active']) ? 1 : 0;
    $maxActivations = (int)($_POST['max_activations'] ?? 3);
    $features = $_POST['features'] ?? [];
    $notes = trim($_POST['notes'] ?? '');

    if (empty($licenseKey)) {
        $error = 'Lizenz-Key ist erforderlich';
    } elseif (empty($validUntil)) {
        $error = 'Gueltig bis ist erforderlich';
    } else {
        try {
            $featuresJson = json_encode(array_values($features));

            if ($isNew) {
                $stmt = $db->prepare("
                    INSERT INTO licenses (license_key, customer_email, customer_name, valid_until, is_active, max_activations, features, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ");
                $stmt->execute([$licenseKey, $customerEmail, $customerName, $validUntil, $isActive, $maxActivations, $featuresJson, $notes]);
                $licenseId = $db->lastInsertId();
                logAudit($db, $licenseId, 'create', ['by' => 'admin']);
                header('Location: admin-licenses.php?msg=Lizenz erstellt');
                exit;
            } else {
                $stmt = $db->prepare("
                    UPDATE licenses SET license_key = ?, customer_email = ?, customer_name = ?, valid_until = ?,
                        is_active = ?, max_activations = ?, features = ?, notes = ? WHERE id = ?
                ");
                $stmt->execute([$licenseKey, $customerEmail, $customerName, $validUntil, $isActive, $maxActivations, $featuresJson, $notes, $id]);
                logAudit($db, $id, 'update', ['by' => 'admin']);
                header('Location: admin-licenses.php?msg=Lizenz aktualisiert');
                exit;
            }
        } catch (PDOException $e) {
            $error = strpos($e->getMessage(), 'Duplicate') !== false
                ? 'Dieser Lizenz-Key existiert bereits'
                : 'Datenbankfehler: ' . $e->getMessage();
        }
    }
}

// Standardwerte
if (!$license) {
    $license = [
        'license_key' => generateLicenseKey(),
        'customer_email' => '',
        'customer_name' => '',
        'valid_until' => date('Y-m-d', strtotime('+1 year')),
        'is_active' => 1,
        'max_activations' => 3,
        'features' => '["basic"]',
        'notes' => ''
    ];
}

$selectedFeatures = json_decode($license['features'] ?? '[]', true) ?: [];

adminHeader();
?>

<div class="page-header">
    <h2><?= $isNew ? 'Neue Lizenz erstellen' : 'Lizenz bearbeiten' ?></h2>
    <a href="admin-licenses.php" class="btn btn-secondary">Zurueck</a>
</div>

<?php if ($error): ?>
    <div class="alert alert-error"><?= htmlspecialchars($error) ?></div>
<?php endif; ?>

<div class="card">
    <div class="card-body">
        <form method="POST">
            <?= csrfField() ?>
            <div class="form-row">
                <div class="form-group">
                    <label for="license_key">Lizenz-Key *</label>
                    <input type="text" id="license_key" name="license_key" value="<?= htmlspecialchars($license['license_key']) ?>" required>
                    <?php if ($isNew): ?>
                        <small style="color: var(--gray-500);">Automatisch generiert, kann angepasst werden</small>
                    <?php endif; ?>
                </div>
                <div class="form-group">
                    <label for="valid_until">Gueltig bis *</label>
                    <input type="date" id="valid_until" name="valid_until" value="<?= htmlspecialchars($license['valid_until']) ?>" required>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="customer_name">Kundenname</label>
                    <input type="text" id="customer_name" name="customer_name" value="<?= htmlspecialchars($license['customer_name']) ?>">
                </div>
                <div class="form-group">
                    <label for="customer_email">E-Mail</label>
                    <input type="email" id="customer_email" name="customer_email" value="<?= htmlspecialchars($license['customer_email']) ?>">
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="max_activations">Max. Aktivierungen</label>
                    <input type="number" id="max_activations" name="max_activations" min="1" max="100" value="<?= htmlspecialchars($license['max_activations']) ?>">
                </div>
                <div class="form-group">
                    <label>Status</label>
                    <div style="padding-top: 8px;">
                        <label class="checkbox-label">
                            <input type="checkbox" name="is_active" <?= $license['is_active'] ? 'checked' : '' ?>>
                            Lizenz ist aktiv
                        </label>
                    </div>
                </div>
            </div>

            <div class="form-group">
                <label>Features</label>
                <div class="checkbox-group">
                    <?php foreach ($availableFeatures as $feature): ?>
                        <label class="checkbox-label">
                            <input type="checkbox" name="features[]" value="<?= $feature ?>" <?= in_array($feature, $selectedFeatures) ? 'checked' : '' ?>>
                            <?= ucfirst($feature) ?>
                        </label>
                    <?php endforeach; ?>
                </div>
            </div>

            <div class="form-group">
                <label for="notes">Notizen</label>
                <textarea id="notes" name="notes" rows="3"><?= htmlspecialchars($license['notes'] ?? '') ?></textarea>
            </div>

            <div style="display: flex; gap: 12px; margin-top: 20px;">
                <button type="submit" class="btn btn-primary"><?= $isNew ? 'Lizenz erstellen' : 'Aenderungen speichern' ?></button>
                <a href="admin-licenses.php" class="btn btn-secondary">Abbrechen</a>
            </div>
        </form>
    </div>
</div>

<?php if (!$isNew): ?>
<?php
$stmt = $db->prepare("SELECT * FROM activations WHERE license_id = ? ORDER BY last_seen DESC");
$stmt->execute([$id]);
$activations = $stmt->fetchAll();
?>
<div class="card" style="margin-top: 20px;">
    <div class="card-header">
        <h3>Aktivierungen (<?= count($activations) ?>)</h3>
    </div>
    <div class="card-body">
        <?php if (empty($activations)): ?>
            <div class="empty-state"><p>Noch keine Aktivierungen fuer diese Lizenz</p></div>
        <?php else: ?>
            <div class="table-container">
                <table>
                    <thead><tr><th>Machine ID</th><th>Machine Name</th><th>Aktiviert am</th><th>Zuletzt gesehen</th><th>Aktionen</th></tr></thead>
                    <tbody>
                        <?php foreach ($activations as $activation): ?>
                            <tr>
                                <td><code><?= htmlspecialchars(substr($activation['machine_id'], 0, 20)) ?>...</code></td>
                                <td><?= htmlspecialchars($activation['machine_name'] ?: '-') ?></td>
                                <td><?= date('d.m.Y H:i', strtotime($activation['activated_at'])) ?></td>
                                <td><?= date('d.m.Y H:i', strtotime($activation['last_seen'])) ?></td>
                                <td>
                                    <form method="POST" action="admin-activations.php" style="display: inline;">
                                        <?= csrfField() ?>
                                        <input type="hidden" name="delete_id" value="<?= $activation['id'] ?>">
                                        <input type="hidden" name="redirect" value="admin-license-edit.php?id=<?= $id ?>">
                                        <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Aktivierung entfernen?')">Entfernen</button>
                                    </form>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>
    </div>
</div>
<?php endif; ?>

<?php adminFooter(); ?>
