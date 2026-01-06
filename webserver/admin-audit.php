<?php
/**
 * Admin Audit Log
 */
require_once __DIR__ . '/lib.php';
requireLogin();

$db = getDBConnection();

// Filter
$action = $_GET['action'] ?? '';
$days = (int)($_GET['days'] ?? 30);

$where = ["la.created_at >= DATE_SUB(NOW(), INTERVAL ? DAY)"];
$params = [$days];

if ($action) {
    $where[] = "la.action = ?";
    $params[] = $action;
}

$whereClause = 'WHERE ' . implode(' AND ', $where);

$stmt = $db->prepare("
    SELECT la.*, l.license_key FROM license_audit_log la
    LEFT JOIN licenses l ON la.license_id = l.id
    $whereClause ORDER BY la.created_at DESC LIMIT 500
");
$stmt->execute($params);
$logs = $stmt->fetchAll();

// Aktionen fuer Filter
$actionsStmt = $db->query("SELECT DISTINCT action FROM license_audit_log ORDER BY action");
$availableActions = $actionsStmt->fetchAll(PDO::FETCH_COLUMN);

adminHeader();
?>

<div class="page-header">
    <h2>Audit Log</h2>
</div>

<div class="card">
    <div class="card-header">
        <h3>Aktivitaeten (<?= count($logs) ?>)</h3>
    </div>
    <div class="card-body">
        <!-- Filter -->
        <form class="filter-bar" method="GET">
            <select name="action">
                <option value="">Alle Aktionen</option>
                <?php foreach ($availableActions as $a): ?>
                    <option value="<?= $a ?>" <?= $action === $a ? 'selected' : '' ?>><?= ucfirst($a) ?></option>
                <?php endforeach; ?>
            </select>
            <select name="days">
                <option value="7" <?= $days === 7 ? 'selected' : '' ?>>Letzte 7 Tage</option>
                <option value="30" <?= $days === 30 ? 'selected' : '' ?>>Letzte 30 Tage</option>
                <option value="90" <?= $days === 90 ? 'selected' : '' ?>>Letzte 90 Tage</option>
                <option value="365" <?= $days === 365 ? 'selected' : '' ?>>Letztes Jahr</option>
            </select>
            <button type="submit" class="btn btn-secondary btn-sm">Filtern</button>
        </form>

        <?php if (empty($logs)): ?>
            <div class="empty-state">
                <div class="icon">&#x1F4DD;</div>
                <p>Keine Aktivitaeten im gewaehlten Zeitraum</p>
            </div>
        <?php else: ?>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Zeit</th>
                            <th>Aktion</th>
                            <th>Lizenz</th>
                            <th>Machine ID</th>
                            <th>IP-Adresse</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($logs as $log): ?>
                            <?php
                            $actionBadge = match($log['action']) {
                                'check' => 'info',
                                'activate' => 'success',
                                'deactivate', 'delete' => 'danger',
                                'create', 'update', 'renew' => 'warning',
                                default => 'info'
                            };
                            $details = json_decode($log['details'] ?? '{}', true) ?: [];
                            ?>
                            <tr>
                                <td><?= date('d.m.Y H:i:s', strtotime($log['created_at'])) ?></td>
                                <td><span class="badge badge-<?= $actionBadge ?>"><?= htmlspecialchars($log['action']) ?></span></td>
                                <td>
                                    <?php if ($log['license_key']): ?>
                                        <code><?= htmlspecialchars($log['license_key']) ?></code>
                                    <?php elseif (isset($details['license_key'])): ?>
                                        <code title="Geloescht"><?= htmlspecialchars($details['license_key']) ?></code>
                                    <?php else: ?>
                                        <span style="color: var(--gray-400);">-</span>
                                    <?php endif; ?>
                                </td>
                                <td>
                                    <?php if ($log['machine_id']): ?>
                                        <code title="<?= htmlspecialchars($log['machine_id']) ?>"><?= htmlspecialchars(substr($log['machine_id'], 0, 12)) ?>...</code>
                                    <?php else: ?>
                                        <span style="color: var(--gray-400);">-</span>
                                    <?php endif; ?>
                                </td>
                                <td><?= htmlspecialchars($log['ip_address'] ?: '-') ?></td>
                                <td>
                                    <?php if (!empty($details)): ?>
                                        <code style="font-size: 11px;"><?= htmlspecialchars(json_encode($details, JSON_UNESCAPED_UNICODE)) ?></code>
                                    <?php else: ?>
                                        <span style="color: var(--gray-400);">-</span>
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

<?php adminFooter(); ?>
