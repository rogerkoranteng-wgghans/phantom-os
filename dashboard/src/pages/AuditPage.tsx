import { useState, useMemo } from 'react'
import { ScrollText, Download, ChevronDown, ChevronRight, CheckCircle2, XCircle } from 'lucide-react'
import { format } from 'date-fns'
import clsx from 'clsx'
import { usePhantomStore } from '../store/phantomStore'
import type { RiskLevel } from '../types'

const RISK_STYLES: Record<RiskLevel, string> = {
  low: 'text-phantom-success',
  medium: 'text-phantom-warning',
  high: 'text-orange-400',
  critical: 'text-phantom-danger',
}

export default function AuditPage() {
  const actionLog = usePhantomStore((s) => s.actionLog)
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'all'>('all')
  const [resultFilter, setResultFilter] = useState<'all' | 'success' | 'failed'>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    return actionLog.filter((entry) => {
      if (riskFilter !== 'all' && entry.action.risk_level !== riskFilter) return false
      if (resultFilter === 'success' && entry.status !== 'success') return false
      if (resultFilter === 'failed' && entry.status !== 'failed') return false
      return true
    })
  }, [actionLog, riskFilter, resultFilter])

  // Stats
  const total = actionLog.length
  const successes = actionLog.filter((e) => e.status === 'success').length
  const highRisk = actionLog.filter((e) => e.action.risk_level === 'high' || e.action.risk_level === 'critical').length
  const avgConf = total > 0
    ? Math.round(actionLog.reduce((s, e) => s + e.action.confidence, 0) / total * 100)
    : 0

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(actionLog, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `phantom-audit-${Date.now()}.json`
    a.click()
  }

  return (
    <div className="flex flex-col h-full bg-phantom-bg p-4 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <ScrollText size={20} className="text-phantom-accent" />
        <h1 className="text-phantom-text font-bold text-sm">Audit Log</h1>
        <button
          onClick={exportJSON}
          disabled={total === 0}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 border border-phantom-border rounded text-xs text-phantom-muted hover:text-phantom-text transition-all disabled:opacity-30"
        >
          <Download size={12} />
          Export JSON
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {[
          { label: 'Total Actions', value: total },
          { label: 'Success Rate', value: total > 0 ? `${Math.round(successes / total * 100)}%` : '—' },
          { label: 'High Risk', value: highRisk },
          { label: 'Avg Confidence', value: `${avgConf}%` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-phantom-surface border border-phantom-border rounded-lg px-3 py-2.5">
            <p className="text-[10px] text-phantom-muted uppercase tracking-wider">{label}</p>
            <p className="text-lg font-bold text-phantom-text">{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-3">
        <div className="flex gap-1">
          {(['all', 'low', 'medium', 'high', 'critical'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRiskFilter(r)}
              className={clsx(
                'px-2 py-1 rounded border text-[10px] transition-all',
                riskFilter === r
                  ? 'border-phantom-accent text-phantom-accent bg-phantom-accent/10'
                  : 'border-phantom-border text-phantom-muted hover:text-phantom-text'
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['all', 'success', 'failed'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setResultFilter(r)}
              className={clsx(
                'px-2 py-1 rounded border text-[10px] transition-all',
                resultFilter === r
                  ? 'border-phantom-accent text-phantom-accent bg-phantom-accent/10'
                  : 'border-phantom-border text-phantom-muted hover:text-phantom-text'
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px] text-phantom-muted self-center">{filtered.length} entries</span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="flex flex-col items-center py-12 text-phantom-muted text-xs gap-2">
            <ScrollText size={32} className="opacity-20" />
            <p>No actions yet. Connect to a session to see activity.</p>
          </div>
        )}
        <div className="space-y-1">
          {filtered.map((entry) => {
            const id = entry.action.action_id
            const isExpanded = expandedId === id

            return (
              <div
                key={id}
                className="bg-phantom-surface border border-phantom-border rounded-lg overflow-hidden"
              >
                <div
                  className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-phantom-border/20"
                  onClick={() => setExpandedId(isExpanded ? null : id)}
                >
                  <button className="text-phantom-muted">
                    {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  </button>

                  {entry.status === 'success' && <CheckCircle2 size={12} className="text-phantom-success flex-shrink-0" />}
                  {entry.status === 'failed' && <XCircle size={12} className="text-phantom-danger flex-shrink-0" />}
                  {!entry.status && <div className="w-3 h-3" />}

                  <span className="text-[10px] text-phantom-muted w-16 flex-shrink-0 font-mono">
                    {entry.action.created_at
                      ? format(new Date(entry.action.created_at), 'HH:mm:ss')
                      : '—'}
                  </span>
                  <span className="text-[10px] text-phantom-muted w-20 flex-shrink-0">
                    {entry.action.action_type}
                  </span>
                  <span className="text-xs text-phantom-text flex-1 truncate">
                    {entry.action.narration || entry.action.action_type}
                  </span>
                  <span className={clsx('text-[10px] w-12 text-right flex-shrink-0', RISK_STYLES[entry.action.risk_level])}>
                    {entry.action.risk_level}
                  </span>
                  <span className="text-[10px] text-phantom-muted w-10 text-right flex-shrink-0">
                    {Math.round(entry.action.confidence * 100)}%
                  </span>
                  <span className="text-[10px] text-phantom-muted w-24 text-right flex-shrink-0 truncate">
                    {entry.action.agent_source}
                  </span>
                </div>

                {isExpanded && (
                  <div className="border-t border-phantom-border p-3">
                    {entry.result?.error && (
                      <p className="text-xs text-phantom-danger mb-2">{entry.result.error}</p>
                    )}
                    <div className="flex gap-4">
                      {entry.result?.screenshot_before && (
                        <div>
                          <p className="text-[10px] text-phantom-muted mb-1">Before</p>
                          <img
                            src={`data:image/jpeg;base64,${entry.result.screenshot_before}`}
                            className="w-48 rounded border border-phantom-border"
                            alt="Before"
                          />
                        </div>
                      )}
                      {entry.result?.screenshot_after && (
                        <div>
                          <p className="text-[10px] text-phantom-muted mb-1">After</p>
                          <img
                            src={`data:image/jpeg;base64,${entry.result.screenshot_after}`}
                            className="w-48 rounded border border-phantom-border"
                            alt="After"
                          />
                        </div>
                      )}
                      {!entry.result?.screenshot_before && !entry.result?.screenshot_after && (
                        <p className="text-xs text-phantom-muted">No screenshots captured for this action.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
