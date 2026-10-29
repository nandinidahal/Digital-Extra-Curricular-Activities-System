import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="bg-pine-800 text-pine-100">
      <div className="container-page grid gap-10 py-14 md:grid-cols-4">
        <div className="md:col-span-2">
          <p className="font-display text-2xl font-bold text-white">XCA</p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed">
            One place for every club, tournament and workshop on campus. Sign up, show up, and keep
            proof of what you achieved.
          </p>
        </div>

        <div>
          <p className="font-display font-semibold text-white">Explore</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link to="/activities" className="hover:text-marigold-300">All activities</Link></li>
            <li><Link to="/verify/check" className="hover:text-marigold-300">Verify a certificate</Link></li>
            <li><Link to="/login" className="hover:text-marigold-300">Log in</Link></li>
            <li><Link to="/register" className="hover:text-marigold-300">Create account</Link></li>
          </ul>
        </div>

        <div>
          <p className="font-display font-semibold text-white">Contact</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li>Student Affairs Office</li>
            <li>Kathmandu, Nepal</li>
            <li>xca@jking.com.np</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 py-5 text-center text-xs">
        © {new Date().getFullYear()} Digital Extra-Curricular Activities. All rights reserved.
      </div>
    </footer>
  );
}
