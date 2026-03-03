export type ActionType =
  | 'click' | 'type' | 'scroll' | 'navigate' | 'open_app'
  | 'key_combo' | 'drag' | 'screenshot' | 'search_web'
  | 'read_clipboard' | 'write_clipboard' | 'wait'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type SessionStatus = 'idle' | 'listening' | 'thinking' | 'executing' | 'waiting_confirmation'
export type MemoryType = 'episodic' | 'semantic' | 'workflow'

export interface ActionTarget {
  type: string
  label?: string
  x?: number
  y?: number
  confidence: number
}

export interface Action {
  action_id: string
  action_type: ActionType
  target?: ActionTarget
  parameters: Record<string, unknown>
  risk_level: RiskLevel
  confidence: number
  narration: string
  requires_confirmation: boolean
  undo_strategy?: string
  agent_source: string
  created_at?: string
}

export interface ActionResult {
  action_id: string
  success: boolean
  error?: string
  screenshot_before?: string
  screenshot_after?: string
  timestamp: string
}

export interface AuditEntry {
  action: Action
  result?: ActionResult
  status?: string
}

export interface AgentStatus {
  name: string
  status: 'idle' | 'running' | 'error'
  last_activity?: string
  current_task?: string
}

export interface EmotionContext {
  frustration: number
  confidence: number
  urgency: number
  engagement: number
}

export interface SessionState {
  session_id: string
  status: SessionStatus
  current_task?: string
  agent_statuses: Record<string, AgentStatus>
  action_queue: Action[]
  emotion_context?: EmotionContext
}

export interface MemoryEntry {
  id: string
  session_id?: string
  memory_type: MemoryType
  content: string
  metadata: Record<string, unknown>
  created_at: string
  tags: string[]
}

export interface WorkflowStep {
  action: Action
  delay_ms: number
}

export interface Workflow {
  id: string
  name: string
  description: string
  steps: WorkflowStep[]
  created_at: string
  use_count: number
  tags?: string[]
}
