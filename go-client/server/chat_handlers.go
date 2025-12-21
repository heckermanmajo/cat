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
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type MessageResponse struct {
	ID         int64              `json:"id"`
	ChatID     int64              `json:"chatId"`
	Role       string             `json:"role"`
	Content    string             `json:"content"`
	CreatedAt  time.Time          `json:"createdAt"`
	Selections []SelectionResponse `json:"selections,omitempty"`
}

type SendMessageRequest struct {
	Content string `json:"content"`
}

type SelectionResponse struct {
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

type CreateSelectionRequest struct {
	Name       string `json:"name"`
	OutputType string `json:"outputType"`
	Filters    any    `json:"filters"`
}

type CreateReportRequest struct {
	Name string `json:"name"`
}

type ReportResponse struct {
	ID        int64               `json:"id"`
	Name      string              `json:"name"`
	CreatedAt time.Time           `json:"createdAt"`
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

	chats, err := h.storage.App.GetAllChats()
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

	// Enrich messages with their selections
	var response []MessageResponse
	for _, m := range messages {
		mr := MessageResponse{
			ID:        m.ID,
			ChatID:    m.ChatID,
			Role:      m.Role,
			Content:   m.Content,
			CreatedAt: m.CreatedAt,
		}

		// Get selections for assistant messages
		if m.Role == "assistant" {
			selections, _ := h.storage.App.GetSelectionsByMessage(m.ID)
			for _, s := range selections {
				mr.Selections = append(mr.Selections, selectionToResponse(s))
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

	// Store user message
	userMsgID, err := h.storage.App.AddMessage(chatID, "user", req.Content)
	if err != nil {
		log.Printf("Error adding user message: %v", err)
		writeError(w, "Failed to add message", http.StatusInternalServerError)
		return
	}

	// Generate AI response with potential selection
	assistantContent, selection := h.generateAIResponse(req.Content)

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
func (h *Handlers) generateAIResponse(userMessage string) (string, *AISelection) {
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
  {"message": "Hallo! Ich bin CatNose...", "selection": null}`

	messages := []ai.Message{
		{Role: "system", Content: systemPrompt},
		{Role: "user", Content: userMessage},
	}

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

	if err := json.Unmarshal([]byte(cleanContent), &aiResp); err != nil {
		// If parsing fails, return the raw content
		log.Printf("Failed to parse AI response as JSON: %v", err)
		return aiContent, nil
	}

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
		CreatedAt:     s.CreatedAt,
		UpdatedAt:     s.UpdatedAt,
	}
}
