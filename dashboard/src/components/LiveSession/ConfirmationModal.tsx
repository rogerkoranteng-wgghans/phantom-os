import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Shield, XCircle, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
import type { Action } from '../../types'

interface Props {
  action: Action
  onConfirm: () => void
  onReject: () => void
  timeoutSeconds?: number
}

export default function ConfirmationModal({
  action,
  onConfirm,
  onReject,
  timeoutSeconds = 30,
}: Props) {
  const [remaining, setRemaining] = useState(timeoutSeconds)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current!)
          onReject()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(intervalRef.current!)
  }, [onReject])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Enter') onConfirm()
      if (e.key === 'Escape') onReject()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onConfirm, onReject])

  const isCritical = action.risk_level === 'critical'
  const isHigh = action.risk_level === 'high'
  const pct = (remaining / timeoutSeconds) * 100

  const riskColor = {
    low: 'border-phantom-success text-phantom-success',
    medium: 'border-phantom-warning text-phantom-warning',
    high: 'border-orange-400 text-orange-400',
    critical: 'border-phantom-danger text-phantom-danger',
  }[action.risk_level]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <motion.div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={onReject}
      />

      {/* Modal */}
      <motion.div
        className="relative z-10 w-full max-w-md mx-4 bg-phantom-surface border border-phantom-border rounded-xl overflow-hidden shadow-2xl"
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      >
        {/* Risk banner */}
        <div
          className={clsx(
            'px-4 py-3 border-b flex items-center gap-3',
            isCritical && 'bg-phantom-danger/20 border-phantom-danger animate-pulse',
            isHigh && 'bg-orange-400/10 border-orange-400/30',
            !isCritical && !isHigh && 'border-phantom-border'
          )}
        >
          {isCritical ? (
            <XCircle size={20} className="text-phantom-danger flex-shrink-0" />
          ) : (
            <AlertTriangle size={20} className={clsx(riskColor.split(' ')[1], 'flex-shrink-0')} />
          )}
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-phantom-muted">
              Confirmation Required
            </p>
            <p className={clsx('text-sm font-bold', riskColor.split(' ')[1])}>
              {action.risk_level.toUpperCase()} RISK ACTION
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-xs text-phantom-muted">Auto-reject in</p>
            <p className={clsx('text-lg font-bold', remaining <= 5 ? 'text-phantom-danger' : 'text-phantom-text')}>
              {remaining}s
            </p>
          </div>
        </div>

        {/* Countdown bar */}
        <div className="h-1 bg-phantom-border">
          <div
            className={clsx(
              'h-full transition-all duration-1000',
              isCritical ? 'bg-phantom-danger' : isHigh ? 'bg-orange-400' : 'bg-phantom-accent'
            )}
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          <div>
            <p className="text-sm text-phantom-muted mb-1">Phantom wants to:</p>
            <p className="text-phantom-text font-medium">{action.narration || action.action_type}</p>
          </div>

          {action.target && (
            <div className="text-xs text-phantom-muted bg-phantom-bg rounded p-3 border border-phantom-border">
              <span className="text-phantom-accent">Target: </span>
              {action.target.label || action.target.type}
              {action.target.x !== undefined && (
                <span className="ml-2">@ ({action.target.x}, {action.target.y})</span>
              )}
            </div>
          )}

          {action.undo_strategy && (
            <div className="flex items-start gap-2 text-xs text-phantom-muted">
              <Shield size={12} className="mt-0.5 flex-shrink-0 text-phantom-success" />
              <span>Undo: {action.undo_strategy}</span>
            </div>
          )}

          {!action.undo_strategy && (
            <div className="flex items-start gap-2 text-xs text-phantom-danger/80">
              <XCircle size={12} className="mt-0.5 flex-shrink-0" />
              <span>This action may be irreversible</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-5 pb-5 flex gap-3">
          <button
            onClick={onReject}
            className="flex-1 py-2.5 rounded-lg border border-phantom-border text-phantom-muted hover:text-phantom-text hover:border-phantom-text transition-all text-sm"
          >
            Cancel <span className="text-xs opacity-50">(Esc)</span>
          </button>
          <button
            onClick={onConfirm}
            className={clsx(
              'flex-1 py-2.5 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2',
              isCritical
                ? 'bg-phantom-danger hover:bg-red-500 text-white'
                : 'bg-phantom-success hover:bg-emerald-400 text-phantom-bg'
            )}
          >
            <CheckCircle size={16} />
            Proceed <span className="text-xs opacity-70">(Enter)</span>
          </button>
        </div>
      </motion.div>
    </div>
  )
}
