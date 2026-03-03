import { useEffect, useRef, useState } from 'react'
import { Zap } from 'lucide-react'
import clsx from 'clsx'
import type { SessionStatus } from '../../types'

interface Props {
  narration: string
  status: SessionStatus
  currentTask?: string
  sessionId?: string
}

const STATUS_STYLES: Record<SessionStatus, string> = {
  idle: 'text-phantom-muted border-phantom-muted/30',
  listening: 'text-phantom-success border-phantom-success/30',
  thinking: 'text-phantom-warning border-phantom-warning/30 animate-pulse',
  executing: 'text-phantom-accent border-phantom-accent/30 animate-pulse',
  waiting_confirmation: 'text-phantom-danger border-phantom-danger/30 animate-pulse',
}

export default function NarrationBar({ narration, status, currentTask, sessionId }: Props) {
  const [displayed, setDisplayed] = useState('')
  const idxRef = useRef(0)
  const prevNarrationRef = useRef('')

  useEffect(() => {
    if (narration === prevNarrationRef.current) return
    prevNarrationRef.current = narration
    idxRef.current = 0
    setDisplayed('')

    const interval = setInterval(() => {
      idxRef.current += 1
      setDisplayed(narration.slice(0, idxRef.current))
      if (idxRef.current >= narration.length) clearInterval(interval)
    }, 18)

    return () => clearInterval(interval)
  }, [narration])

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-phantom-surface border-t border-phantom-border">
      {/* Phantom icon */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Zap
          size={16}
          className={clsx(
            status === 'idle' ? 'text-phantom-muted' : 'text-phantom-accent'
          )}
        />
        <span
          className={clsx(
            'text-[10px] px-2 py-0.5 rounded border uppercase tracking-widest',
            STATUS_STYLES[status]
          )}
        >
          {status.replace('_', ' ')}
        </span>
      </div>

      {/* Narration text */}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-phantom-text truncate">
          {displayed}
          <span className="animate-blink">|</span>
        </p>
        {currentTask && (
          <p className="text-[10px] text-phantom-muted truncate">Task: {currentTask}</p>
        )}
      </div>

      {/* Session ID */}
      {sessionId && (
        <span className="text-[10px] text-phantom-muted flex-shrink-0 font-mono">
          {sessionId.slice(0, 8)}
        </span>
      )}
    </div>
  )
}
