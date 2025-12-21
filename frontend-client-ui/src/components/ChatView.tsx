import { useState, useEffect, useRef } from 'react'
import SelectionCard from './SelectionCard'
import './ChatView.css'

const API_BASE = '/api'

interface Selection {
  id: number
  name: string
  outputType: string
  filtersJson: string
  resultCount: number
  createdBy: string
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
  createdAt: string
  updatedAt: string
}

export function ChatView() {
  const [chats, setChats] = useState<Chat[]>([])
  const [activeChat, setActiveChat] = useState<Chat | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load all chats
  useEffect(() => {
    loadChats()
  }, [])

  // Load messages when active chat changes
  useEffect(() => {
    if (activeChat) {
      loadMessages(activeChat.id)
    } else {
      setMessages([])
    }
  }, [activeChat?.id])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadChats = async () => {
    try {
      const res = await fetch(`${API_BASE}/chats`)
      if (res.ok) {
        const data = await res.json()
        setChats(data)
        // Select most recent chat if none selected
        if (data.length > 0 && !activeChat) {
          setActiveChat(data[0])
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

  const createNewChat = async () => {
    try {
      const res = await fetch(`${API_BASE}/chats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' })
      })
      if (res.ok) {
        const chat = await res.json()
        setChats(prev => [chat, ...prev])
        setActiveChat(chat)
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to create chat:', err)
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

  return (
    <div className="chat-view">
      {/* Sidebar with chat list */}
      <aside className="chat-sidebar">
        <button className="new-chat-btn" onClick={createNewChat}>
          + New Chat
        </button>
        <div className="chat-list">
          {chats.map(chat => (
            <div
              key={chat.id}
              className={`chat-item ${activeChat?.id === chat.id ? 'active' : ''}`}
              onClick={() => setActiveChat(chat)}
            >
              <span className="chat-title">{chat.title}</span>
              <button
                className="delete-btn"
                onClick={(e) => { e.stopPropagation(); deleteChat(chat.id) }}
                title="Delete chat"
              >
                x
              </button>
            </div>
          ))}
          {chats.length === 0 && (
            <p className="no-chats">No chats available</p>
          )}
        </div>
      </aside>

      {/* Main chat area */}
      <main className="chat-main">
        {activeChat ? (
          <>
            <div className="chat-header">
              <h3>{activeChat.title}</h3>
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
                          <SelectionCard key={sel.id} selection={sel} />
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
            <button onClick={createNewChat}>Start new chat</button>
          </div>
        )}
      </main>
    </div>
  )
}

export default ChatView
