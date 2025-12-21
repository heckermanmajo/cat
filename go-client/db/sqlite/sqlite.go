package sqlite

import (
	"database/sql"
	_ "embed"
	"fmt"
	"time"

	_ "modernc.org/sqlite"
)

//go:embed schema.sql
var schema string

type AppDB struct {
	db *sql.DB
}

func Connect(dbPath string) (*AppDB, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("sqlite open error: %w", err)
	}

	// Foreign Keys aktivieren
	if _, err := db.Exec("PRAGMA foreign_keys = ON;"); err != nil {
		return nil, err
	}

	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("sqlite schema error: %w", err)
	}

	return &AppDB{db: db}, nil
}

func (a *AppDB) Close() error {
	return a.db.Close()
}

// === Settings ===

func (a *AppDB) GetSetting(key string) (string, error) {
	var value string
	err := a.db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return value, err
}

func (a *AppDB) SetSetting(key, value string) error {
	_, err := a.db.Exec(`
		INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
	`, key, value, time.Now(), value, time.Now())
	return err
}

func (a *AppDB) GetAllSettings() (map[string]string, error) {
	rows, err := a.db.Query("SELECT key, value FROM settings")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[string]string)
	for rows.Next() {
		var key, value string
		if err := rows.Scan(&key, &value); err != nil {
			return nil, err
		}
		result[key] = value
	}
	return result, rows.Err()
}

// === UI State ===

func (a *AppDB) GetUIState(key string) (string, error) {
	var value string
	err := a.db.QueryRow("SELECT value FROM ui_state WHERE key = ?", key).Scan(&value)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return value, err
}

func (a *AppDB) SetUIState(key, value string) error {
	_, err := a.db.Exec(`
		INSERT INTO ui_state (key, value, updated_at) VALUES (?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
	`, key, value, time.Now(), value, time.Now())
	return err
}

// === Saved Queries ===

type SavedQuery struct {
	ID        int64
	Name      string
	QueryType string
	QueryJSON string
	CreatedAt time.Time
}

func (a *AppDB) SaveQuery(name, queryType, queryJSON string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO saved_queries (name, query_type, query_json, created_at)
		VALUES (?, ?, ?, ?)
	`, name, queryType, queryJSON, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetSavedQueries(queryType string) ([]SavedQuery, error) {
	rows, err := a.db.Query(`
		SELECT id, name, query_type, query_json, created_at
		FROM saved_queries
		WHERE query_type = ?
		ORDER BY created_at DESC
	`, queryType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var queries []SavedQuery
	for rows.Next() {
		var q SavedQuery
		if err := rows.Scan(&q.ID, &q.Name, &q.QueryType, &q.QueryJSON, &q.CreatedAt); err != nil {
			return nil, err
		}
		queries = append(queries, q)
	}
	return queries, rows.Err()
}

func (a *AppDB) DeleteSavedQuery(id int64) error {
	_, err := a.db.Exec("DELETE FROM saved_queries WHERE id = ?", id)
	return err
}

// === License ===

type License struct {
	Key       string
	Status    string
	ExpiresAt *time.Time
	CheckedAt time.Time
}

func (a *AppDB) GetLicense() (*License, error) {
	var lic License
	var expiresAt sql.NullTime
	err := a.db.QueryRow(`
		SELECT license_key, status, expires_at, checked_at
		FROM license WHERE id = 1
	`).Scan(&lic.Key, &lic.Status, &expiresAt, &lic.CheckedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if expiresAt.Valid {
		lic.ExpiresAt = &expiresAt.Time
	}
	return &lic, nil
}

func (a *AppDB) SetLicense(key, status string, expiresAt *time.Time) error {
	_, err := a.db.Exec(`
		INSERT INTO license (id, license_key, status, expires_at, checked_at)
		VALUES (1, ?, ?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			license_key = ?, status = ?, expires_at = ?, checked_at = ?
	`, key, status, expiresAt, time.Now(), key, status, expiresAt, time.Now())
	return err
}

// === Reports ===

type Report struct {
	ID         int64
	Name       string
	ReportType string
	DataJSON   string
	CreatedAt  time.Time
}

func (a *AppDB) SaveReport(name, reportType, dataJSON string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO reports (name, report_type, data_json, created_at)
		VALUES (?, ?, ?, ?)
	`, name, reportType, dataJSON, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetReports(reportType string) ([]Report, error) {
	rows, err := a.db.Query(`
		SELECT id, name, report_type, data_json, created_at
		FROM reports
		WHERE report_type = ?
		ORDER BY created_at DESC
	`, reportType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var reports []Report
	for rows.Next() {
		var r Report
		if err := rows.Scan(&r.ID, &r.Name, &r.ReportType, &r.DataJSON, &r.CreatedAt); err != nil {
			return nil, err
		}
		reports = append(reports, r)
	}
	return reports, rows.Err()
}

// === Sync Log ===

type SyncLogEntry struct {
	ID           int64
	SyncType     string
	EntityCount  int
	Status       string
	ErrorMessage string
	SyncedAt     time.Time
}

func (a *AppDB) LogSync(syncType string, entityCount int, status, errorMsg string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO sync_log (sync_type, entity_count, status, error_message, synced_at)
		VALUES (?, ?, ?, ?, ?)
	`, syncType, entityCount, status, errorMsg, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetRecentSyncs(limit int) ([]SyncLogEntry, error) {
	rows, err := a.db.Query(`
		SELECT id, sync_type, entity_count, status, COALESCE(error_message, ''), synced_at
		FROM sync_log
		ORDER BY synced_at DESC
		LIMIT ?
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []SyncLogEntry
	for rows.Next() {
		var e SyncLogEntry
		if err := rows.Scan(&e.ID, &e.SyncType, &e.EntityCount, &e.Status, &e.ErrorMessage, &e.SyncedAt); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, rows.Err()
}

// === Logging ===

type LogLevel string

const (
	LogLevelDebug LogLevel = "debug"
	LogLevelInfo  LogLevel = "info"
	LogLevelWarn  LogLevel = "warn"
	LogLevelError LogLevel = "error"
)

type LogEntry struct {
	ID        int64     `json:"id"`
	Level     string    `json:"level"`
	Source    string    `json:"source"`
	Message   string    `json:"message"`
	Details   string    `json:"details,omitempty"`
	CreatedAt time.Time `json:"createdAt"`
}

type LogFilter struct {
	Level  string
	Source string
	Limit  int
	Offset int
}

func (a *AppDB) WriteLog(level LogLevel, source, message, details string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO logs (level, source, message, details, created_at)
		VALUES (?, ?, ?, ?, ?)
	`, string(level), source, message, details, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) LogDebug(source, message string) {
	a.WriteLog(LogLevelDebug, source, message, "")
}

func (a *AppDB) LogInfo(source, message string) {
	a.WriteLog(LogLevelInfo, source, message, "")
}

func (a *AppDB) LogWarn(source, message string) {
	a.WriteLog(LogLevelWarn, source, message, "")
}

func (a *AppDB) LogError(source, message, details string) {
	a.WriteLog(LogLevelError, source, message, details)
}

func (a *AppDB) GetLogs(filter LogFilter) ([]LogEntry, error) {
	query := `SELECT id, level, source, message, COALESCE(details, ''), created_at FROM logs WHERE 1=1`
	args := []interface{}{}

	if filter.Level != "" {
		query += " AND level = ?"
		args = append(args, filter.Level)
	}
	if filter.Source != "" {
		query += " AND source = ?"
		args = append(args, filter.Source)
	}

	query += " ORDER BY created_at DESC"

	if filter.Limit > 0 {
		query += " LIMIT ?"
		args = append(args, filter.Limit)
	} else {
		query += " LIMIT 100"
	}

	if filter.Offset > 0 {
		query += " OFFSET ?"
		args = append(args, filter.Offset)
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []LogEntry
	for rows.Next() {
		var e LogEntry
		if err := rows.Scan(&e.ID, &e.Level, &e.Source, &e.Message, &e.Details, &e.CreatedAt); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, rows.Err()
}

func (a *AppDB) GetLogSources() ([]string, error) {
	rows, err := a.db.Query("SELECT DISTINCT source FROM logs ORDER BY source")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var sources []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, err
		}
		sources = append(sources, s)
	}
	return sources, rows.Err()
}

func (a *AppDB) ClearLogs() error {
	_, err := a.db.Exec("DELETE FROM logs")
	return err
}

func (a *AppDB) GetLogCount() (int64, error) {
	var count int64
	err := a.db.QueryRow("SELECT COUNT(*) FROM logs").Scan(&count)
	return count, err
}

// === Chats ===

type Chat struct {
	ID        int64     `json:"id"`
	Title     string    `json:"title"`
	ReportID  *int64    `json:"reportId,omitempty"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

func (a *AppDB) CreateChat(title string) (int64, error) {
	if title == "" {
		title = "Neuer Chat"
	}
	result, err := a.db.Exec(`
		INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)
	`, title, time.Now(), time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetChat(id int64) (*Chat, error) {
	var c Chat
	var reportID sql.NullInt64
	err := a.db.QueryRow(`
		SELECT id, title, report_id, created_at, updated_at FROM chats WHERE id = ?
	`, id).Scan(&c.ID, &c.Title, &reportID, &c.CreatedAt, &c.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if reportID.Valid {
		c.ReportID = &reportID.Int64
	}
	return &c, nil
}

func (a *AppDB) GetAllChats() ([]Chat, error) {
	rows, err := a.db.Query(`
		SELECT id, title, report_id, created_at, updated_at
		FROM chats ORDER BY updated_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var chats []Chat
	for rows.Next() {
		var c Chat
		var reportID sql.NullInt64
		if err := rows.Scan(&c.ID, &c.Title, &reportID, &c.CreatedAt, &c.UpdatedAt); err != nil {
			return nil, err
		}
		if reportID.Valid {
			c.ReportID = &reportID.Int64
		}
		chats = append(chats, c)
	}
	return chats, rows.Err()
}

func (a *AppDB) UpdateChatTitle(id int64, title string) error {
	_, err := a.db.Exec(`
		UPDATE chats SET title = ?, updated_at = ? WHERE id = ?
	`, title, time.Now(), id)
	return err
}

func (a *AppDB) DeleteChat(id int64) error {
	_, err := a.db.Exec("DELETE FROM chats WHERE id = ?", id)
	return err
}

// === Messages ===

type Message struct {
	ID        int64     `json:"id"`
	ChatID    int64     `json:"chatId"`
	Role      string    `json:"role"`
	Content   string    `json:"content"`
	CreatedAt time.Time `json:"createdAt"`
}

func (a *AppDB) AddMessage(chatID int64, role, content string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)
	`, chatID, role, content, time.Now())
	if err != nil {
		return 0, err
	}

	// Update chat's updated_at
	a.db.Exec("UPDATE chats SET updated_at = ? WHERE id = ?", time.Now(), chatID)

	return result.LastInsertId()
}

func (a *AppDB) GetMessages(chatID int64) ([]Message, error) {
	rows, err := a.db.Query(`
		SELECT id, chat_id, role, content, created_at
		FROM messages WHERE chat_id = ? ORDER BY created_at ASC
	`, chatID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var messages []Message
	for rows.Next() {
		var m Message
		if err := rows.Scan(&m.ID, &m.ChatID, &m.Role, &m.Content, &m.CreatedAt); err != nil {
			return nil, err
		}
		messages = append(messages, m)
	}
	return messages, rows.Err()
}

// === Selections ===

type Selection struct {
	ID            int64     `json:"id"`
	Name          string    `json:"name"`
	OutputType    string    `json:"outputType"`
	FiltersJSON   string    `json:"filtersJson"`
	ResultCount   int       `json:"resultCount"`
	ResultIDsJSON string    `json:"resultIdsJson"`
	CreatedBy     string    `json:"createdBy"`
	MessageID     *int64    `json:"messageId,omitempty"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (a *AppDB) CreateSelection(name, outputType, filtersJSON, createdBy string, messageID *int64) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO selections (name, output_type, filters_json, created_by, message_id, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, name, outputType, filtersJSON, createdBy, messageID, time.Now(), time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetSelection(id int64) (*Selection, error) {
	var s Selection
	var messageID sql.NullInt64
	err := a.db.QueryRow(`
		SELECT id, name, output_type, filters_json, result_count, result_ids_json, created_by, message_id, created_at, updated_at
		FROM selections WHERE id = ?
	`, id).Scan(&s.ID, &s.Name, &s.OutputType, &s.FiltersJSON, &s.ResultCount, &s.ResultIDsJSON, &s.CreatedBy, &messageID, &s.CreatedAt, &s.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if messageID.Valid {
		s.MessageID = &messageID.Int64
	}
	return &s, nil
}

func (a *AppDB) GetSelectionsByMessage(messageID int64) ([]Selection, error) {
	rows, err := a.db.Query(`
		SELECT id, name, output_type, filters_json, result_count, result_ids_json, created_by, message_id, created_at, updated_at
		FROM selections WHERE message_id = ? ORDER BY created_at ASC
	`, messageID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var selections []Selection
	for rows.Next() {
		var s Selection
		var msgID sql.NullInt64
		if err := rows.Scan(&s.ID, &s.Name, &s.OutputType, &s.FiltersJSON, &s.ResultCount, &s.ResultIDsJSON, &s.CreatedBy, &msgID, &s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, err
		}
		if msgID.Valid {
			s.MessageID = &msgID.Int64
		}
		selections = append(selections, s)
	}
	return selections, rows.Err()
}

func (a *AppDB) GetAllSelections() ([]Selection, error) {
	rows, err := a.db.Query(`
		SELECT id, name, output_type, filters_json, result_count, result_ids_json, created_by, message_id, created_at, updated_at
		FROM selections ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var selections []Selection
	for rows.Next() {
		var s Selection
		var msgID sql.NullInt64
		if err := rows.Scan(&s.ID, &s.Name, &s.OutputType, &s.FiltersJSON, &s.ResultCount, &s.ResultIDsJSON, &s.CreatedBy, &msgID, &s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, err
		}
		if msgID.Valid {
			s.MessageID = &msgID.Int64
		}
		selections = append(selections, s)
	}
	return selections, rows.Err()
}

func (a *AppDB) UpdateSelectionResults(id int64, resultCount int, resultIDsJSON string) error {
	_, err := a.db.Exec(`
		UPDATE selections SET result_count = ?, result_ids_json = ?, updated_at = ? WHERE id = ?
	`, resultCount, resultIDsJSON, time.Now(), id)
	return err
}

func (a *AppDB) DeleteSelection(id int64) error {
	_, err := a.db.Exec("DELETE FROM selections WHERE id = ?", id)
	return err
}

// === Report Blocks ===

type ReportBlock struct {
	ID          int64     `json:"id"`
	ReportID    int64     `json:"reportId"`
	BlockType   string    `json:"blockType"`
	Position    int       `json:"position"`
	Content     string    `json:"content,omitempty"`
	SelectionID *int64    `json:"selectionId,omitempty"`
	ViewType    string    `json:"viewType"`
	CreatedAt   time.Time `json:"createdAt"`
}

func (a *AppDB) AddReportBlock(reportID int64, blockType string, position int, content string, selectionID *int64, viewType string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO report_blocks (report_id, block_type, position, content, selection_id, view_type, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, reportID, blockType, position, content, selectionID, viewType, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetReportBlocks(reportID int64) ([]ReportBlock, error) {
	rows, err := a.db.Query(`
		SELECT id, report_id, block_type, position, COALESCE(content, ''), selection_id, COALESCE(view_type, 'list'), created_at
		FROM report_blocks WHERE report_id = ? ORDER BY position ASC
	`, reportID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var blocks []ReportBlock
	for rows.Next() {
		var b ReportBlock
		var selID sql.NullInt64
		if err := rows.Scan(&b.ID, &b.ReportID, &b.BlockType, &b.Position, &b.Content, &selID, &b.ViewType, &b.CreatedAt); err != nil {
			return nil, err
		}
		if selID.Valid {
			b.SelectionID = &selID.Int64
		}
		blocks = append(blocks, b)
	}
	return blocks, rows.Err()
}

func (a *AppDB) UpdateReportBlockPosition(id int64, position int) error {
	_, err := a.db.Exec("UPDATE report_blocks SET position = ? WHERE id = ?", position, id)
	return err
}

func (a *AppDB) DeleteReportBlock(id int64) error {
	_, err := a.db.Exec("DELETE FROM report_blocks WHERE id = ?", id)
	return err
}

// === Enhanced Reports ===

func (a *AppDB) CreateReport(name, reportType string) (int64, error) {
	result, err := a.db.Exec(`
		INSERT INTO reports (name, report_type, data_json, created_at) VALUES (?, ?, '{}', ?)
	`, name, reportType, time.Now())
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func (a *AppDB) GetReport(id int64) (*Report, error) {
	var r Report
	err := a.db.QueryRow(`
		SELECT id, name, report_type, data_json, created_at FROM reports WHERE id = ?
	`, id).Scan(&r.ID, &r.Name, &r.ReportType, &r.DataJSON, &r.CreatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

func (a *AppDB) GetAllReports() ([]Report, error) {
	rows, err := a.db.Query(`
		SELECT id, name, report_type, data_json, created_at FROM reports ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var reports []Report
	for rows.Next() {
		var r Report
		if err := rows.Scan(&r.ID, &r.Name, &r.ReportType, &r.DataJSON, &r.CreatedAt); err != nil {
			return nil, err
		}
		reports = append(reports, r)
	}
	return reports, rows.Err()
}

func (a *AppDB) DeleteReport(id int64) error {
	_, err := a.db.Exec("DELETE FROM reports WHERE id = ?", id)
	return err
}
