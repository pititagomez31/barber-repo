import { useEffect, useState } from "react";
import { MessageCircle, Star } from "lucide-react";
import { api } from "@/lib/api";

export default function FloatingContact() {
  const [b, setB] = useState({ whatsapp: "", reviews_url: "" });
  useEffect(() => {
    api.get("/business").then((r) => setB(r.data)).catch(() => {});
  }, []);
  const waMsg = encodeURIComponent("¡Hola +58 BarberStudio! Me gustaría reservar una cita.");
  return (
    <div className="fixed right-3 md:right-4 bottom-24 md:bottom-8 z-40 flex flex-col gap-2.5 md:gap-3" data-testid="floating-contact">
      {b.whatsapp && (
        <a data-testid="float-whatsapp" href={`https://wa.me/${b.whatsapp}?text=${waMsg}`} target="_blank" rel="noreferrer"
           className="h-11 w-11 md:h-12 md:w-12 grid place-items-center rounded-full bg-[#25D366] text-white shadow-lg hover:scale-105 active:scale-95 transition-transform">
          <MessageCircle className="h-5 w-5" />
        </a>
      )}
      {b.reviews_url && (
        <a data-testid="float-reviews" href={b.reviews_url} target="_blank" rel="noreferrer"
           className="h-11 w-11 md:h-12 md:w-12 grid place-items-center rounded-full bg-[#1A1A1E] border border-[#D4B77A]/50 text-[#D4B77A] shadow-lg hover:scale-105 active:scale-95 transition-transform" title="Deja tu reseña">
          <Star className="h-5 w-5 fill-[#D4B77A]" />
        </a>
      )}
    </div>
  );
}
