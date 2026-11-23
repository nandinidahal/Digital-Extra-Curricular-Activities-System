// import { Megaphone } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { Button } from "@/components/common/Button";
import { cn } from "@/utils/cn";
import { Logo } from "./Logo";
import {Footer} from "../layout/Footer"

/** Navbar for logged-out visitors: brand, Announcements, Create Account, Log In. */
export function PublicNavbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Logo />
          <NavLink
            to="/"
            end
            className={({ isActive }) => cn("hidden items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium sm:inline-flex", isActive ? "text-brand-800" : "text-slate-600 hover:text-slate-900")}
          >
            {/* <Megaphone className="h-4 w-4" /> Announcements */}
          </NavLink>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/login"><Button variant="ghost" size="sm" className="sm:h-10 sm:px-4">Log in</Button></Link>
          <Link to="/register"><Button size="sm" className="sm:h-10 sm:px-4">Create account</Button></Link>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter() {
  return (
    // <footer className="border-t border-slate-200 bg-white">
    //   {/* <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-6 text-sm text-slate-500 sm:flex-row">
    //     <Logo compact />
    //     <p>Digital Extra-Curricular Activities System · From Screen Time to Life Time</p>
    //   </div> */}
    // </footer>
    <Footer/>
  );
}
