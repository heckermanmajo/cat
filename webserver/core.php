<?php
declare(strict_types = 1);
error_reporting(E_ALL);
ini_set('display_errors', '1');
session_start();

class UserError extends Exception {}
const DB = "sqlite:./catknows.db";
const ADMIN_USER = "admin";
const ADMIN_PASS = "admin123";
const LICENSE_PRIVATE_KEY = "";
const LICENSE_PUBLIC_KEY = "";

// ============================================================================
// Model - ORM
// ============================================================================
class Model {
    private static function connect(): PDO {
        static $PDO = null;
        if($PDO === null) $PDO = new PDO(DB, options: [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
        return $PDO;
    }
    private static function props(string $class): array {
        $props = [];
        foreach((new ReflectionClass($class))->getProperties(ReflectionProperty::IS_PUBLIC) as $p) {
            if($p->getName()[0] === '_') continue;
            $type = $p->getType(); $sqlType = 'TEXT';
            if($type instanceof ReflectionNamedType) $sqlType = match($type->getName()) { 'int' => 'INTEGER', 'float' => 'REAL', default => 'TEXT' };
            $props[$p->getName()] = $sqlType;
        }
        return $props;
    }
    static function updateTable(string $class): void {
        $table = strtolower($class); $props = self::props($class); $pdo = self::connect();
        $cols = array_map(fn($n, $t) => "$n $t" . ($n === 'id' ? ' PRIMARY KEY AUTOINCREMENT' : ''), array_keys($props), $props);
        $pdo->exec("CREATE TABLE IF NOT EXISTS $table (" . implode(', ', $cols) . ")");
        foreach($props as $name => $type) { try { $pdo->exec("ALTER TABLE $table ADD COLUMN $name $type"); } catch(Throwable) {} }
    }
    static function save(object &$instance): void {
        $class = get_class($instance); $table = strtolower($class); $props = self::props($class);
        $data = []; foreach(array_keys($props) as $k) if($k !== 'id') $data[$k] = $instance->$k;
        if($instance->id === null) {
            $instance->created_at = time(); $data['created_at'] = $instance->created_at;
            $cols = implode(', ', array_keys($data)); $placeholders = implode(', ', array_map(fn($k) => ":$k", array_keys($data)));
            $stmt = self::connect()->prepare("INSERT INTO $table ($cols) VALUES ($placeholders)");
            $stmt->execute($data); $instance->id = (int)self::connect()->lastInsertId();
        } else {
            $instance->updated_at = time(); $data['updated_at'] = $instance->updated_at;
            $sets = implode(', ', array_map(fn($k) => "$k = :$k", array_keys($data)));
            $stmt = self::connect()->prepare("UPDATE $table SET $sets WHERE id = :id");
            $stmt->execute([...$data, 'id' => $instance->id]);
        }
    }
    static function delete(object $instance): void {
        $table = strtolower(get_class($instance));
        self::connect()->prepare("DELETE FROM $table WHERE id = ?")->execute([$instance->id]);
    }
    static function byId(string $class, int $id): ?object {
        $table = strtolower($class);
        $stmt = self::connect()->prepare("SELECT * FROM $table WHERE id = ?"); $stmt->execute([$id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC); if(!$row) return null;
        $obj = new $class(); foreach($row as $k => $v) if(property_exists($obj, $k)) $obj->$k = $v;
        return $obj;
    }
    static function all(string $class, string $order = 'id DESC'): array {
        $table = strtolower($class);
        return self::getList($class, "SELECT * FROM $table ORDER BY $order");
    }
    static function getList(string $class, string $sql, array $args = []): array {
        $stmt = self::connect()->prepare($sql); $stmt->execute($args);
        $list = []; while($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $obj = new $class(); foreach($row as $k => $v) if(property_exists($obj, $k)) $obj->$k = $v;
            $list[] = $obj;
        }
        return $list;
    }
    static function count(string $class, string $where = '1=1', array $args = []): int {
        $table = strtolower($class);
        $stmt = self::connect()->prepare("SELECT COUNT(*) FROM $table WHERE $where");
        $stmt->execute($args);
        return (int)$stmt->fetchColumn();
    }
    static function query(string $sql, array $args = []): array {
        $stmt = self::connect()->prepare($sql); $stmt->execute($args);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
}

// ============================================================================
// App - Utilities
// ============================================================================
class App {
    static function e(string $t): string { return htmlspecialchars($t); }
    static function csrf(): string { return $_SESSION['_csrf'] ??= bin2hex(random_bytes(32)); }
    static function csrfCheck(): void {
        $t = $_POST['_csrf'] ?? '';
        if(!hash_equals(self::csrf(), $t)) throw new UserError('CSRF token invalid');
    }
    static function csrfInput(): string { return '<input type="hidden" name="_csrf" value="'.self::csrf().'">'; }
    static function isLoggedIn(): bool { return ($_SESSION['admin'] ?? 0) === 1; }
    static function login(): void { $_SESSION['admin'] = 1; }
    static function logout(): void { $_SESSION['admin'] = 0; }
    static function requireLogin(): void { if(!self::isLoggedIn()) self::redirect('login.php'); }
    static function redirect(string $url): never { header("Location: $url"); exit; }
    static function s(string $k, ?string $d = null): string { return $_POST[$k] ?? $_GET[$k] ?? $d ?? ''; }
    static function i(string $k, ?int $d = null): int { return (int)($_POST[$k] ?? $_GET[$k] ?? $d ?? 0); }
    static function ago(int $ts): string {
        if($ts === 0) return '-';
        $d = time() - $ts;
        if($d < 60) return 'gerade';
        if($d < 3600) return floor($d/60).'m';
        if($d < 86400) return floor($d/3600).'h';
        return floor($d/86400).'d';
    }
    static function date(int $ts): string { return $ts ? date('d.m.Y', $ts) : '-'; }
    static function generateKey(): string {
        $chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
        $parts = [];
        for ($i = 0; $i < 4; $i++) {
            $part = '';
            for ($j = 0; $j < 4; $j++) $part .= $chars[random_int(0, strlen($chars) - 1)];
            $parts[] = $part;
        }
        return implode('-', $parts);
    }
}

// ============================================================================
// Models
// ============================================================================
trait Table {
    public ?int $id = null;
    public int $created_at = 0;
    public int $updated_at = 0;
}

class License implements JsonSerializable {
    use Table;
    public string $license_key = "";
    public string $customer_name = "";
    public string $customer_email = "";
    public int $valid_until = 0;
    public int $is_active = 1;
    public int $max_activations = 3;
    public string $features = "[]";
    public string $notes = "";
    public int $last_check = 0;

    function jsonSerialize(): mixed { return get_object_vars($this); }
    function isExpired(): bool { return $this->valid_until < time(); }
    function isValid(): bool { return $this->is_active && !$this->isExpired(); }
    function getFeatures(): array { return json_decode($this->features, true) ?: []; }
    function setFeatures(array $f): void { $this->features = json_encode($f); }
    function activationCount(): int { return Model::count(Activation::class, 'license_id = ?', [$this->id]); }
}

class Activation implements JsonSerializable {
    use Table;
    public int $license_id = 0;
    public string $machine_id = "";
    public string $machine_name = "";
    public int $last_seen = 0;
    function jsonSerialize(): mixed { return get_object_vars($this); }
}

class AuditLog implements JsonSerializable {
    use Table;
    public ?int $license_id = null;
    public string $action = "";
    public string $details = "";
    public string $ip = "";
    function jsonSerialize(): mixed { return get_object_vars($this); }
    static function log(string $action, ?int $licenseId = null, array $details = []): void {
        $l = new self();
        $l->action = $action;
        $l->license_id = $licenseId;
        $l->details = json_encode($details);
        $l->ip = $_SERVER['REMOTE_ADDR'] ?? '';
        Model::save($l);
    }
}
