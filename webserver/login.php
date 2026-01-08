<?php
require_once __DIR__ . '/core.php';

$error = '';
if($_POST) {
    if(App::s('username') === ADMIN_USER && App::s('password') === ADMIN_PASS) {
        App::login();
        App::redirect('dashboard.php');
    }
    $error = 'Falsche Anmeldedaten';
}
?>
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<title>Login - CatKnows</title>
<style><?= css() ?></style>
</head><body>
<h1>CatKnows Admin</h1>
<?php if($error): ?><div class="alert alert-err"><?= $error ?></div><?php endif; ?>
<div class="card"><div class="card-body">
    <form method="POST">
        <label>Benutzer</label>
        <input name="username" required autofocus>
        <label>Passwort</label>
        <input name="password" type="password" required>
        <p style="margin-top:15px"><button type="submit">Anmelden</button></p>
    </form>
</div></div>
</body></html>
