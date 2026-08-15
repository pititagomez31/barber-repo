import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X, Scissors } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    { href: "#servicios", label: "Servicios" },
    { href: "#galeria", label: "Galería" },
    { href: "#sobre", label: "El Barbero" },
    { href: "#opiniones", label: "Opiniones" },
    { href: "#ubicacion", label: "Ubicación" },
  ];

  return (
    <header data-testid="navbar" className={`fixed top-0 inset-x-0 z-40 transition-[background,border,padding] duration-300 ${scrolled ? "glass border-b border-white/5 py-3" : "py-5"}`}>
      <div className="max-w-7xl mx-auto px-5 md:px-10 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="brand-logo">
          <Scissors className="h-5 w-5 text-[#D4B77A]" />
          <span className="font-display text-xl tracking-tight">+58 <span className="text-[#D4B77A]">BarberStudio</span></span>
        </Link>
        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="text-sm text-neutral-300 hover:text-[#D4B77A] transition-colors" data-testid={`nav-${l.label.toLowerCase()}`}>{l.label}</a>
          ))}
          <Link to="/reservar">
            <Button data-testid="nav-book-btn" className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold rounded-md btn-shine">RESERVAR</Button>
          </Link>
        </nav>
        <button onClick={() => setOpen((v) => !v)} className="md:hidden text-neutral-200" data-testid="nav-mobile-toggle" aria-label="Menú">
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>
      {open && (
        <div className="md:hidden glass border-t border-white/5 mt-3">
          <div className="max-w-7xl mx-auto px-5 py-4 flex flex-col gap-4">
            {links.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="text-neutral-200 py-2" data-testid={`nav-mobile-${l.label.toLowerCase()}`}>{l.label}</a>
            ))}
            <Link to="/reservar" onClick={() => setOpen(false)}>
              <Button data-testid="nav-mobile-book-btn" className="w-full bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold">RESERVAR CITA</Button>
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
