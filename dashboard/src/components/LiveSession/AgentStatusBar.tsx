import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import type { AgentStatus } from '../../types'

const AGENT_ORDER = [
  'phantom_core', 'orchestrator', 'safety', 'memory',
  'research', 'prediction', 'workflow', 'communication',
]

const AGENT_LABELS: Record<string, string> = {
  phantom_core: 'Core',
  orchestrator: 'Orch',
  safety: 'Safety',
  memory: 'Memory',
  research: 'Research',
  prediction: 'Predict',
  workflow: 'Workflow',
  communication: 'Comms',
}

interface Props {
  agentStatuses: Record<string, AgentStatus>
}

export default function AgentStatusBar({ agentStatuses }: Props) {
  return (
    <div className="flex gap-2 px-4 py-2 bg-phantom-surface border-b border-phantom-border overflow-x-auto">
      {AGENT_ORDER.map((name) => {
        const agent = agentStatuses[name]
        const status = agent?.status ?? 'idle'
        return (
          <div
            key={name}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs whitespace-nowrap flex-shrink-0',
              status === 'running' && 'border-phantom-accent bg-phantom-accent/10',
              status === 'idle' && 'border-phantom-border bg-transparent',
              status === 'error' && 'border-phantom-danger bg-phantom-danger/10'
            )}
          >
            {/* Status dot */}
            <span
              className={clsx(
                'w-1.5 h-1.5 rounded-full',
                status === 'running' && 'bg-phantom-accent animate-pulse',
                status === 'idle' && 'bg-phantom-muted',
                status === 'error' && 'bg-phantom-danger'
              )}
            />
            <span
              className={clsx(
                status === 'running' ? 'text-phantom-accent-glow' : 'text-phantom-muted'
              )}
            >
              {AGENT_LABELS[name] ?? name}
            </span>
            {agent?.last_activity && (
              <span className="text-phantom-muted text-[10px]">
                {formatDistanceToNow(new Date(agent.last_activity), { addSuffix: true })}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
