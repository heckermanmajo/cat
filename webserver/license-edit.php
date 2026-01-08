<?php
require_once __DIR__ . '/core.php';
App::requireLogin();
setupDB();

$id = App::i('id');
$license = $id ? Model::byId(License::class, $id) : null;
$isNew = !$license;
$error = '';
$features = ['basic', 'analytics', 'ai', 'dev'];

if($_POST) {
    App::csrfCheck();
    if(!$license) $license = new License();

    $license->license_key = App::s('license_key');
    $license->customer_name = App::s('customer_name');
    $license->customer_email = App::s('customer_email');
    $license->valid_until = strtotime(App::s('valid_until')) ?: time() + 86400*365;
    $license->is_active = isset($_POST['is_active']) ? 1 : 0;
    $license->max_activations = App::i('max_activations', 3);
    $license->setFeatures($_POST['features'] ?? []);
    $license->notes = App::s('notes');

    if(!$license->license_key) {
        $error = 'Key erforderlich';
    } else {
        Model::save($license);
        AuditLog::log($isNew ? 'create' : 'update', $license->id);
        App::redirect('licenses.php?msg=' . ($isNew ? 'erstellt' : 'aktualisiert'));
    }
}

// Defaults for new license
if(!$license) {
    $license = new License();
    $license->license_key = App::generateKey();
    $license->valid_until = time() + 86400*365;
    $license->features = '["basic"]';
}

head($isNew ? 'Neue Lizenz' : 'Lizenz bearbeiten');
?>
<h2>
    <?= $isNew ? 'Neue Lizenz' : 'Lizenz bearbeiten' ?>
    <a href="licenses.php" class="btn btn-sm btn-outline" style="float:right">Zurueck</a>
</h2>

<?php if($error): ?>
    <div class="alert alert-err"><?= $error ?></div>
<?php endif; ?>

<div class="card"><div class="card-body">
    <form method="POST">
        <?= App::csrfInput() ?>

        <div class="form-row">
            <div>
                <label>Lizenz-Key *</label>
                <input name="license_key" value="<?= App::e($license->license_key) ?>" required>
            </div>
            <div>
                <label>Gueltig bis *</label>
                <input type="date" name="valid_until" value="<?= date('Y-m-d', $license->valid_until) ?>" required>
            </div>
        </div>

        <div class="form-row">
            <div>
                <label>Kundenname</label>
                <input name="customer_name" value="<?= App::e($license->customer_name) ?>">
            </div>
            <div>
                <label>E-Mail</label>
                <input type="email" name="customer_email" value="<?= App::e($license->customer_email) ?>">
            </div>
        </div>

        <div class="form-row">
            <div>
                <label>Max. Aktivierungen</label>
                <input type="number" name="max_activations" min="1" value="<?= $license->max_activations ?>">
            </div>
            <div>
                <label>&nbsp;</label>
                <label><input type="checkbox" name="is_active" <?= $license->is_active ? 'checked' : '' ?>> Aktiv</label>
            </div>
        </div>

        <label>Features</label>
        <div style="margin:10px 0">
            <?php $sel = $license->getFeatures(); foreach($features as $f): ?>
                <label style="display:inline-block;margin-right:15px">
                    <input type="checkbox" name="features[]" value="<?= $f ?>" <?= in_array($f,$sel)?'checked':'' ?>>
                    <?= ucfirst($f) ?>
                </label>
            <?php endforeach; ?>
        </div>

        <label>Notizen</label>
        <textarea name="notes" rows="3"><?= App::e($license->notes) ?></textarea>

        <p style="margin-top:15px">
            <button type="submit"><?= $isNew ? 'Erstellen' : 'Speichern' ?></button>
        </p>
    </form>
</div></div>

<?php if(!$isNew): ?>
    <?php $acts = Model::getList(Activation::class, "SELECT * FROM activation WHERE license_id = ? ORDER BY last_seen DESC", [$license->id]); ?>
    <div class="card">
        <div class="card-header">Aktivierungen (<?= count($acts) ?>)</div>
        <div class="card-body">
            <?php if(!$acts): ?>
                <p class="empty">Keine Aktivierungen</p>
            <?php else: ?>
                <table>
                    <tr><th>Machine ID</th><th>Name</th><th>Zuletzt</th><th></th></tr>
                    <?php foreach($acts as $a): ?>
                    <tr>
                        <td><code><?= App::e(substr($a->machine_id, 0, 16)) ?>...</code></td>
                        <td><?= App::e($a->machine_name ?: '-') ?></td>
                        <td><?= App::ago($a->last_seen) ?></td>
                        <td>
                            <form method="POST" action="activations.php" style="display:inline">
                                <?= App::csrfInput() ?>
                                <input type="hidden" name="action" value="delete">
                                <input type="hidden" name="id" value="<?= $a->id ?>">
                                <input type="hidden" name="redirect" value="license-edit.php?id=<?= $license->id ?>">
                                <button class="btn btn-sm btn-danger">X</button>
                            </form>
                        </td>
                    </tr>
                    <?php endforeach; ?>
                </table>
            <?php endif; ?>
        </div>
    </div>
<?php endif; ?>

<?php foot();
