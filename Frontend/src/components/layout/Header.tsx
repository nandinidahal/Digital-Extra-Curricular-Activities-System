import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { dashboardPath } from "../../utils/format";

// Section links scroll the home page. BASE_URL keeps them working under /xca/
const home = import.meta.env.BASE_URL;
const links = [
  { label: "Activities", href: `${home}#activities` },
  { label: "Categories", href: `${home}#categories` },
  { label: "How it works", href: `${home}#how-it-works` },
  { label: "News", href: `${home}#news` },
];

export default function Header() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-pine-100 bg-paper/95 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-display text-xl font-bold text-pine-700">
          <span className="grid h-8 w-8 place-items-center rounded-md bg-marigold-400 text-sm text-ink">X</span>
          XCA
        </Link>

        {/* Desktop navigation */}
        <nav className="hidden items-center gap-7 md:flex" aria-label="Main">
          {links.map((l) => (
            <a key={l.label} href={l.href} className="text-sm font-medium text-ink/80 hover:text-pine-700">
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {user ? (
            <>
              <Link to={dashboardPath(user.role)} className="btn-outline">My dashboard</Link>
              <button onClick={logout} className="text-sm font-medium text-ink/70 hover:text-brick">Log out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-sm font-semibold text-pine-700">Log in</Link>
              <Link to="/register" className="btn-primary">Create account</Link>
            </>
          )}
        </div>

        {/* Mobile menu button */}
        <button
          className="rounded-md p-2 md:hidden"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>

      {/* Mobile navigation */}
      {open && (
        <div className="border-t border-pine-100 bg-paper md:hidden">
          <div className="container-page flex flex-col gap-1 py-3">
            {links.map((l) => (
              <a key={l.label} href={l.href} onClick={() => setOpen(false)} className="rounded-md px-2 py-2.5 font-medium hover:bg-pine-50">
                {l.label}
              </a>
            ))}
            <div className="mt-2 flex gap-3">
              {user ? (
                <Link to={dashboardPath(user.role)} onClick={() => setOpen(false)} className="btn-primary flex-1">My dashboard</Link>
              ) : (
                <>
                  <Link to="/login" onClick={() => setOpen(false)} className="btn-outline flex-1">Log in</Link>
                  <Link to="/register" onClick={() => setOpen(false)} className="btn-primary flex-1">Create account</Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
