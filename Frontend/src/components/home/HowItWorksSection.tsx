import SectionHeading from "../common/SectionHeading";

// This is a real sequence, so numbered steps make sense here
const steps = [
  { title: "Create an account", text: "Sign up with your email. It takes under a minute." },
  { title: "Register for an activity", text: "Open any activity and press Register. A coordinator reviews it." },
  { title: "Show up", text: "Coordinators mark attendance on the day, and you get a notification." },
  { title: "Collect your certificate", text: "Download it as a PDF. Anyone can verify it with its code." },
];

export default function HowItWorksSection() {
  return (
    <section id="how-it-works" className="container-page py-20">
      <SectionHeading title="From sign-up to certificate" />

      <ol className="mt-10 grid gap-8 md:grid-cols-4">
        {steps.map((s, i) => (
          <li key={s.title}>
            <span className="grid h-10 w-10 place-items-center rounded-full bg-marigold-400 font-display font-bold">
              {i + 1}
            </span>
            <h3 className="mt-4 text-xl font-bold">{s.title}</h3>
            <p className="mt-2 leading-relaxed text-ink/70">{s.text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
