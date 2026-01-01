import { useState, useEffect, useCallback } from 'react'
import { ThemeProvider } from './contexts/ThemeContext'
import SettingsView from './components/SettingsView'
import ChatView from './components/ChatView'
import ReportView from './components/ReportView'
import ThemeSelector from './components/ThemeSelector'
import './App.css'

type Tab = 'chat' | 'reports' | 'settings'

const VALID_TABS: Tab[] = ['chat', 'reports', 'settings']

function getTabFromHash(): Tab {
  const hash = window.location.hash.slice(1) // Remove '#'
  if (VALID_TABS.includes(hash as Tab)) {
    return hash as Tab
  }
  return 'chat'
}

function AppContent() {
  const [activeTab, setActiveTab] = useState<Tab>(getTabFromHash)

  // Update URL when tab changes
  const navigateToTab = useCallback((tab: Tab) => {
    setActiveTab(tab)
    window.location.hash = tab
  }, [])

  // Listen for browser back/forward navigation
  useEffect(() => {
    const handleHashChange = () => {
      setActiveTab(getTabFromHash())
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  return (
    <div className="app">
      <nav className="nav">
        <strong>CatKnows</strong>
        <span className="nav-sep">|</span>
        <button
          className={activeTab === 'chat' ? 'active' : ''}
          onClick={() => navigateToTab('chat')}
        >
          Chat
        </button>
        <button
          className={activeTab === 'reports' ? 'active' : ''}
          onClick={() => navigateToTab('reports')}
        >
          Reports
        </button>
        <span className="nav-spacer"></span>
        <ThemeSelector />
        <button
          className={`nav-settings ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => navigateToTab('settings')}
          title="Settings"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        </button>
      </nav>

      <main className="content">
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'reports' && <ReportView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  )
}

export default App
