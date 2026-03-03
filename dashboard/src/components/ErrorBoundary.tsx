import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[Phantom] Component error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="flex flex-col items-center justify-center h-full bg-phantom-bg text-phantom-text p-8">
            <div className="text-phantom-danger text-2xl mb-2">⚠</div>
            <p className="text-sm text-phantom-danger mb-1">Component Error</p>
            <p className="text-xs text-phantom-muted max-w-md text-center font-mono">
              {this.state.error.message}
            </p>
            <button
              className="mt-4 px-4 py-2 text-xs border border-phantom-border rounded hover:border-phantom-accent text-phantom-muted hover:text-phantom-text transition-all"
              onClick={() => this.setState({ error: null })}
            >
              Retry
            </button>
          </div>
        )
      )
    }
    return this.props.children
  }
}
