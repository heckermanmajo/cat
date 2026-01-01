package fetchqueue

import (
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"time"

	"school-local-backend/db/duckdb"
)

// FetchType definiert die verschiedenen Fetch-Arten
type FetchType string

const (
	FetchTypeMembers           FetchType = "members"            // Primär: Member-Listen (paginiert)
	FetchTypeCommunityPage     FetchType = "community_page"     // Primär: Posts-Übersicht (paginiert)
	FetchTypePostDetails       FetchType = "post_details"       // Sekundär: Post-Details inkl. Kommentare
	FetchTypeLikes             FetchType = "likes"              // Sekundär: Post-Likes
	FetchTypeProfile           FetchType = "profile"            // Tertiär: Member-Profile
	FetchTypeAboutPage         FetchType = "about_page"         // Optional: Community About-Seite
	FetchTypeSharedCommunities FetchType = "shared_communities" // Erweitert: Communities mit gemeinsamen Members
)

// FetchPriority definiert die Priorität eines Fetches
// Niedrigere Werte = höhere Priorität
type FetchPriority int

const (
	PriorityCritical FetchPriority = 0 // Initiale Fetches, ohne die nichts geht
	PriorityHigh     FetchPriority = 1 // Primäre Fetches (Members, Posts)
	PriorityMedium   FetchPriority = 2 // Sekundäre Fetches (Details, Likes)
	PriorityLow      FetchPriority = 3 // Tertiäre Fetches (Profile)
	PriorityLowest   FetchPriority = 4 // Erweiterte Fetches (Shared Communities)
)

// FetchTask repräsentiert einen einzelnen Fetch-Auftrag
type FetchTask struct {
	ID            string                 `json:"id"`
	Type          FetchType              `json:"type"`
	Priority      FetchPriority          `json:"priority"`
	CommunityID   string                 `json:"communityId,omitempty"`
	EntityID      string                 `json:"entityId,omitempty"`
	Page          int                    `json:"page,omitempty"`
	Params        map[string]interface{} `json:"params,omitempty"`
	Reason        string                 `json:"reason"`
	LastFetchedAt *time.Time             `json:"lastFetchedAt,omitempty"`
}

// FetchQueue enthält die priorisierte Liste der nächsten Fetches
type FetchQueue struct {
	Tasks       []FetchTask `json:"tasks"`
	GeneratedAt time.Time   `json:"generatedAt"`
	TotalTasks  int         `json:"totalTasks"`
}

// QueueConfig enthält die Konfiguration für die Queue-Generierung
type QueueConfig struct {
	CommunityIDs             []string      // Zu überwachende Communities
	MaxTasksPerType          int           // Max Tasks pro Typ (0 = unbegrenzt)
	RefreshInterval          time.Duration // Wie oft sollen Daten refresht werden
	MembersPageSize          int           // Seitengröße für Members
	PostsPageSize            int           // Seitengröße für Posts
	FetchPostLikes           bool          // Ob Post-Likes gefetcht werden sollen
	FetchPostComments        bool          // Ob Post-Kommentare gefetcht werden sollen (via post_details)
	FetchMemberProfiles      bool          // Ob Member-Profile gefetcht werden sollen
	FetchSharedCommunities   bool          // Ob Shared Communities analysiert werden sollen
	MinSharedMembersForFetch int           // Mindestanzahl gemeinsamer Members für Community-Fetch
	StopOnOldData            bool          // Stoppt Pagination wenn alte Daten erreicht werden
}

// DefaultConfig gibt die Standard-Konfiguration zurück
func DefaultConfig() QueueConfig {
	return QueueConfig{
		MaxTasksPerType:          0, // Unbegrenzt
		RefreshInterval:          24 * time.Hour,
		MembersPageSize:          50,
		PostsPageSize:            20,
		FetchPostLikes:           true,
		FetchPostComments:        true,
		FetchMemberProfiles:      true,
		FetchSharedCommunities:   true,
		MinSharedMembersForFetch: 3, // Mindestens 3 gemeinsame Members
		StopOnOldData:            true,
	}
}

// CommunityWithSharedMembers repräsentiert eine Community mit Anzahl gemeinsamer Members
type CommunityWithSharedMembers struct {
	CommunityID   string   `json:"communityId"`
	CommunityName string   `json:"communityName"`
	SharedCount   int      `json:"sharedCount"`
	MemberIDs     []string `json:"memberIds,omitempty"`
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

// BuildQueue erstellt die aktuelle Fetch-Queue nach der neuen Hierarchie:
// 1. PRIMÄR: Members + Community Page (Posts) - inkrementell bis alte Daten
// 2. SEKUNDÄR: Post Details (Kommentare) + Likes für neue Posts
// 3. TERTIÄR: Profile für neue Members
// 4. ERWEITERT: Shared Communities (Communities mit vielen gemeinsamen Members)
func (qb *QueueBuilder) BuildQueue(communityIDs []string) (*FetchQueue, error) {
	queue := &FetchQueue{
		Tasks:       make([]FetchTask, 0),
		GeneratedAt: time.Now(),
	}

	// Sammle alle neuen Post-IDs und Member-IDs über alle Communities
	allNewPostIDs := make(map[string]string)     // postID -> communityID
	allNewMemberIDs := make(map[string]string)   // memberID -> communityID
	communityGroupIDs := make(map[string]string) // communityID (slug) -> groupId (Skool UUID)

	for _, communityID := range communityIDs {
		// Hole den letzten Fetch-Zeitpunkt für diese Community (Wasserzeichen)
		watermark := qb.getLastFetchWatermark(communityID)

		// ========================================
		// PHASE 1: PRIMÄRE FETCHES (Members + Posts)
		// ========================================

		// 1a. Members Pages - Inkrementell fetchen
		membersTasks, newMemberIDs, err := qb.buildMembersTasks(communityID, watermark)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, membersTasks...)
		for _, mid := range newMemberIDs {
			allNewMemberIDs[mid] = communityID
		}

		// 1b. Community Page (Posts) - Inkrementell fetchen
		postsTasks, newPostIDs, err := qb.buildPostsTasks(communityID, watermark)
		if err != nil {
			return nil, err
		}
		queue.Tasks = append(queue.Tasks, postsTasks...)
		for _, pid := range newPostIDs {
			allNewPostIDs[pid] = communityID
		}

		// Extrahiere groupId (Skool UUID) für diese Community aus den Posts
		// Wird für api2.skool.com API-Aufrufe benötigt (z.B. Likes)
		page1ID := communityID + "_page_1"
		if rawJSON, _, err := qb.rawDB.GetLatestFetch(string(FetchTypeCommunityPage), page1ID); err == nil {
			if groupID := qb.extractGroupID(rawJSON); groupID != "" {
				communityGroupIDs[communityID] = groupID
			}
		}
	}

	// ========================================
	// PHASE 2: SEKUNDÄRE FETCHES (Post Details + Likes)
	// ========================================

	// 2a. Post Details (inkl. Kommentare) für neue Posts
	if qb.config.FetchPostComments {
		for postID, communityID := range allNewPostIDs {
			groupID := communityGroupIDs[communityID] // Skool UUID für api2.skool.com
			detailsTasks := qb.buildPostDetailsTasks(communityID, postID, groupID)
			queue.Tasks = append(queue.Tasks, detailsTasks...)
		}
	}

	// 2b. Likes für neue Posts
	if qb.config.FetchPostLikes {
		for postID, communityID := range allNewPostIDs {
			groupID := communityGroupIDs[communityID] // Skool UUID für api2.skool.com
			likesTasks := qb.buildLikesTasks(communityID, postID, groupID)
			queue.Tasks = append(queue.Tasks, likesTasks...)
		}
	}

	// ========================================
	// PHASE 3: TERTIÄRE FETCHES (Member Profiles)
	// ========================================

	if qb.config.FetchMemberProfiles {
		for memberID, communityID := range allNewMemberIDs {
			profileTasks := qb.buildProfileTasks(communityID, memberID)
			queue.Tasks = append(queue.Tasks, profileTasks...)
		}
	}

	// ========================================
	// PHASE 4: ERWEITERTE FETCHES (Shared Communities)
	// ========================================

	if qb.config.FetchSharedCommunities {
		for _, communityID := range communityIDs {
			sharedTasks, err := qb.buildSharedCommunitiesTasks(communityID)
			if err != nil {
				// Fehler loggen aber nicht abbrechen
				continue
			}
			queue.Tasks = append(queue.Tasks, sharedTasks...)
		}
	}

	// Nach Priorität sortieren (stabil, damit Reihenfolge innerhalb gleicher Priorität erhalten bleibt)
	sort.SliceStable(queue.Tasks, func(i, j int) bool {
		return queue.Tasks[i].Priority < queue.Tasks[j].Priority
	})

	queue.TotalTasks = len(queue.Tasks)
	return queue, nil
}

// getLastFetchWatermark holt den Zeitpunkt des letzten vollständigen Fetches für eine Community
func (qb *QueueBuilder) getLastFetchWatermark(communityID string) time.Time {
	// Prüfe den neuesten Members-Fetch für diese Community
	page1ID := communityID + "_page_1"
	_, membersTime, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), page1ID)
	if err != nil {
		return time.Time{} // Kein vorheriger Fetch
	}

	// Prüfe auch den neuesten Community-Page-Fetch
	_, postsTime, err := qb.rawDB.GetLatestFetch(string(FetchTypeCommunityPage), page1ID)
	if err != nil {
		return membersTime
	}

	// Nimm den älteren der beiden als Wasserzeichen
	if membersTime.Before(postsTime) {
		return membersTime
	}
	return postsTime
}

// buildMembersTasks erstellt Tasks für Members-Fetches und gibt neue Member-IDs zurück
func (qb *QueueBuilder) buildMembersTasks(communityID string, watermark time.Time) ([]FetchTask, []string, error) {
	tasks := make([]FetchTask, 0)
	newMemberIDs := make([]string, 0)

	// Prüfe ob Page 1 existiert
	page1ID := communityID + "_page_1"
	rawJSON, lastFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), page1ID)

	if err != nil {
		// Noch nie gefetcht - CRITICAL Priority für initiale Daten
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeMembers, communityID, "page_1"),
			Type:        FetchTypeMembers,
			Priority:    PriorityCritical,
			CommunityID: communityID,
			Page:        1,
			Reason:      "Initiales Members-Fetch - noch keine Daten vorhanden",
		})
		return tasks, newMemberIDs, nil
	}

	// Prüfe ob Refresh nötig (älter als RefreshInterval)
	needsRefresh := time.Since(lastFetchedAt) > qb.config.RefreshInterval

	if needsRefresh {
		// Refresh nötig - HIGH Priority
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeMembers, communityID, "page_1"),
			Type:          FetchTypeMembers,
			Priority:      PriorityHigh,
			CommunityID:   communityID,
			Page:          1,
			Reason:        fmt.Sprintf("Members-Refresh fällig (letzter Fetch: %s)", lastFetchedAt.Format("2006-01-02 15:04")),
			LastFetchedAt: &lastFetchedAt,
		})
	}

	// Extrahiere Member-IDs aus existierenden Daten und prüfe auf neue Members
	existingMemberIDs, totalPages := qb.extractMemberInfo(rawJSON)

	// Identifiziere neue Members (die noch kein Profile haben)
	for _, memberID := range existingMemberIDs {
		entityID := communityID + "_" + memberID
		_, _, err := qb.rawDB.GetLatestFetch(string(FetchTypeProfile), entityID)
		if err != nil {
			// Profil noch nicht gefetcht - ist ein "neuer" Member
			newMemberIDs = append(newMemberIDs, memberID)
		}
	}

	// Prüfe weitere Pages
	for page := 2; page <= totalPages; page++ {
		pageID := communityID + "_page_" + strconv.Itoa(page)
		_, pageFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), pageID)

		if err != nil {
			// Page noch nicht gefetcht
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypeMembers, communityID, "page_"+strconv.Itoa(page)),
				Type:        FetchTypeMembers,
				Priority:    PriorityHigh,
				CommunityID: communityID,
				Page:        page,
				Reason:      fmt.Sprintf("Members Page %d noch nicht gefetcht", page),
			})
		} else if needsRefresh || time.Since(pageFetchedAt) > qb.config.RefreshInterval {
			// Page braucht Refresh
			tasks = append(tasks, FetchTask{
				ID:            generateTaskID(FetchTypeMembers, communityID, "page_"+strconv.Itoa(page)),
				Type:          FetchTypeMembers,
				Priority:      PriorityHigh,
				CommunityID:   communityID,
				Page:          page,
				Reason:        fmt.Sprintf("Members Page %d Refresh fällig", page),
				LastFetchedAt: &pageFetchedAt,
			})
		}

		// Limitierung falls konfiguriert
		if qb.config.MaxTasksPerType > 0 && len(tasks) >= qb.config.MaxTasksPerType {
			break
		}
	}

	return tasks, newMemberIDs, nil
}

// buildPostsTasks erstellt Tasks für Community-Page-Fetches und gibt neue Post-IDs zurück
func (qb *QueueBuilder) buildPostsTasks(communityID string, watermark time.Time) ([]FetchTask, []string, error) {
	tasks := make([]FetchTask, 0)
	newPostIDs := make([]string, 0)

	// Prüfe ob Page 1 existiert
	page1ID := communityID + "_page_1"
	rawJSON, lastFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeCommunityPage), page1ID)

	if err != nil {
		// Noch nie gefetcht - CRITICAL Priority
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeCommunityPage, communityID, "page_1"),
			Type:        FetchTypeCommunityPage,
			Priority:    PriorityCritical,
			CommunityID: communityID,
			Page:        1,
			Reason:      "Initiales Posts-Fetch - noch keine Daten vorhanden",
		})
		return tasks, newPostIDs, nil
	}

	// Prüfe ob Refresh nötig
	needsRefresh := time.Since(lastFetchedAt) > qb.config.RefreshInterval

	if needsRefresh {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeCommunityPage, communityID, "page_1"),
			Type:          FetchTypeCommunityPage,
			Priority:      PriorityHigh,
			CommunityID:   communityID,
			Page:          1,
			Reason:        fmt.Sprintf("Posts-Refresh fällig (letzter Fetch: %s)", lastFetchedAt.Format("2006-01-02 15:04")),
			LastFetchedAt: &lastFetchedAt,
		})
	}

	// Extrahiere Post-IDs und identifiziere neue Posts
	existingPostIDs := qb.extractPostIDs(rawJSON)

	for _, postID := range existingPostIDs {
		entityID := communityID + "_" + postID
		_, _, err := qb.rawDB.GetLatestFetch(string(FetchTypePostDetails), entityID)
		if err != nil {
			// Post-Details noch nicht gefetcht - ist ein "neuer" Post
			newPostIDs = append(newPostIDs, postID)
		}
	}

	return tasks, newPostIDs, nil
}

// buildPostDetailsTasks erstellt einen Task für Post-Details (inkl. Kommentare)
// groupID ist die Skool UUID (nicht der Slug) - wird für api2.skool.com benötigt
func (qb *QueueBuilder) buildPostDetailsTasks(communityID, postID, groupID string) []FetchTask {
	tasks := make([]FetchTask, 0)

	entityID := communityID + "_" + postID
	_, lastFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypePostDetails), entityID)

	// Params mit groupId für api2.skool.com API-Aufrufe
	params := map[string]interface{}{}
	if groupID != "" {
		params["groupId"] = groupID
	}

	if err != nil {
		// Noch nie gefetcht
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypePostDetails, communityID, postID),
			Type:        FetchTypePostDetails,
			Priority:    PriorityMedium,
			CommunityID: communityID,
			EntityID:    postID,
			Params:      params,
			Reason:      "Post-Details (Kommentare) noch nie gefetcht",
		})
	} else if time.Since(lastFetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypePostDetails, communityID, postID),
			Type:          FetchTypePostDetails,
			Priority:      PriorityMedium,
			CommunityID:   communityID,
			EntityID:      postID,
			Params:        params,
			Reason:        "Post-Details Refresh fällig",
			LastFetchedAt: &lastFetchedAt,
		})
	}

	return tasks
}

// buildLikesTasks erstellt einen Task für Post-Likes
// groupID ist die Skool UUID (nicht der Slug) - wird für api2.skool.com benötigt
func (qb *QueueBuilder) buildLikesTasks(communityID, postID, groupID string) []FetchTask {
	tasks := make([]FetchTask, 0)

	entityID := communityID + "_post_" + postID
	_, lastFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeLikes), entityID)

	// Params mit groupId für api2.skool.com API-Aufrufe
	params := map[string]interface{}{
		"targetType": "post",
	}
	if groupID != "" {
		params["groupId"] = groupID
	}

	if err != nil {
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeLikes, communityID, "post_"+postID),
			Type:        FetchTypeLikes,
			Priority:    PriorityMedium,
			CommunityID: communityID,
			EntityID:    postID,
			Params:      params,
			Reason:      "Post-Likes noch nie gefetcht",
		})
	} else if time.Since(lastFetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeLikes, communityID, "post_"+postID),
			Type:          FetchTypeLikes,
			Priority:      PriorityMedium,
			CommunityID:   communityID,
			EntityID:      postID,
			Params:        params,
			Reason:        "Post-Likes Refresh fällig",
			LastFetchedAt: &lastFetchedAt,
		})
	}

	return tasks
}

// buildProfileTasks erstellt einen Task für Member-Profile
func (qb *QueueBuilder) buildProfileTasks(communityID, memberID string) []FetchTask {
	tasks := make([]FetchTask, 0)

	entityID := communityID + "_" + memberID
	_, lastFetchedAt, err := qb.rawDB.GetLatestFetch(string(FetchTypeProfile), entityID)

	if err != nil {
		tasks = append(tasks, FetchTask{
			ID:          generateTaskID(FetchTypeProfile, communityID, memberID),
			Type:        FetchTypeProfile,
			Priority:    PriorityLow,
			CommunityID: communityID,
			EntityID:    memberID,
			Reason:      "Member-Profil noch nie gefetcht",
		})
	} else if time.Since(lastFetchedAt) > qb.config.RefreshInterval {
		tasks = append(tasks, FetchTask{
			ID:            generateTaskID(FetchTypeProfile, communityID, memberID),
			Type:          FetchTypeProfile,
			Priority:      PriorityLow,
			CommunityID:   communityID,
			EntityID:      memberID,
			Reason:        "Member-Profil Refresh fällig",
			LastFetchedAt: &lastFetchedAt,
		})
	}

	return tasks
}

// buildSharedCommunitiesTasks analysiert Member-Profile und erstellt Tasks für gemeinsame Communities
func (qb *QueueBuilder) buildSharedCommunitiesTasks(communityID string) ([]FetchTask, error) {
	tasks := make([]FetchTask, 0)

	// Hole alle Profile-Fetches für diese Community
	sharedCommunities, err := qb.analyzeSharedCommunities(communityID)
	if err != nil {
		return tasks, err
	}

	// Erstelle Tasks für Communities mit genug gemeinsamen Members
	for _, sc := range sharedCommunities {
		if sc.SharedCount < qb.config.MinSharedMembersForFetch {
			continue
		}

		// Prüfe ob wir diese Community schon fetchen
		_, _, err := qb.rawDB.GetLatestFetch(string(FetchTypeMembers), sc.CommunityID+"_page_1")
		if err != nil {
			// Community noch nicht gefetcht
			tasks = append(tasks, FetchTask{
				ID:          generateTaskID(FetchTypeSharedCommunities, communityID, sc.CommunityID),
				Type:        FetchTypeSharedCommunities,
				Priority:    PriorityLowest,
				CommunityID: sc.CommunityID,
				Params: map[string]interface{}{
					"sourceCommunity": communityID,
					"sharedCount":     sc.SharedCount,
					"communityName":   sc.CommunityName,
				},
				Reason: fmt.Sprintf("Community mit %d gemeinsamen Members", sc.SharedCount),
			})
		}
	}

	// Sortiere nach Anzahl gemeinsamer Members (absteigend)
	sort.SliceStable(tasks, func(i, j int) bool {
		countI := tasks[i].Params["sharedCount"].(int)
		countJ := tasks[j].Params["sharedCount"].(int)
		return countI > countJ
	})

	return tasks, nil
}

// analyzeSharedCommunities analysiert die Profile-Daten um gemeinsame Communities zu finden
func (qb *QueueBuilder) analyzeSharedCommunities(communityID string) ([]CommunityWithSharedMembers, error) {
	// Hole alle Profile-Fetches
	fetches, err := qb.rawDB.GetAllLatestByType(string(FetchTypeProfile))
	if err != nil {
		return nil, err
	}

	// Map: CommunityID -> Liste von MemberIDs
	communityMembers := make(map[string][]string)
	communityNames := make(map[string]string)

	for _, fetch := range fetches {
		// Nur Profile aus unserer Community betrachten
		if len(fetch.EntityID) <= len(communityID)+1 {
			continue
		}
		if fetch.EntityID[:len(communityID)] != communityID {
			continue
		}

		memberID := fetch.EntityID[len(communityID)+1:]

		// Communities aus dem Profil extrahieren
		var profileData struct {
			PageProps struct {
				User struct {
					Groups []struct {
						ID   string `json:"id"`
						Name string `json:"name"`
						Slug string `json:"slug"`
					} `json:"groups"`
				} `json:"user"`
			} `json:"pageProps"`
		}

		if err := json.Unmarshal([]byte(fetch.RawJSON), &profileData); err != nil {
			continue
		}

		for _, group := range profileData.PageProps.User.Groups {
			if group.ID == communityID || group.Slug == communityID {
				continue // Eigene Community überspringen
			}

			targetID := group.Slug
			if targetID == "" {
				targetID = group.ID
			}

			communityMembers[targetID] = append(communityMembers[targetID], memberID)
			if group.Name != "" {
				communityNames[targetID] = group.Name
			}
		}
	}

	// Konvertiere zu Ergebnis-Slice
	result := make([]CommunityWithSharedMembers, 0, len(communityMembers))
	for cid, members := range communityMembers {
		result = append(result, CommunityWithSharedMembers{
			CommunityID:   cid,
			CommunityName: communityNames[cid],
			SharedCount:   len(members),
			MemberIDs:     members,
		})
	}

	// Sortiere nach Anzahl (absteigend)
	sort.SliceStable(result, func(i, j int) bool {
		return result[i].SharedCount > result[j].SharedCount
	})

	return result, nil
}

// extractMemberInfo extrahiert Member-IDs und Gesamtseitenzahl aus Members-JSON
func (qb *QueueBuilder) extractMemberInfo(rawJSON string) ([]string, int) {
	memberIDs := make([]string, 0)
	totalPages := 1

	var data map[string]interface{}
	if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
		return memberIDs, totalPages
	}

	if pageProps, ok := data["pageProps"].(map[string]interface{}); ok {
		// Gesamtseitenzahl
		if tp, ok := pageProps["totalPages"].(float64); ok {
			totalPages = int(tp)
		}

		// Member-IDs
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

	return memberIDs, totalPages
}

// extractPostIDs extrahiert Post-IDs aus Community-Page-JSON
func (qb *QueueBuilder) extractPostIDs(rawJSON string) []string {
	postIDs := make([]string, 0)

	var data map[string]interface{}
	if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
		return postIDs
	}

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

	return postIDs
}

// extractGroupID extrahiert die Skool Group-ID (UUID) aus Community-Page-JSON
// Die groupId wird benötigt für api2.skool.com API-Aufrufe (z.B. Likes)
func (qb *QueueBuilder) extractGroupID(rawJSON string) string {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(rawJSON), &data); err != nil {
		return ""
	}

	// Try to get groupId from first post
	if pageProps, ok := data["pageProps"].(map[string]interface{}); ok {
		if postTrees, ok := pageProps["postTrees"].([]interface{}); ok {
			for _, pt := range postTrees {
				if tree, ok := pt.(map[string]interface{}); ok {
					if post, ok := tree["post"].(map[string]interface{}); ok {
						if groupId, ok := post["groupId"].(string); ok && groupId != "" {
							return groupId
						}
					}
				}
			}
		}
		// Fallback: try pageProps.groupId directly
		if groupId, ok := pageProps["groupId"].(string); ok && groupId != "" {
			return groupId
		}
		// Fallback: try pageProps.group.id
		if group, ok := pageProps["group"].(map[string]interface{}); ok {
			if groupId, ok := group["id"].(string); ok && groupId != "" {
				return groupId
			}
		}
	}

	return ""
}

// Helper: Task ID generieren
func generateTaskID(fetchType FetchType, communityID, suffix string) string {
	id := string(fetchType) + "_" + communityID
	if suffix != "" {
		id += "_" + suffix
	}
	return id
}

// GetSharedCommunities gibt die Shared-Communities-Analyse für eine Community zurück
// Dies kann vom Handler genutzt werden, um dem User die Analyse anzuzeigen
func (qb *QueueBuilder) GetSharedCommunities(communityID string) ([]CommunityWithSharedMembers, error) {
	return qb.analyzeSharedCommunities(communityID)
}
