import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts'
import { AlertTriangle } from 'lucide-react'
import type { EmotionContext } from '../../types'

interface Props {
  emotion: EmotionContext | null
}

export default function EmotionWidget({ emotion }: Props) {
  const data = [
    { metric: 'Frustration', value: Math.round((emotion?.frustration ?? 0) * 100) },
    { metric: 'Confidence', value: Math.round((emotion?.confidence ?? 0.5) * 100) },
    { metric: 'Urgency', value: Math.round((emotion?.urgency ?? 0) * 100) },
    { metric: 'Engagement', value: Math.round((emotion?.engagement ?? 0.5) * 100) },
  ]

  const isFrustrated = (emotion?.frustration ?? 0) > 0.7

  return (
    <div className="bg-phantom-surface border border-phantom-border rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-phantom-muted uppercase tracking-widest">Emotional Context</p>
        {isFrustrated && (
          <div className="flex items-center gap-1 text-phantom-warning text-xs">
            <AlertTriangle size={12} />
            <span>Frustrated</span>
          </div>
        )}
      </div>

      {emotion ? (
        <>
          <ResponsiveContainer width="100%" height={160}>
            <RadarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <PolarGrid stroke="#1e1e2e" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono' }}
              />
              <Radar
                dataKey="value"
                stroke="#7c3aed"
                fill="#7c3aed"
                fillOpacity={0.3}
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>

          <div className="grid grid-cols-2 gap-1.5 mt-1">
            {data.map((d) => (
              <div key={d.metric} className="flex justify-between text-[10px]">
                <span className="text-phantom-muted">{d.metric}</span>
                <span className="text-phantom-text">{d.value}%</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center h-32 text-phantom-muted text-xs">
          No camera data
        </div>
      )}
    </div>
  )
}
