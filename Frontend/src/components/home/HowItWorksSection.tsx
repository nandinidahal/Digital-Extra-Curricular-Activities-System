// import SectionHeading from "../common/SectionHeading";

// // This is a real sequence, so numbered steps make sense here
// const steps = [
//   { title: "Create an account", text: "Sign up with your email. It takes under a minute." },
//   { title: "Register for an activity", text: "Open any activity and press Register. A coordinator reviews it." },
//   { title: "Show up", text: "Coordinators mark attendance on the day, and you get a notification." },
//   { title: "Collect your certificate", text: "Download it as a PDF. Anyone can verify it with its code." },
// ];

// export default function HowItWorksSection() {
//   return (
//     <section id="how-it-works" className="container-page py-20">
//       <SectionHeading title="From sign-up to certificate" />

//       <ol className="mt-10 grid gap-8 md:grid-cols-4">
//         {steps.map((s, i) => (
//           <li key={s.title}>
//             <span className="grid h-10 w-10 place-items-center rounded-full bg-marigold-400 font-display font-bold">
//               {i + 1}
//             </span>
//             <h3 className="mt-4 text-xl font-bold">{s.title}</h3>
//             <p className="mt-2 leading-relaxed text-ink/70">{s.text}</p>
//           </li>
//         ))}
//       </ol>
//     </section>
//   );
// }



import {
  LuUserPlus,
  LuClipboardList,
  LuCalendarCheck,
  LuAward,
} from "react-icons/lu";

const steps = [
  {
    title: "Create Your Account",
    icon: LuUserPlus,
  },
  {
    title: "Explore & Register",
    icon: LuClipboardList,
  },
  {
    title: "Attend the Activity",
    icon: LuCalendarCheck,
  },
  {
    title: "Earn Your Certificate",
    icon: LuAward,
  },
];

export default function HowItWorksSection() {
  return (
    <section
      id="how-it-works"
      className="bg-pine-800 px-5 py-16 sm:px-8 lg:py-20"
    >
      <div className="mx-auto max-w-6xl">

        {/* Section Heading */}
        <div className="mb-14 text-center">
          <h2 className="font-display text-3xl font-semibold text-white sm:text-4xl">
            From Sign-up to Certificate
          </h2>
          <p className="mt-4 text-base text-gray-400 sm:text-lg">
            Your journey to getting involved in extracurricular activities.
          </p>
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-8">

          {steps.map((step, index) => {
            const Icon = step.icon;
            const isGreen = index % 2 === 0;

            return (
              <div
                key={step.title}
                className="group flex flex-col items-center text-center"
              >

                {/* Icon Circle */}
                <div
                  className={`
                    flex h-20 w-20 items-center justify-center
                    rounded-full shadow-sm
                    transition-all duration-300
                    group-hover:-translate-y-2 group-hover:shadow-lg
                    ${
                      isGreen
                        ? "bg-pine-600 text-white"
                        : "bg-marigold-400 text-pine-900"
                    }
                  `}
                >
                  <Icon size={32} strokeWidth={1.8} />
                </div>

                {/* Step Title */}
                <h3 className="mt-6 max-w-[220px]  font-display text-lg   text-white sm:text-xl">
                  {step.title}
                </h3>

                {/* Accent Line */}
                {/* <span
                  className={`
                    mt-4 h-1 w-10 rounded-full
                    ${
                      isGreen
                        ? "bg-pine-300"
                        : "bg-marigold-400"
                    }
                  `}
                /> */}

              </div>
            );
          })}

        </div>
      </div>
    </section>
  );
}
