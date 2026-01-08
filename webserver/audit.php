<?php
require_once __DIR__ . '/core.php';
App::requireLogin();
setupDB();

$logs = Model::query("
    SELECT a.*, l.license_key
    FROM auditlog a
    LEFT JOIN license l ON a.license_id = l.id
    ORDER BY a.created_at DESC
    LIMIT 100
");

head('Audit Log');
?>
<h2>Audit Log</h2>

<?php if(!$logs): ?>
    <p class="empty">Keine Eintraege</p>
<?php else: ?>
    <table>
        <tr>
            <th>Zeit</th>
            <th>Aktion</th>
            <th>Lizenz</th>
            <th>IP</th>
            <th>Details</th>
        </tr>
        <?php foreach($logs as $log): ?>
        <tr>
            <td><?= App::ago((int)$log['created_at']) ?></td>
            <td><span class="badge"><?= App::e($log['action']) ?></span></td>
            <td><code><?= App::e($log['license_key'] ?? '-') ?></code></td>
            <td><?= App::e($log['ip']) ?></td>
            <td><small><?= App::e($log['details']) ?></small></td>
        </tr>
        <?php endforeach; ?>
    </table>
<?php endif; ?>

<?php foot();
