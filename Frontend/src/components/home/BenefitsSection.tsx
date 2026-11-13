// import SectionHeading from "../common/SectionHeading";

// const benefits = [
//   { title: "No more paper forms", text: "Register, cancel and check your status from your phone." },
//   { title: "A record that follows you", text: "Every activity, award and attendance is saved on your profile." },
//   { title: "Certificates people can trust", text: "Each one has a unique number that anyone can check online." },
//   { title: "Fair for everyone", text: "Deadlines and slot limits are enforced automatically." },
// ];

// export default function BenefitsSection() {
//   return (
//     <section className="bg-pine-800 py-20 text-white">
//       <div className="container-page grid gap-12 md:grid-cols-2">
//         <SectionHeading title="Why students and coordinators use XCA" text="Less chasing, more doing." />
//         <dl className="grid gap-6 sm:grid-cols-2">
//           {benefits.map((b) => (
//             <div key={b.title} className="border-l-2 border-marigold-400 pl-4">
//               <dt className="font-display text-lg font-bold">{b.title}</dt>
//               <dd className="mt-1 text-sm leading-relaxed text-pine-100">{b.text}</dd>
//             </div>
//           ))}
//         </dl>
//       </div>
//     </section>
//   );
// }


import {
  LuFileText,
  LuUserRound,
  LuAward,
  LuUsers,
} from "react-icons/lu";

const benefits = [
  {
    title: "No more paper forms",
    text: "Register, cancel and check your status from your phone.",
    icon: LuFileText,
  },
  {
    title: "A record that follows you",
    text: "Every activity, award and attendance is saved on your profile.",
    icon: LuUserRound,
  },
  {
    title: "Certificates people can trust",
    text: "Each one has a unique number that anyone can check online.",
    icon: LuAward,
  },
  {
    title: "Fair for everyone",
    text: "Deadlines and slot limits are enforced automatically.",
    icon: LuUsers,
  },
];

export default function BenefitsSection() {
  return (
    <section className="bg-pine-50 px-5 py-16 sm:px-8 lg:py-20">
      <div className="mx-auto max-w-5xl">

        {/* Section Heading */}
        <div className="mb-10 text-center">
          <h2 className="font-display text-3xl font-semibold text-pine-900 sm:text-4xl">
            {/* Why Students and Coordinators Use XCA */}
             Why  Use XCA
          </h2>

          <p className="mt-3 text-base text-pine-700 sm:text-lg">
            Less chasing, more doing.
          </p>
        </div>

        {/* Benefits Cards */}
        <div className="mx-auto grid grid-cols-1 gap-6 sm:grid-cols-2 lg:gap-8">

          {benefits.map((benefit, index) => {
            const Icon = benefit.icon;

            const isGreen = index === 0 || index === 3;

            return (
              <div
                key={benefit.title}
                className={`
                  group flex min-h-[100px] flex-col
                  items-center justify-center
                  rounded-2xl border p-7 text-center
                  shadow-sm
                  transition-all duration-300
                  hover:-translate-y-1.5 hover:shadow-lg
                  sm:min-h-[200px] sm:p-8
                  cursor-pointer
                  ${
                    isGreen
                      ? "border-pine-200 bg-pine-100"
                      : "border-white bg-white"
                  }
                `}
              >

                {/* Icon */}
                <div
                  className={`
                    mb-5 flex h-14 w-14 items-center
                    justify-center rounded-2xl
                    transition-transform duration-300
                    group-hover:scale-110
                    ${
                      isGreen
                        ? "bg-pine-200 text-pine-800"
                        : "bg-pine-50 text-pine-800"
                    }
                  `}
                >
                  <Icon size={30} strokeWidth={1.8} />
                </div>

                {/* Title */}
                <h3 className="font-display text-lg font-bold text-pine-900 sm:text-xl">
                  {benefit.title}
                </h3>

                {/* Description */}
                <p className="mt-3 max-w-sm text-sm leading-relaxed text-pine-700">
                  {benefit.text}
                </p>

              </div>
            );
          })}

        </div>
      </div>
    </section>
  );
}
