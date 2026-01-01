package server

import (
	"io"
	"net/http"
	"strings"

	"school-local-backend/storage"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

func NewRouter(staticFS http.FileSystem, store *storage.Storage) http.Handler {
	r := chi.NewRouter()

	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// Handler mit Storage erstellen
	h := NewHandlers(store)

	// API endpoints
	r.Route("/api", func(r chi.Router) {
		r.Get("/hello", h.HelloHandler)
		r.Post("/ping", h.PingHandler)
		r.Options("/ping", h.PingHandler)
		r.Post("/sync", h.SyncHandler)
		r.Options("/sync", h.SyncHandler)
		r.Get("/stats", h.StatsHandler)
		r.Options("/stats", h.StatsHandler)
		r.Get("/data/latest", h.GetLatestHandler)
		r.Options("/data/latest", h.GetLatestHandler)

		// Logging endpoints
		r.Get("/logs", h.GetLogsHandler)
		r.Options("/logs", h.GetLogsHandler)
		r.Post("/logs", h.PostLogHandler)
		r.Delete("/logs", h.ClearLogsHandler)
		r.Options("/logs", h.ClearLogsHandler)

		// Fetches endpoints
		r.Get("/fetches", h.GetFetchesHandler)
		r.Options("/fetches", h.GetFetchesHandler)

		// Posts endpoints - extrahierte Posts aus Fetches
		r.Get("/posts", h.GetPostsHandler)
		r.Options("/posts", h.GetPostsHandler)

		// Fetch Queue endpoints - für die Browser Extension
		r.Get("/fetch-queue", h.GetFetchQueueHandler)
		r.Post("/fetch-queue", h.GetFetchQueueHandler)
		r.Options("/fetch-queue", h.GetFetchQueueHandler)
		r.Get("/fetch-queue/next", h.GetNextFetchHandler)
		r.Options("/fetch-queue/next", h.GetNextFetchHandler)

		// Settings endpoints
		r.Get("/settings", h.GetSettingsHandler)
		r.Options("/settings", h.GetSettingsHandler)
		r.Get("/setting", h.GetSettingHandler)
		r.Options("/setting", h.GetSettingHandler)
		r.Post("/settings", h.SetSettingHandler)
		r.Options("/settings", h.SetSettingHandler)

		// Chat endpoints
		r.Get("/chats", h.GetChatsHandler)
		r.Options("/chats", h.GetChatsHandler)
		r.Post("/chats", h.CreateChatHandler)
		r.Get("/chat", h.GetChatHandler)
		r.Options("/chat", h.GetChatHandler)
		r.Put("/chat", h.UpdateChatHandler)
		r.Delete("/chat", h.DeleteChatHandler)
		r.Options("/chat", h.DeleteChatHandler)
		r.Post("/chat/archive", h.ArchiveChatHandler)
		r.Options("/chat/archive", h.ArchiveChatHandler)

		// Chat Report endpoints (lazy report creation + AI condensation)
		r.Post("/chat/add-to-report", h.AddSelectionToReportHandler)
		r.Options("/chat/add-to-report", h.AddSelectionToReportHandler)
		r.Get("/chat/report", h.GetChatReportHandler)
		r.Options("/chat/report", h.GetChatReportHandler)

		// Message endpoints
		r.Get("/messages", h.GetMessagesHandler)
		r.Options("/messages", h.GetMessagesHandler)
		r.Post("/messages", h.SendMessageHandler)
		r.Options("/messages", h.SendMessageHandler)

		// Selection endpoints
		r.Get("/selections", h.GetSelectionsHandler)
		r.Options("/selections", h.GetSelectionsHandler)
		r.Post("/selections", h.CreateSelectionHandler)
		r.Get("/selection", h.GetSelectionHandler)
		r.Options("/selection", h.GetSelectionHandler)
		r.Put("/selection", h.UpdateSelectionHandler)
		r.Options("/selection", h.UpdateSelectionHandler)
		r.Delete("/selection", h.DeleteSelectionHandler)
		r.Get("/selection/execute", h.ExecuteSelectionHandler)
		r.Options("/selection/execute", h.ExecuteSelectionHandler)
		r.Post("/selection/duplicate", h.DuplicateSelectionHandler)
		r.Options("/selection/duplicate", h.DuplicateSelectionHandler)

		// Report endpoints (enhanced)
		r.Get("/reports", h.GetReportsHandler)
		r.Options("/reports", h.GetReportsHandler)
		r.Post("/reports", h.CreateReportHandler)
		r.Get("/report", h.GetReportHandler)
		r.Options("/report", h.GetReportHandler)
		r.Delete("/report", h.DeleteReportHandler)
		r.Options("/report", h.DeleteReportHandler)

		// Report block endpoints
		r.Post("/report-blocks", h.AddReportBlockHandler)
		r.Options("/report-blocks", h.AddReportBlockHandler)
		r.Delete("/report-block", h.DeleteReportBlockHandler)
		r.Options("/report-block", h.DeleteReportBlockHandler)

		// Data View endpoints - Schema und Tabellen-Inspektion
		r.Get("/schema", h.GetSchemaHandler)
		r.Options("/schema", h.GetSchemaHandler)
		r.Get("/table-data", h.GetTableDataHandler)
		r.Options("/table-data", h.GetTableDataHandler)

		// Activity & Connection endpoints - fuer Visualisierungen
		r.Get("/activity", h.GetActivityHandler)
		r.Options("/activity", h.GetActivityHandler)
		r.Get("/connections", h.GetConnectionsHandler)
		r.Options("/connections", h.GetConnectionsHandler)

		// Prompt Template endpoints
		r.Get("/prompt-templates", h.GetPromptTemplatesHandler)
		r.Options("/prompt-templates", h.GetPromptTemplatesHandler)
		r.Post("/prompt-templates", h.CreatePromptTemplateHandler)
		r.Get("/prompt-template", h.GetPromptTemplateHandler)
		r.Options("/prompt-template", h.GetPromptTemplateHandler)
		r.Put("/prompt-template", h.UpdatePromptTemplateHandler)
		r.Options("/prompt-template", h.UpdatePromptTemplateHandler)
		r.Delete("/prompt-template", h.DeletePromptTemplateHandler)
	})

	// Static files (Frontend) - SPA handler
	r.Get("/*", spaHandler(staticFS))

	return r
}

// spaHandler serves static files and falls back to index.html for SPA routing
func spaHandler(staticFS http.FileSystem) http.HandlerFunc {
	fileServer := http.FileServer(staticFS)

	return func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Try to open the file
		f, err := staticFS.Open(path)
		if err != nil {
			// File not found -> serve index.html (for SPA client-side routing)
			serveIndex(w, r, staticFS)
			return
		}
		defer f.Close()

		// Check if it's a directory
		stat, err := f.Stat()
		if err != nil {
			serveIndex(w, r, staticFS)
			return
		}

		// If directory, try to serve index.html from that directory
		if stat.IsDir() {
			indexPath := strings.TrimSuffix(path, "/") + "/index.html"
			if _, err := staticFS.Open(indexPath); err != nil {
				serveIndex(w, r, staticFS)
				return
			}
		}

		// Serve the file
		fileServer.ServeHTTP(w, r)
	}
}

func serveIndex(w http.ResponseWriter, r *http.Request, staticFS http.FileSystem) {
	indexFile, err := staticFS.Open("/index.html")
	if err != nil {
		http.Error(w, "index.html not found", http.StatusNotFound)
		return
	}
	defer indexFile.Close()

	stat, err := indexFile.Stat()
	if err != nil {
		http.Error(w, "Could not read index.html", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	http.ServeContent(w, r, "index.html", stat.ModTime(), indexFile.(io.ReadSeeker))
}
