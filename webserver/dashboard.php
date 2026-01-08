<?php
require_once __DIR__ . '/core.php';
App::requireLogin();
setupDB();

$total = Model::count(License::class);
$active = Model::count(License::class, 'is_active = 1 AND valid_until >= ?', [time()]);
$expired = Model::count(License::class, 'valid_until < ?', [time()]);
$activations = Model::count(Activation::class);

head('Dashboard');
?>
<h2>Dashboard</h2>

<div class="stats">
    <div class="stat"><div class="stat-val"><?= $total ?></div><div class="stat-label">Lizenzen</div></div>
    <div class="stat"><div class="stat-val"><?= $active ?></div><div class="stat-label">Aktiv</div></div>
    <div class="stat"><div class="stat-val"><?= $expired ?></div><div class="stat-label">Abgelaufen</div></div>
    <div class="stat"><div class="stat-val"><?= $activations ?></div><div class="stat-label">Aktivierungen</div></div>
</div>

<div class="row">
    <div class="col">
        <div class="card">
            <div class="card-header">Letzte Lizenzen</div>
            <div class="card-body">
                <?php $recent = Model::getList(License::class, "SELECT * FROM license ORDER BY created_at DESC LIMIT 5"); ?>
                <?php if(!$recent): ?>
                    <p class="empty">Keine Lizenzen</p>
                <?php else: ?>
                    <table>
                        <tr><th>Key</th><th>Kunde</th><th>Status</th></tr>
                        <?php foreach($recent as $l): ?>
                        <tr>
                            <td><a href="license-edit.php?id=<?= $l->id ?>"><code><?= App::e($l->license_key) ?></code></a></td>
                            <td><?= App::e($l->customer_name ?: $l->customer_email ?: '-') ?></td>
                            <td>
                                <?php if($l->isValid()): ?><span class="badge badge-ok">Aktiv</span>
                                <?php elseif($l->isExpired()): ?><span class="badge badge-err">Abgelaufen</span>
                                <?php else: ?><span class="badge badge-warn">Deaktiviert</span><?php endif; ?>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                    </table>
                <?php endif; ?>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card">
            <div class="card-header">Letzte Aktivitaet</div>
            <div class="card-body">
                <?php $logs = Model::getList(AuditLog::class, "SELECT * FROM auditlog ORDER BY created_at DESC LIMIT 5"); ?>
                <?php if(!$logs): ?>
                    <p class="empty">Keine Aktivitaet</p>
                <?php else: ?>
                    <table>
                        <tr><th>Zeit</th><th>Aktion</th></tr>
                        <?php foreach($logs as $log): ?>
                        <tr>
                            <td><?= App::ago($log->created_at) ?></td>
                            <td><?= App::e($log->action) ?></td>
                        </tr>
                        <?php endforeach; ?>
                    </table>
                <?php endif; ?>
            </div>
        </div>
    </div>
</div>

<?php foot();
