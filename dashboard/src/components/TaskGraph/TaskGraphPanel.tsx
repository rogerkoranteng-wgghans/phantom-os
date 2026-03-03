import ReactFlow, {
  Background,
  MiniMap,
  Controls,
  BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Node, Edge } from 'reactflow'

interface Props {
  nodes: Node[]
  edges: Edge[]
}

const nodeStyle = (status?: string) => ({
  background: status === 'completed'
    ? '#10b981'
    : status === 'running'
    ? '#7c3aed'
    : status === 'failed'
    ? '#ef4444'
    : '#12121a',
  border: `1px solid ${
    status === 'completed' ? '#10b981'
      : status === 'running' ? '#8b5cf6'
      : status === 'failed' ? '#ef4444'
      : '#1e1e2e'
  }`,
  color: '#e2e8f0',
  fontSize: '11px',
  fontFamily: '"JetBrains Mono", monospace',
  padding: '8px 12px',
  borderRadius: '8px',
  minWidth: '120px',
  textAlign: 'center' as const,
})

// Default demo nodes when no real data
const DEFAULT_NODES: Node[] = [
  {
    id: '1',
    data: { label: '🧠 Phantom Core', status: 'idle' },
    position: { x: 200, y: 50 },
    style: nodeStyle('idle'),
  },
  {
    id: '2',
    data: { label: '🎯 Orchestrator', status: 'idle' },
    position: { x: 200, y: 130 },
    style: nodeStyle('idle'),
  },
  {
    id: '3',
    data: { label: '🔍 Research', status: 'idle' },
    position: { x: 60, y: 230 },
    style: nodeStyle('idle'),
  },
  {
    id: '4',
    data: { label: '💾 Memory', status: 'idle' },
    position: { x: 200, y: 230 },
    style: nodeStyle('idle'),
  },
  {
    id: '5',
    data: { label: '🛡 Safety', status: 'idle' },
    position: { x: 340, y: 230 },
    style: nodeStyle('idle'),
  },
]

const DEFAULT_EDGES: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', style: { stroke: '#1e1e2e' }, animated: false },
  { id: 'e2-3', source: '2', target: '3', style: { stroke: '#1e1e2e' }, animated: false },
  { id: 'e2-4', source: '2', target: '4', style: { stroke: '#1e1e2e' }, animated: false },
  { id: 'e2-5', source: '2', target: '5', style: { stroke: '#1e1e2e' }, animated: false },
]

export default function TaskGraphPanel({ nodes, edges }: Props) {
  const displayNodes = nodes.length > 0 ? nodes : DEFAULT_NODES
  const displayEdges = edges.length > 0 ? edges : DEFAULT_EDGES

  return (
    <div className="h-full bg-phantom-surface rounded-lg border border-phantom-border overflow-hidden">
      <div className="px-3 py-2 border-b border-phantom-border flex items-center justify-between">
        <p className="text-xs text-phantom-muted uppercase tracking-widest">Agent Task Graph</p>
        <div className="flex items-center gap-3 text-[10px] text-phantom-muted">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-phantom-accent inline-block" />running
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-phantom-success inline-block" />done
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-phantom-danger inline-block" />failed
          </span>
        </div>
      </div>
      <ReactFlow
        nodes={displayNodes}
        edges={displayEdges}
        fitView
        attributionPosition="bottom-right"
        style={{ background: '#0a0a0f' }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e1e2e" />
        <MiniMap
          nodeColor={(node) =>
            node.style?.background as string ?? '#12121a'
          }
          maskColor="rgba(10,10,15,0.7)"
          style={{ background: '#12121a', border: '1px solid #1e1e2e' }}
        />
        <Controls style={{ background: '#12121a', border: '1px solid #1e1e2e', color: '#e2e8f0' }} />
      </ReactFlow>
    </div>
  )
}
