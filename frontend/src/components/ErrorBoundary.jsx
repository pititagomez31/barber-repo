import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("[+58 BarberStudio] ErrorBoundary:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#14141A] text-neutral-100 grid place-items-center px-6 py-10" data-testid="error-boundary">
          <div className="max-w-md text-center">
            <div className="h-14 w-14 mx-auto rounded-full border border-[#D4B77A]/40 grid place-items-center mb-5">
              <span className="text-[#D4B77A] text-2xl">!</span>
            </div>
            <p className="tracking-[0.2em] uppercase text-xs text-[#D4B77A] mb-3">Ups</p>
            <h1 className="text-3xl italic mb-3" style={{fontFamily:"'Cormorant Garamond', serif"}}>Algo se ha torcido.</h1>
            <p className="text-sm text-neutral-400 leading-relaxed mb-6">
              La web ha tenido un problema al cargar. Prueba a recargar la página.
              Si sigue fallando, avisa al barbero.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="h-11 px-6 rounded-md bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold"
              data-testid="reload-btn"
            >
              Recargar
            </button>
            <p className="mt-6 text-[10px] text-neutral-600 font-mono break-all">{String(this.state.error?.message || "")}</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
