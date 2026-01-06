<?php
/**
 * Admin Lizenzen-Uebersicht
 */
require_once __DIR__ . '/lib.php';
requireLogin();

$db = getDBConnection();

// Filter
$filter = $_GET['filter'] ?? 'all';
$search = $_GET['search'] ?? '';

// Query bauen
$where = [];
$params = [];

if ($filter === 'active') {
    $where[] = "is_active = 1 AND valid_until >= CURDATE()";
} elseif ($filter === 'expired') {
    $where[] = "valid_until < CURDATE()";
} elseif ($filter === 'inactive') {
    $where[] = "is_active = 0";
}

if ($search) {
    $where[] = "(license_key LIKE :search OR customer_email LIKE :search OR customer_name LIKE :search)";
    $params[':search'] = "%$search%";
}

$whereClause = $where ? 'WHERE ' . implode(' AND ', $where) : '';

$stmt = $db->prepare("
    SELECT l.*, (SELECT COUNT(*) FROM activations a WHERE a.license_id = l.id) as activation_count
    FROM licenses l $whereClause ORDER BY l.created_at DESC
");
$stmt->execute($params);
$licenses = $stmt->fetchAll();

// Lizenz loeschen
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_id'])) {
    requireCsrf();
    $deleteId = (int)$_POST['delete_id'];
    $stmt = $db->prepare("SELECT license_key FROM licenses WHERE id = ?");
    $stmt->execute([$deleteId]);
    $license = $stmt->fetch();

    if ($license) {
        $db->prepare("DELETE FROM licenses WHERE id = ?")->execute([$deleteId]);
        logAudit($db, null, 'delete', ['license_key' => $license['license_key'], 'by' => 'admin']);
        header('Location: admin-licenses.php?msg=Lizenz geloescht');
        exit;
    }
}

$message = $_GET['msg'] ?? '';

adminHeader();
?>

<div class="page-header">
    <h2>Lizenzen</h2>
    <a href="admin-license-edit.php" class="btn btn-primary">+ Neue Lizenz</a>
</div>

<?php if ($message): ?>
    <div class="alert alert-success"><?= htmlspecialchars($message) ?></div>
<?php endif; ?>

<div class="card">
    <div class="card-header">
        <h3>Alle Lizenzen (<?= count($licenses) ?>)</h3>
    </div>
    <div class="card-body">
        <!-- Filter -->
        <form class="filter-bar" method="GET">
            <input type="text" name="search" placeholder="Suchen..." value="<?= htmlspecialchars($search) ?>">
            <select name="filter" onchange="this.form.submit()">
                <option value="all" <?= $filter === 'all' ? 'selected' : '' ?>>Alle</option>
                <option value="active" <?= $filter === 'active' ? 'selected' : '' ?>>Aktiv</option>
                <option value="expired" <?= $filter === 'expired' ? 'selected' : '' ?>>Abgelaufen</option>
                <option value="inactive" <?= $filter === 'inactive' ? 'selected' : '' ?>>Deaktiviert</option>
            </select>
            <button type="submit" class="btn btn-secondary btn-sm">Filtern</button>
        </form>

        <?php if (empty($licenses)): ?>
            <div class="empty-state">
                <div class="icon">&#x1F511;</div>
                <p>Keine Lizenzen gefunden</p>
                <a href="admin-license-edit.php" class="btn btn-primary">Erste Lizenz erstellen</a>
            </div>
        <?php else: ?>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Lizenz-Key</th>
                            <th>Kunde</th>
                            <th>Gueltig bis</th>
                            <th>Aktivierungen</th>
                            <th>Features</th>
                            <th>Status</th>
                            <th>Aktionen</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($licenses as $license): ?>
                            <?php
                            $isExpired = strtotime($license['valid_until']) < time();
                            $isActive = $license['is_active'] && !$isExpired;
                            $features = json_decode($license['features'] ?? '[]', true) ?: [];
                            ?>
                            <tr>
                                <td><code><?= htmlspecialchars($license['license_key']) ?></code></td>
                                <td>
                                    <strong><?= htmlspecialchars($license['customer_name'] ?: '-') ?></strong><br>
                                    <small><?= htmlspecialchars($license['customer_email'] ?: '-') ?></small>
                                </td>
                                <td><?= date('d.m.Y', strtotime($license['valid_until'])) ?></td>
                                <td><?= $license['activation_count'] ?> / <?= $license['max_activations'] ?></td>
                                <td>
                                    <div class="feature-tags">
                                        <?php foreach ($features as $feature): ?>
                                            <span class="feature-tag"><?= htmlspecialchars($feature) ?></span>
                                        <?php endforeach; ?>
                                    </div>
                                </td>
                                <td>
                                    <?php if ($isActive): ?>
                                        <span class="badge badge-success">Aktiv</span>
                                    <?php elseif ($isExpired): ?>
                                        <span class="badge badge-danger">Abgelaufen</span>
                                    <?php else: ?>
                                        <span class="badge badge-warning">Deaktiviert</span>
                                    <?php endif; ?>
                                </td>
                                <td>
                                    <div class="actions">
                                        <a href="admin-license-edit.php?id=<?= $license['id'] ?>" class="btn btn-sm btn-secondary">Bearbeiten</a>
                                        <form method="POST" style="display: inline;" onsubmit="return confirm('Lizenz wirklich loeschen?')">
                                            <?= csrfField() ?>
                                            <input type="hidden" name="delete_id" value="<?= $license['id'] ?>">
                                            <button type="submit" class="btn btn-sm btn-danger">Loeschen</button>
                                        </form>
                                    </div>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>
    </div>
</div>

<?php adminFooter(); ?>
