import { useState } from 'react'
import { Plug, PlugZap } from 'lucide-react'
import { usePhantomStore } from '../store/phantomStore'
import AgentStatusBar from '../components/LiveSession/AgentStatusBar'
import ActionFeed from '../components/LiveSession/ActionFeed'
import ConfirmationModal from '../components/LiveSession/ConfirmationModal'
import EmotionWidget from '../components/LiveSession/EmotionWidget'
import NarrationBar from '../components/LiveSession/NarrationBar'
import TaskGraphPanel from '../components/TaskGraph/TaskGraphPanel'

export default function Dashboard() {
  const {
    connected, connect, disconnect,
    session, actionLog, narration,
    taskNodes, taskEdges,
    pendingConfirmation, confirmAction, rejectAction,
  } = usePhantomStore()

  const [sessionInput, setSessionInput] = useState('')
  const [backendInput, setBackendInput] = useState('ws://localhost:8000')

  const handleConnect = () => {
    const id = sessionInput.trim() || crypto.randomUUID()
    connect(id, backendInput)
  }

  return (
    <div className="flex flex-col h-full bg-phantom-bg">
      {/* Connect bar (shown when disconnected) */}
      {!connected && (
        <div className="flex items-center gap-2 px-4 py-3 bg-phantom-surface border-b border-phantom-border">
          <input
            className="flex-1 bg-phantom-bg border border-phantom-border rounded px-3 py-1.5 text-xs text-phantom-text placeholder-phantom-muted focus:outline-none focus:border-phantom-accent"
            placeholder="Backend URL (ws://localhost:8000)"
            value={backendInput}
            onChange={(e) => setBackendInput(e.target.value)}
          />
          <input
            className="w-48 bg-phantom-bg border border-phantom-border rounded px-3 py-1.5 text-xs text-phantom-text placeholder-phantom-muted focus:outline-none focus:border-phantom-accent"
            placeholder="Session ID (auto)"
            value={sessionInput}
            onChange={(e) => setSessionInput(e.target.value)}
          />
          <button
            onClick={handleConnect}
            className="flex items-center gap-2 px-4 py-1.5 bg-phantom-accent hover:bg-phantom-accent-glow rounded text-white text-xs font-bold transition-all"
          >
            <PlugZap size={14} />
            Connect
          </button>
        </div>
      )}

      {connected && (
        <div className="flex items-center gap-2 px-4 py-2 bg-phantom-surface border-b border-phantom-border">
          <div className="w-2 h-2 rounded-full bg-phantom-success animate-pulse" />
          <span className="text-xs text-phantom-success">Connected</span>
          {session && (
            <span className="text-xs text-phantom-muted ml-1">— {session.session_id.slice(0, 8)}</span>
          )}
          <button
            onClick={disconnect}
            className="ml-auto flex items-center gap-1.5 px-3 py-1 text-xs text-phantom-muted hover:text-phantom-danger border border-phantom-border hover:border-phantom-danger rounded transition-all"
          >
            <Plug size={12} />
            Disconnect
          </button>
        </div>
      )}

      {/* Agent status bar */}
      <AgentStatusBar agentStatuses={session?.agent_statuses ?? {}} />

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-5 overflow-hidden">
        {/* Action Feed (3/5) */}
        <div className="col-span-3 border-r border-phantom-border overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-phantom-border">
            <p className="text-xs text-phantom-muted uppercase tracking-widest">Live Action Feed</p>
            <span className="text-[10px] text-phantom-muted">{actionLog.length} total</span>
          </div>
          <div className="h-[calc(100%-36px)]">
            <ActionFeed actions={actionLog} />
          </div>
        </div>

        {/* Right column (2/5) */}
        <div className="col-span-2 flex flex-col overflow-hidden">
          {/* Task graph (top) */}
          <div className="flex-1 p-2">
            <TaskGraphPanel nodes={taskNodes} edges={taskEdges} />
          </div>
          {/* Emotion widget (bottom) */}
          <div className="p-2 border-t border-phantom-border">
            <EmotionWidget emotion={session?.emotion_context ?? null} />
          </div>
        </div>
      </div>

      {/* Narration bar */}
      <NarrationBar
        narration={narration}
        status={session?.status ?? 'idle'}
        currentTask={session?.current_task}
        sessionId={session?.session_id}
      />

      {/* Confirmation modal overlay */}
      {pendingConfirmation && (
        <ConfirmationModal
          action={pendingConfirmation}
          onConfirm={confirmAction}
          onReject={rejectAction}
          timeoutSeconds={30}
        />
      )}
    </div>
  )
}
