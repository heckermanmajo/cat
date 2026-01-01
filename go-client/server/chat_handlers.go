package server

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"school-local-backend/ai"
	"school-local-backend/db/duckdb"
	"school-local-backend/db/sqlite"
)

// === Request/Response Types ===

type CreateChatRequest struct {
	Title string `json:"title"`
}

type ChatResponse struct {
	ID        int64     `json:"id"`
	Title     string    `json:"title"`
	ReportID  *int64    `json:"reportId,omitempty"`
	Archived  bool      `json:"archived"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type MessageResponse struct {
	ID         int64               `json:"id"`
	ChatID     int64               `json:"chatId"`
	Role       string              `json:"role"`
	Content    string              `json:"content"`
	CreatedAt  time.Time           `json:"createdAt"`
	Selections []SelectionResponse `json:"selections,omitempty"`
}

type SendMessageRequest struct {
	Content string `json:"content"`
}

type SelectionResponse struct {
	ID                int64               `json:"id"`
	Name              string              `json:"name"`
	OutputType        string              `json:"outputType"`
	FiltersJSON       string              `json:"filtersJson"`
	ResultCount       int                 `json:"resultCount"`
	ResultIDsJSON     string              `json:"resultIdsJson"`
	CreatedBy         string              `json:"createdBy"`
	MessageID         *int64              `json:"messageId,omitempty"`
	ParentID          *int64              `json:"parentId,omitempty"`
	CreatedAt         time.Time           `json:"createdAt"`
	UpdatedAt         time.Time           `json:"updatedAt"`
	DerivedSelections []SelectionResponse `json:"derivedSelections,omitempty"`
}

type CreateSelectionRequest struct {
	Name       string `json:"name"`
	OutputType string `json:"outputType"`
	Filters    any    `json:"filters"`
}

type CreateReportRequest struct {
	Name string `json:"name"`
}

type ReportResponse struct {
	ID        int64                 `json:"id"`
	Name      string                `json:"name"`
	CreatedAt time.Time             `json:"createdAt"`
	Blocks    []ReportBlockResponse `json:"blocks,omitempty"`
}

type ReportBlockResponse struct {
	ID          int64     `json:"id"`
	ReportID    int64     `json:"reportId"`
	BlockType   string    `json:"blockType"`
	Position    int       `json:"position"`
	Content     string    `json:"content,omitempty"`
	SelectionID *int64    `json:"selectionId,omitempty"`
	ViewType    string    `json:"viewType"`
	CreatedAt   time.Time `json:"createdAt"`
}

type AddReportBlockRequest struct {
	BlockType   string `json:"blockType"`
	Content     string `json:"content,omitempty"`
	SelectionID *int64 `json:"selectionId,omitempty"`
	ViewType    string `json:"viewType,omitempty"`
}

// === Chat Handlers ===

func (h *Handlers) GetChatsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	// Parse archived filter from query params
	var archivedFilter *bool
	archivedParam := r.URL.Query().Get("archived")
	if archivedParam != "" {
		archived := archivedParam == "true"
		archivedFilter = &archived
	}

	chats, err := h.storage.App.GetAllChats(archivedFilter)
	if err != nil {
		log.Printf("Error getting chats: %v", err)
		writeError(w, "Failed to get chats", http.StatusInternalServerError)
		return
	}

	if chats == nil {
		chats = []sqlite.Chat{}
	}
	writeJSON(w, chats)
}

func (h *Handlers) CreateChatHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req CreateChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		req.Title = "Neuer Chat"
	}

	id, err := h.storage.App.CreateChat(req.Title)
	if err != nil {
		log.Printf("Error creating chat: %v", err)
		writeError(w, "Failed to create chat", http.StatusInternalServerError)
		return
	}

	chat, _ := h.storage.App.GetChat(id)
	writeJSON(w, chat)
}

func (h *Handlers) GetChatHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	chat, err := h.storage.App.GetChat(id)
	if err != nil {
		log.Printf("Error getting chat: %v", err)
		writeError(w, "Failed to get chat", http.StatusInternalServerError)
		return
	}
	if chat == nil {
		writeError(w, "Chat not found", http.StatusNotFound)
		return
	}

	writeJSON(w, chat)
}

func (h *Handlers) DeleteChatHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.DeleteChat(id); err != nil {
		log.Printf("Error deleting chat: %v", err)
		writeError(w, "Failed to delete chat", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]string{"status": "ok"})
}

// UpdateChatRequest for renaming a chat
type UpdateChatRequest struct {
	Title string `json:"title"`
}

func (h *Handlers) UpdateChatHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	var req UpdateChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Title == "" {
		writeError(w, "Title is required", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.UpdateChatTitle(id, req.Title); err != nil {
		log.Printf("Error updating chat: %v", err)
		writeError(w, "Failed to update chat", http.StatusInternalServerError)
		return
	}

	chat, _ := h.storage.App.GetChat(id)
	writeJSON(w, chat)
}

func (h *Handlers) ArchiveChatHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	// Check current status to toggle
	chat, err := h.storage.App.GetChat(id)
	if err != nil || chat == nil {
		writeError(w, "Chat not found", http.StatusNotFound)
		return
	}

	if chat.Archived {
		// Unarchive
		if err := h.storage.App.UnarchiveChat(id); err != nil {
			log.Printf("Error unarchiving chat: %v", err)
			writeError(w, "Failed to unarchive chat", http.StatusInternalServerError)
			return
		}
	} else {
		// Archive
		if err := h.storage.App.ArchiveChat(id); err != nil {
			log.Printf("Error archiving chat: %v", err)
			writeError(w, "Failed to archive chat", http.StatusInternalServerError)
			return
		}
	}

	updatedChat, _ := h.storage.App.GetChat(id)
	writeJSON(w, updatedChat)
}

// === Message Handlers ===

func (h *Handlers) GetMessagesHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	chatIDStr := r.URL.Query().Get("chatId")
	chatID, err := strconv.ParseInt(chatIDStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	messages, err := h.storage.App.GetMessages(chatID)
	if err != nil {
		log.Printf("Error getting messages: %v", err)
		writeError(w, "Failed to get messages", http.StatusInternalServerError)
		return
	}

	// Enrich messages with their selections (including derived ones)
	var response []MessageResponse
	for _, m := range messages {
		mr := MessageResponse{
			ID:        m.ID,
			ChatID:    m.ChatID,
			Role:      m.Role,
			Content:   m.Content,
			CreatedAt: m.CreatedAt,
		}

		// Get selections for assistant messages (with derived selections)
		if m.Role == "assistant" {
			selections, _ := h.storage.App.GetSelectionsByMessage(m.ID)
			for _, s := range selections {
				mr.Selections = append(mr.Selections, h.selectionToResponseWithDerived(s))
			}
		}

		response = append(response, mr)
	}

	if response == nil {
		response = []MessageResponse{}
	}
	writeJSON(w, response)
}

func (h *Handlers) SendMessageHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	chatIDStr := r.URL.Query().Get("chatId")
	chatID, err := strconv.ParseInt(chatIDStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	var req SendMessageRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Content == "" {
		writeError(w, "Message content required", http.StatusBadRequest)
		return
	}

	// Load existing messages for context
	existingMessages, err := h.storage.App.GetMessages(chatID)
	if err != nil {
		log.Printf("Error loading messages: %v", err)
		existingMessages = []sqlite.Message{}
	}

	// Store user message
	userMsgID, err := h.storage.App.AddMessage(chatID, "user", req.Content)
	if err != nil {
		log.Printf("Error adding user message: %v", err)
		writeError(w, "Failed to add message", http.StatusInternalServerError)
		return
	}

	// Generate AI response with potential selection (include chat history)
	assistantContent, selection := h.generateAIResponse(req.Content, existingMessages)

	// Store assistant message
	assistantMsgID, err := h.storage.App.AddMessage(chatID, "assistant", assistantContent)
	if err != nil {
		log.Printf("Error adding assistant message: %v", err)
		writeError(w, "Failed to add assistant response", http.StatusInternalServerError)
		return
	}

	// Create selection if AI suggested one
	var createdSelections []SelectionResponse
	if selection != nil {
		filtersJSON, _ := json.Marshal(selection.Filters)
		selID, err := h.storage.App.CreateSelection(
			selection.Name,
			selection.OutputType,
			string(filtersJSON),
			"assistant",
			&assistantMsgID,
		)
		if err == nil {
			sel, _ := h.storage.App.GetSelection(selID)
			if sel != nil {
				createdSelections = append(createdSelections, selectionToResponse(*sel))
			}
		}
	}

	// Return both messages
	userMsg, _ := h.storage.App.GetMessages(chatID)
	var response []MessageResponse
	for _, m := range userMsg {
		if m.ID == userMsgID || m.ID == assistantMsgID {
			mr := MessageResponse{
				ID:        m.ID,
				ChatID:    m.ChatID,
				Role:      m.Role,
				Content:   m.Content,
				CreatedAt: m.CreatedAt,
			}
			if m.ID == assistantMsgID {
				mr.Selections = createdSelections
			}
			response = append(response, mr)
		}
	}

	writeJSON(w, response)
}

// AISelection represents a selection suggested by AI
type AISelection struct {
	Name       string         `json:"name"`
	OutputType string         `json:"outputType"`
	Filters    map[string]any `json:"filters"`
}

// generateAIResponse generates an AI response and potentially a selection
// It now includes the chat history for context
func (h *Handlers) generateAIResponse(userMessage string, chatHistory []sqlite.Message) (string, *AISelection) {
	apiKey := h.GetOpenAIKey()
	if apiKey == "" {
		return "Ich kann dir bei der Datenanalyse helfen. Bitte konfiguriere zuerst einen OpenAI API-Key in den Einstellungen.", nil
	}

	client := ai.NewClient(ai.Config{
		APIKey:  apiKey,
		Timeout: 60 * time.Second,
	})

	systemPrompt := `Du bist CatNose, ein Analyseassistent für Community-Daten von Skool.com.
Deine Aufgabe ist es, dem Nutzer bei der Exploration seiner Community-Daten zu helfen.

Wenn der Nutzer nach Daten fragt (z.B. "aktive Mitglieder", "beliebte Posts"), erstelle eine Selektion.
Eine Selektion ist eine strukturierte Datenabfrage.

WICHTIG: Antworte IMMER mit validem JSON ohne Kommentare! Keine // oder /* Kommentare verwenden!

Antworte IMMER im folgenden JSON-Format:
{
  "message": "Deine Erklärung für den Nutzer",
  "selection": null oder {
    "name": "Beschreibender Name",
    "outputType": "member" oder "post" oder "community",
    "filters": {
      "beispiel_filter": "wert"
    }
  }
}

Verfügbare Filter für 'member': community_ids, joined_after, joined_before, post_count_min, post_count_max
Verfügbare Filter für 'post': community_ids, created_after, created_before, likes_min, author_id
Verfügbare Filter für 'community': keine Filter nötig (zeigt alle)

Beispiel-Antworten:
- Frage: "Welche Mitglieder sind besonders aktiv?"
  {"message": "Ich habe eine Selektion für aktive Mitglieder erstellt...", "selection": {"name": "Aktive Mitglieder", "outputType": "member", "filters": {"post_count_min": 5}}}

- Frage: "Hallo"
  {"message": "Hallo! Ich bin CatNose...", "selection": null}

- Frage: "Gib mir alle neuen Mitglieder"
  {"message": "Ich habe eine Selektion für neue Mitglieder erstellt. Du kannst das Datum anpassen.", "selection": {"name": "Neue Mitglieder", "outputType": "member", "filters": {"joined_after": "2024-01-01"}}}`

	// Build messages array with chat history
	messages := []ai.Message{
		{Role: "system", Content: systemPrompt},
	}

	// Add previous messages from chat history
	for _, msg := range chatHistory {
		messages = append(messages, ai.Message{
			Role:    msg.Role,
			Content: msg.Content,
		})
	}

	// Add the current user message
	messages = append(messages, ai.Message{
		Role:    "user",
		Content: userMessage,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	resp, err := client.Chat(ctx, messages)
	if err != nil {
		log.Printf("AI error: %v", err)
		return "Entschuldigung, es gab ein Problem mit der AI-Verarbeitung. Bitte versuche es erneut.", nil
	}

	if len(resp.Choices) == 0 {
		return "Keine Antwort von der AI erhalten.", nil
	}

	// Parse AI response
	aiContent := resp.Choices[0].Message.Content

	// DEBUG: Log raw AI response
	log.Printf("=== RAW AI RESPONSE ===\n%s\n=== END RAW ===", aiContent)

	// Try to parse as JSON
	var aiResp struct {
		Message   string       `json:"message"`
		Selection *AISelection `json:"selection"`
	}

	// Clean up response - sometimes AI adds markdown code blocks
	cleanContent := strings.TrimPrefix(aiContent, "```json")
	cleanContent = strings.TrimPrefix(cleanContent, "```")
	cleanContent = strings.TrimSuffix(cleanContent, "```")
	cleanContent = strings.TrimSpace(cleanContent)

	// Remove single-line comments (// ...) from JSON - AI sometimes adds them despite instructions
	cleanContent = removeJSONComments(cleanContent)

	// DEBUG: Log cleaned content
	log.Printf("=== CLEANED CONTENT ===\n%s\n=== END CLEANED ===", cleanContent)

	if err := json.Unmarshal([]byte(cleanContent), &aiResp); err != nil {
		// If parsing fails, return the raw content
		log.Printf("Failed to parse AI response as JSON: %v", err)
		return aiContent, nil
	}

	// DEBUG: Log parsed message
	log.Printf("=== PARSED MESSAGE ===\n%s\n=== END PARSED ===", aiResp.Message)

	return aiResp.Message, aiResp.Selection
}

// === Selection Handlers ===

func (h *Handlers) GetSelectionsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	selections, err := h.storage.App.GetAllSelections()
	if err != nil {
		log.Printf("Error getting selections: %v", err)
		writeError(w, "Failed to get selections", http.StatusInternalServerError)
		return
	}

	var response []SelectionResponse
	for _, s := range selections {
		response = append(response, selectionToResponse(s))
	}

	if response == nil {
		response = []SelectionResponse{}
	}
	writeJSON(w, response)
}

func (h *Handlers) GetSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid selection ID", http.StatusBadRequest)
		return
	}

	selection, err := h.storage.App.GetSelection(id)
	if err != nil {
		log.Printf("Error getting selection: %v", err)
		writeError(w, "Failed to get selection", http.StatusInternalServerError)
		return
	}
	if selection == nil {
		writeError(w, "Selection not found", http.StatusNotFound)
		return
	}

	writeJSON(w, selectionToResponse(*selection))
}

func (h *Handlers) CreateSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req CreateSelectionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if req.OutputType == "" {
		writeError(w, "outputType is required", http.StatusBadRequest)
		return
	}

	filtersJSON, _ := json.Marshal(req.Filters)
	if req.Name == "" {
		req.Name = "Neue Selektion"
	}

	id, err := h.storage.App.CreateSelection(req.Name, req.OutputType, string(filtersJSON), "user", nil)
	if err != nil {
		log.Printf("Error creating selection: %v", err)
		writeError(w, "Failed to create selection", http.StatusInternalServerError)
		return
	}

	selection, _ := h.storage.App.GetSelection(id)
	writeJSON(w, selectionToResponse(*selection))
}

func (h *Handlers) DeleteSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid selection ID", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.DeleteSelection(id); err != nil {
		log.Printf("Error deleting selection: %v", err)
		writeError(w, "Failed to delete selection", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]string{"status": "ok"})
}

// DuplicateSelectionHandler dupliziert eine Selection und setzt parent_id
func (h *Handlers) DuplicateSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid selection ID", http.StatusBadRequest)
		return
	}

	// Original Selection holen
	original, err := h.storage.App.GetSelection(id)
	if err != nil {
		log.Printf("Error getting selection: %v", err)
		writeError(w, "Failed to get selection", http.StatusInternalServerError)
		return
	}
	if original == nil {
		writeError(w, "Selection not found", http.StatusNotFound)
		return
	}

	// Parent-ID bestimmen: Wenn das Original schon ein Duplikat ist, nimm dessen Parent
	// Sonst ist das Original selbst der Parent
	var parentID int64
	if original.ParentID != nil {
		parentID = *original.ParentID
	} else {
		parentID = original.ID
	}

	// Duplikat erstellen mit parent_id
	newName := original.Name + " (Kopie)"
	newID, err := h.storage.App.CreateSelectionWithParent(newName, original.OutputType, original.FiltersJSON, "user", nil, &parentID)
	if err != nil {
		log.Printf("Error duplicating selection: %v", err)
		writeError(w, "Failed to duplicate selection", http.StatusInternalServerError)
		return
	}

	// Neue Selection zurueckgeben
	newSelection, _ := h.storage.App.GetSelection(newID)
	writeJSON(w, selectionToResponse(*newSelection))
}

// UpdateSelectionRequest für das Aktualisieren einer Selection
type UpdateSelectionRequest struct {
	Name       string `json:"name"`
	OutputType string `json:"outputType"`
	Filters    any    `json:"filters"`
}

// UpdateSelectionHandler aktualisiert eine Selection
func (h *Handlers) UpdateSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid selection ID", http.StatusBadRequest)
		return
	}

	var req UpdateSelectionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Bestehende Selection prüfen
	existing, err := h.storage.App.GetSelection(id)
	if err != nil || existing == nil {
		writeError(w, "Selection not found", http.StatusNotFound)
		return
	}

	// Filter zu JSON konvertieren
	filtersJSON, _ := json.Marshal(req.Filters)

	// Selection aktualisieren
	if err := h.storage.App.UpdateSelection(id, req.Name, req.OutputType, string(filtersJSON)); err != nil {
		log.Printf("Error updating selection: %v", err)
		writeError(w, "Failed to update selection", http.StatusInternalServerError)
		return
	}

	// Aktualisierte Selection zurückgeben
	updated, _ := h.storage.App.GetSelection(id)
	writeJSON(w, selectionToResponse(*updated))
}

// === Report Handlers ===

func (h *Handlers) GetReportsHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	reports, err := h.storage.App.GetAllReports()
	if err != nil {
		log.Printf("Error getting reports: %v", err)
		writeError(w, "Failed to get reports", http.StatusInternalServerError)
		return
	}

	var response []ReportResponse
	for _, r := range reports {
		response = append(response, ReportResponse{
			ID:        r.ID,
			Name:      r.Name,
			CreatedAt: r.CreatedAt,
		})
	}

	if response == nil {
		response = []ReportResponse{}
	}
	writeJSON(w, response)
}

func (h *Handlers) CreateReportHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req CreateReportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		req.Name = "Neuer Report"
	}
	if req.Name == "" {
		req.Name = "Neuer Report"
	}

	id, err := h.storage.App.CreateReport(req.Name, "analysis")
	if err != nil {
		log.Printf("Error creating report: %v", err)
		writeError(w, "Failed to create report", http.StatusInternalServerError)
		return
	}

	report, _ := h.storage.App.GetReport(id)
	writeJSON(w, ReportResponse{
		ID:        report.ID,
		Name:      report.Name,
		CreatedAt: report.CreatedAt,
		Blocks:    []ReportBlockResponse{},
	})
}

func (h *Handlers) GetReportHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid report ID", http.StatusBadRequest)
		return
	}

	report, err := h.storage.App.GetReport(id)
	if err != nil {
		log.Printf("Error getting report: %v", err)
		writeError(w, "Failed to get report", http.StatusInternalServerError)
		return
	}
	if report == nil {
		writeError(w, "Report not found", http.StatusNotFound)
		return
	}

	blocks, _ := h.storage.App.GetReportBlocks(id)
	var blockResponses []ReportBlockResponse
	for _, b := range blocks {
		blockResponses = append(blockResponses, ReportBlockResponse{
			ID:          b.ID,
			ReportID:    b.ReportID,
			BlockType:   b.BlockType,
			Position:    b.Position,
			Content:     b.Content,
			SelectionID: b.SelectionID,
			ViewType:    b.ViewType,
			CreatedAt:   b.CreatedAt,
		})
	}

	if blockResponses == nil {
		blockResponses = []ReportBlockResponse{}
	}

	writeJSON(w, ReportResponse{
		ID:        report.ID,
		Name:      report.Name,
		CreatedAt: report.CreatedAt,
		Blocks:    blockResponses,
	})
}

func (h *Handlers) DeleteReportHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid report ID", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.DeleteReport(id); err != nil {
		log.Printf("Error deleting report: %v", err)
		writeError(w, "Failed to delete report", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]string{"status": "ok"})
}

// === Report Block Handlers ===

func (h *Handlers) AddReportBlockHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	reportIDStr := r.URL.Query().Get("reportId")
	reportID, err := strconv.ParseInt(reportIDStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid report ID", http.StatusBadRequest)
		return
	}

	var req AddReportBlockRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if req.BlockType == "" {
		writeError(w, "blockType is required", http.StatusBadRequest)
		return
	}
	if req.ViewType == "" {
		req.ViewType = "list"
	}

	// Get current max position
	blocks, _ := h.storage.App.GetReportBlocks(reportID)
	position := len(blocks)

	id, err := h.storage.App.AddReportBlock(reportID, req.BlockType, position, req.Content, req.SelectionID, req.ViewType)
	if err != nil {
		log.Printf("Error adding report block: %v", err)
		writeError(w, "Failed to add report block", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]interface{}{
		"status": "ok",
		"id":     id,
	})
}

func (h *Handlers) DeleteReportBlockHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid block ID", http.StatusBadRequest)
		return
	}

	if err := h.storage.App.DeleteReportBlock(id); err != nil {
		log.Printf("Error deleting report block: %v", err)
		writeError(w, "Failed to delete report block", http.StatusInternalServerError)
		return
	}

	writeJSON(w, map[string]string{"status": "ok"})
}

// === Selection Execution Handler ===

type ExecuteSelectionResponse struct {
	Selection   SelectionResponse `json:"selection"`
	Posts       []PostResult      `json:"posts,omitempty"`
	Members     []MemberResult    `json:"members,omitempty"`
	Communities []CommunityResult `json:"communities,omitempty"`
	Total       int64             `json:"total"`
}

type MemberResult struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Slug        string `json:"slug"`
	Picture     string `json:"picture,omitempty"`
	CommunityID string `json:"communityId"`
	JoinedAt    string `json:"joinedAt,omitempty"`
	LastOnline  string `json:"lastOnline,omitempty"`
	PostCount   int    `json:"postCount"`
	Level       int    `json:"level"`
}

type CommunityResult struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Slug        string `json:"slug"`
	Description string `json:"description,omitempty"`
	MemberCount int    `json:"memberCount"`
	PostCount   int    `json:"postCount"`
	Picture     string `json:"picture,omitempty"`
}

type PostResult struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Content     string `json:"content"`
	AuthorID    string `json:"authorId"`
	AuthorName  string `json:"authorName"`
	CommunityID string `json:"communityId"`
	Likes       int    `json:"likes"`
	Comments    int    `json:"comments"`
	CreatedAt   string `json:"createdAt"`
}

// ExecuteSelectionHandler führt eine Selection aus und gibt die Ergebnisse zurück
func (h *Handlers) ExecuteSelectionHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	idStr := r.URL.Query().Get("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid selection ID", http.StatusBadRequest)
		return
	}

	selection, err := h.storage.App.GetSelection(id)
	if err != nil {
		log.Printf("Error getting selection: %v", err)
		writeError(w, "Failed to get selection", http.StatusInternalServerError)
		return
	}
	if selection == nil {
		writeError(w, "Selection not found", http.StatusNotFound)
		return
	}

	resp := ExecuteSelectionResponse{
		Selection: selectionToResponse(*selection),
	}

	// Filter aus JSON parsen
	var filters map[string]interface{}
	if err := json.Unmarshal([]byte(selection.FiltersJSON), &filters); err != nil {
		log.Printf("Error parsing filters: %v", err)
		filters = make(map[string]interface{})
	}

	// Je nach OutputType die entsprechenden Daten holen
	switch selection.OutputType {
	case "post":
		posts, total := h.executePostSelection(filters)
		resp.Posts = posts
		resp.Total = total

		// Selection-Ergebnisse aktualisieren
		postIDs := make([]string, len(posts))
		for i, p := range posts {
			postIDs[i] = p.ID
		}
		idsJSON, _ := json.Marshal(postIDs)
		h.storage.App.UpdateSelectionResults(id, len(posts), string(idsJSON))

	case "member":
		members, total := h.executeMemberSelection(filters)
		resp.Members = members
		resp.Total = total

		// Selection-Ergebnisse aktualisieren
		memberIDs := make([]string, len(members))
		for i, m := range members {
			memberIDs[i] = m.ID
		}
		idsJSON, _ := json.Marshal(memberIDs)
		h.storage.App.UpdateSelectionResults(id, len(members), string(idsJSON))

	case "community":
		communities, total := h.executeCommunitySelection(filters)
		resp.Communities = communities
		resp.Total = total

		// Selection-Ergebnisse aktualisieren
		communityIDs := make([]string, len(communities))
		for i, c := range communities {
			communityIDs[i] = c.ID
		}
		idsJSON, _ := json.Marshal(communityIDs)
		h.storage.App.UpdateSelectionResults(id, len(communities), string(idsJSON))
	}

	writeJSON(w, resp)
}

// executePostSelection führt eine Post-Selektion basierend auf den Filtern aus
func (h *Handlers) executePostSelection(filters map[string]interface{}) ([]PostResult, int64) {
	// Filter in DuckDB PostFilter konvertieren
	postFilter := h.filtersToPostFilter(filters)

	posts, total, err := h.storage.Raw.GetPosts(postFilter)
	if err != nil {
		log.Printf("Error executing post selection: %v", err)
		return []PostResult{}, 0
	}

	// Zu PostResult konvertieren
	results := make([]PostResult, len(posts))
	for i, p := range posts {
		results[i] = PostResult{
			ID:          p.ID,
			Title:       p.Title,
			Content:     p.Content,
			AuthorID:    p.AuthorID,
			AuthorName:  p.AuthorName,
			CommunityID: p.CommunityID,
			Likes:       p.Likes,
			Comments:    p.Comments,
			CreatedAt:   p.CreatedAt,
		}
	}

	return results, total
}

// filtersToPostFilter konvertiert die JSON-Filter in einen DuckDB PostFilter
func (h *Handlers) filtersToPostFilter(filters map[string]interface{}) duckdb.PostFilter {
	pf := duckdb.PostFilter{
		Limit: 100, // Default limit
	}

	if communityIDs, ok := filters["community_ids"].([]interface{}); ok {
		for _, cid := range communityIDs {
			if s, ok := cid.(string); ok {
				pf.CommunityIDs = append(pf.CommunityIDs, s)
			}
		}
	}

	if authorID, ok := filters["author_id"].(string); ok {
		pf.AuthorID = authorID
	}

	if likesMin, ok := filters["likes_min"].(float64); ok {
		pf.LikesMin = int(likesMin)
	}

	if createdAfter, ok := filters["created_after"].(string); ok {
		pf.CreatedAfter = createdAfter
	}

	if createdBefore, ok := filters["created_before"].(string); ok {
		pf.CreatedBefore = createdBefore
	}

	if limit, ok := filters["limit"].(float64); ok {
		pf.Limit = int(limit)
	}

	return pf
}

// executeMemberSelection führt eine Member-Selektion basierend auf den Filtern aus
func (h *Handlers) executeMemberSelection(filters map[string]interface{}) ([]MemberResult, int64) {
	memberFilter := h.filtersToMemberFilter(filters)

	members, total, err := h.storage.Raw.GetMembers(memberFilter)
	if err != nil {
		log.Printf("Error executing member selection: %v", err)
		return []MemberResult{}, 0
	}

	// Zu MemberResult konvertieren
	results := make([]MemberResult, len(members))
	for i, m := range members {
		results[i] = MemberResult{
			ID:          m.ID,
			Name:        m.Name,
			Slug:        m.Slug,
			Picture:     m.Picture,
			CommunityID: m.CommunityID,
			JoinedAt:    m.JoinedAt,
			LastOnline:  m.LastOnline,
			PostCount:   m.PostCount,
			Level:       m.Level,
		}
	}

	return results, total
}

// filtersToMemberFilter konvertiert die JSON-Filter in einen DuckDB MemberFilter
func (h *Handlers) filtersToMemberFilter(filters map[string]interface{}) duckdb.MemberFilter {
	mf := duckdb.MemberFilter{
		Limit: 100, // Default limit
	}

	if communityIDs, ok := filters["community_ids"].([]interface{}); ok {
		for _, cid := range communityIDs {
			if s, ok := cid.(string); ok {
				mf.CommunityIDs = append(mf.CommunityIDs, s)
			}
		}
	}

	if joinedAfter, ok := filters["joined_after"].(string); ok {
		mf.JoinedAfter = joinedAfter
	}

	if joinedBefore, ok := filters["joined_before"].(string); ok {
		mf.JoinedBefore = joinedBefore
	}

	if postCountMin, ok := filters["post_count_min"].(float64); ok {
		mf.PostCountMin = int(postCountMin)
	}

	if postCountMax, ok := filters["post_count_max"].(float64); ok {
		mf.PostCountMax = int(postCountMax)
	}

	if levelMin, ok := filters["level_min"].(float64); ok {
		mf.LevelMin = int(levelMin)
	}

	if limit, ok := filters["limit"].(float64); ok {
		mf.Limit = int(limit)
	}

	return mf
}

// executeCommunitySelection führt eine Community-Selektion basierend auf den Filtern aus
func (h *Handlers) executeCommunitySelection(filters map[string]interface{}) ([]CommunityResult, int64) {
	communityFilter := h.filtersToCommunityFilter(filters)

	communities, total, err := h.storage.Raw.GetCommunities(communityFilter)
	if err != nil {
		log.Printf("Error executing community selection: %v", err)
		return []CommunityResult{}, 0
	}

	// Zu CommunityResult konvertieren
	results := make([]CommunityResult, len(communities))
	for i, c := range communities {
		results[i] = CommunityResult{
			ID:          c.ID,
			Name:        c.Name,
			Slug:        c.Slug,
			Description: c.Description,
			MemberCount: c.MemberCount,
			PostCount:   c.PostCount,
			Picture:     c.Picture,
		}
	}

	return results, total
}

// filtersToCommunityFilter konvertiert die JSON-Filter in einen DuckDB CommunityFilter
func (h *Handlers) filtersToCommunityFilter(filters map[string]interface{}) duckdb.CommunityFilter {
	cf := duckdb.CommunityFilter{
		Limit: 100, // Default limit
	}

	if communityIDs, ok := filters["community_ids"].([]interface{}); ok {
		for _, cid := range communityIDs {
			if s, ok := cid.(string); ok {
				cf.CommunityIDs = append(cf.CommunityIDs, s)
			}
		}
	}

	if memberCountMin, ok := filters["member_count_min"].(float64); ok {
		cf.MemberCountMin = int(memberCountMin)
	}

	if limit, ok := filters["limit"].(float64); ok {
		cf.Limit = int(limit)
	}

	return cf
}

// === Chat Report Handlers (Lazy Report + AI Condensation) ===

type AddSelectionToReportRequest struct {
	ChatID      int64 `json:"chatId"`
	SelectionID int64 `json:"selectionId"`
}

type AddSelectionToReportResponse struct {
	ReportID     int64               `json:"reportId"`
	Block        ReportBlockResponse `json:"block"`
	Condensation string              `json:"condensation"`
}

type ChatReportResponse struct {
	ChatID int64           `json:"chatId"`
	Report *ReportResponse `json:"report,omitempty"`
}

// AddSelectionToReportHandler adds a selection to the chat's report with AI condensation
func (h *Handlers) AddSelectionToReportHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var req AddSelectionToReportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// 1. Get chat
	chat, err := h.storage.App.GetChat(req.ChatID)
	if err != nil || chat == nil {
		writeError(w, "Chat not found", http.StatusNotFound)
		return
	}

	// 2. Get selection
	selection, err := h.storage.App.GetSelection(req.SelectionID)
	if err != nil || selection == nil {
		writeError(w, "Selection not found", http.StatusNotFound)
		return
	}

	// 3. Lazy create report if needed
	reportID := chat.ReportID
	if reportID == nil {
		newReportID, err := h.storage.App.CreateReport(chat.Title+" - Report", "chat")
		if err != nil {
			log.Printf("Error creating report: %v", err)
			writeError(w, "Failed to create report", http.StatusInternalServerError)
			return
		}
		if err := h.storage.App.SetChatReportID(req.ChatID, newReportID); err != nil {
			log.Printf("Error linking report to chat: %v", err)
			writeError(w, "Failed to link report", http.StatusInternalServerError)
			return
		}
		reportID = &newReportID
	}

	// 4. Get chat history for AI context
	messages, _ := h.storage.App.GetMessages(req.ChatID)

	// 5. Get existing report blocks for context
	existingBlocks, _ := h.storage.App.GetReportBlocks(*reportID)

	// 6. Generate AI condensation
	condensation := h.generateCondensation(messages, existingBlocks, selection)

	// 7. Create report block
	position := len(existingBlocks)
	blockID, err := h.storage.App.AddReportBlock(
		*reportID,
		"text",
		position,
		condensation,
		&req.SelectionID,
		"condensed",
	)
	if err != nil {
		log.Printf("Error adding report block: %v", err)
		writeError(w, "Failed to add report block", http.StatusInternalServerError)
		return
	}

	// 8. Return response
	writeJSON(w, AddSelectionToReportResponse{
		ReportID: *reportID,
		Block: ReportBlockResponse{
			ID:          blockID,
			ReportID:    *reportID,
			BlockType:   "text",
			Position:    position,
			Content:     condensation,
			SelectionID: &req.SelectionID,
			ViewType:    "condensed",
		},
		Condensation: condensation,
	})
}

// GetChatReportHandler retrieves the report for a specific chat
func (h *Handlers) GetChatReportHandler(w http.ResponseWriter, r *http.Request) {
	setCORSHeaders(w)
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	chatIDStr := r.URL.Query().Get("chatId")
	chatID, err := strconv.ParseInt(chatIDStr, 10, 64)
	if err != nil {
		writeError(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	chat, err := h.storage.App.GetChat(chatID)
	if err != nil || chat == nil {
		writeError(w, "Chat not found", http.StatusNotFound)
		return
	}

	response := ChatReportResponse{ChatID: chatID}

	if chat.ReportID != nil {
		report, _ := h.storage.App.GetReport(*chat.ReportID)
		if report != nil {
			blocks, _ := h.storage.App.GetReportBlocks(*chat.ReportID)
			var blockResponses []ReportBlockResponse
			for _, b := range blocks {
				blockResponses = append(blockResponses, ReportBlockResponse{
					ID:          b.ID,
					ReportID:    b.ReportID,
					BlockType:   b.BlockType,
					Position:    b.Position,
					Content:     b.Content,
					SelectionID: b.SelectionID,
					ViewType:    b.ViewType,
					CreatedAt:   b.CreatedAt,
				})
			}
			if blockResponses == nil {
				blockResponses = []ReportBlockResponse{}
			}
			response.Report = &ReportResponse{
				ID:        report.ID,
				Name:      report.Name,
				CreatedAt: report.CreatedAt,
				Blocks:    blockResponses,
			}
		}
	}

	writeJSON(w, response)
}

// generateCondensation creates an AI summary of a selection based on chat context
func (h *Handlers) generateCondensation(messages []sqlite.Message, existingBlocks []sqlite.ReportBlock, selection *sqlite.Selection) string {
	apiKey := h.GetOpenAIKey()
	if apiKey == "" {
		return h.generateFallbackCondensation(selection)
	}

	client := ai.NewClient(ai.Config{
		APIKey:  apiKey,
		Timeout: 60 * time.Second,
	})

	// Build chat history context
	var chatContext strings.Builder
	chatContext.WriteString("Chat-Verlauf:\n")
	for _, m := range messages {
		role := "User"
		if m.Role == "assistant" {
			role = "CatNose"
		}
		chatContext.WriteString(role + ": " + m.Content + "\n")
	}

	// Build existing report context
	var reportContext strings.Builder
	if len(existingBlocks) > 0 {
		reportContext.WriteString("\nBisheriger Report-Inhalt:\n")
		for i, b := range existingBlocks {
			reportContext.WriteString(strconv.Itoa(i+1) + ". " + b.Content + "\n")
		}
	}

	// Build selection info
	var filters map[string]interface{}
	json.Unmarshal([]byte(selection.FiltersJSON), &filters)

	selectionInfo := "Aktuelle Selektion:\n" +
		"- Name: " + selection.Name + "\n" +
		"- Typ: " + selection.OutputType + "\n" +
		"- Ergebnisse: " + strconv.Itoa(selection.ResultCount) + " Items\n"

	if len(filters) > 0 {
		filtersStr, _ := json.Marshal(filters)
		selectionInfo += "- Filter: " + string(filtersStr) + "\n"
	}

	systemPrompt := `Du bist ein Berichts-Assistent für Community-Datenanalyse.
Deine Aufgabe ist es, eine kurze, prägnante Zusammenfassung einer Datenselektion zu erstellen.

Die Zusammenfassung soll:
1. Den Kontext aus dem Chat-Verlauf berücksichtigen (warum wurde diese Selektion erstellt?)
2. Die wichtigsten Erkenntnisse aus der Selektion hervorheben
3. Prägnant sein (2-4 Sätze)
4. In einem professionellen Berichtsstil geschrieben sein

Antworte NUR mit der Zusammenfassung, ohne zusätzliche Erklärungen oder Formatierung.`

	userPrompt := chatContext.String() + reportContext.String() + "\n" + selectionInfo +
		"\nErstelle eine Zusammenfassung dieser Selektion für den Report."

	aiMessages := []ai.Message{
		{Role: "system", Content: systemPrompt},
		{Role: "user", Content: userPrompt},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	resp, err := client.Chat(ctx, aiMessages)
	if err != nil || len(resp.Choices) == 0 {
		log.Printf("AI condensation error: %v", err)
		return h.generateFallbackCondensation(selection)
	}

	return strings.TrimSpace(resp.Choices[0].Message.Content)
}

// generateFallbackCondensation creates a simple summary when AI is not available
func (h *Handlers) generateFallbackCondensation(selection *sqlite.Selection) string {
	typeLabel := selection.OutputType
	switch selection.OutputType {
	case "member":
		typeLabel = "Mitglieder"
	case "post":
		typeLabel = "Posts"
	case "community":
		typeLabel = "Communities"
	}
	return "Selektion \"" + selection.Name + "\" (" + typeLabel + "): " +
		strconv.Itoa(selection.ResultCount) + " Ergebnisse gefunden."
}

// === Helper Functions ===

func selectionToResponse(s sqlite.Selection) SelectionResponse {
	return SelectionResponse{
		ID:            s.ID,
		Name:          s.Name,
		OutputType:    s.OutputType,
		FiltersJSON:   s.FiltersJSON,
		ResultCount:   s.ResultCount,
		ResultIDsJSON: s.ResultIDsJSON,
		CreatedBy:     s.CreatedBy,
		MessageID:     s.MessageID,
		ParentID:      s.ParentID,
		CreatedAt:     s.CreatedAt,
		UpdatedAt:     s.UpdatedAt,
	}
}

// removeJSONComments removes single-line comments (// ...) from JSON strings
// This is needed because AI sometimes adds comments despite instructions not to
func removeJSONComments(jsonStr string) string {
	lines := strings.Split(jsonStr, "\n")
	var result []string
	for _, line := range lines {
		// Find // that's not inside a string
		inString := false
		commentIdx := -1
		for i := 0; i < len(line); i++ {
			if line[i] == '"' && (i == 0 || line[i-1] != '\\') {
				inString = !inString
			}
			if !inString && i+1 < len(line) && line[i] == '/' && line[i+1] == '/' {
				commentIdx = i
				break
			}
		}
		if commentIdx >= 0 {
			line = strings.TrimRight(line[:commentIdx], " \t")
		}
		result = append(result, line)
	}
	return strings.Join(result, "\n")
}

// selectionToResponseWithDerived konvertiert Selection und laedt abgeleitete Selektionen
func (h *Handlers) selectionToResponseWithDerived(s sqlite.Selection) SelectionResponse {
	resp := selectionToResponse(s)

	// Nur fuer Ursprungs-Selektionen (ohne Parent) die abgeleiteten laden
	if s.ParentID == nil {
		derived, err := h.storage.App.GetDerivedSelections(s.ID)
		if err == nil && len(derived) > 0 {
			resp.DerivedSelections = make([]SelectionResponse, len(derived))
			for i, d := range derived {
				resp.DerivedSelections[i] = selectionToResponse(d)
			}
		}
	}

	return resp
}
