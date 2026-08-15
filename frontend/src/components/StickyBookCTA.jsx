import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function StickyBookCTA() {
  return (
    <div className="md:hidden fixed bottom-0 inset-x-0 z-40 glass border-t border-white/5 px-4 py-3" data-testid="sticky-book-cta">
      <Link to="/reservar">
        <Button data-testid="sticky-book-btn" className="w-full h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine text-base">
          RESERVAR CITA
        </Button>
      </Link>
    </div>
  );
}
