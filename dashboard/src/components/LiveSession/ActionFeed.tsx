import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import clsx from 'clsx'
import {
  MousePointerClick, Keyboard, ArrowUpDown, Globe, AppWindow,
  Command, Move, Camera, Search, Clipboard, Timer, CheckCircle2, XCircle,
} from 'lucide-react'
import type { AuditEntry, RiskLevel, ActionType } from '../../types'

const ACTION_ICONS: Record<ActionType, React.ElementType> = {
  click: MousePointerClick,
  type: Keyboard,
  scroll: ArrowUpDown,
  navigate: Globe,
  open_app: AppWindow,
  key_combo: Command,
  drag: Move,
  screenshot: Camera,
  search_web: Search,
  read_clipboard: Clipboard,
  write_clipboard: Clipboard,
  wait: Timer,
}

const RISK_STYLES: Record<RiskLevel, string> = {
  low: 'text-phantom-success border-phantom-success/30 bg-phantom-success/10',
  medium: 'text-phantom-warning border-phantom-warning/30 bg-phantom-warning/10',
  high: 'text-orange-400 border-orange-400/30 bg-orange-400/10',
  critical: 'text-phantom-danger border-phantom-danger/30 bg-phantom-danger/10 animate-pulse',
}

interface Props {
  actions: AuditEntry[]
}

export default function ActionFeed({ actions }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [filter, setFilter] = useState<RiskLevel | 'all'>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [actions.length])

  const filtered = filter === 'all'
    ? actions
    : actions.filter((e) => e.action.risk_level === filter)

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex gap-2 px-3 py-2 border-b border-phantom-border text-xs">
        {(['all', 'low', 'medium', 'high', 'critical'] as const).map((lvl) => (
          <button
            key={lvl}
            onClick={() => setFilter(lvl)}
            className={clsx(
              'px-2 py-1 rounded border transition-all',
              filter === lvl
                ? 'border-phantom-accent text-phantom-accent bg-phantom-accent/10'
                : 'border-phantom-border text-phantom-muted hover:text-phantom-text'
            )}
          >
            {lvl}
          </button>
        ))}
        <span className="ml-auto text-phantom-muted">{filtered.length} actions</span>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        <AnimatePresence initial={false}>
          {filtered.map((entry, i) => {
            const Icon = ACTION_ICONS[entry.action.action_type] ?? MousePointerClick
            const id = entry.action.action_id || String(i)
            const isExpanded = expandedId === id
            const success = entry.status === 'success' || entry.result?.success
            const failed = entry.status === 'failed' || entry.result?.success === false

            return (
              <motion.div
                key={id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="group cursor-pointer"
                onClick={() => setExpandedId(isExpanded ? null : id)}
              >
                <div className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-phantom-border/30">
                  {/* Icon */}
                  <Icon size={14} className="text-phantom-muted mt-0.5 flex-shrink-0" />

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-phantom-text truncate">{entry.action.narration || entry.action.action_type}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', RISK_STYLES[entry.action.risk_level])}>
                        {entry.action.risk_level}
                      </span>
                      <span className="text-[10px] text-phantom-muted">
                        {Math.round(entry.action.confidence * 100)}%
                      </span>
                      <span className="text-[10px] text-phantom-muted">
                        {entry.action.agent_source}
                      </span>
                    </div>
                  </div>

                  {/* Status + time */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {success && <CheckCircle2 size={12} className="text-phantom-success" />}
                    {failed && <XCircle size={12} className="text-phantom-danger" />}
                    {entry.action.created_at && (
                      <span className="text-[10px] text-phantom-muted">
                        {format(new Date(entry.action.created_at), 'HH:mm:ss')}
                      </span>
                    )}
                  </div>
                </div>

                {/* Expanded: screenshots */}
                {isExpanded && entry.result && (
                  <div className="ml-6 mt-1 mb-2 flex gap-2">
                    {entry.result.screenshot_before && (
                      <div>
                        <p className="text-[10px] text-phantom-muted mb-1">Before</p>
                        <img
                          src={`data:image/jpeg;base64,${entry.result.screenshot_before}`}
                          className="w-40 rounded border border-phantom-border"
                          alt="Before"
                        />
                      </div>
                    )}
                    {entry.result.screenshot_after && (
                      <div>
                        <p className="text-[10px] text-phantom-muted mb-1">After</p>
                        <img
                          src={`data:image/jpeg;base64,${entry.result.screenshot_after}`}
                          className="w-40 rounded border border-phantom-border"
                          alt="After"
                        />
                      </div>
                    )}
                    {entry.result.error && (
                      <p className="text-[10px] text-phantom-danger">{entry.result.error}</p>
                    )}
                  </div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
