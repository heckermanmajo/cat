package server

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"school-local-backend/db/duckdb"
	"school-local-backend/db/sqlite"
	"school-local-backend/fetchqueue"
	"school-local-backend/storage"
)

// Handlers contains all HTTP handlers with storage access
type Handlers struct {
	storage *storage.Storage
}

func NewHandlers(s *storage.Storage) *Handlers {
	return &Handlers{storage: s}
}

// === Response/Request Types ===

type HelloResponse struct {
	Message string `json:"message"`
}

type PingRequest struct {
	Action    string `json:"action"`
	Timestamp string `json:"timestamp"`
}

type PingResponse struct {
	Message  string `json:"message"`
	Received string `json:"received"`
	Server   string `json:"server"`
}

type SyncRequest struct {
	Action     string          `json:"action"`
	Timestamp  string          `json:"timestamp"`
	EntityType string          `json:"entityType"`
	Source     string          `json:"source"`
	Data       json.RawMessage `json:"data"`
}

type SyncResponse struct {
	Message string `json:"message"`
	Status  string `json:"status"`
	Count   int    `json:"count,omitempty"`
}

type StatsResponse struct {
	RawFetchCount   int64            `json:"rawFetchCount"`
	FetchesByType   map[string]int64 `json:"fetchesByType"`
	RecentSyncCount int              `json:"recentSyncCount"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

type LogRequest struct {
	Level   string `json:"level"`
	Source  string `json:"source"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

type LogsResponse struct {
	Logs    []LogEntry `json:"logs"`
	Total   int64      `json:"total"`
	Sources []string   `json:"sources"`
}

type LogEntry struct {
	ID        int64  `json:"id"`
	Level     string `json:"level"`
	Source    string `json:"source"`
	Message   string `json:"message"`
	Details   string `json:"details,omitempty"`
	CreatedAt string `json:"createdAt"`
}

// === Handlers ===

func (h *Handlers) HelloHandler(w http.ResponseWriter, r *http.Request) {
	resp := HelloResponse{
		Message: "Hello from CatKnows local backend!",
	}
	writeJSON(w, resp)
}

func (h *Handlers) PingHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req PingRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	log.Printf("PING received: action=%s, timestamp=%s", req.Action, req.Timestamp)

	resp := PingResponse{
		Message:  "Pong! Server is running.",
		Received: req.Timestamp,
		Server:   time.Now().Format(time.RFC3339),
	}
	writeJSON(w, resp)
}

func (h *Handlers) SyncHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req SyncRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	log.Printf("SYNC received: action=%s, entityType=%s", req.Action, req.EntityType)

	// Daten verarbeiten und in DuckDB speichern
	count := 0
	if req.Data != nil && len(req.Data) > 0 {
		// Prüfen ob es ein Array oder ein einzelnes Objekt ist
		var items []json.RawMessage
		if err := json.Unmarshal(req.Data, &items); err != nil {
			// Einzelnes Objekt
			items = []json.RawMessage{req.Data}
		}

		// Bulk-Insert vorbereiten
		fetchItems := make([]duckdb.FetchItem, 0, len(items))
		for i, item := range items {
			// EntityID aus dem JSON extrahieren (falls vorhanden)
			var obj map[string]interface{}
			if err := json.Unmarshal(item, &obj); err == nil {
				entityID := ""
				if id, ok := obj["id"]; ok {
					switch v := id.(type) {
					case string:
						entityID = v
					case float64:
						entityID = json.Number(string(rune(int(v)))).String()
					}
				}
				if entityID == "" {
					entityID = string(rune(i))
				}
				fetchItems = append(fetchItems, duckdb.FetchItem{
					EntityID: entityID,
					RawJSON:  string(item),
				})
			}
		}

		source := req.Source
		if source == "" {
			source = "skool"
		}

		if len(fetchItems) > 0 {
			if err := h.storage.Raw.StoreBulkFetch(req.EntityType, source, fetchItems); err != nil {
				log.Printf("Error storing fetch data: %v", err)
				h.storage.App.LogSync(req.EntityType, 0, "error", err.Error())
				writeError(w, "Failed to store data", http.StatusInternalServerError)
				return
			}
			count = len(fetchItems)
		}
	}

	// Sync protokollieren
	h.storage.App.LogSync(req.EntityType, count, "success", "")

	resp := SyncResponse{
		Message: "Sync completed successfully",
		Status:  "ok",
		Count:   count,
	}
	writeJSON(w, resp)
}

func (h *Handlers) StatsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	stats, err := h.storage.GetStats()
	if err != nil {
		log.Printf("Error getting stats: %v", err)
		writeError(w, "Failed to get stats", http.StatusInternalServerError)
		return
	}

	resp := StatsResponse{
		RawFetchCount:   stats.RawFetchCount,
		FetchesByType:   stats.FetchesByType,
		RecentSyncCount: stats.RecentSyncCount,
	}
	writeJSON(w, resp)
}

// GetLatestHandler holt die neuesten Daten für einen Entity-Typ
func (h *Handlers) GetLatestHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	entityType := r.URL.Query().Get("type")
	if entityType == "" {
		writeError(w, "Missing 'type' parameter", http.StatusBadRequest)
		return
	}

	fetches, err := h.storage.Raw.GetAllLatestByType(entityType)
	if err != nil {
		log.Printf("Error getting latest fetches: %v", err)
		writeError(w, "Failed to get data", http.StatusInternalServerError)
		return
	}

	// Rohdaten als JSON-Array zurückgeben
	var results []json.RawMessage
	for _, f := range fetches {
		results = append(results, json.RawMessage(f.RawJSON))
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

// === Helper Functions ===

func setCORSHeaders(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(ErrorResponse{Error: message})
}

// === Logging Handlers ===

func (h *Handlers) GetLogsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Filter-Parameter aus Query
	filter := sqlite.LogFilter{
		Level:  r.URL.Query().Get("level"),
		Source: r.URL.Query().Get("source"),
	}

	if limit := r.URL.Query().Get("limit"); limit != "" {
		if l, err := strconv.Atoi(limit); err == nil {
			filter.Limit = l
		}
	}
	if offset := r.URL.Query().Get("offset"); offset != "" {
		if o, err := strconv.Atoi(offset); err == nil {
			filter.Offset = o
		}
	}

	logs, err := h.storage.App.GetLogs(filter)
	if err != nil {
		log.Printf("Error getting logs: %v", err)
		writeError(w, "Failed to get logs", http.StatusInternalServerError)
		return
	}

	total, _ := h.storage.App.GetLogCount()
	sources, _ := h.storage.App.GetLogSources()

	// Konvertiere zu Response-Format
	entries := make([]LogEntry, len(logs))
	for i, l := range logs {
		entries[i] = LogEntry{
			ID:        l.ID,
			Level:     l.Level,
			Source:    l.Source,
			Message:   l.Message,
			Details:   l.Details,
			CreatedAt: l.CreatedAt.Format(time.RFC3339),
		}
	}

	resp := LogsResponse{
		Logs:    entries,
		Total:   total,
		Sources: sources,
	}
	writeJSON(w, resp)
}

func (h *Handlers) PostLogHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req LogRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Level validieren
	level := sqlite.LogLevelInfo
	switch req.Level {
	case "debug":
		level = sqlite.LogLevelDebug
	case "info":
		level = sqlite.LogLevelInfo
	case "warn":
		level = sqlite.LogLevelWarn
	case "error":
		level = sqlite.LogLevelError
	}

	id, err := h.storage.App.WriteLog(level, req.Source, req.Message, req.Details)
	if err != nil {
		log.Printf("Error writing log: %v", err)
		writeError(w, "Failed to write log", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]interface{}{
		"status": "ok",
		"id":     id,
	})
}

func (h *Handlers) ClearLogsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	if err := h.storage.App.ClearLogs(); err != nil {
		log.Printf("Error clearing logs: %v", err)
		writeError(w, "Failed to clear logs", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]string{"status": "ok"})
}

// === Settings Handlers ===

type SettingsResponse struct {
	Settings map[string]string `json:"settings"`
}

type SetSettingRequest struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

func (h *Handlers) GetSettingsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	settings, err := h.storage.App.GetAllSettings()
	if err != nil {
		log.Printf("Error getting settings: %v", err)
		writeError(w, "Failed to get settings", http.StatusInternalServerError)
		return
	}

	// API-Keys maskieren für die Ausgabe
	maskedSettings := make(map[string]string)
	for k, v := range settings {
		if strings.Contains(k, "api_key") && len(v) > 8 {
			maskedSettings[k] = v[:4] + "..." + v[len(v)-4:]
		} else {
			maskedSettings[k] = v
		}
	}

	writeJSON(w, SettingsResponse{Settings: maskedSettings})
}

func (h *Handlers) GetSettingHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	key := r.URL.Query().Get("key")
	if key == "" {
		writeError(w, "Missing 'key' parameter", http.StatusBadRequest)
		return
	}

	value, err := h.storage.App.GetSetting(key)
	if err != nil {
		log.Printf("Error getting setting: %v", err)
		writeError(w, "Failed to get setting", http.StatusInternalServerError)
		return
	}

	// API-Keys maskieren
	if strings.Contains(key, "api_key") && len(value) > 8 {
		value = value[:4] + "..." + value[len(value)-4:]
	}

	writeJSON(w, map[string]string{"key": key, "value": value})
}

func (h *Handlers) SetSettingHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req SetSettingRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if req.Key == "" {
		writeError(w, "Key is required", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.SetSetting(req.Key, req.Value); err != nil {
		log.Printf("Error setting setting: %v", err)
		writeError(w, "Failed to save setting", http.StatusInternalServerError)
		return
	}

	log.Printf("Setting saved: %s", req.Key)
	writeJSON(w, map[string]string{"status": "ok", "key": req.Key})
}

// HasOpenAIKey prüft ob ein OpenAI API-Key konfiguriert ist
func (h *Handlers) HasOpenAIKey() bool {
	key, _ := h.storage.App.GetSetting("openai_api_key")
	return key != ""
}

// GetOpenAIKey gibt den OpenAI API-Key zurück (für interne Verwendung)
func (h *Handlers) GetOpenAIKey() string {
	key, _ := h.storage.App.GetSetting("openai_api_key")
	return key
}

// === Fetches Handlers ===

type FetchEntry struct {
	EntityType string `json:"entityType"`
	EntityID   string `json:"entityId"`
	RawJSON    string `json:"rawJson"`
	Source     string `json:"source"`
	FetchedAt  string `json:"fetchedAt"`
}

type FetchesResponse struct {
	Fetches     []FetchEntry `json:"fetches"`
	Total       int64        `json:"total"`
	EntityTypes []string     `json:"entityTypes"`
	Sources     []string     `json:"sources"`
}

func (h *Handlers) GetFetchesHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Filter-Parameter aus Query
	filter := duckdb.FetchFilter{
		EntityType: r.URL.Query().Get("entityType"),
		Source:     r.URL.Query().Get("source"),
	}

	if limit := r.URL.Query().Get("limit"); limit != "" {
		if l, err := strconv.Atoi(limit); err == nil {
			filter.Limit = l
		}
	}
	if offset := r.URL.Query().Get("offset"); offset != "" {
		if o, err := strconv.Atoi(offset); err == nil {
			filter.Offset = o
		}
	}

	// Default limit
	if filter.Limit == 0 {
		filter.Limit = 50
	}

	fetches, total, err := h.storage.Raw.GetAllFetches(filter)
	if err != nil {
		log.Printf("Error getting fetches: %v", err)
		writeError(w, "Failed to get fetches", http.StatusInternalServerError)
		return
	}

	entityTypes, _ := h.storage.Raw.GetEntityTypes()
	sources, _ := h.storage.Raw.GetSources()

	// Konvertiere zu Response-Format
	entries := make([]FetchEntry, len(fetches))
	for i, f := range fetches {
		entries[i] = FetchEntry{
			EntityType: f.EntityType,
			EntityID:   f.EntityID,
			RawJSON:    f.RawJSON,
			Source:     f.Source,
			FetchedAt:  f.FetchedAt.Format(time.RFC3339),
		}
	}

	resp := FetchesResponse{
		Fetches:     entries,
		Total:       total,
		EntityTypes: entityTypes,
		Sources:     sources,
	}
	writeJSON(w, resp)
}

// === Fetch Queue Handlers ===

type FetchQueueRequest struct {
	CommunityIDs []string `json:"communityIds"`
}

// GetFetchQueueHandler generiert die aktuelle Fetch-Queue
// Die Queue wird bei jedem Aufruf neu berechnet basierend auf dem Datenstand
func (h *Handlers) GetFetchQueueHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Community IDs aus Query oder Body
	var communityIDs []string

	if r.Method == "POST" {
		var req FetchQueueRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
			communityIDs = req.CommunityIDs
		}
	} else {
		// GET: Community IDs aus Query Parameter (komma-separiert)
		if ids := r.URL.Query().Get("communityIds"); ids != "" {
			communityIDs = strings.Split(ids, ",")
		}
	}

	if len(communityIDs) == 0 {
		writeError(w, "communityIds required", http.StatusBadRequest)
		return
	}

	// Queue Builder erstellen und Queue generieren
	config := fetchqueue.DefaultConfig()
	builder := fetchqueue.NewQueueBuilder(h.storage.Raw, config)

	queue, err := builder.BuildQueue(communityIDs)
	if err != nil {
		log.Printf("Error building fetch queue: %v", err)
		writeError(w, "Failed to build fetch queue", http.StatusInternalServerError)
		return
	}

	writeJSON(w, queue)
}

// === Data View Handlers ===

// TableInfo enthält Informationen über eine Tabelle
type TableInfo struct {
	Name    string        `json:"name"`
	Type    string        `json:"type"`
	Columns []ColumnInfo  `json:"columns"`
	RowCount int64        `json:"rowCount"`
}

type ColumnInfo struct {
	Name     string `json:"name"`
	Type     string `json:"type"`
	Nullable bool   `json:"nullable"`
}

type SchemaResponse struct {
	DuckDB  []TableInfo `json:"duckdb"`
	SQLite  []TableInfo `json:"sqlite"`
}

type TableDataResponse struct {
	Columns []string        `json:"columns"`
	Rows    [][]interface{} `json:"rows"`
	Total   int64           `json:"total"`
}

// GetSchemaHandler gibt alle Tabellen-Schemas zurück
func (h *Handlers) GetSchemaHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	resp := SchemaResponse{
		DuckDB: []TableInfo{
			{
				Name: "raw_fetches",
				Type: "duckdb",
				Columns: []ColumnInfo{
					{Name: "entity_type", Type: "TEXT", Nullable: false},
					{Name: "entity_id", Type: "TEXT", Nullable: false},
					{Name: "raw_json", Type: "TEXT", Nullable: false},
					{Name: "source", Type: "TEXT", Nullable: true},
					{Name: "fetched_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
		},
		SQLite: []TableInfo{
			{
				Name: "settings",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "key", Type: "TEXT", Nullable: false},
					{Name: "value", Type: "TEXT", Nullable: false},
					{Name: "updated_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "ui_state",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "key", Type: "TEXT", Nullable: false},
					{Name: "value", Type: "TEXT", Nullable: false},
					{Name: "updated_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "saved_queries",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "name", Type: "TEXT", Nullable: false},
					{Name: "query_type", Type: "TEXT", Nullable: false},
					{Name: "query_json", Type: "TEXT", Nullable: false},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "license",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "license_key", Type: "TEXT", Nullable: true},
					{Name: "status", Type: "TEXT", Nullable: true},
					{Name: "expires_at", Type: "TIMESTAMP", Nullable: true},
					{Name: "checked_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "reports",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "name", Type: "TEXT", Nullable: false},
					{Name: "report_type", Type: "TEXT", Nullable: false},
					{Name: "data_json", Type: "TEXT", Nullable: false},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "sync_log",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "sync_type", Type: "TEXT", Nullable: false},
					{Name: "entity_count", Type: "INTEGER", Nullable: true},
					{Name: "status", Type: "TEXT", Nullable: false},
					{Name: "error_message", Type: "TEXT", Nullable: true},
					{Name: "synced_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "logs",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "level", Type: "TEXT", Nullable: false},
					{Name: "source", Type: "TEXT", Nullable: false},
					{Name: "message", Type: "TEXT", Nullable: false},
					{Name: "details", Type: "TEXT", Nullable: true},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "chats",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "title", Type: "TEXT", Nullable: false},
					{Name: "report_id", Type: "INTEGER", Nullable: true},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
					{Name: "updated_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "messages",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "chat_id", Type: "INTEGER", Nullable: false},
					{Name: "role", Type: "TEXT", Nullable: false},
					{Name: "content", Type: "TEXT", Nullable: false},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "selections",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "name", Type: "TEXT", Nullable: false},
					{Name: "output_type", Type: "TEXT", Nullable: false},
					{Name: "filters_json", Type: "TEXT", Nullable: false},
					{Name: "result_count", Type: "INTEGER", Nullable: true},
					{Name: "result_ids_json", Type: "TEXT", Nullable: true},
					{Name: "created_by", Type: "TEXT", Nullable: false},
					{Name: "message_id", Type: "INTEGER", Nullable: true},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
					{Name: "updated_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
			{
				Name: "report_blocks",
				Type: "sqlite",
				Columns: []ColumnInfo{
					{Name: "id", Type: "INTEGER", Nullable: false},
					{Name: "report_id", Type: "INTEGER", Nullable: false},
					{Name: "block_type", Type: "TEXT", Nullable: false},
					{Name: "position", Type: "INTEGER", Nullable: false},
					{Name: "content", Type: "TEXT", Nullable: true},
					{Name: "selection_id", Type: "INTEGER", Nullable: true},
					{Name: "view_type", Type: "TEXT", Nullable: true},
					{Name: "created_at", Type: "TIMESTAMP", Nullable: true},
				},
			},
		},
	}

	// Get row counts for each table
	if count, err := h.storage.Raw.GetFetchCount(); err == nil {
		resp.DuckDB[0].RowCount = count
	}

	writeJSON(w, resp)
}

// GetTableDataHandler gibt die Daten einer Tabelle zurück
func (h *Handlers) GetTableDataHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	tableName := r.URL.Query().Get("table")
	dbType := r.URL.Query().Get("db") // "duckdb" oder "sqlite"

	if tableName == "" || dbType == "" {
		writeError(w, "table and db parameters required", http.StatusBadRequest)
		return
	}

	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 1000 {
			limit = parsed
		}
	}

	offset := 0
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	var resp TableDataResponse

	if dbType == "duckdb" {
		// DuckDB Tabellen-Abfrage
		if tableName == "raw_fetches" {
			fetches, total, err := h.storage.Raw.GetAllFetches(duckdb.FetchFilter{
				Limit:  limit,
				Offset: offset,
			})
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}

			resp.Columns = []string{"entity_type", "entity_id", "raw_json", "source", "fetched_at"}
			resp.Total = total
			resp.Rows = make([][]interface{}, len(fetches))
			for i, f := range fetches {
				resp.Rows[i] = []interface{}{f.EntityType, f.EntityID, f.RawJSON, f.Source, f.FetchedAt.Format(time.RFC3339)}
			}
		} else {
			writeError(w, "Unknown DuckDB table", http.StatusBadRequest)
			return
		}
	} else if dbType == "sqlite" {
		// SQLite Tabellen-Abfrage - wir nutzen die bestehenden Methoden
		switch tableName {
		case "settings":
			settings, err := h.storage.App.GetAllSettings()
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"key", "value"}
			resp.Total = int64(len(settings))
			resp.Rows = make([][]interface{}, 0, len(settings))
			for k, v := range settings {
				resp.Rows = append(resp.Rows, []interface{}{k, v})
			}

		case "logs":
			logs, err := h.storage.App.GetLogs(sqlite.LogFilter{Limit: limit, Offset: offset})
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			total, _ := h.storage.App.GetLogCount()
			resp.Columns = []string{"id", "level", "source", "message", "details", "created_at"}
			resp.Total = total
			resp.Rows = make([][]interface{}, len(logs))
			for i, l := range logs {
				resp.Rows[i] = []interface{}{l.ID, l.Level, l.Source, l.Message, l.Details, l.CreatedAt.Format(time.RFC3339)}
			}

		case "sync_log":
			syncs, err := h.storage.App.GetRecentSyncs(limit)
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"id", "sync_type", "entity_count", "status", "error_message", "synced_at"}
			resp.Total = int64(len(syncs))
			resp.Rows = make([][]interface{}, len(syncs))
			for i, s := range syncs {
				resp.Rows[i] = []interface{}{s.ID, s.SyncType, s.EntityCount, s.Status, s.ErrorMessage, s.SyncedAt.Format(time.RFC3339)}
			}

		case "chats":
			chats, err := h.storage.App.GetAllChats()
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"id", "title", "report_id", "created_at", "updated_at"}
			resp.Total = int64(len(chats))
			resp.Rows = make([][]interface{}, len(chats))
			for i, c := range chats {
				reportID := interface{}(nil)
				if c.ReportID != nil {
					reportID = *c.ReportID
				}
				resp.Rows[i] = []interface{}{c.ID, c.Title, reportID, c.CreatedAt.Format(time.RFC3339), c.UpdatedAt.Format(time.RFC3339)}
			}

		case "reports":
			reports, err := h.storage.App.GetAllReports()
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"id", "name", "report_type", "data_json", "created_at"}
			resp.Total = int64(len(reports))
			resp.Rows = make([][]interface{}, len(reports))
			for i, r := range reports {
				resp.Rows[i] = []interface{}{r.ID, r.Name, r.ReportType, r.DataJSON, r.CreatedAt.Format(time.RFC3339)}
			}

		case "selections":
			selections, err := h.storage.App.GetAllSelections()
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"id", "name", "output_type", "filters_json", "result_count", "created_by", "created_at"}
			resp.Total = int64(len(selections))
			resp.Rows = make([][]interface{}, len(selections))
			for i, s := range selections {
				resp.Rows[i] = []interface{}{s.ID, s.Name, s.OutputType, s.FiltersJSON, s.ResultCount, s.CreatedBy, s.CreatedAt.Format(time.RFC3339)}
			}

		case "license":
			lic, err := h.storage.App.GetLicense()
			if err != nil {
				writeError(w, "Failed to get data: "+err.Error(), http.StatusInternalServerError)
				return
			}
			resp.Columns = []string{"id", "license_key", "status", "expires_at", "checked_at"}
			resp.Total = 0
			resp.Rows = [][]interface{}{}
			if lic != nil {
				resp.Total = 1
				expiresAt := interface{}(nil)
				if lic.ExpiresAt != nil {
					expiresAt = lic.ExpiresAt.Format(time.RFC3339)
				}
				resp.Rows = [][]interface{}{{1, lic.Key, lic.Status, expiresAt, lic.CheckedAt.Format(time.RFC3339)}}
			}

		default:
			writeError(w, "Table not supported for direct query. Available: settings, logs, sync_log, chats, reports, selections, license", http.StatusBadRequest)
			return
		}
	} else {
		writeError(w, "db must be 'duckdb' or 'sqlite'", http.StatusBadRequest)
		return
	}

	writeJSON(w, resp)
}

// GetNextFetchHandler gibt den nächsten Fetch-Task zurück
// Praktisch für die Extension um einen Task nach dem anderen abzuarbeiten
func (h *Handlers) GetNextFetchHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Community IDs aus Query
	var communityIDs []string
	if ids := r.URL.Query().Get("communityIds"); ids != "" {
		communityIDs = strings.Split(ids, ",")
	}

	if len(communityIDs) == 0 {
		writeError(w, "communityIds required", http.StatusBadRequest)
		return
	}

	// Queue bauen
	config := fetchqueue.DefaultConfig()
	builder := fetchqueue.NewQueueBuilder(h.storage.Raw, config)

	queue, err := builder.BuildQueue(communityIDs)
	if err != nil {
		log.Printf("Error building fetch queue: %v", err)
		writeError(w, "Failed to build fetch queue", http.StatusInternalServerError)
		return
	}

	// Ersten Task zurückgeben oder leere Response
	if len(queue.Tasks) > 0 {
		writeJSON(w, map[string]interface{}{
			"hasNext": true,
			"task":    queue.Tasks[0],
			"remaining": len(queue.Tasks) - 1,
		})
	} else {
		writeJSON(w, map[string]interface{}{
			"hasNext":   false,
			"task":      nil,
			"remaining": 0,
		})
	}
}
