package duckdb

import (
	"database/sql"
	_ "embed"
	"encoding/json"
	"fmt"
	"os"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

//go:embed schema.sql
var schema string

type RawDB struct {
	db *sql.DB
}

func Connect(dbPath string) (*RawDB, error) {
	db, err := sql.Open("duckdb", dbPath)
	if err != nil {
		return nil, fmt.Errorf("duckdb open error: %w", err)
	}

	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("duckdb schema error: %w", err)
	}

	return &RawDB{db: db}, nil
}

func (r *RawDB) Close() error {
	return r.db.Close()
}

// StoreFetch speichert einen Rohdaten-Fetch (append-only)
func (r *RawDB) StoreFetch(entityType, entityID, rawJSON, source string) error {
	_, err := r.db.Exec(`
		INSERT INTO raw_fetches (entity_type, entity_id, raw_json, source)
		VALUES (?, ?, ?, ?)
	`, entityType, entityID, rawJSON, source)
	return err
}

// StoreBulkFetch speichert mehrere Fetches auf einmal
func (r *RawDB) StoreBulkFetch(entityType, source string, items []FetchItem) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT INTO raw_fetches (entity_type, entity_id, raw_json, source)
		VALUES (?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, item := range items {
		if _, err := stmt.Exec(entityType, item.EntityID, item.RawJSON, source); err != nil {
			return err
		}
	}

	return tx.Commit()
}

type FetchItem struct {
	EntityID string
	RawJSON  string
}

// GetLatestFetch holt den neuesten Fetch für eine Entität
func (r *RawDB) GetLatestFetch(entityType, entityID string) (string, time.Time, error) {
	var rawJSON string
	var fetchedAt time.Time
	err := r.db.QueryRow(`
		SELECT raw_json, fetched_at
		FROM raw_fetches
		WHERE entity_type = ? AND entity_id = ?
		ORDER BY fetched_at DESC
		LIMIT 1
	`, entityType, entityID).Scan(&rawJSON, &fetchedAt)
	if err != nil {
		return "", time.Time{}, err
	}
	return rawJSON, fetchedAt, nil
}

// GetAllLatestByType holt den neuesten Stand aller Entitäten eines Typs
func (r *RawDB) GetAllLatestByType(entityType string) ([]LatestFetch, error) {
	rows, err := r.db.Query(`
		WITH latest AS (
			SELECT entity_id, MAX(fetched_at) as max_fetched_at
			FROM raw_fetches
			WHERE entity_type = ?
			GROUP BY entity_id
		)
		SELECT r.entity_id, r.raw_json, r.fetched_at
		FROM raw_fetches r
		INNER JOIN latest l ON r.entity_id = l.entity_id AND r.fetched_at = l.max_fetched_at
		WHERE r.entity_type = ?
	`, entityType, entityType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []LatestFetch
	for rows.Next() {
		var f LatestFetch
		if err := rows.Scan(&f.EntityID, &f.RawJSON, &f.FetchedAt); err != nil {
			return nil, err
		}
		results = append(results, f)
	}
	return results, rows.Err()
}

type LatestFetch struct {
	EntityID  string
	RawJSON   string
	FetchedAt time.Time
}

// GetFetchCount gibt die Anzahl der gespeicherten Fetches zurück
func (r *RawDB) GetFetchCount() (int64, error) {
	var count int64
	err := r.db.QueryRow("SELECT COUNT(*) FROM raw_fetches").Scan(&count)
	return count, err
}

// GetFetchCountByType gibt die Anzahl pro Entity-Typ zurück
func (r *RawDB) GetFetchCountByType() (map[string]int64, error) {
	rows, err := r.db.Query(`
		SELECT entity_type, COUNT(*)
		FROM raw_fetches
		GROUP BY entity_type
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[string]int64)
	for rows.Next() {
		var entityType string
		var count int64
		if err := rows.Scan(&entityType, &count); err != nil {
			return nil, err
		}
		result[entityType] = count
	}
	return result, rows.Err()
}

// QueryRaw führt eine beliebige SELECT-Query auf den Rohdaten aus
func (r *RawDB) QueryRaw(query string, args ...interface{}) (*sql.Rows, error) {
	return r.db.Query(query, args...)
}

// FetchRecord repräsentiert einen einzelnen Fetch-Eintrag
type FetchRecord struct {
	EntityType string
	EntityID   string
	RawJSON    string
	Source     string
	FetchedAt  time.Time
}

// FetchFilter enthält Filter-Optionen für GetAllFetches
type FetchFilter struct {
	EntityType string
	Source     string
	Limit      int
	Offset     int
}

// GetAllFetches holt alle Fetches mit Filtern und Pagination
func (r *RawDB) GetAllFetches(filter FetchFilter) ([]FetchRecord, int64, error) {
	// Basis-Query
	query := "SELECT entity_type, entity_id, raw_json, source, fetched_at FROM raw_fetches WHERE 1=1"
	countQuery := "SELECT COUNT(*) FROM raw_fetches WHERE 1=1"
	args := []interface{}{}

	if filter.EntityType != "" {
		query += " AND entity_type = ?"
		countQuery += " AND entity_type = ?"
		args = append(args, filter.EntityType)
	}
	if filter.Source != "" {
		query += " AND source = ?"
		countQuery += " AND source = ?"
		args = append(args, filter.Source)
	}

	// Total Count
	var total int64
	countArgs := make([]interface{}, len(args))
	copy(countArgs, args)
	if err := r.db.QueryRow(countQuery, countArgs...).Scan(&total); err != nil {
		return nil, 0, err
	}

	// Order und Limit
	query += " ORDER BY fetched_at DESC"
	if filter.Limit > 0 {
		query += " LIMIT ?"
		args = append(args, filter.Limit)
	}
	if filter.Offset > 0 {
		query += " OFFSET ?"
		args = append(args, filter.Offset)
	}

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var results []FetchRecord
	for rows.Next() {
		var f FetchRecord
		if err := rows.Scan(&f.EntityType, &f.EntityID, &f.RawJSON, &f.Source, &f.FetchedAt); err != nil {
			return nil, 0, err
		}
		results = append(results, f)
	}
	return results, total, rows.Err()
}

// GetEntityTypes gibt alle vorhandenen Entity-Typen zurück
func (r *RawDB) GetEntityTypes() ([]string, error) {
	rows, err := r.db.Query("SELECT DISTINCT entity_type FROM raw_fetches ORDER BY entity_type")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var types []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err != nil {
			return nil, err
		}
		types = append(types, t)
	}
	return types, rows.Err()
}

// GetSources gibt alle vorhandenen Sources zurück
func (r *RawDB) GetSources() ([]string, error) {
	rows, err := r.db.Query("SELECT DISTINCT source FROM raw_fetches ORDER BY source")
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

// Post repräsentiert einen extrahierten Post
type Post struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Content     string    `json:"content"`
	AuthorID    string    `json:"authorId"`
	AuthorName  string    `json:"authorName"`
	CommunityID string    `json:"communityId"`
	Likes       int       `json:"likes"`
	Comments    int       `json:"comments"`
	CreatedAt   string    `json:"createdAt"`
	FetchedAt   time.Time `json:"fetchedAt"`
	RawJSON     string    `json:"rawJson,omitempty"`
}

// PostFilter enthält Filter-Optionen für GetPosts
type PostFilter struct {
	CommunityIDs  []string
	AuthorID      string
	LikesMin      int
	CreatedAfter  string
	CreatedBefore string
	Limit         int
	Offset        int
	IncludeRaw    bool
}

// GetPosts extrahiert Posts aus community_page und post Fetches
func (r *RawDB) GetPosts(filter PostFilter) ([]Post, int64, error) {
	// Wir holen die neuesten Fetches für community_page und post entity types
	// und extrahieren die Posts daraus

	// Basis-Query: Holt die neuesten Fetches pro entity_id für relevante entity_types
	query := `
		WITH latest_fetches AS (
			SELECT entity_type, entity_id, raw_json, fetched_at,
				   ROW_NUMBER() OVER (PARTITION BY entity_type, entity_id ORDER BY fetched_at DESC) as rn
			FROM raw_fetches
			WHERE entity_type IN ('community_page', 'post', 'post_details')
		)
		SELECT entity_type, entity_id, raw_json, fetched_at
		FROM latest_fetches
		WHERE rn = 1
		ORDER BY fetched_at DESC
	`

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, 0, fmt.Errorf("query error: %w", err)
	}
	defer rows.Close()

	// Map um Duplikate zu vermeiden (post_id -> Post)
	postsMap := make(map[string]Post)

	for rows.Next() {
		var entityType, entityID, rawJSON string
		var fetchedAt time.Time
		if err := rows.Scan(&entityType, &entityID, &rawJSON, &fetchedAt); err != nil {
			return nil, 0, err
		}

		// Posts aus dem JSON extrahieren
		extractedPosts := extractPostsFromJSON(entityType, rawJSON, fetchedAt)
		for _, p := range extractedPosts {
			// Filter anwenden
			if !matchesPostFilter(p, filter) {
				continue
			}
			// Nur den neuesten Stand behalten
			if existing, ok := postsMap[p.ID]; ok {
				if p.FetchedAt.After(existing.FetchedAt) {
					if !filter.IncludeRaw {
						p.RawJSON = ""
					}
					postsMap[p.ID] = p
				}
			} else {
				if !filter.IncludeRaw {
					p.RawJSON = ""
				}
				postsMap[p.ID] = p
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, 0, err
	}

	// Map zu Slice konvertieren
	posts := make([]Post, 0, len(postsMap))
	for _, p := range postsMap {
		posts = append(posts, p)
	}

	// Nach Datum sortieren (neueste zuerst)
	for i := 0; i < len(posts)-1; i++ {
		for j := i + 1; j < len(posts); j++ {
			if posts[j].CreatedAt > posts[i].CreatedAt {
				posts[i], posts[j] = posts[j], posts[i]
			}
		}
	}

	total := int64(len(posts))

	// Pagination anwenden
	if filter.Offset > 0 && filter.Offset < len(posts) {
		posts = posts[filter.Offset:]
	} else if filter.Offset >= len(posts) {
		posts = []Post{}
	}

	if filter.Limit > 0 && filter.Limit < len(posts) {
		posts = posts[:filter.Limit]
	}

	return posts, total, nil
}

// extractPostsFromJSON extrahiert Posts aus verschiedenen JSON-Strukturen
func extractPostsFromJSON(entityType, rawJSON string, fetchedAt time.Time) []Post {
	var posts []Post

	switch entityType {
	case "community_page":
		// Skool community_page format: pageProps.postTrees[].post
		var skoolData struct {
			PageProps struct {
				PostTrees []struct {
					Post struct {
						ID        string `json:"id"`
						Name      string `json:"name"`
						GroupID   string `json:"groupId"`
						UserID    string `json:"userId"`
						CreatedAt string `json:"createdAt"`
						Metadata  struct {
							Title    string `json:"title"`
							Content  string `json:"content"`
							Upvotes  int    `json:"upvotes"`
							Comments int    `json:"comments"`
						} `json:"metadata"`
						User struct {
							ID        string `json:"id"`
							FirstName string `json:"firstName"`
							LastName  string `json:"lastName"`
						} `json:"user"`
					} `json:"post"`
				} `json:"postTrees"`
			} `json:"pageProps"`
		}
		if err := json.Unmarshal([]byte(rawJSON), &skoolData); err == nil && len(skoolData.PageProps.PostTrees) > 0 {
			for _, pt := range skoolData.PageProps.PostTrees {
				p := pt.Post
				if p.ID == "" {
					continue
				}
				authorName := p.User.FirstName
				if p.User.LastName != "" {
					authorName += " " + p.User.LastName
				}
				posts = append(posts, Post{
					ID:          p.ID,
					Title:       p.Metadata.Title,
					Content:     p.Metadata.Content,
					AuthorID:    p.UserID,
					AuthorName:  authorName,
					CommunityID: p.GroupID,
					Likes:       p.Metadata.Upvotes,
					Comments:    p.Metadata.Comments,
					CreatedAt:   p.CreatedAt,
					FetchedAt:   fetchedAt,
					RawJSON:     rawJSON,
				})
			}
		}

		// Fallback: Alternative Strukturen
		var altData struct {
			Posts []struct {
				ID      interface{} `json:"id"`
				Title   string      `json:"title"`
				Content string      `json:"content"`
				Author  struct {
					ID   interface{} `json:"id"`
					Name string      `json:"name"`
				} `json:"author"`
				CommunityID interface{} `json:"communityId"`
				Likes       int         `json:"likes"`
				Comments    int         `json:"comments"`
				CreatedAt   string      `json:"createdAt"`
			} `json:"posts"`
			CommunityID interface{} `json:"communityId"`
		}
		if len(posts) == 0 {
			if err := json.Unmarshal([]byte(rawJSON), &altData); err == nil {
				communityID := interfaceToString(altData.CommunityID)
				for _, p := range altData.Posts {
					postCommunityID := interfaceToString(p.CommunityID)
					if postCommunityID == "" {
						postCommunityID = communityID
					}
					posts = append(posts, Post{
						ID:          interfaceToString(p.ID),
						Title:       p.Title,
						Content:     p.Content,
						AuthorID:    interfaceToString(p.Author.ID),
						AuthorName:  p.Author.Name,
						CommunityID: postCommunityID,
						Likes:       p.Likes,
						Comments:    p.Comments,
						CreatedAt:   p.CreatedAt,
						FetchedAt:   fetchedAt,
						RawJSON:     rawJSON,
					})
				}
			}
		}

	case "post", "post_details":
		// Einzelner Post
		var p struct {
			ID      interface{} `json:"id"`
			Title   string      `json:"title"`
			Content string      `json:"content"`
			Author  struct {
				ID   interface{} `json:"id"`
				Name string      `json:"name"`
			} `json:"author"`
			CommunityID interface{} `json:"communityId"`
			Likes       int         `json:"likes"`
			Comments    int         `json:"comments"`
			CreatedAt   string      `json:"createdAt"`
		}
		if err := json.Unmarshal([]byte(rawJSON), &p); err == nil && interfaceToString(p.ID) != "" {
			posts = append(posts, Post{
				ID:          interfaceToString(p.ID),
				Title:       p.Title,
				Content:     p.Content,
				AuthorID:    interfaceToString(p.Author.ID),
				AuthorName:  p.Author.Name,
				CommunityID: interfaceToString(p.CommunityID),
				Likes:       p.Likes,
				Comments:    p.Comments,
				CreatedAt:   p.CreatedAt,
				FetchedAt:   fetchedAt,
				RawJSON:     rawJSON,
			})
		}
	}

	return posts
}

// matchesPostFilter prüft ob ein Post den Filterkriterien entspricht
func matchesPostFilter(p Post, filter PostFilter) bool {
	// Community-Filter
	if len(filter.CommunityIDs) > 0 {
		found := false
		for _, cid := range filter.CommunityIDs {
			if p.CommunityID == cid {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// Author-Filter
	if filter.AuthorID != "" && p.AuthorID != filter.AuthorID {
		return false
	}

	// Likes-Filter
	if filter.LikesMin > 0 && p.Likes < filter.LikesMin {
		return false
	}

	// Datums-Filter
	if filter.CreatedAfter != "" && p.CreatedAt < filter.CreatedAfter {
		return false
	}
	if filter.CreatedBefore != "" && p.CreatedAt > filter.CreatedBefore {
		return false
	}

	return true
}

// interfaceToString konvertiert verschiedene Typen zu String
func interfaceToString(v interface{}) string {
	if v == nil {
		return ""
	}
	switch val := v.(type) {
	case string:
		return val
	case float64:
		return fmt.Sprintf("%.0f", val)
	case int:
		return fmt.Sprintf("%d", val)
	case int64:
		return fmt.Sprintf("%d", val)
	default:
		return fmt.Sprintf("%v", val)
	}
}

// EnsureDataDir stellt sicher, dass das Verzeichnis für die DB existiert
func EnsureDataDir(path string) error {
	dir := path[:len(path)-len("/raw.duckdb")]
	if dir != "" {
		return os.MkdirAll(dir, 0755)
	}
	return nil
}

// === Member Selection ===

// Member repräsentiert ein extrahiertes Mitglied
type Member struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Slug        string    `json:"slug"`
	Picture     string    `json:"picture,omitempty"`
	CommunityID string    `json:"communityId"`
	JoinedAt    string    `json:"joinedAt,omitempty"`
	LastOnline  string    `json:"lastOnline,omitempty"`
	PostCount   int       `json:"postCount"`
	Level       int       `json:"level"`
	FetchedAt   time.Time `json:"fetchedAt"`
}

// MemberFilter enthält Filter-Optionen für GetMembers
type MemberFilter struct {
	CommunityIDs []string
	JoinedAfter  string
	JoinedBefore string
	PostCountMin int
	PostCountMax int
	LevelMin     int
	Limit        int
	Offset       int
}

// GetMembers extrahiert Members aus members Fetches
func (r *RawDB) GetMembers(filter MemberFilter) ([]Member, int64, error) {
	query := `
		WITH latest_fetches AS (
			SELECT entity_id, raw_json, fetched_at,
				   ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY fetched_at DESC) as rn
			FROM raw_fetches
			WHERE entity_type = 'members'
		)
		SELECT entity_id, raw_json, fetched_at
		FROM latest_fetches
		WHERE rn = 1
		ORDER BY fetched_at DESC
	`

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, 0, fmt.Errorf("query error: %w", err)
	}
	defer rows.Close()

	// Map um Duplikate zu vermeiden (user_id -> Member)
	membersMap := make(map[string]Member)

	for rows.Next() {
		var entityID, rawJSON string
		var fetchedAt time.Time
		if err := rows.Scan(&entityID, &rawJSON, &fetchedAt); err != nil {
			return nil, 0, err
		}

		// Members aus dem JSON extrahieren
		extractedMembers := extractMembersFromJSON(entityID, rawJSON, fetchedAt)
		for _, m := range extractedMembers {
			// Filter anwenden
			if !matchesMemberFilter(m, filter) {
				continue
			}
			// Nur den neuesten Stand behalten
			if existing, ok := membersMap[m.ID]; ok {
				if m.FetchedAt.After(existing.FetchedAt) {
					membersMap[m.ID] = m
				}
			} else {
				membersMap[m.ID] = m
			}
		}
	}

	if err := rows.Err(); err != nil {
		return nil, 0, err
	}

	// Map zu Slice konvertieren
	members := make([]Member, 0, len(membersMap))
	for _, m := range membersMap {
		members = append(members, m)
	}

	// Nach Name sortieren
	for i := 0; i < len(members)-1; i++ {
		for j := i + 1; j < len(members); j++ {
			if members[j].Name < members[i].Name {
				members[i], members[j] = members[j], members[i]
			}
		}
	}

	total := int64(len(members))

	// Pagination anwenden
	if filter.Offset > 0 && filter.Offset < len(members) {
		members = members[filter.Offset:]
	} else if filter.Offset >= len(members) {
		members = []Member{}
	}

	if filter.Limit > 0 && filter.Limit < len(members) {
		members = members[:filter.Limit]
	}

	return members, total, nil
}

// extractMembersFromJSON extrahiert Members aus dem Skool JSON-Format
func extractMembersFromJSON(entityID, rawJSON string, fetchedAt time.Time) []Member {
	var members []Member

	// Skool members format: pageProps.users[]
	var skoolData struct {
		PageProps struct {
			Group struct {
				ID string `json:"id"`
			} `json:"group"`
			Users []struct {
				ID       string `json:"id"`
				Name     string `json:"name"` // slug
				Metadata struct {
					Name        string `json:"name"`
					Picture     string `json:"picture"`
					LastOffline int64  `json:"lastOffline"`
					JoinedAt    int64  `json:"joinedAt"`
					Posts       int    `json:"posts"`
					Level       int    `json:"level"`
				} `json:"metadata"`
			} `json:"users"`
		} `json:"pageProps"`
	}

	if err := json.Unmarshal([]byte(rawJSON), &skoolData); err == nil {
		communityID := skoolData.PageProps.Group.ID
		// Fallback: entityID enthält oft communityId-page format
		if communityID == "" {
			communityID = entityID
		}

		for _, u := range skoolData.PageProps.Users {
			if u.ID == "" {
				continue
			}

			var joinedAt, lastOnline string
			if u.Metadata.JoinedAt > 0 {
				ts := u.Metadata.JoinedAt
				if ts > 1000000000000 {
					ts = ts / 1000
				}
				joinedAt = time.Unix(ts, 0).Format("2006-01-02")
			}
			if u.Metadata.LastOffline > 0 {
				ts := u.Metadata.LastOffline
				if ts > 1000000000000 {
					ts = ts / 1000
				}
				lastOnline = time.Unix(ts, 0).Format("2006-01-02T15:04:05")
			}

			members = append(members, Member{
				ID:          u.ID,
				Name:        u.Metadata.Name,
				Slug:        u.Name,
				Picture:     u.Metadata.Picture,
				CommunityID: communityID,
				JoinedAt:    joinedAt,
				LastOnline:  lastOnline,
				PostCount:   u.Metadata.Posts,
				Level:       u.Metadata.Level,
				FetchedAt:   fetchedAt,
			})
		}
	}

	return members
}

// matchesMemberFilter prüft ob ein Member den Filterkriterien entspricht
func matchesMemberFilter(m Member, filter MemberFilter) bool {
	// Community-Filter
	if len(filter.CommunityIDs) > 0 {
		found := false
		for _, cid := range filter.CommunityIDs {
			if m.CommunityID == cid {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// JoinedAt-Filter
	if filter.JoinedAfter != "" && m.JoinedAt != "" && m.JoinedAt < filter.JoinedAfter {
		return false
	}
	if filter.JoinedBefore != "" && m.JoinedAt != "" && m.JoinedAt > filter.JoinedBefore {
		return false
	}

	// PostCount-Filter
	if filter.PostCountMin > 0 && m.PostCount < filter.PostCountMin {
		return false
	}
	if filter.PostCountMax > 0 && m.PostCount > filter.PostCountMax {
		return false
	}

	// Level-Filter
	if filter.LevelMin > 0 && m.Level < filter.LevelMin {
		return false
	}

	return true
}

// === Community Selection ===

// Community repräsentiert eine extrahierte Community
type Community struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Slug        string    `json:"slug"`
	Description string    `json:"description,omitempty"`
	MemberCount int       `json:"memberCount"`
	PostCount   int       `json:"postCount"`
	Picture     string    `json:"picture,omitempty"`
	FetchedAt   time.Time `json:"fetchedAt"`
}

// CommunityFilter enthält Filter-Optionen für GetCommunities
type CommunityFilter struct {
	CommunityIDs   []string
	MemberCountMin int
	Limit          int
	Offset         int
}

// GetCommunities extrahiert Communities aus about_page und community_page Fetches
func (r *RawDB) GetCommunities(filter CommunityFilter) ([]Community, int64, error) {
	query := `
		WITH latest_fetches AS (
			SELECT entity_type, entity_id, raw_json, fetched_at,
				   ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY fetched_at DESC) as rn
			FROM raw_fetches
			WHERE entity_type IN ('about_page', 'community_page')
		)
		SELECT entity_type, entity_id, raw_json, fetched_at
		FROM latest_fetches
		WHERE rn = 1
		ORDER BY fetched_at DESC
	`

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, 0, fmt.Errorf("query error: %w", err)
	}
	defer rows.Close()

	// Map um Duplikate zu vermeiden (community_id -> Community)
	communitiesMap := make(map[string]Community)

	for rows.Next() {
		var entityType, entityID, rawJSON string
		var fetchedAt time.Time
		if err := rows.Scan(&entityType, &entityID, &rawJSON, &fetchedAt); err != nil {
			return nil, 0, err
		}

		// Community aus dem JSON extrahieren
		community := extractCommunityFromJSON(entityType, entityID, rawJSON, fetchedAt)
		if community == nil || community.ID == "" {
			continue
		}

		// Filter anwenden
		if !matchesCommunityFilter(*community, filter) {
			continue
		}

		// Nur den neuesten Stand behalten oder mergen
		if existing, ok := communitiesMap[community.ID]; ok {
			if community.FetchedAt.After(existing.FetchedAt) {
				// Merge: behalte bessere Daten
				if community.Description == "" && existing.Description != "" {
					community.Description = existing.Description
				}
				if community.MemberCount == 0 && existing.MemberCount > 0 {
					community.MemberCount = existing.MemberCount
				}
				communitiesMap[community.ID] = *community
			}
		} else {
			communitiesMap[community.ID] = *community
		}
	}

	if err := rows.Err(); err != nil {
		return nil, 0, err
	}

	// Map zu Slice konvertieren
	communities := make([]Community, 0, len(communitiesMap))
	for _, c := range communitiesMap {
		communities = append(communities, c)
	}

	// Nach Name sortieren
	for i := 0; i < len(communities)-1; i++ {
		for j := i + 1; j < len(communities); j++ {
			if communities[j].Name < communities[i].Name {
				communities[i], communities[j] = communities[j], communities[i]
			}
		}
	}

	total := int64(len(communities))

	// Pagination anwenden
	if filter.Offset > 0 && filter.Offset < len(communities) {
		communities = communities[filter.Offset:]
	} else if filter.Offset >= len(communities) {
		communities = []Community{}
	}

	if filter.Limit > 0 && filter.Limit < len(communities) {
		communities = communities[:filter.Limit]
	}

	return communities, total, nil
}

// extractCommunityFromJSON extrahiert eine Community aus dem JSON
func extractCommunityFromJSON(entityType, entityID, rawJSON string, fetchedAt time.Time) *Community {
	// Skool about_page format: pageProps.group
	var skoolData struct {
		PageProps struct {
			Group struct {
				ID       string `json:"id"`
				Name     string `json:"name"` // slug
				Metadata struct {
					Name        string `json:"name"`
					Description string `json:"description"`
					Picture     string `json:"picture"`
					Members     int    `json:"members"`
					Posts       int    `json:"posts"`
				} `json:"metadata"`
			} `json:"group"`
			PostTrees []interface{} `json:"postTrees"` // für PostCount aus community_page
		} `json:"pageProps"`
	}

	if err := json.Unmarshal([]byte(rawJSON), &skoolData); err != nil {
		return nil
	}

	g := skoolData.PageProps.Group
	if g.ID == "" {
		// Fallback: entityID als Community-ID verwenden
		return &Community{
			ID:        entityID,
			Slug:      entityID,
			FetchedAt: fetchedAt,
		}
	}

	postCount := g.Metadata.Posts
	if postCount == 0 && len(skoolData.PageProps.PostTrees) > 0 {
		postCount = len(skoolData.PageProps.PostTrees)
	}

	return &Community{
		ID:          g.ID,
		Name:        g.Metadata.Name,
		Slug:        g.Name,
		Description: g.Metadata.Description,
		MemberCount: g.Metadata.Members,
		PostCount:   postCount,
		Picture:     g.Metadata.Picture,
		FetchedAt:   fetchedAt,
	}
}

// matchesCommunityFilter prüft ob eine Community den Filterkriterien entspricht
func matchesCommunityFilter(c Community, filter CommunityFilter) bool {
	// Community-ID Filter
	if len(filter.CommunityIDs) > 0 {
		found := false
		for _, cid := range filter.CommunityIDs {
			if c.ID == cid || c.Slug == cid {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	// MemberCount-Filter
	if filter.MemberCountMin > 0 && c.MemberCount < filter.MemberCountMin {
		return false
	}

	return true
}

// === Activity Data ===

// ActivityData enthält die Heatmap- und Breakdown-Daten für Member-Aktivität
type ActivityData struct {
	Heatmap        [7][24]int      `json:"heatmap"` // 7 Tage x 24 Stunden
	DailyBreakdown []DailyActivity `json:"dailyBreakdown"`
	Total          int             `json:"total"`
}

type DailyActivity struct {
	Date    string `json:"date"`
	DayName string `json:"dayName"`
	Count   int    `json:"count"`
}

// GetMemberActivity extrahiert lastOffline-Daten aus members Fetches für die Heatmap
func (r *RawDB) GetMemberActivity(communityIDs []string, timezone string, days int) (*ActivityData, error) {
	// Hole alle members Fetches der letzten X Tage
	since := time.Now().AddDate(0, 0, -days)

	query := `
		SELECT raw_json, fetched_at
		FROM raw_fetches
		WHERE entity_type = 'members'
		  AND fetched_at >= ?
		ORDER BY fetched_at DESC
	`

	rows, err := r.db.Query(query, since)
	if err != nil {
		return nil, fmt.Errorf("query error: %w", err)
	}
	defer rows.Close()

	// Lade Timezone
	loc, err := time.LoadLocation(timezone)
	if err != nil {
		loc = time.UTC
	}

	// Sammle alle Aktivitäten
	// Map: date -> userId -> timestamp (um Duplikate pro User pro Tag zu vermeiden)
	activityByDay := make(map[string]map[string]time.Time)
	dayNames := []string{"Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"}

	for rows.Next() {
		var rawJSON string
		var fetchedAt time.Time
		if err := rows.Scan(&rawJSON, &fetchedAt); err != nil {
			continue
		}

		// Parse das JSON und extrahiere lastOffline Werte
		var data struct {
			PageProps struct {
				Users []struct {
					ID       string `json:"id"`
					Metadata struct {
						LastOffline int64  `json:"lastOffline"`
						Name        string `json:"name"`
					} `json:"metadata"`
				} `json:"users"`
			} `json:"pageProps"`
		}

		if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
			continue
		}

		for _, user := range data.PageProps.Users {
			lastOffline := user.Metadata.LastOffline
			if lastOffline <= 0 {
				continue
			}

			// Konvertiere Nanosekunden zu Sekunden falls nötig
			if lastOffline > 1000000000000 {
				lastOffline = lastOffline / 1_000_000_000
			}

			offlineTime := time.Unix(lastOffline, 0).In(loc)

			// Nur wenn innerhalb des Zeitraums
			if offlineTime.Before(since) {
				continue
			}

			dateKey := offlineTime.Format("2006-01-02")

			if activityByDay[dateKey] == nil {
				activityByDay[dateKey] = make(map[string]time.Time)
			}

			// Behalte die neueste Zeit pro User pro Tag
			if existing, ok := activityByDay[dateKey][user.ID]; ok {
				if offlineTime.After(existing) {
					activityByDay[dateKey][user.ID] = offlineTime
				}
			} else {
				activityByDay[dateKey][user.ID] = offlineTime
			}
		}
	}

	// Baue Heatmap und Daily Breakdown
	result := &ActivityData{}
	dailyMap := make(map[string]*DailyActivity)

	for dateKey, users := range activityByDay {
		for _, ts := range users {
			// Heatmap: dayOfWeek (0=Mo, 6=So) x hour
			dow := int(ts.Weekday())
			if dow == 0 {
				dow = 6 // Sonntag = 6
			} else {
				dow-- // Mo=0, Di=1, ...
			}
			hour := ts.Hour()
			result.Heatmap[dow][hour]++
			result.Total++

			// Daily Breakdown
			if dailyMap[dateKey] == nil {
				dayOfWeek := int(ts.Weekday())
				if dayOfWeek == 0 {
					dayOfWeek = 6
				} else {
					dayOfWeek--
				}
				dailyMap[dateKey] = &DailyActivity{
					Date:    dateKey,
					DayName: dayNames[dayOfWeek],
					Count:   0,
				}
			}
			dailyMap[dateKey].Count++
		}
	}

	// Sortiere Daily Breakdown nach Datum (absteigend)
	for _, da := range dailyMap {
		result.DailyBreakdown = append(result.DailyBreakdown, *da)
	}
	// Einfache Sortierung
	for i := 0; i < len(result.DailyBreakdown)-1; i++ {
		for j := i + 1; j < len(result.DailyBreakdown); j++ {
			if result.DailyBreakdown[j].Date > result.DailyBreakdown[i].Date {
				result.DailyBreakdown[i], result.DailyBreakdown[j] = result.DailyBreakdown[j], result.DailyBreakdown[i]
			}
		}
	}

	return result, nil
}

// === Connection Data ===

// ConnectionData enthält Nodes und Edges für den Verbindungsgraph
type ConnectionData struct {
	Members     []ConnectionMember `json:"members"`
	Connections []MemberConnection `json:"connections"`
}

type ConnectionMember struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Slug    string `json:"slug,omitempty"`
	Picture string `json:"picture,omitempty"`
}

type MemberConnection struct {
	From     string         `json:"from"`
	To       string         `json:"to"`
	FromName string         `json:"fromName"`
	ToName   string         `json:"toName"`
	Types    map[string]int `json:"types"` // like, comment -> count
	Count    int            `json:"count"`
}

// GetMemberConnections extrahiert Verbindungen zwischen Members aus Likes/Comments
func (r *RawDB) GetMemberConnections(communityIDs []string) (*ConnectionData, error) {
	result := &ConnectionData{
		Members:     []ConnectionMember{},
		Connections: []MemberConnection{},
	}

	// Map für Member-Info
	memberMap := make(map[string]*ConnectionMember)
	// Map für Connections: "from|to" -> Connection
	connectionMap := make(map[string]*MemberConnection)

	// 1. Lade alle Member aus members Fetches
	membersQuery := `
		WITH latest AS (
			SELECT entity_id, MAX(fetched_at) as max_fetched_at
			FROM raw_fetches
			WHERE entity_type = 'members'
			GROUP BY entity_id
		)
		SELECT r.raw_json
		FROM raw_fetches r
		INNER JOIN latest l ON r.entity_id = l.entity_id AND r.fetched_at = l.max_fetched_at
		WHERE r.entity_type = 'members'
	`

	rows, err := r.db.Query(membersQuery)
	if err != nil {
		return nil, fmt.Errorf("members query error: %w", err)
	}

	for rows.Next() {
		var rawJSON string
		if err := rows.Scan(&rawJSON); err != nil {
			continue
		}

		var data struct {
			PageProps struct {
				Users []struct {
					ID       string `json:"id"`
					Name     string `json:"name"` // slug
					Metadata struct {
						Name    string `json:"name"`
						Picture string `json:"picture"`
					} `json:"metadata"`
				} `json:"users"`
			} `json:"pageProps"`
		}

		if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
			continue
		}

		for _, user := range data.PageProps.Users {
			if user.ID == "" {
				continue
			}
			memberMap[user.ID] = &ConnectionMember{
				ID:      user.ID,
				Name:    user.Metadata.Name,
				Slug:    user.Name,
				Picture: user.Metadata.Picture,
			}
		}
	}
	rows.Close()

	// 2. Lade Likes aus likes Fetches
	likesQuery := `
		SELECT raw_json
		FROM raw_fetches
		WHERE entity_type = 'likes'
	`

	rows, err = r.db.Query(likesQuery)
	if err != nil {
		return nil, fmt.Errorf("likes query error: %w", err)
	}

	for rows.Next() {
		var rawJSON string
		if err := rows.Scan(&rawJSON); err != nil {
			continue
		}

		// Parse Likes - Struktur variiert je nach Fetch
		var likesData struct {
			PostID   string `json:"postId"`
			AuthorID string `json:"authorId"` // Post-Autor
			Likes    []struct {
				UserID string `json:"userId"`
			} `json:"likes"`
		}

		if err := json.Unmarshal([]byte(rawJSON), &likesData); err != nil {
			// Versuche alternatives Format
			var altData []struct {
				UserID string `json:"userId"`
				PostID string `json:"postId"`
			}
			if err := json.Unmarshal([]byte(rawJSON), &altData); err == nil {
				// Alternative Format verarbeiten falls vorhanden
				continue
			}
			continue
		}

		// Erstelle Verbindungen: Liker -> Post-Autor
		for _, like := range likesData.Likes {
			if like.UserID == "" || likesData.AuthorID == "" || like.UserID == likesData.AuthorID {
				continue
			}

			key := like.UserID + "|" + likesData.AuthorID
			if connectionMap[key] == nil {
				connectionMap[key] = &MemberConnection{
					From:  like.UserID,
					To:    likesData.AuthorID,
					Types: make(map[string]int),
				}
			}
			connectionMap[key].Types["like"]++
			connectionMap[key].Count++
		}
	}
	rows.Close()

	// 3. Lade Comments aus post_details Fetches
	commentsQuery := `
		SELECT raw_json
		FROM raw_fetches
		WHERE entity_type IN ('post_details', 'post_comments')
	`

	rows, err = r.db.Query(commentsQuery)
	if err != nil {
		return nil, fmt.Errorf("comments query error: %w", err)
	}

	for rows.Next() {
		var rawJSON string
		if err := rows.Scan(&rawJSON); err != nil {
			continue
		}

		// Parse Comments
		var postData struct {
			PageProps struct {
				Post struct {
					UserID   string `json:"userId"`
					Comments []struct {
						UserID string `json:"userId"`
					} `json:"comments"`
				} `json:"post"`
				CommentTrees []struct {
					Comment struct {
						UserID string `json:"userId"`
					} `json:"comment"`
				} `json:"commentTrees"`
			} `json:"pageProps"`
		}

		if err := json.Unmarshal([]byte(rawJSON), &postData); err != nil {
			continue
		}

		postAuthor := postData.PageProps.Post.UserID

		// Aus Comments
		for _, comment := range postData.PageProps.Post.Comments {
			if comment.UserID == "" || postAuthor == "" || comment.UserID == postAuthor {
				continue
			}

			key := comment.UserID + "|" + postAuthor
			if connectionMap[key] == nil {
				connectionMap[key] = &MemberConnection{
					From:  comment.UserID,
					To:    postAuthor,
					Types: make(map[string]int),
				}
			}
			connectionMap[key].Types["comment"]++
			connectionMap[key].Count++
		}

		// Aus CommentTrees
		for _, ct := range postData.PageProps.CommentTrees {
			if ct.Comment.UserID == "" || postAuthor == "" || ct.Comment.UserID == postAuthor {
				continue
			}

			key := ct.Comment.UserID + "|" + postAuthor
			if connectionMap[key] == nil {
				connectionMap[key] = &MemberConnection{
					From:  ct.Comment.UserID,
					To:    postAuthor,
					Types: make(map[string]int),
				}
			}
			connectionMap[key].Types["comment"]++
			connectionMap[key].Count++
		}
	}
	rows.Close()

	// Konvertiere Maps zu Arrays
	involvedMembers := make(map[string]bool)
	for _, conn := range connectionMap {
		// Namen hinzufügen
		if m, ok := memberMap[conn.From]; ok {
			conn.FromName = m.Name
		}
		if m, ok := memberMap[conn.To]; ok {
			conn.ToName = m.Name
		}

		involvedMembers[conn.From] = true
		involvedMembers[conn.To] = true
		result.Connections = append(result.Connections, *conn)
	}

	// Nur involvierte Members zurückgeben
	for id := range involvedMembers {
		if m, ok := memberMap[id]; ok {
			result.Members = append(result.Members, *m)
		}
	}

	// Sortiere Connections nach Count (absteigend)
	for i := 0; i < len(result.Connections)-1; i++ {
		for j := i + 1; j < len(result.Connections); j++ {
			if result.Connections[j].Count > result.Connections[i].Count {
				result.Connections[i], result.Connections[j] = result.Connections[j], result.Connections[i]
			}
		}
	}

	return result, nil
}
