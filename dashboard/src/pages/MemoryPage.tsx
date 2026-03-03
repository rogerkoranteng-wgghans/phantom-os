import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Brain, Plus, Trash2, Tag, Search } from 'lucide-react'
import { format } from 'date-fns'
import clsx from 'clsx'
import type { MemoryEntry, MemoryType } from '../types'

const TABS: { label: string; type: MemoryType | 'all' }[] = [
  { label: 'All', type: 'all' },
  { label: 'Episodic', type: 'episodic' },
  { label: 'Semantic', type: 'semantic' },
  { label: 'Workflow', type: 'workflow' },
]

const TYPE_COLORS: Record<MemoryType, string> = {
  episodic: 'text-phantom-accent bg-phantom-accent/10 border-phantom-accent/30',
  semantic: 'text-phantom-success bg-phantom-success/10 border-phantom-success/30',
  workflow: 'text-phantom-warning bg-phantom-warning/10 border-phantom-warning/30',
}

async function fetchMemories(type?: string, search?: string): Promise<MemoryEntry[]> {
  const params = new URLSearchParams()
  if (type && type !== 'all') params.set('memory_type', type)
  const res = await fetch(`/api/memory?${params}`)
  if (!res.ok) throw new Error('Failed to fetch')
  const data: MemoryEntry[] = await res.json()
  if (search) return data.filter((e) => e.content.toLowerCase().includes(search.toLowerCase()))
  return data
}

async function deleteMemory(id: string): Promise<void> {
  await fetch(`/api/memory/${id}`, { method: 'DELETE' })
}

async function createMemory(body: Partial<MemoryEntry>): Promise<MemoryEntry> {
  const res = await fetch('/api/memory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to create')
  return res.json()
}

export default function MemoryPage() {
  const [tab, setTab] = useState<MemoryType | 'all'>('all')
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newContent, setNewContent] = useState('')
  const [newType, setNewType] = useState<MemoryType>('semantic')
  const [newTags, setNewTags] = useState('')
  const qc = useQueryClient()

  const { data: memories = [], isLoading } = useQuery({
    queryKey: ['memories', tab, search],
    queryFn: () => fetchMemories(tab, search),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMemory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['memories'] }),
  })

  const createMut = useMutation({
    mutationFn: createMemory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memories'] })
      setShowAdd(false)
      setNewContent('')
      setNewTags('')
    },
  })

  return (
    <div className="flex flex-col h-full bg-phantom-bg p-4 overflow-hidden">
      <div className="flex items-center gap-3 mb-4">
        <Brain size={20} className="text-phantom-accent" />
        <h1 className="text-phantom-text font-bold text-sm">Memory Browser</h1>
        <span className="text-[10px] text-phantom-muted bg-phantom-surface border border-phantom-border px-2 py-0.5 rounded">
          {memories.length} entries
        </span>
        <div className="flex-1" />
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-phantom-accent hover:bg-phantom-accent-glow text-white rounded text-xs transition-all"
        >
          <Plus size={14} />
          Add Memory
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="mb-4 p-3 bg-phantom-surface border border-phantom-border rounded-lg space-y-2">
          <textarea
            className="w-full bg-phantom-bg border border-phantom-border rounded px-3 py-2 text-xs text-phantom-text placeholder-phantom-muted resize-none focus:outline-none focus:border-phantom-accent"
            rows={3}
            placeholder="Memory content..."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
          />
          <div className="flex gap-2">
            <select
              className="bg-phantom-bg border border-phantom-border rounded px-2 py-1 text-xs text-phantom-text focus:outline-none"
              value={newType}
              onChange={(e) => setNewType(e.target.value as MemoryType)}
            >
              <option value="episodic">Episodic</option>
              <option value="semantic">Semantic</option>
              <option value="workflow">Workflow</option>
            </select>
            <input
              className="flex-1 bg-phantom-bg border border-phantom-border rounded px-2 py-1 text-xs text-phantom-text placeholder-phantom-muted focus:outline-none"
              placeholder="Tags (comma separated)"
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
            />
            <button
              onClick={() => createMut.mutate({
                content: newContent,
                memory_type: newType,
                tags: newTags.split(',').map(t => t.trim()).filter(Boolean),
              })}
              disabled={!newContent.trim()}
              className="px-3 py-1 bg-phantom-accent text-white rounded text-xs disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-3">
        {TABS.map(({ label, type }) => (
          <button
            key={type}
            onClick={() => setTab(type)}
            className={clsx(
              'px-3 py-1.5 rounded text-xs transition-all',
              tab === type
                ? 'bg-phantom-accent text-white'
                : 'text-phantom-muted hover:text-phantom-text border border-phantom-border'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-3">
        <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-phantom-muted" />
        <input
          className="w-full bg-phantom-surface border border-phantom-border rounded pl-8 pr-3 py-2 text-xs text-phantom-text placeholder-phantom-muted focus:outline-none focus:border-phantom-accent"
          placeholder="Search memories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Memory list */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {isLoading && (
          <div className="flex justify-center py-8 text-phantom-muted text-xs">Loading...</div>
        )}
        {!isLoading && memories.length === 0 && (
          <div className="flex flex-col items-center py-12 text-phantom-muted text-xs gap-2">
            <Brain size={32} className="opacity-20" />
            <p>No memories found</p>
          </div>
        )}
        {memories.map((entry) => (
          <div
            key={entry.id}
            className="bg-phantom-surface border border-phantom-border rounded-lg px-3 py-2.5 group"
          >
            <div className="flex items-start gap-2">
              <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border flex-shrink-0', TYPE_COLORS[entry.memory_type])}>
                {entry.memory_type}
              </span>
              <p className="text-xs text-phantom-text flex-1 leading-relaxed">{entry.content}</p>
              <button
                onClick={() => deleteMut.mutate(entry.id)}
                className="opacity-0 group-hover:opacity-100 text-phantom-muted hover:text-phantom-danger transition-all flex-shrink-0"
              >
                <Trash2 size={12} />
              </button>
            </div>
            {entry.tags.length > 0 && (
              <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                <Tag size={10} className="text-phantom-muted" />
                {entry.tags.map((tag) => (
                  <span key={tag} className="text-[10px] text-phantom-muted bg-phantom-border px-1.5 py-0.5 rounded">
                    {tag}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[10px] text-phantom-muted mt-1">
              {format(new Date(entry.created_at), 'MMM d, HH:mm')}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
