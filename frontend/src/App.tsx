import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Checklist from "./pages/Checklist";
import Sources from "./pages/Sources";
import About from "./pages/About";

const NAV_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/chat", label: "Chat" },
  { to: "/checklist", label: "Checklist" },
  { to: "/sources", label: "Sources" },
  { to: "/about", label: "About" },
];

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <NavLink to="/" className="text-lg font-semibold text-brand-700">
            CampusGuide AI
          </NavLink>
          <nav className="flex gap-1">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/checklist" element={<Checklist />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        CampusGuide AI is an unofficial, student-built portfolio project — not
        affiliated with the University of Illinois Urbana-Champaign.
      </footer>
    </div>
  );
}
