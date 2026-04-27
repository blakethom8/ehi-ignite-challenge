import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, Home, RotateCcw } from "lucide-react";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Unhandled React error", error, errorInfo);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <main className="flex min-h-screen items-center justify-center bg-[#f7f8fb] px-6 py-12">
        <section className="w-full max-w-xl rounded-lg border border-[#e9eaef] bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#fff1f2] text-[#dc2626]">
              <AlertTriangle size={22} />
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#dc2626]">
                Workspace Error
              </p>
              <h1 className="text-xl font-semibold text-[#1c1c1e]">
                This view hit an unexpected error.
              </h1>
              <p className="mt-2 text-sm leading-6 text-[#555a6a]">
                The app shell is still available. You can retry the current view or return to the
                clinical workspace.
              </p>
            </div>
          </div>

          {import.meta.env.DEV && (
            <pre className="mb-5 max-h-40 overflow-auto rounded-md bg-[#f5f6f8] p-3 text-xs leading-5 text-[#555a6a]">
              {this.state.error.message}
            </pre>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={this.reset}
              className="inline-flex items-center gap-2 rounded-md bg-[#5b76fe] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#4d63d8]"
            >
              <RotateCcw size={16} />
              Retry view
            </button>
            <a
              href="/explorer"
              className="inline-flex items-center gap-2 rounded-md border border-[#d9dce7] bg-white px-4 py-2 text-sm font-medium text-[#1c1c1e] transition-colors hover:bg-[#f5f6f8]"
            >
              <Home size={16} />
              Clinical workspace
            </a>
          </div>
        </section>
      </main>
    );
  }
}
