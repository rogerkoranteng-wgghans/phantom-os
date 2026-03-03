import { create } from 'zustand'
import type { Node, Edge } from 'reactflow'
import type { Action, AuditEntry, SessionState } from '../types'

interface PhantomStore {
  // WebSocket
  ws: WebSocket | null
  connected: boolean
  connect: (sessionId: string, backendUrl?: string) => void
  disconnect: () => void

  // Session
  session: SessionState | null
  setSession: (s: SessionState) => void

  // Live action feed (last 200 entries)
  actionLog: AuditEntry[]
  addAction: (entry: AuditEntry) => void
  clearActionLog: () => void

  // Live narration
  narration: string
  setNarration: (text: string) => void

  // Pending confirmation
  pendingConfirmation: Action | null
  setPendingConfirmation: (action: Action | null) => void
  confirmAction: () => void
  rejectAction: () => void

  // Task DAG for React Flow
  taskNodes: Node[]
  taskEdges: Edge[]
  setTaskGraph: (nodes: Node[], edges: Edge[]) => void
}

export const usePhantomStore = create<PhantomStore>((set, get) => ({
  ws: null,
  connected: false,

  connect: (sessionId: string, backendUrl = 'ws://localhost:8000') => {
    const existing = get().ws
    if (existing) existing.close()

    const url = `${backendUrl}/ws/${sessionId}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      set({ connected: true })
      console.log(`[Phantom] Connected to ${url}`)
    }

    ws.onclose = () => {
      set({ connected: false, ws: null })
      console.log('[Phantom] Disconnected')
    }

    ws.onerror = (e) => {
      console.error('[Phantom] WebSocket error:', e)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string)
        const { type, payload } = msg

        if (type === 'session_state') {
          set({ session: payload as SessionState })
        } else if (type === 'action') {
          const action = payload as Action
          get().addAction({ action, status: 'queued' })
        } else if (type === 'text') {
          const text = (payload as { content: string }).content || ''
          if (text.trim()) {
            get().setNarration(text.trim())
          }
        } else if (type === 'confirmation_request') {
          get().setPendingConfirmation((payload as { action: Action }).action)
        } else if (type === 'action_result') {
          // Update matching audit entry with result
          const result = payload as { action_id: string; success: boolean; error?: string }
          set((state) => ({
            actionLog: state.actionLog.map((entry) =>
              entry.action.action_id === result.action_id
                ? { ...entry, status: result.success ? 'success' : 'failed' }
                : entry
            ),
          }))
        }
      } catch (e) {
        console.error('[Phantom] Parse error:', e)
      }
    }

    set({ ws, connected: false })
  },

  disconnect: () => {
    const ws = get().ws
    if (ws) ws.close()
    set({ ws: null, connected: false })
  },

  session: null,
  setSession: (s) => set({ session: s }),

  actionLog: [],
  addAction: (entry) =>
    set((state) => ({
      actionLog: [...state.actionLog.slice(-199), entry],
    })),
  clearActionLog: () => set({ actionLog: [] }),

  narration: '',
  setNarration: (text) => set({ narration: text }),

  pendingConfirmation: null,
  setPendingConfirmation: (action) => set({ pendingConfirmation: action }),

  confirmAction: () => {
    const { ws, pendingConfirmation } = get()
    if (ws && pendingConfirmation) {
      ws.send(
        JSON.stringify({
          type: 'confirm_action',
          payload: { action_id: pendingConfirmation.action_id },
        })
      )
    }
    set({ pendingConfirmation: null })
  },

  rejectAction: () => {
    const { ws, pendingConfirmation } = get()
    if (ws && pendingConfirmation) {
      ws.send(
        JSON.stringify({
          type: 'reject_action',
          payload: { action_id: pendingConfirmation.action_id },
        })
      )
    }
    set({ pendingConfirmation: null })
  },

  taskNodes: [],
  taskEdges: [],
  setTaskGraph: (taskNodes, taskEdges) => set({ taskNodes, taskEdges }),
}))
