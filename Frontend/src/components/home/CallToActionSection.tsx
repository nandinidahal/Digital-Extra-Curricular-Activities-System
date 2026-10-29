import { Link } from "react-router-dom";

export default function CallToActionSection() {
  return (
    <section className="container-page pb-20">
      <div className="rounded-3xl bg-marigold-400 px-8 py-12 text-center md:py-16">
        <h2 className="text-3xl font-bold sm:text-4xl">Your next certificate is one sign-up away</h2>
        <p className="mx-auto mt-3 max-w-lg text-ink/80">Free for every enrolled student.</p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link to="/register" className="btn bg-ink text-white hover:bg-pine-800">Create account</Link>
          <Link to="/verify/check" className="btn border border-ink/40 hover:bg-white/40">Verify a certificate</Link>
        </div>
      </div>
    </section>
  );
}
