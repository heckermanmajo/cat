import { useState } from 'react'
import { ThemeProvider } from './contexts/ThemeContext'
import LoggingView from './components/LoggingView'
import FetchesView from './components/FetchesView'
import FetchQueueView from './components/FetchQueueView'
import SettingsView from './components/SettingsView'
import ChatView from './components/ChatView'
import ReportView from './components/ReportView'
import DataView from './components/DataView'
import ThemeSelector from './components/ThemeSelector'
import './App.css'

type Tab = 'chat' | 'reports' | 'fetch-queue' | 'fetches' | 'data' | 'logs' | 'settings'

function AppContent() {
  const [activeTab, setActiveTab] = useState<Tab>('chat')

  return (
    <div className="app">
      <nav className="nav">
        <strong>CatKnows</strong>
        <span className="nav-sep">|</span>
        <button
          className={activeTab === 'chat' ? 'active' : ''}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button
          className={activeTab === 'reports' ? 'active' : ''}
          onClick={() => setActiveTab('reports')}
        >
          Reports
        </button>
        <button
          className={activeTab === 'fetch-queue' ? 'active' : ''}
          onClick={() => setActiveTab('fetch-queue')}
        >
          Fetch Queue
        </button>
        <button
          className={activeTab === 'fetches' ? 'active' : ''}
          onClick={() => setActiveTab('fetches')}
        >
          Fetches
        </button>
        <button
          className={activeTab === 'data' ? 'active' : ''}
          onClick={() => setActiveTab('data')}
        >
          Data View
        </button>
        <button
          className={activeTab === 'logs' ? 'active' : ''}
          onClick={() => setActiveTab('logs')}
        >
          Logs
        </button>
        <button
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <span className="nav-spacer"></span>
        <ThemeSelector />
      </nav>

      <main className="content">
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'reports' && <ReportView />}
        {activeTab === 'fetch-queue' && <FetchQueueView />}
        {activeTab === 'fetches' && <FetchesView />}
        {activeTab === 'data' && <DataView />}
        {activeTab === 'logs' && <LoggingView />}
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
