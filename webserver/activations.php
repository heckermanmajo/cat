<?php
require_once __DIR__ . '/core.php';
App::requireLogin();
setupDB();

// Delete action
if($_POST && App::s('action') === 'delete') {
    App::csrfCheck();
    $a = Model::byId(Activation::class, App::i('id'));
    if($a) {
        Model::delete($a);
        AuditLog::log('activation_removed', $a->license_id);
    }
    $redirect = App::s('redirect') ?: 'activations.php';
    App::redirect($redirect);
}

$activations = Model::query("
    SELECT a.*, l.license_key
    FROM activation a
    LEFT JOIN license l ON a.license_id = l.id
    ORDER BY a.last_seen DESC
");

head('Aktivierungen');
?>
<h2>Aktivierungen</h2>

<?php if(!$activations): ?>
    <p class="empty">Keine Aktivierungen</p>
<?php else: ?>
    <table>
        <tr>
            <th>Lizenz</th>
            <th>Machine ID</th>
            <th>Name</th>
            <th>Zuletzt</th>
            <th></th>
        </tr>
        <?php foreach($activations as $a): ?>
        <tr>
            <td><code><?= App::e($a['license_key'] ?? '-') ?></code></td>
            <td><code><?= App::e(substr($a['machine_id'], 0, 16)) ?>...</code></td>
            <td><?= App::e($a['machine_name'] ?: '-') ?></td>
            <td><?= App::ago((int)$a['last_seen']) ?></td>
            <td>
                <form method="POST" onsubmit="return confirm('Entfernen?')">
                    <?= App::csrfInput() ?>
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="id" value="<?= $a['id'] ?>">
                    <button class="btn btn-sm btn-danger">X</button>
                </form>
            </td>
        </tr>
        <?php endforeach; ?>
    </table>
<?php endif; ?>

<?php foot();
