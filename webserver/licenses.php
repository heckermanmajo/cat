<?php
require_once __DIR__ . '/core.php';
App::requireLogin();
setupDB();

// Delete action
if($_POST && App::s('action') === 'delete') {
    App::csrfCheck();
    $l = Model::byId(License::class, App::i('id'));
    if($l) {
        Model::delete($l);
        AuditLog::log('delete', $l->id, ['key' => $l->license_key]);
    }
    App::redirect('licenses.php?msg=geloescht');
}

$filter = App::s('filter', 'all');
$search = App::s('search');

$where = '1=1';
$args = [];

if($filter === 'active') {
    $where = 'is_active = 1 AND valid_until >= ?';
    $args = [time()];
}
if($filter === 'expired') {
    $where = 'valid_until < ?';
    $args = [time()];
}
if($filter === 'inactive') {
    $where = 'is_active = 0';
}
if($search) {
    $where .= " AND (license_key LIKE ? OR customer_name LIKE ? OR customer_email LIKE ?)";
    $args = array_merge($args, ["%$search%", "%$search%", "%$search%"]);
}

$licenses = Model::getList(License::class, "SELECT * FROM license WHERE $where ORDER BY created_at DESC", $args);

head('Lizenzen');
?>
<h2>Lizenzen <a href="license-edit.php" class="btn btn-sm" style="float:right">+ Neu</a></h2>

<?php if(App::s('msg')): ?>
    <div class="alert alert-ok"><?= App::e(App::s('msg')) ?></div>
<?php endif; ?>

<form method="GET" style="margin:15px 0">
    <div class="form-row">
        <div><input name="search" placeholder="Suchen..." value="<?= App::e($search) ?>"></div>
        <div>
            <select name="filter" onchange="this.form.submit()">
                <option value="all" <?= $filter==='all'?'selected':'' ?>>Alle</option>
                <option value="active" <?= $filter==='active'?'selected':'' ?>>Aktiv</option>
                <option value="expired" <?= $filter==='expired'?'selected':'' ?>>Abgelaufen</option>
                <option value="inactive" <?= $filter==='inactive'?'selected':'' ?>>Deaktiviert</option>
            </select>
        </div>
        <div><button type="submit">Filtern</button></div>
    </div>
</form>

<?php if(!$licenses): ?>
    <p class="empty">Keine Lizenzen gefunden</p>
<?php else: ?>
    <table>
        <tr>
            <th>Key</th>
            <th>Kunde</th>
            <th>Gueltig bis</th>
            <th>Aktivierungen</th>
            <th>Status</th>
            <th></th>
        </tr>
        <?php foreach($licenses as $l): ?>
        <tr>
            <td><a href="license-edit.php?id=<?= $l->id ?>"><code><?= App::e($l->license_key) ?></code></a></td>
            <td><?= App::e($l->customer_name ?: '-') ?><br><small><?= App::e($l->customer_email) ?></small></td>
            <td><?= App::date($l->valid_until) ?></td>
            <td><?= $l->activationCount() ?> / <?= $l->max_activations ?></td>
            <td>
                <?php if($l->isValid()): ?><span class="badge badge-ok">Aktiv</span>
                <?php elseif($l->isExpired()): ?><span class="badge badge-err">Abgelaufen</span>
                <?php else: ?><span class="badge badge-warn">Deaktiviert</span><?php endif; ?>
            </td>
            <td class="actions">
                <a href="license-edit.php?id=<?= $l->id ?>" class="btn btn-sm btn-outline">Edit</a>
                <form method="POST" style="display:inline" onsubmit="return confirm('Wirklich loeschen?')">
                    <?= App::csrfInput() ?>
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="id" value="<?= $l->id ?>">
                    <button class="btn btn-sm btn-danger">X</button>
                </form>
            </td>
        </tr>
        <?php endforeach; ?>
    </table>
<?php endif; ?>

<?php foot();
