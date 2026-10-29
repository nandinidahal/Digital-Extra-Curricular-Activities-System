
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SectionHeading from "../common/SectionHeading";
import { activityService } from "../../services/activityService";
import { mockCategories } from "../../data/mockData";
import type { Category } from "../../types";

export default function CategoriesSection() {
  const [categories, setCategories] = useState<Category[]>([]);

  useEffect(() => {
    activityService
      .categories()
      .then((data) => {
        // Ensure the response is an array
        if (Array.isArray(data)) {
          setCategories(data);
        } else {
          setCategories(mockCategories);
        }
      })
      .catch(() => {
        setCategories(mockCategories);
      });
  }, []);

  return (
    <section id="categories" className="bg-pine-50 py-20">
      <div className="container-page">
        <SectionHeading
          title="Find your thing"
          text="Pick a category to see what is happening in it."
        />

        <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
          {(categories ?? []).map((c) => (
            <Link
              key={c.id}
              to={`/activities?category=${c.id}`}
              className="rounded-xl bg-white p-5 transition-colors hover:bg-marigold-300/40"
            >
              <span className="text-3xl" aria-hidden="true">
                {c.icon}
              </span>

              <p className="mt-3 font-display text-lg font-bold">
                {c.name}
              </p>

              <p className="mt-1 text-sm text-ink/70">
                {c.description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}





// import { useEffect, useState } from "react";
// import { Link } from "react-router-dom";
// import SectionHeading from "../common/SectionHeading";
// import { activityService } from "../../services/activityService";
// import { mockCategories } from "../../data/mockData";
// import type { Category } from "../../types";

// export default function CategoriesSection() {
//   const [categories, setCategories] = useState<Category[]>([]);

//   useEffect(() => {
//     activityService.categories().then(setCategories).catch(() => setCategories(mockCategories));
//   }, []);

//   return (
//     <section id="categories" className="bg-pine-50 py-20">
//       <div className="container-page">
//         <SectionHeading title="Find your thing" text="Pick a category to see what is happening in it." />

//         <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
//           {categories.map((c) => (
//             <Link
//               key={c.id}
//               to={`/activities?category=${c.id}`}
//               className="rounded-xl bg-white p-5 transition-colors hover:bg-marigold-300/40"
//             >
//               <span className="text-3xl" aria-hidden="true">{c.icon}</span>
//               <p className="mt-3 font-display text-lg font-bold">{c.name}</p>
//               <p className="mt-1 text-sm text-ink/70">{c.description}</p>
//             </Link>
//           ))}
//         </div>
//       </div>
//     </section>
//   );
// }





