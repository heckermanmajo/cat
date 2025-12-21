package main

import (
	"embed"
	"io/fs"
	"net/http"
)

//go:embed static/*
var staticFiles embed.FS

// GetStaticFS returns the embedded static files as http.FileSystem
func GetStaticFS() http.FileSystem {
	// Strip the "static" prefix so files are served from root
	subFS, err := fs.Sub(staticFiles, "static")
	if err != nil {
		panic(err)
	}
	return http.FS(subFS)
}
