package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	"school-local-backend/server"
	"school-local-backend/storage"
)

var (
	port      = flag.Int("port", 3000, "Server port")
	noBrowser = flag.Bool("no-browser", false, "Don't open browser automatically")
	dataDir   = flag.String("data-dir", "", "Directory for database files (default: catknows_data next to binary)")
)

func main() {
	flag.Parse()

	fmt.Println("Starting CatKnows...")

	// Data-Verzeichnis bestimmen (Standard: catknows_data neben dem Binary)
	dataDirPath := *dataDir
	if dataDirPath == "" {
		execPath, err := os.Executable()
		if err != nil {
			log.Fatal("Could not determine executable path:", err)
		}
		dataDirPath = filepath.Join(filepath.Dir(execPath), "catknows_data")
	}

	// Storage initialisieren (DuckDB + SQLite)
	store, err := storage.New(storage.Config{
		DataDir: dataDirPath,
	})
	if err != nil {
		log.Fatal("Storage error:", err)
	}
	defer store.Close()

	fmt.Printf("Storage initialized in: %s\n", dataDirPath)
	fmt.Println("  - DuckDB (raw data): raw.duckdb")
	fmt.Println("  - SQLite (app data): app.sqlite")

	// Router mit eingebetteten statischen Dateien
	staticFS := GetStaticFS()
	r := server.NewRouter(staticFS, store)

	url := fmt.Sprintf("http://localhost:%d", *port)
	fmt.Printf("Server running on %s\n", url)

	// Browser öffnen (nach kurzer Verzögerung)
	if !*noBrowser {
		go func() {
			time.Sleep(500 * time.Millisecond)
			openBrowser(url)
		}()
	}

	addr := fmt.Sprintf(":%d", *port)
	log.Fatal(http.ListenAndServe(addr, r))
}

func openBrowser(url string) {
	var err error
	switch runtime.GOOS {
	case "darwin":
		err = exec.Command("open", url).Start()
	case "windows":
		err = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	case "linux":
		err = exec.Command("xdg-open", url).Start()
	}
	if err != nil {
		log.Printf("Could not open browser: %v", err)
	}
}
