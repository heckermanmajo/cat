<?php
/**
 * Admin Aktivierungen
 */
require_once __DIR__ . '/lib.php';
requireLogin();

$db = getDBConnection();

// Aktivierung loeschen
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_id'])) {
    requireCsrf();
    $deleteId = (int)$_POST['delete_id'];
    $db->prepare("DELETE FROM activations WHERE id = ?")->execute([$deleteId]);

    // Open Redirect Prevention: nur interne Admin-Seiten erlauben
    $redirect = $_POST['redirect'] ?? 'admin-activations.php';
    $allowedPages = ['admin-activations.php', 'admin-license-edit.php', 'admin-licenses.php', 'admin-dashboard.php'];
    $redirectBase = parse_url($redirect, PHP_URL_PATH) ?: $redirect;
    $redirectFile = basename($redirectBase);
    if (!in_array($redirectFile, $allowedPages)) {
        $redirect = 'admin-activations.php';
    }

    header('Location: ' . $redirect . (strpos($redirect, '?') ? '&' : '?') . 'msg=Aktivierung entfernt');
    exit;
}

// Alle Aktivierungen laden
$stmt = $db->query("
    SELECT a.*, l.license_key, l.customer_name, l.customer_email
    FROM activations a JOIN licenses l ON a.license_id = l.id
    ORDER BY a.last_seen DESC
");
$activations = $stmt->fetchAll();

$message = $_GET['msg'] ?? '';

adminHeader();
?>

<div class="page-header">
    <h2>Geraete-Aktivierungen</h2>
</div>

<?php if ($message): ?>
    <div class="alert alert-success"><?= htmlspecialchars($message) ?></div>
<?php endif; ?>

<div class="card">
    <div class="card-header">
        <h3>Alle Aktivierungen (<?= count($activations) ?>)</h3>
    </div>
    <div class="card-body">
        <?php if (empty($activations)): ?>
            <div class="empty-state">
                <div class="icon">&#x1F4BB;</div>
                <p>Noch keine Geraete aktiviert</p>
            </div>
        <?php else: ?>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Lizenz</th>
                            <th>Kunde</th>
                            <th>Machine ID</th>
                            <th>Machine Name</th>
                            <th>Aktiviert am</th>
                            <th>Zuletzt gesehen</th>
                            <th>Aktionen</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($activations as $activation): ?>
                            <?php
                            $lastSeen = strtotime($activation['last_seen']);
                            $daysSince = (time() - $lastSeen) / 86400;
                            $badge = $daysSince < 1 ? 'success' : ($daysSince < 7 ? 'warning' : 'danger');
                            ?>
                            <tr>
                                <td><a href="admin-license-edit.php?id=<?= $activation['license_id'] ?>"><code><?= htmlspecialchars($activation['license_key']) ?></code></a></td>
                                <td><?= htmlspecialchars($activation['customer_name'] ?: $activation['customer_email'] ?: '-') ?></td>
                                <td><code title="<?= htmlspecialchars($activation['machine_id']) ?>"><?= htmlspecialchars(substr($activation['machine_id'], 0, 16)) ?>...</code></td>
                                <td><?= htmlspecialchars($activation['machine_name'] ?: '-') ?></td>
                                <td><?= date('d.m.Y H:i', strtotime($activation['activated_at'])) ?></td>
                                <td><span class="badge badge-<?= $badge ?>"><?= date('d.m.Y H:i', $lastSeen) ?></span></td>
                                <td>
                                    <form method="POST" style="display: inline;" onsubmit="return confirm('Aktivierung entfernen?')">
                                        <?= csrfField() ?>
                                        <input type="hidden" name="delete_id" value="<?= $activation['id'] ?>">
                                        <button type="submit" class="btn btn-sm btn-danger">Entfernen</button>
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

<?php adminFooter(); ?>
