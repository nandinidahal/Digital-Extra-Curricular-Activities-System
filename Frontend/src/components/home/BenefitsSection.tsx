import SectionHeading from "../common/SectionHeading";

const benefits = [
  { title: "No more paper forms", text: "Register, cancel and check your status from your phone." },
  { title: "A record that follows you", text: "Every activity, award and attendance is saved on your profile." },
  { title: "Certificates people can trust", text: "Each one has a unique number that anyone can check online." },
  { title: "Fair for everyone", text: "Deadlines and slot limits are enforced automatically." },
];

export default function BenefitsSection() {
  return (
    <section className="bg-pine-800 py-20 text-white">
      <div className="container-page grid gap-12 md:grid-cols-2">
        <SectionHeading title="Why students and coordinators use XCA" text="Less chasing, more doing." />
        <dl className="grid gap-6 sm:grid-cols-2">
          {benefits.map((b) => (
            <div key={b.title} className="border-l-2 border-marigold-400 pl-4">
              <dt className="font-display text-lg font-bold">{b.title}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-pine-100">{b.text}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
