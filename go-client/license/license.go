package license

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// API-Endpunkt - in Produktion: https://api.cat-knows.com
const LicenseAPIURL = "https://api.cat-knows.com/api/license/validate.php"

// Server Public Key - wird vom Server generiert und hier eingebettet
// WICHTIG: Diesen Key durch den echten ersetzen nach Key-Generierung!
// Kann jeder sehen - das ist OK, nur der Server hat den Private Key
var ServerPublicKey = mustDecodeHex("0000000000000000000000000000000000000000000000000000000000000000") // 32 bytes placeholder

func mustDecodeHex(s string) ed25519.PublicKey {
	b, err := hex.DecodeString(s)
	if err != nil {
		panic("invalid public key hex: " + err.Error())
	}
	return ed25519.PublicKey(b)
}

// LicensePayload ist die signierte Antwort vom Server
type LicensePayload struct {
	Valid     bool   `json:"valid"`
	ExpiresAt string `json:"expires_at"` // Format: 2025-12-31
	Nonce     string `json:"nonce"`
	Timestamp int64  `json:"timestamp"`
	Product   string `json:"product"`
	Features  []string `json:"features,omitempty"`
}

// LicenseResponse ist die komplette Server-Antwort
type LicenseResponse struct {
	Payload   LicensePayload `json:"payload"`
	Signature string         `json:"signature"` // hex-encoded
}

// LicenseRequest wird an den Server gesendet
type LicenseRequest struct {
	LicenseKey string `json:"license_key"`
	Nonce      string `json:"nonce"`
	MachineID  string `json:"machine_id"`
}

// CachedLicense wird lokal in SQLite gespeichert
type CachedLicense struct {
	LicenseKey string
	Valid      bool
	ExpiresAt  time.Time
	LastCheck  time.Time
	Features   []string
}

// Manager verwaltet den Lizenz-Status
type Manager struct {
	db           *sql.DB
	licenseKey   string
	machineID    string
	checkInterval time.Duration
	cache        *CachedLicense
}

// NewManager erstellt einen neuen Lizenz-Manager
func NewManager(db *sql.DB, licenseKey, machineID string) *Manager {
	return &Manager{
		db:           db,
		licenseKey:   licenseKey,
		machineID:    machineID,
		checkInterval: 24 * time.Hour, // Check alle 24h
	}
}

// InitDB erstellt die Lizenz-Cache-Tabelle
func (m *Manager) InitDB() error {
	_, err := m.db.Exec(`
		CREATE TABLE IF NOT EXISTS license_cache (
			id INTEGER PRIMARY KEY,
			license_key TEXT NOT NULL,
			valid INTEGER NOT NULL,
			expires_at TEXT NOT NULL,
			last_check TEXT NOT NULL,
			features TEXT
		)
	`)
	return err
}

// CheckLicense prüft die Lizenz (mit Cache)
func (m *Manager) CheckLicense() (bool, error) {
	// 1. Cache laden
	cached, err := m.loadCache()
	if err == nil && cached != nil {
		// Cache vorhanden - prüfen ob noch aktuell
		if time.Since(cached.LastCheck) < m.checkInterval && cached.Valid {
			// Cache ist frisch genug
			if time.Now().Before(cached.ExpiresAt) {
				m.cache = cached
				return true, nil
			}
		}
	}

	// 2. Online-Check durchführen
	valid, err := m.checkOnline()
	if err != nil {
		// Offline? Dann Cache mit Grace-Period nutzen
		if cached != nil && time.Since(cached.LastCheck) < 7*24*time.Hour {
			// Max 7 Tage offline erlaubt
			return cached.Valid && time.Now().Before(cached.ExpiresAt), nil
		}
		return false, fmt.Errorf("lizenz-check fehlgeschlagen: %w", err)
	}

	return valid, nil
}

// checkOnline führt den eigentlichen API-Call durch
func (m *Manager) checkOnline() (bool, error) {
	// 1. Nonce generieren
	nonce, err := generateNonce()
	if err != nil {
		return false, err
	}

	// 2. Request erstellen
	reqBody := LicenseRequest{
		LicenseKey: m.licenseKey,
		Nonce:      nonce,
		MachineID:  m.machineID,
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return false, err
	}

	// 3. HTTP-Request senden
	resp, err := http.Post(LicenseAPIURL, "application/json", bytes.NewBuffer(jsonBody))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return false, fmt.Errorf("server returned status %d", resp.StatusCode)
	}

	// 4. Response parsen
	var licenseResp LicenseResponse
	if err := json.NewDecoder(resp.Body).Decode(&licenseResp); err != nil {
		return false, err
	}

	// 5. Signatur verifizieren
	if !m.verifySignature(licenseResp) {
		return false, fmt.Errorf("ungueltige signatur - moegliche manipulation")
	}

	// 6. Nonce prüfen
	if licenseResp.Payload.Nonce != nonce {
		return false, fmt.Errorf("nonce mismatch - replay attack?")
	}

	// 7. Timestamp prüfen (max 5 min alt)
	if time.Now().Unix()-licenseResp.Payload.Timestamp > 300 {
		return false, fmt.Errorf("response zu alt")
	}

	// 8. Cache aktualisieren
	expiresAt, _ := time.Parse("2006-01-02", licenseResp.Payload.ExpiresAt)
	cached := &CachedLicense{
		LicenseKey: m.licenseKey,
		Valid:      licenseResp.Payload.Valid,
		ExpiresAt:  expiresAt,
		LastCheck:  time.Now(),
		Features:   licenseResp.Payload.Features,
	}
	m.saveCache(cached)
	m.cache = cached

	return licenseResp.Payload.Valid, nil
}

// verifySignature prüft die kryptographische Signatur
func (m *Manager) verifySignature(resp LicenseResponse) bool {
	// Payload als JSON serialisieren (gleiche Reihenfolge wie Server!)
	payloadBytes, err := json.Marshal(resp.Payload)
	if err != nil {
		return false
	}

	// Signatur dekodieren
	signature, err := hex.DecodeString(resp.Signature)
	if err != nil {
		return false
	}

	// Ed25519 Verifikation
	return ed25519.Verify(ServerPublicKey, payloadBytes, signature)
}

// loadCache lädt den Cache aus SQLite
func (m *Manager) loadCache() (*CachedLicense, error) {
	row := m.db.QueryRow(`
		SELECT license_key, valid, expires_at, last_check, features
		FROM license_cache
		WHERE license_key = ?
		LIMIT 1
	`, m.licenseKey)

	var cached CachedLicense
	var expiresAtStr, lastCheckStr, featuresJSON string
	var validInt int

	err := row.Scan(&cached.LicenseKey, &validInt, &expiresAtStr, &lastCheckStr, &featuresJSON)
	if err != nil {
		return nil, err
	}

	cached.Valid = validInt == 1
	cached.ExpiresAt, _ = time.Parse(time.RFC3339, expiresAtStr)
	cached.LastCheck, _ = time.Parse(time.RFC3339, lastCheckStr)

	if featuresJSON != "" {
		json.Unmarshal([]byte(featuresJSON), &cached.Features)
	}

	return &cached, nil
}

// saveCache speichert den Cache in SQLite
func (m *Manager) saveCache(cached *CachedLicense) error {
	featuresJSON, _ := json.Marshal(cached.Features)
	validInt := 0
	if cached.Valid {
		validInt = 1
	}

	_, err := m.db.Exec(`
		INSERT OR REPLACE INTO license_cache (id, license_key, valid, expires_at, last_check, features)
		VALUES (1, ?, ?, ?, ?, ?)
	`, cached.LicenseKey, validInt, cached.ExpiresAt.Format(time.RFC3339), cached.LastCheck.Format(time.RFC3339), string(featuresJSON))

	return err
}

// GetFeatures gibt die lizenzierten Features zurück
func (m *Manager) GetFeatures() []string {
	if m.cache != nil {
		return m.cache.Features
	}
	return nil
}

// GetExpiresAt gibt das Ablaufdatum zurück
func (m *Manager) GetExpiresAt() time.Time {
	if m.cache != nil {
		return m.cache.ExpiresAt
	}
	return time.Time{}
}

// generateNonce erstellt eine kryptographisch sichere Zufallszahl
func generateNonce() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
