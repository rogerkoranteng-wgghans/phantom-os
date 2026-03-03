import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Workflow, Play, Trash2, ChevronDown, ChevronRight, Zap } from 'lucide-react'
import { format } from 'date-fns'
import clsx from 'clsx'
import type { Workflow as WorkflowType } from '../types'

async function fetchWorkflows(): Promise<WorkflowType[]> {
  const res = await fetch('/api/workflows')
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json()
}

async function deleteWorkflow(id: string): Promise<void> {
  await fetch(`/api/workflows/${id}`, { method: 'DELETE' })
}

async function runWorkflow(id: string, sessionId: string): Promise<void> {
  await fetch(`/api/workflows/${id}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export default function WorkflowPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState('')
  const qc = useQueryClient()

  const { data: workflows = [], isLoading } = useQuery({
    queryKey: ['workflows'],
    queryFn: fetchWorkflows,
  })

  const deleteMut = useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  })

  const runMut = useMutation({
    mutationFn: ({ id, sid }: { id: string; sid: string }) => runWorkflow(id, sid),
  })

  return (
    <div className="flex flex-col h-full bg-phantom-bg p-4 overflow-hidden">
      <div className="flex items-center gap-3 mb-4">
        <Workflow size={20} className="text-phantom-accent" />
        <h1 className="text-phantom-text font-bold text-sm">Workflow Library</h1>
        <span className="text-[10px] text-phantom-muted bg-phantom-surface border border-phantom-border px-2 py-0.5 rounded">
          {workflows.length} saved
        </span>
      </div>

      {/* Session ID for running */}
      <div className="flex gap-2 mb-4">
        <input
          className="flex-1 bg-phantom-surface border border-phantom-border rounded px-3 py-1.5 text-xs text-phantom-text placeholder-phantom-muted focus:outline-none focus:border-phantom-accent"
          placeholder="Session ID to run workflows in..."
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
        />
      </div>

      {/* Workflow grid */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {isLoading && (
          <div className="text-center py-8 text-phantom-muted text-xs">Loading workflows...</div>
        )}
        {!isLoading && workflows.length === 0 && (
          <div className="flex flex-col items-center py-16 text-phantom-muted gap-3">
            <Zap size={40} className="opacity-20" />
            <p className="text-sm">No workflows saved yet</p>
            <p className="text-xs opacity-60">
              Tell Phantom "remember this as my [name] workflow" to save one
            </p>
          </div>
        )}
        {workflows.map((wf) => {
          const isExpanded = expandedId === wf.id
          return (
            <div
              key={wf.id}
              className="bg-phantom-surface border border-phantom-border rounded-lg overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center gap-3 px-4 py-3">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : wf.id)}
                  className="text-phantom-muted hover:text-phantom-text transition-all"
                >
                  {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-phantom-text font-medium">{wf.name}</p>
                  {wf.description && (
                    <p className="text-[11px] text-phantom-muted truncate">{wf.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-phantom-muted flex-shrink-0">
                  <span>{wf.steps.length} steps</span>
                  <span>{wf.use_count}× used</span>
                  <span>{format(new Date(wf.created_at), 'MMM d')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => runMut.mutate({ id: wf.id, sid: sessionId })}
                    disabled={!sessionId}
                    title={sessionId ? 'Run workflow' : 'Enter session ID first'}
                    className="p-1.5 rounded bg-phantom-accent/10 hover:bg-phantom-accent text-phantom-accent hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <Play size={14} />
                  </button>
                  <button
                    onClick={() => deleteMut.mutate(wf.id)}
                    className="p-1.5 rounded hover:bg-phantom-danger/10 text-phantom-muted hover:text-phantom-danger transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Steps */}
              {isExpanded && (
                <div className="border-t border-phantom-border px-4 py-3 space-y-2">
                  {wf.steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-3 text-xs">
                      <span className="w-5 h-5 rounded-full bg-phantom-border flex items-center justify-center text-[10px] text-phantom-muted flex-shrink-0">
                        {i + 1}
                      </span>
                      <div>
                        <p className="text-phantom-text">{step.action.narration || step.action.action_type}</p>
                        <p className="text-phantom-muted text-[10px]">
                          {step.action.action_type} · {step.delay_ms}ms delay
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
