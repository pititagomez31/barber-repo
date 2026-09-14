import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Booking from "@/pages/Booking";
import AdminDashboard from "@/pages/AdminDashboard";
import { Scissors } from "lucide-react";

const Nav = () => {
  const loc = useLocation();
  return (
    <nav className="nav-bar" data-testid="main-nav">
      <Link to="/" className="brand" data-testid="brand-link">
        <Scissors size={22} className="brand-icon" />
        <span className="brand-name">+58 <b>BarberStudio</b></span>
      </Link>
      <div className="nav-links">
        <Link
          to="/"
          data-testid="nav-reservar"
          className={loc.pathname === "/" ? "nav-link active" : "nav-link"}
        >
          Reservar
        </Link>
        <Link
          to="/admin"
          data-testid="nav-admin"
          className={loc.pathname.startsWith("/admin") ? "nav-link active" : "nav-link"}
        >
          Panel barbero
        </Link>
      </div>
    </nav>
  );
};

function App() {
  useEffect(() => {
    document.title = "+58 BarberStudio";
  }, []);
  return (
    <div className="App">
      <BrowserRouter>
        <Nav />
        <Routes>
          <Route path="/" element={<Booking />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
