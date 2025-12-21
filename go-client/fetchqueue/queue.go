package fetchqueue

import (
	"encoding/json"
	"time"

	"school-local-backend/db/duckdb"
)

// FetchType definiert die verschiedenen Fetch-Arten
type FetchType string

const (
	FetchTypeAboutPage     FetchType = "about_page"
	FetchTypeProfile       FetchType = "profile"
	FetchTypeMembers       FetchType = "members"
	FetchTypeCommunityPage FetchType = "community_page"
	FetchTypePostDetails   FetchType = "post_details"
	FetchTypeLikes         FetchType = "likes"
)

// FetchPriority definiert die Priorität eines Fetches
type FetchPriority int

const (
	PriorityHigh   FetchPriority = 1
	PriorityMedium FetchPriority = 2
	PriorityLow    FetchPriority = 3
)

// FetchTask repräsentiert einen einzelnen Fetch-Auftrag
type FetchTask struct {
	ID           string                 `json:"id"`
	Type         FetchType              `json:"type"`
	Priority     FetchPriority          `json:"priority"`
	CommunityID  string                 `json:"communityId,omitempty"`
	EntityID     string                 `json:"entityId,omitempty"`
	Page         int                    `json:"page,omitempty"`
	Params       map[string]interface{} `json:"params,omitempty"`
	Reason       string                 `json:"reason"`
	LastFetchedAt *time.Time            `json:"lastFetchedAt,omitempty"`
}

// FetchQueue enthält die priorisierte Liste der nächsten Fetches
type FetchQueue struct {
	Tasks       []FetchTask `json:"tasks"`
	GeneratedAt time.Time   `json:"generatedAt"`
	TotalTasks  int         `json:"totalTasks"`
}

// QueueConfig enthält die Konfiguration für die Queue-Generierung
type QueueConfig struct {
	CommunityIDs        []string      // Zu überwachende Communities
	MaxTasksPerType     int           // Max Tasks pro Typ
	RefreshInterval     time.Duration // Wie oft sollen Daten refresht werden
	MembersPageSize     int           // Seitengröße für Members
	PostsPageSize       int           // Seitengröße für Posts
	FetchPostLikes      bool          // Ob Post-Likes gefetcht werden sollen
}

// DefaultConfig gibt die Standard-Konfiguration zurück
func DefaultConfig() QueueConfig {
	return QueueConfig{
		MaxTasksPerType:  10,
		RefreshInterval:  24 * time.Hour,
		MembersPageSize:  50,
		PostsPageSize:    20,
		FetchPostLikes:   true,
	}
}

// QueueBuilder baut die Fetch-Queue basierend auf dem aktuellen Datenstand
type QueueBuilder struct {
	rawDB  *duckdb.RawDB
	config QueueConfig
}

// NewQueueBuilder erstellt einen neuen QueueBuilder
func NewQueueBuilder(rawDB *duckdb.RawDB, config QueueConfig) *QueueBuilder {
	return &QueueBuilder{
		rawDB:  rawDB,
		config: config,
	}
}

// BuildQueue erstellt die aktuelle Fetch-Queue
func (qb *QueueBuilder) BuildQueue(communityIDs []string) (*FetchQueue, error) {
	queue := &FetchQueue{
		Tasks:       make([]FetchTask, 0),
		GeneratedAt: time.Now(),
	}

	for _, communityID := range communityIDs {
		// 1. About Page prüfen
		aboutTasks, err := qb.checkAboutPage(communityID)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, aboutTasks...)

		// 2. Members Pages prüfen
		membersTasks, err := qb.checkMembersPages(communityID)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, membersTasks...)

		// 3. Community Page (Posts) prüfen
		postsTasks, err := qb.checkCommunityPage(communityID)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, postsTasks...)

		// 4. Profile Pages für bekannte Members prüfen
		profileTasks, err := qb.checkProfiles(communityID)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, profileTasks...)

		// 5. Post Details für bekannte Posts prüfen
		detailsTasks, err := qb.checkPostDetails(communityID)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, detailsTasks...)

		// 6. Likes für Posts prüfen
		if qb.config.FetchPostLikes {
			likesTasks, err := qb.checkLikes(communityID)
			if err != nil {
				return nil, err
			}
			queue.Tasks = append(queue.Tasks, likesTasks...)
		}
	}

	// Nach Priorität sortieren
	qb.sortByPriority(queue.Tasks)

	queue.TotalTasks = len(queue.Tasks)
	return queue, nil
}

// checkAboutPage prüft ob die About Page gefetcht werden muss
func (qb *QueueBuilder) checkAboutPage(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Prüfen ob wir bereits einen About Page Fetch haben
	_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeAboutPage), communityID)
	if err != nil {
		// Kein Fetch vorhanden - muss gefetcht werden
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeAboutPage, communityID, ""),
			Type:        FetchTypeAboutPage,
			Priority:    PriorityHigh,
			CommunityID: communityID,
			Reason:      "About Page noch nie gefetcht",
		})
		return tasks, nil
	}

	// Prüfen ob Refresh nötig
	if time.Since(fetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeAboutPage, communityID, ""),
			Type:          FetchTypeAboutPage,
			Priority:      PriorityMedium,
			CommunityID:   communityID,
			Reason:        "About Page Refresh fällig",
			LastFetchedAt: &fetchedAt,
		})
	}

	return tasks, nil
}

// checkMembersPages prüft welche Members Pages gefetcht werden müssen
func (qb *QueueBuilder) checkMembersPages(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Prüfen ob wir Page 1 haben
	page1ID := communityID + "_page_1"
	_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), page1ID)
	if err != nil {
		// Erste Members Page muss gefetcht werden
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeMembers, communityID, "page_1"),
			Type:        FetchTypeMembers,
			Priority:    PriorityHigh,
			CommunityID: communityID,
			Page:        1,
			Reason:      "Members Page 1 noch nie gefetcht",
		})
		return tasks, nil
	}

	// Aus Page 1 die Gesamtzahl und weitere Pages ermitteln
	totalPages, err := qb.getTotalMembersPages(communityID)
	if err != nil {
		totalPages = 1 // Fallback
	}

	// Prüfen ob Refresh der ersten Seite nötig
	if time.Since(fetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeMembers, communityID, "page_1"),
			Type:          FetchTypeMembers,
			Priority:      PriorityMedium,
			CommunityID:   communityID,
			Page:          1,
			Reason:        "Members Page 1 Refresh fällig",
			LastFetchedAt: &fetchedAt,
		})
	}

	// Weitere Pages prüfen
	for page := 2; page <= totalPages && page <= qb.config.MaxTasksPerType; page++ {
		pageID := communityID + "_page_" + string(rune('0'+page))
		_, _, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), pageID)
		if err != nil {
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypeMembers, communityID, "page_"+string(rune('0'+page))),
				Type:        FetchTypeMembers,
				Priority:    PriorityMedium,
				CommunityID: communityID,
				Page:        page,
				Reason:      "Members Page noch nicht gefetcht",
			})
		}
	}

	return tasks, nil
}

// checkCommunityPage prüft ob die Community Page (Posts) gefetcht werden muss
func (qb *QueueBuilder) checkCommunityPage(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Prüfen ob Page 1 vorhanden
	page1ID := communityID + "_page_1"
	_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeCommunityPage), page1ID)
	if err != nil {
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeCommunityPage, communityID, "page_1"),
			Type:        FetchTypeCommunityPage,
			Priority:    PriorityHigh,
			CommunityID: communityID,
			Page:        1,
			Reason:      "Community Posts Page 1 noch nie gefetcht",
		})
		return tasks, nil
	}

	// Refresh prüfen
	if time.Since(fetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeCommunityPage, communityID, "page_1"),
			Type:          FetchTypeCommunityPage,
			Priority:      PriorityMedium,
			CommunityID:   communityID,
			Page:          1,
			Reason:        "Community Posts Refresh fällig",
			LastFetchedAt: &fetchedAt,
		})
	}

	return tasks, nil
}

// checkProfiles prüft welche Profile Pages gefetcht werden müssen
func (qb *QueueBuilder) checkProfiles(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Member IDs aus den Members-Fetches extrahieren
	memberIDs, err := qb.getMemberIDsFromFetches(communityID)
	if err != nil || len(memberIDs) == 0 {
		return tasks, nil
	}

	// Für jeden Member prüfen ob Profile gefetcht wurde
	count := 0
	for _, memberID := range memberIDs {
		if count >= qb.config.MaxTasksPerType {
			break
		}

		entityID := communityID + "_" + memberID
		_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeProfile), entityID)
		if err != nil {
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypeProfile, communityID, memberID),
				Type:        FetchTypeProfile,
				Priority:    PriorityLow,
				CommunityID: communityID,
				EntityID:    memberID,
				Reason:      "Member Profil noch nie gefetcht",
			})
			count++
		} else if time.Since(fetchedAt) > qb.config.RefreshInterval {
			tasks = append(tasks, FetchTask{
				ID:            generateTaskID(FetchTypeProfile, communityID, memberID),
				Type:          FetchTypeProfile,
				Priority:      PriorityLow,
				CommunityID:   communityID,
				EntityID:      memberID,
				Reason:        "Member Profil Refresh fällig",
				LastFetchedAt: &fetchedAt,
			})
			count++
		}
	}

	return tasks, nil
}

// checkPostDetails prüft welche Post Details gefetcht werden müssen
func (qb *QueueBuilder) checkPostDetails(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Post IDs aus den Community Page Fetches extrahieren
	postIDs, err := qb.getPostIDsFromFetches(communityID)
	if err != nil || len(postIDs) == 0 {
		return tasks, nil
	}

	// Für jeden Post prüfen ob Details gefetcht wurden
	count := 0
	for _, postID := range postIDs {
		if count >= qb.config.MaxTasksPerType {
			break
		}

		entityID := communityID + "_" + postID
		_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypePostDetails), entityID)
		if err != nil {
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypePostDetails, communityID, postID),
				Type:        FetchTypePostDetails,
				Priority:    PriorityMedium,
				CommunityID: communityID,
				EntityID:    postID,
				Reason:      "Post Details noch nie gefetcht",
			})
			count++
		} else if time.Since(fetchedAt) > qb.config.RefreshInterval {
			tasks = append(tasks, FetchTask{
				ID:            generateTaskID(FetchTypePostDetails, communityID, postID),
				Type:          FetchTypePostDetails,
				Priority:      PriorityLow,
				CommunityID:   communityID,
				EntityID:      postID,
				Reason:        "Post Details Refresh fällig",
				LastFetchedAt: &fetchedAt,
			})
			count++
		}
	}

	return tasks, nil
}

// checkLikes prüft welche Post Likes gefetcht werden müssen
func (qb *QueueBuilder) checkLikes(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Post IDs aus den Community Page Fetches extrahieren
	postIDs, err := qb.getPostIDsFromFetches(communityID)
	if err != nil || len(postIDs) == 0 {
		return tasks, nil
	}

	// Für jeden Post prüfen ob Likes gefetcht wurden
	count := 0
	for _, postID := range postIDs {
		if count >= qb.config.MaxTasksPerType {
			break
		}

		entityID := communityID + "_post_" + postID
		_, fetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeLikes), entityID)
		if err != nil {
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypeLikes, communityID, "post_"+postID),
				Type:        FetchTypeLikes,
				Priority:    PriorityLow,
				CommunityID: communityID,
				EntityID:    postID,
				Params:      map[string]interface{}{"targetType": "post"},
				Reason:      "Post Likes noch nie gefetcht",
			})
			count++
		} else if time.Since(fetchedAt) > qb.config.RefreshInterval {
			tasks = append(tasks, FetchTask{
				ID:            generateTaskID(FetchTypeLikes, communityID, "post_"+postID),
				Type:          FetchTypeLikes,
				Priority:      PriorityLow,
				CommunityID:   communityID,
				EntityID:      postID,
				Params:        map[string]interface{}{"targetType": "post"},
				Reason:        "Post Likes Refresh fällig",
				LastFetchedAt: &fetchedAt,
			})
			count++
		}
	}

	return tasks, nil
}

// Helper: Task ID generieren
func generateTaskID(fetchType FetchType, communityID, suffix string) string {
	id := string(fetchType) + "_" + communityID
	if suffix != "" {
		id += "_" + suffix
	}
	return id
}

// Helper: Tasks nach Priorität sortieren
func (qb *QueueBuilder) sortByPriority(tasks []FetchTask) {
	// Simple Bubble Sort für kleine Listen
	for i := 0; i < len(tasks); i++ {
		for j := i + 1; j < len(tasks); j++ {
			if tasks[j].Priority < tasks[i].Priority {
				tasks[i], tasks[j] = tasks[j], tasks[i]
			}
		}
	}
}

// Helper: Member IDs aus Fetches extrahieren
func (qb *QueueBuilder) getMemberIDsFromFetches(communityID string) ([]string, error) {
	fetches, err := qb.rawDB.GetAllLatestByType(string(FetchTypeMembers))
	if err != nil {
		return nil, err
	}

	memberIDs := make([]string, 0)
	for _, fetch := range fetches {
		// JSON parsen und Member IDs extrahieren
		var data map[string]interface{}
		if err := json.Unmarshal([]byte(fetch.RawJSON), &data); err != nil {
			continue
		}

		// pageProps.users oder pageProps.renderData.members
		if pageProps, ok := data["pageProps"].(map[string]interface{}); ok {
			if users, ok := pageProps["users"].([]interface{}); ok {
				for _, user := range users {
					if u, ok := user.(map[string]interface{}); ok {
						if id, ok := u["id"].(string); ok {
							memberIDs = append(memberIDs, id)
						}
					}
				}
			}
		}
	}

	return memberIDs, nil
}

// Helper: Post IDs aus Fetches extrahieren
func (qb *QueueBuilder) getPostIDsFromFetches(communityID string) ([]string, error) {
	fetches, err := qb.rawDB.GetAllLatestByType(string(FetchTypeCommunityPage))
	if err != nil {
		return nil, err
	}

	postIDs := make([]string, 0)
	for _, fetch := range fetches {
		var data map[string]interface{}
		if err := json.Unmarshal([]byte(fetch.RawJSON), &data); err != nil {
			continue
		}

		// pageProps.postTrees
		if pageProps, ok := data["pageProps"].(map[string]interface{}); ok {
			if postTrees, ok := pageProps["postTrees"].([]interface{}); ok {
				for _, pt := range postTrees {
					if tree, ok := pt.(map[string]interface{}); ok {
						if post, ok := tree["post"].(map[string]interface{}); ok {
							if id, ok := post["id"].(string); ok {
								postIDs = append(postIDs, id)
							}
						}
					}
				}
			}
		}
	}

	return postIDs, nil
}

// Helper: Gesamtzahl der Members Pages ermitteln
func (qb *QueueBuilder) getTotalMembersPages(communityID string) (int, error) {
	page1ID := communityID + "_page_1"
	rawJSON, _, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), page1ID)
	if err != nil {
		return 1, err
	}

	var data map[string]interface{}
	if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
		return 1, err
	}

	if pageProps, ok := data["pageProps"].(map[string]interface{}); ok {
		if totalPages, ok := pageProps["totalPages"].(float64); ok {
			return int(totalPages), nil
		}
	}

	return 1, nil
}
