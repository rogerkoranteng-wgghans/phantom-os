import { Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Brain, Workflow, ScrollText, Settings, Zap } from 'lucide-react'
import clsx from 'clsx'
import Dashboard from './pages/Dashboard'
import MemoryPage from './pages/MemoryPage'
import WorkflowPage from './pages/WorkflowPage'
import AuditPage from './pages/AuditPage'
import { usePhantomStore } from './store/phantomStore'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/memory', icon: Brain, label: 'Memory' },
  { to: '/workflows', icon: Workflow, label: 'Workflows' },
  { to: '/audit', icon: ScrollText, label: 'Audit Log' },
]

export default function App() {
  const connected = usePhantomStore((s) => s.connected)

  return (
    <div className="flex h-screen bg-phantom-bg text-phantom-text font-mono overflow-hidden">
      {/* Sidebar */}
      <aside className="w-16 flex flex-col items-center py-4 bg-phantom-surface border-r border-phantom-border gap-2">
        {/* Logo */}
        <div className="w-10 h-10 rounded-lg bg-phantom-accent flex items-center justify-center mb-4 animate-pulse-glow">
          <Zap size={20} className="text-white" />
        </div>

        {/* Connection dot */}
        <div
          className={clsx(
            'w-2 h-2 rounded-full mb-2',
            connected ? 'bg-phantom-success' : 'bg-phantom-muted'
          )}
          title={connected ? 'Connected' : 'Disconnected'}
        />

        {/* Nav items */}
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={label}
            className={({ isActive }) =>
              clsx(
                'w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-150',
                isActive
                  ? 'bg-phantom-accent text-white'
                  : 'text-phantom-muted hover:text-phantom-text hover:bg-phantom-border'
              )
            }
          >
            <Icon size={18} />
          </NavLink>
        ))}

        {/* Settings at bottom */}
        <div className="flex-1" />
        <button
          className="w-10 h-10 rounded-lg flex items-center justify-center text-phantom-muted hover:text-phantom-text hover:bg-phantom-border transition-all"
          title="Settings"
        >
          <Settings size={18} />
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/workflows" element={<WorkflowPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </main>
    </div>
  )
}
