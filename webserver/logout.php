<?php
require_once __DIR__ . '/core.php';
App::logout();
App::redirect('login.php');
