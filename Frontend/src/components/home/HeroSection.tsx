import { Link } from "react-router-dom";

export default function HeroSection() {
  return (
    <section className="bg-pine-700 text-white">
      <div className="container-page grid items-center gap-12 py-16 md:grid-cols-5 md:py-24">
        <div className="md:col-span-3">
          <h1 className="text-4xl font-bold leading-[1.1] sm:text-5xl lg:text-6xl">
            Discover it. Join it. Get recognised for it.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-pine-100">
            Every sports match, hackathon, concert and clean-up drive on campus, in one place. Register
            in a minute and collect certificates you can prove are real.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href={`${import.meta.env.BASE_URL}#activities`} className="btn-accent">Explore activities</a>
            <Link to="/login" className="btn border border-white/40 text-white hover:bg-white/10">Log in</Link>
          </div>
        </div>

        {/* A sample registration ticket, to show what the system gives you */}
        <div className="md:col-span-2">
          <div className="-rotate-2 rounded-2xl bg-paper p-6 text-ink shadow-xl">
            <p className="text-sm font-semibold text-pine-700">You are registered</p>
            <p className="mt-2 font-display text-2xl font-bold">Inter-College Futsal Cup</p>
            <p className="mt-1 text-sm text-ink/70">14 Nov 2026, College Ground</p>
            <div className="mt-5 flex items-center justify-between border-t border-dashed border-pine-600/30 pt-4 text-sm">
              <span>Status</span>
              <span className="rounded-full bg-green-100 px-3 py-1 font-semibold text-green-800">Approved</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
