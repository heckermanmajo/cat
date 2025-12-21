package ai

import (
	"context"
	"fmt"
	"log"
	"os"
	"testing"
	"time"
)

const (
	// Klare Meldungen für ausgegraut Tests
	msgNoAPIKey = `
================================================================================
  ⚠️  AI-TESTS AUSGEGRAUT - KEIN API-KEY KONFIGURIERT
================================================================================

  Um AI-Tests auszuführen, setze den OpenAI API-Key:

  Option 1: Environment-Variable
    export OPENAI_API_KEY="sk-..."
    go test -v ./ai/...

  Option 2: In der App-UI
    Öffne Settings → OpenAI API-Key eingeben

================================================================================
`
)

// checkAPIKey prüft ob ein API-Key verfügbar ist und gibt eine klare Meldung aus
func checkAPIKey(t *testing.T) string {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		fmt.Print(msgNoAPIKey)
		t.Skip("AI-Test ausgegraut: Kein OpenAI API-Key konfiguriert")
	}
	return apiKey
}

// TestSimpleChat testet einen einfachen AI-Aufruf mit Logging
func TestSimpleChat(t *testing.T) {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)

	apiKey := checkAPIKey(t)

	log.Println("[AI_TEST] === Test gestartet ===")
	log.Printf("[AI_TEST] API-Key vorhanden: %v", apiKey != "")

	client := NewClient(Config{
		APIKey:  apiKey,
		Timeout: 30 * time.Second,
	})

	log.Printf("[AI_TEST] Client erstellt mit Model: gpt-4o-mini")
	log.Printf("[AI_TEST] Client konfiguriert: %v", client.IsConfigured())

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	prompt := "Antworte mit genau einem Wort: Was ist 2+2?"
	log.Printf("[AI_TEST] Sende Prompt: %s", prompt)

	startTime := time.Now()
	response, err := client.SimpleChat(ctx, prompt)
	duration := time.Since(startTime)

	log.Printf("[AI_TEST] Anfrage-Dauer: %v", duration)

	if err != nil {
		log.Printf("[AI_TEST] ERROR: %v", err)
		t.Fatalf("SimpleChat fehlgeschlagen: %v", err)
	}

	log.Printf("[AI_TEST] Antwort erhalten: %s", response)
	log.Println("[AI_TEST] === Test erfolgreich beendet ===")

	if response == "" {
		t.Error("Leere Antwort erhalten")
	}
}

// TestChatWithMessages testet einen Chat mit mehreren Nachrichten
func TestChatWithMessages(t *testing.T) {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)

	apiKey := checkAPIKey(t)

	log.Println("[AI_TEST] === Chat-Test mit Nachrichten gestartet ===")

	client := NewClient(Config{
		APIKey:  apiKey,
		Timeout: 30 * time.Second,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	messages := []Message{
		{Role: "system", Content: "Du bist ein hilfreicher Assistent. Antworte kurz und präzise."},
		{Role: "user", Content: "Was ist die Hauptstadt von Deutschland?"},
	}

	log.Printf("[AI_TEST] Sende %d Nachrichten", len(messages))
	for i, msg := range messages {
		log.Printf("[AI_TEST]   [%d] %s: %s", i, msg.Role, msg.Content)
	}

	startTime := time.Now()
	resp, err := client.Chat(ctx, messages)
	duration := time.Since(startTime)

	log.Printf("[AI_TEST] Anfrage-Dauer: %v", duration)

	if err != nil {
		log.Printf("[AI_TEST] ERROR: %v", err)
		t.Fatalf("Chat fehlgeschlagen: %v", err)
	}

	if len(resp.Choices) == 0 {
		log.Println("[AI_TEST] ERROR: Keine Choices in der Antwort")
		t.Fatal("Keine Choices in der Antwort")
	}

	log.Printf("[AI_TEST] Response ID: %s", resp.ID)
	log.Printf("[AI_TEST] Model: %s", resp.Model)
	log.Printf("[AI_TEST] Antwort: %s", resp.Choices[0].Message.Content)
	log.Printf("[AI_TEST] Finish Reason: %s", resp.Choices[0].FinishReason)
	log.Printf("[AI_TEST] Token-Verbrauch: Prompt=%d, Completion=%d, Total=%d",
		resp.Usage.PromptTokens, resp.Usage.CompletionTokens, resp.Usage.TotalTokens)

	log.Println("[AI_TEST] === Chat-Test erfolgreich beendet ===")
}

// TestClientNotConfigured testet das Verhalten ohne API-Key
func TestClientNotConfigured(t *testing.T) {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)
	log.Println("[AI_TEST] === Test: Client ohne API-Key ===")

	// Client ohne API-Key erstellen (und OPENAI_API_KEY temporär leeren)
	originalKey := os.Getenv("OPENAI_API_KEY")
	os.Unsetenv("OPENAI_API_KEY")
	defer func() {
		if originalKey != "" {
			os.Setenv("OPENAI_API_KEY", originalKey)
		}
	}()

	client := NewClient(Config{})

	log.Printf("[AI_TEST] Client konfiguriert: %v", client.IsConfigured())

	if client.IsConfigured() {
		t.Error("Client sollte nicht konfiguriert sein ohne API-Key")
	}

	ctx := context.Background()
	_, err := client.SimpleChat(ctx, "Test")

	log.Printf("[AI_TEST] Erwarteter Fehler: %v", err)

	if err == nil {
		t.Error("Erwarteter Fehler bei unkonfiguriertem Client")
	}

	log.Println("[AI_TEST] === Test erfolgreich: Fehler wie erwartet ===")
}

// TestAIClientCreation testet nur die Client-Erstellung (läuft immer)
func TestAIClientCreation(t *testing.T) {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)
	log.Println("[AI_TEST] === Test: Client-Erstellung ===")

	client := NewClient(Config{
		APIKey:  "test-key",
		BaseURL: "https://api.openai.com/v1",
		Model:   "gpt-4o-mini",
		Timeout: 10 * time.Second,
	})

	if client == nil {
		t.Fatal("Client sollte nicht nil sein")
	}

	if !client.IsConfigured() {
		t.Error("Client sollte mit test-key konfiguriert sein")
	}

	log.Printf("[AI_TEST] Client erstellt: Model=%s, BaseURL=%s", client.model, client.baseURL)
	log.Println("[AI_TEST] === Test erfolgreich ===")
}
