import { useState, useEffect, useRef } from 'react'
import SelectionCard from './SelectionCard'
import PromptTemplatePanel from './PromptTemplatePanel'
import './ChatView.css'

const API_BASE = '/api'

// Ausklappbare Selektion im Report-Panel
function SelectionReportCard({ selectionId }: { selectionId: number }) {
  const [selection, setSelection] = useState<Selection | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const [posts, setPosts] = useState<Post[]>([])
  const [postsLoading, setPostsLoading] = useState(false)
  const [postsLoaded, setPostsLoaded] = useState(false)

  useEffect(() => {
    const loadSelection = async () => {
      try {
        const res = await fetch(`${API_BASE}/selection?id=${selectionId}`)
        if (res.ok) {
          const data = await res.json()
          setSelection(data)
        }
      } catch (err) {
        console.error('Failed to load selection:', err)
      } finally {
        setLoading(false)
      }
    }
    loadSelection()
  }, [selectionId])

  // Lade Posts wenn aufgeklappt
  useEffect(() => {
    if (expanded && !postsLoaded && selection?.outputType === 'post') {
      const loadPosts = async () => {
        setPostsLoading(true)
        try {
          const res = await fetch(`${API_BASE}/selection/execute?id=${selectionId}`)
          if (res.ok) {
            const data = await res.json()
            setPosts(data.posts || [])
            setPostsLoaded(true)
          }
        } catch (err) {
          console.error('Failed to load posts:', err)
        } finally {
          setPostsLoading(false)
        }
      }
      loadPosts()
    }
  }, [expanded, postsLoaded, selection?.outputType, selectionId])

  if (loading) {
    return <div className="selection-report-loading">Lade Selektion...</div>
  }

  if (!selection) {
    return <div className="selection-report-error">Selektion nicht gefunden</div>
  }

  const filters = (() => {
    try {
      return JSON.parse(selection.filtersJson)
    } catch {
      return {}
    }
  })()
  const filterEntries = Object.entries(filters).filter(([_, v]) => v !== null && v !== undefined && v !== '')

  return (
    <div className={`selection-report-card ${expanded ? 'expanded' : ''}`}>
      <div className="selection-report-header" onClick={() => setExpanded(!expanded)}>
        <span className="selection-type-badge">{selection.outputType}</span>
        <span className="selection-name">{selection.name}</span>
        <span className="selection-count">{selection.resultCount} Ergebnisse</span>
        <span className="expand-icon">{expanded ? '\u25BC' : '\u25B6'}</span>
      </div>

      {expanded && (
        <div className="selection-report-details">
          {/* Filter anzeigen */}
          {filterEntries.length > 0 && (
            <div className="selection-report-filters">
              <strong>Filter:</strong>
              {filterEntries.map(([key, value]) => (
                <span key={key} className="filter-tag">
                  {key}: {Array.isArray(value) ? value.join(', ') : String(value)}
                </span>
              ))}
            </div>
          )}

          {/* Ergebnisse anzeigen */}
          <div className="selection-report-results">
            {postsLoading ? (
              <p className="loading-hint">Lade Ergebnisse...</p>
            ) : posts.length > 0 ? (
              <div className="posts-preview">
                {posts.slice(0, 5).map(post => (
                  <div key={post.id} className="post-preview-item">
                    <span className="post-title">{post.title || '(Kein Titel)'}</span>
                    <span className="post-meta">{post.likes} Likes</span>
                  </div>
                ))}
                {posts.length > 5 && (
                  <p className="more-hint">+ {posts.length - 5} weitere</p>
                )}
              </div>
            ) : selection.outputType !== 'post' ? (
              <p className="type-hint">{selection.outputType === 'member' ? 'Mitglieder-Selektion' : 'Community-Selektion'}</p>
            ) : (
              <p className="no-results">Keine Ergebnisse</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface Post {
  id: string
  title: string
  content: string
  authorId: string
  authorName: string
  communityId: string
  likes: number
  comments: number
  createdAt: string
}

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
  parentId?: number
  derivedSelections?: Selection[]
}

interface Message {
  id: number
  chatId: number
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  selections?: Selection[]
}

interface Chat {
  id: number
  title: string
  archived: boolean
  createdAt: string
  updatedAt: string
}

interface ReportBlock {
  id: number
  reportId: number
  blockType: 'text' | 'selection'
  position: number
  content?: string
  selectionId?: number
  viewType: string
  createdAt: string
}

interface Report {
  id: number
  name: string
  createdAt: string
  blocks: ReportBlock[]
}

export function ChatView() {
  const [chats, setChats] = useState<Chat[]>([])
  const [activeChat, setActiveChat] = useState<Chat | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [chatReport, setChatReport] = useState<Report | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [addingToReport, setAddingToReport] = useState<number | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [editingChatId, setEditingChatId] = useState<number | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [newChatTitle, setNewChatTitle] = useState('')
  const [showNewChatInput, setShowNewChatInput] = useState(false)
  const [openMenuChatId, setOpenMenuChatId] = useState<number | null>(null)
  const [showTemplates, setShowTemplates] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const newChatInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Load all chats when showArchived changes
  useEffect(() => {
    loadChats()
  }, [showArchived])

  // Focus new chat input when shown
  useEffect(() => {
    if (showNewChatInput && newChatInputRef.current) {
      newChatInputRef.current.focus()
    }
  }, [showNewChatInput])

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuChatId(null)
      }
    }
    if (openMenuChatId !== null) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [openMenuChatId])

  // Load messages and report when active chat changes
  useEffect(() => {
    if (activeChat) {
      loadMessages(activeChat.id)
      loadChatReport(activeChat.id)
    } else {
      setMessages([])
      setChatReport(null)
    }
  }, [activeChat?.id])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadChats = async () => {
    try {
      const url = showArchived
        ? `${API_BASE}/chats?archived=true`
        : `${API_BASE}/chats?archived=false`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setChats(data)
        // Select most recent chat if none selected and we have chats
        if (data.length > 0 && !activeChat) {
          setActiveChat(data[0])
        }
        // Clear active chat if it's not in the current list
        if (activeChat && !data.find((c: Chat) => c.id === activeChat.id)) {
          setActiveChat(data.length > 0 ? data[0] : null)
        }
      }
    } catch (err) {
      console.error('Failed to load chats:', err)
    }
  }

  const loadMessages = async (chatId: number) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/messages?chatId=${chatId}`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data)
      }
    } catch (err) {
      console.error('Failed to load messages:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadChatReport = async (chatId: number) => {
    setReportLoading(true)
    try {
      const res = await fetch(`${API_BASE}/chat/report?chatId=${chatId}`)
      if (res.ok) {
        const data = await res.json()
        setChatReport(data.report || null)
      }
    } catch (err) {
      console.error('Failed to load chat report:', err)
    } finally {
      setReportLoading(false)
    }
  }

  const addSelectionToReport = async (selectionId: number) => {
    if (!activeChat || addingToReport) return

    setAddingToReport(selectionId)
    try {
      const res = await fetch(`${API_BASE}/chat/add-to-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chatId: activeChat.id,
          selectionId: selectionId
        })
      })

      if (res.ok) {
        // Reload report to show new block
        await loadChatReport(activeChat.id)
      }
    } catch (err) {
      console.error('Failed to add to report:', err)
    } finally {
      setAddingToReport(null)
    }
  }

  const createNewChat = async (title?: string) => {
    const chatTitle = title?.trim() || 'New Chat'
    try {
      const res = await fetch(`${API_BASE}/chats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: chatTitle })
      })
      if (res.ok) {
        const chat = await res.json()
        setChats(prev => [chat, ...prev])
        setActiveChat(chat)
        setMessages([])
        setShowNewChatInput(false)
        setNewChatTitle('')
      }
    } catch (err) {
      console.error('Failed to create chat:', err)
    }
  }

  const handleNewChatSubmit = () => {
    createNewChat(newChatTitle)
  }

  const handleNewChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleNewChatSubmit()
    } else if (e.key === 'Escape') {
      setShowNewChatInput(false)
      setNewChatTitle('')
    }
  }

  const updateChatTitle = async (chatId: number, newTitle: string) => {
    if (!newTitle.trim()) return
    try {
      const res = await fetch(`${API_BASE}/chat?id=${chatId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle.trim() })
      })
      if (res.ok) {
        const updatedChat = await res.json()
        setChats(prev => prev.map(c => c.id === chatId ? updatedChat : c))
        if (activeChat?.id === chatId) {
          setActiveChat(updatedChat)
        }
      }
    } catch (err) {
      console.error('Failed to update chat:', err)
    }
    setEditingChatId(null)
    setEditingTitle('')
  }

  const startEditingChat = (chat: Chat, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingChatId(chat.id)
    setEditingTitle(chat.title)
  }

  const handleEditKeyDown = (e: React.KeyboardEvent, chatId: number) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      updateChatTitle(chatId, editingTitle)
    } else if (e.key === 'Escape') {
      setEditingChatId(null)
      setEditingTitle('')
    }
  }

  const archiveChat = async (chatId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const res = await fetch(`${API_BASE}/chat/archive?id=${chatId}`, {
        method: 'POST'
      })
      if (res.ok) {
        // Remove from current list (will appear in the other list)
        setChats(prev => prev.filter(c => c.id !== chatId))
        if (activeChat?.id === chatId) {
          setActiveChat(null)
        }
      }
    } catch (err) {
      console.error('Failed to archive chat:', err)
    }
  }

  const deleteChat = async (chatId: number) => {
    if (!confirm('Really delete chat?')) return
    try {
      const res = await fetch(`${API_BASE}/chat?id=${chatId}`, { method: 'DELETE' })
      if (res.ok) {
        setChats(prev => prev.filter(c => c.id !== chatId))
        if (activeChat?.id === chatId) {
          setActiveChat(null)
        }
      }
    } catch (err) {
      console.error('Failed to delete chat:', err)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !activeChat || sending) return

    const userMessage = input.trim()
    setInput('')
    setSending(true)

    // Optimistic update - add user message immediately
    const tempUserMsg: Message = {
      id: -1,
      chatId: activeChat.id,
      role: 'user',
      content: userMessage,
      createdAt: new Date().toISOString()
    }
    setMessages(prev => [...prev, tempUserMsg])

    try {
      const res = await fetch(`${API_BASE}/messages?chatId=${activeChat.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: userMessage })
      })

      if (res.ok) {
        // Reload all messages to get the real IDs and assistant response
        await loadMessages(activeChat.id)
      }
    } catch (err) {
      console.error('Failed to send message:', err)
      // Remove the optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== -1))
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // Handler zum Einfuegen von Template-Text in das Input-Feld
  const handleInsertTemplate = (text: string) => {
    setInput(prev => prev + (prev ? '\n' : '') + text)
  }

  const copyChat = async (chat: Chat) => {
    // Fetch messages for the chat
    try {
      const res = await fetch(`${API_BASE}/messages?chatId=${chat.id}`)
      if (!res.ok) {
        alert('Failed to load messages')
        return
      }
      const chatMessages: Message[] = await res.json()

      if (chatMessages.length === 0) {
        alert('Chat is empty')
        return
      }

      const lines: string[] = []
      lines.push(`=== Chat: ${chat.title} ===`)
      lines.push(`Created: ${chat.createdAt}`)
      lines.push('')

      for (const msg of chatMessages) {
        const role = msg.role === 'user' ? 'User' : 'Assistant'
        lines.push(`[${role}]:`)
        lines.push(msg.content)

        // Include selections if present
        if (msg.selections && msg.selections.length > 0) {
          lines.push('')
          lines.push('  Selections:')
          for (const sel of msg.selections) {
            lines.push(`    - ${sel.name} (${sel.outputType}, ${sel.resultCount} results)`)
          }
        }
        lines.push('')
        lines.push('---')
        lines.push('')
      }

      const text = lines.join('\n')

      await navigator.clipboard.writeText(text)
      alert('Chat copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy:', err)
      alert('Copy failed - see console')
    }
  }

  return (
    <div className="chat-view">
      {/* Sidebar with chat list */}
      <aside className="chat-sidebar">
        {showNewChatInput ? (
          <div className="new-chat-form">
            <input
              ref={newChatInputRef}
              type="text"
              value={newChatTitle}
              onChange={(e) => setNewChatTitle(e.target.value)}
              onKeyDown={handleNewChatKeyDown}
              placeholder="Chat name..."
              className="new-chat-input"
            />
            <div className="new-chat-actions">
              <button onClick={handleNewChatSubmit} className="confirm-btn">OK</button>
              <button onClick={() => { setShowNewChatInput(false); setNewChatTitle('') }} className="cancel-btn">X</button>
            </div>
          </div>
        ) : (
          <button className="new-chat-btn" onClick={() => setShowNewChatInput(true)}>
            + New Chat
          </button>
        )}
        <div className="archive-toggle">
          <label>
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            Show archived
          </label>
        </div>
        <div className="chat-list">
          {chats.map(chat => (
            <div
              key={chat.id}
              className={`chat-item ${activeChat?.id === chat.id ? 'active' : ''} ${chat.archived ? 'archived' : ''}`}
              onClick={() => setActiveChat(chat)}
            >
              {editingChatId === chat.id ? (
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={(e) => handleEditKeyDown(e, chat.id)}
                  onBlur={() => updateChatTitle(chat.id, editingTitle)}
                  onClick={(e) => e.stopPropagation()}
                  className="chat-title-input"
                  autoFocus
                />
              ) : (
                <span className="chat-title">{chat.title}</span>
              )}
              <div className="chat-menu-container">
                <button
                  className="chat-menu-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    setOpenMenuChatId(openMenuChatId === chat.id ? null : chat.id)
                  }}
                  title="Options"
                >
                  ⋮
                </button>
                {openMenuChatId === chat.id && (
                  <div className="chat-menu-dropdown" ref={menuRef}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpenMenuChatId(null)
                        startEditingChat(chat, e)
                      }}
                    >
                      Rename
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpenMenuChatId(null)
                        copyChat(chat)
                      }}
                    >
                      Copy
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpenMenuChatId(null)
                        archiveChat(chat.id, e)
                      }}
                    >
                      {chat.archived ? 'Unarchive' : 'Archive'}
                    </button>
                    <button
                      className="delete-option"
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpenMenuChatId(null)
                        deleteChat(chat.id)
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {chats.length === 0 && (
            <p className="no-chats">{showArchived ? 'No archived chats' : 'No chats available'}</p>
          )}
        </div>
      </aside>

      {/* Template panel (collapsible) */}
      {showTemplates && (
        <PromptTemplatePanel onInsert={handleInsertTemplate} />
      )}

      {/* Main chat area */}
      <main className="chat-main">
        {activeChat ? (
          <>
            <div className="chat-main-header">
              <button
                className={`template-toggle-btn ${showTemplates ? 'active' : ''}`}
                onClick={() => setShowTemplates(!showTemplates)}
                title={showTemplates ? 'Templates ausblenden' : 'Templates anzeigen'}
              >
                {showTemplates ? 'Templates X' : 'Templates'}
              </button>
            </div>
            <div className="messages-container">
              {loading ? (
                <p className="loading">Loading messages...</p>
              ) : messages.length === 0 ? (
                <div className="empty-chat">
                  <p>Start a conversation!</p>
                  <p className="hint">Ask for example: "Which members are particularly active?"</p>
                </div>
              ) : (
                messages.map(msg => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-content">
                      <strong>{msg.role === 'user' ? 'You' : 'CatNose'}</strong>
                      <p>{msg.content}</p>
                    </div>
                    {msg.selections && msg.selections.length > 0 && (
                      <div className="message-selections">
                        {msg.selections.map(sel => (
                          <SelectionCard
                            key={sel.id}
                            selection={sel}
                            onAddToReport={addSelectionToReport}
                            onSelectionDuplicated={() => {
                              // Reload messages to show derived selections
                              if (activeChat) loadMessages(activeChat.id)
                            }}
                            isAddingToReport={addingToReport === sel.id}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
              {sending && (
                <div className="message assistant typing">
                  <div className="message-content">
                    <strong>CatNose</strong>
                    <p>Thinking...</p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter message... (Enter to send)"
                disabled={sending}
                rows={2}
              />
              <button onClick={sendMessage} disabled={sending || !input.trim()}>
                {sending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </>
        ) : (
          <div className="no-chat-selected">
            <p>Select a chat from the list or create a new one.</p>
            <button onClick={() => setShowNewChatInput(true)}>Start new chat</button>
          </div>
        )}
      </main>

      {/* Report panel on the right */}
      {activeChat && (
        <aside className="chat-report-panel">
          <div className="report-panel-header">
            <h4>Report</h4>
          </div>
          <div className="report-panel-content">
            {addingToReport && (
              <div className="report-adding-indicator">
                Selektion wird hinzugefuegt...
              </div>
            )}
            {reportLoading ? (
              <p className="loading">Loading report...</p>
            ) : chatReport ? (
              <div className="report-blocks">
                {chatReport.blocks.map(block => (
                  <div key={block.id} className="report-block-item">
                    {/* AI-Beschreibung (Text) */}
                    {block.content && (
                      <p className="report-block-text">{block.content}</p>
                    )}
                    {/* Selektion (ausklappbar) */}
                    {block.selectionId && (
                      <SelectionReportCard selectionId={block.selectionId} />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-report-panel">
                <p>No report yet.</p>
                <p className="hint">Click "Add to Report" on a selection.</p>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  )
}

export default ChatView
