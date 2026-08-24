import { Scissors, MapPin, Star } from "lucide-react";

export default function Footer({ business }) {
  return (
    <footer className="border-t border-white/5 mt-24 py-12 px-6" data-testid="footer">
      <div className="max-w-7xl mx-auto grid md:grid-cols-3 gap-8 text-sm text-neutral-400">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Scissors className="h-5 w-5 text-[#D4B77A]" />
            <span className="font-display text-2xl italic text-neutral-100">+58 BarberStudio</span>
          </div>
          <p className="leading-relaxed">Barbería boutique en Tenerife. Estilo, precisión y respeto por tu tiempo.</p>
        </div>
        <div>
          <p className="tracking-overline uppercase text-xs text-neutral-500 mb-3">Contacto</p>
          <p className="flex gap-2 items-start"><MapPin className="h-4 w-4 text-[#D4B77A] mt-0.5" /> {business?.address}</p>
          {business?.reviews_url && (
            <a href={business.reviews_url} target="_blank" rel="noreferrer" className="flex gap-2 items-center mt-2 hover:text-[#D4B77A]"><Star className="h-4 w-4 text-[#D4B77A]" /> Déjanos tu reseña</a>
          )}
        </div>
        <div>
          <p className="tracking-overline uppercase text-xs text-neutral-500 mb-3">Legal</p>
          <p className="leading-relaxed">Política de reserva: se requiere aceptar el compromiso del 50% al reservar. Cancelaciones hasta 12 horas antes.</p>
        </div>
      </div>
      <p className="mt-10 text-center text-xs text-neutral-600">© {new Date().getFullYear()} +58 BarberStudio · Hecho con ✂ en Tenerife</p>
    </footer>
  );
}
