
// import { Link } from "react-router-dom";
// import {
//   Home,
//   Megaphone,
//   Award,
//   Users,
//   MessageCircle,
//   User,
//   Mail,
// } from "lucide-react";
// import { Logo } from "./Logo";

// const footerLinks = [
//   { to: "/home", label: "Home", icon: Home },
//   { to: "/announcements", label: "Events", icon: Megaphone },
//   { to: "/achievements", label: "Achievements", icon: Award },
//   { to: "/friends", label: "Friends", icon: Users },
//   { to: "/messages", label: "Messages", icon: MessageCircle },
//   { to: "/profile", label: "My Profile", icon: User },
// ];

// export function Footer() {
//   return (
//     <footer className="mt-auto border-t border-slate-200 bg-white">
//       <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
//         <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
//           {/* Brand */}
          // <div>
          //   <Logo to="/home" />
          //   <p className="mt-4 max-w-sm text-sm leading-6 text-slate-500">
          //     A digital platform for managing extracurricular activities,
          //     showcasing student achievements, and connecting students
          //     through campus activities.
          //   </p>
          // </div>

//           {/* Quick Links */}
//           <div>
//             <h3 className="mb-4 text-sm font-semibold text-slate-900">
//               Quick Links
//             </h3>

//             <div className="grid grid-cols-2 gap-x-4 gap-y-3">
//               {footerLinks.map(({ to, label, icon: Icon }) => (
//                 <Link
//                   key={to}
//                   to={to}
//                   className="flex items-center gap-2 text-sm text-slate-500 transition hover:text-brand-700"
//                 >
//                   <Icon className="h-4 w-4" />
//                   {label}
//                 </Link>
//               ))}
//             </div>
//           </div>

//           {/* Contact */}
//           <div>
//             <h3 className="mb-4 text-sm font-semibold text-slate-900">
//               Need Help?
//             </h3>

//             <p className="text-sm leading-6 text-slate-500">
//               Have questions or need assistance with the platform?
//               Contact the support team.
//             </p>

//             <a
//               href="mailto:support@example.com"
//               className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-brand-700 transition hover:text-brand-900"
//             >
//               <Mail className="h-4 w-4" />
//               Contact Support
//             </a>
//           </div>
//         </div>

//         {/* Bottom Bar */}
//         <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-slate-100 pt-6 text-center sm:flex-row sm:text-left">
//           <p className="text-xs text-slate-500">
//             © {new Date().getFullYear()} XCA. All rights reserved.
//           </p>

//           <p className="text-xs text-slate-400">
//             Digital Extra-Curricular Activities System
//           </p>
//         </div>
//       </div>
//     </footer>
//   );
// }


import { Link } from "react-router-dom";
import {
  ArrowRight,
  Home,
  Megaphone,
  Award,
  Users,
  MessageCircle,
  User,
  Mail,
} from "lucide-react";
import { Logo } from "./Logo";

// const footerLinks = [
//   { label: "Home", icon: Home },
//   { label: "Events", icon: Megaphone },
//   { label: "Achievements", icon: Award },
//   { label: "Students", icon: Users },
//   { label: "Messages", icon: MessageCircle },
//   { label: "My Profile", icon: User },
// ];

const footerLinks = [
  { label: "Home", to: "/home", icon: Home },
  { label: "Events", to: "/announcements", icon: Megaphone },
  { label: "Achievements", to: "/achievements", icon: Award },
  { label: "Students", to: "/friends", icon: Users },
  { label: "Messages", to: "/messages", icon: MessageCircle },
  { label: "My Profile", to: "/profile", icon: User },
];

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8">

        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-3">

          {/* Brand */}
          <div>
            <Logo to="/login" />

            <p className="mt-4 max-w-sm text-sm leading-7 text-slate-500">
              A digital platform that helps students manage extracurricular
              activities, showcase achievements, and stay connected with
              their campus community.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="mb-5 text-sm font-semibold text-slate-900">
              Quick Links
            </h3>

            <div className="grid grid-cols-2 gap-x-5 gap-y-4">
              {footerLinks.map(({ label, icon: Icon }) => (
                <Link
                  key={label}
                  to="/login"
                  className="group flex items-center gap-2 text-sm text-slate-500 transition-colors duration-200 hover:text-brand-700"
                >
                  <Icon
                    size={16}
                    className="text-slate-400 transition-colors group-hover:text-brand-700"
                  />
                  <span>{label}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Support */}
          <div>
            <h3 className="mb-5 text-sm font-semibold text-slate-900">
              Need Help?
            </h3>

            <p className="max-w-xs text-sm leading-7 text-slate-500">
              Have questions or need assistance? We're here to help you
              get the most out of your campus activity experience.
            </p>

            <a
              href="mailto:support@example.com"
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-brand-50 px-4 py-2.5 text-sm font-semibold text-brand-700 transition hover:bg-brand-100"
            >
              <Mail size={16} />
              Contact Support
              <ArrowRight size={15} />
            </a>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">

          <p className="text-center text-xs text-slate-500 sm:text-left">
            © {new Date().getFullYear()} DEAS. All rights reserved.
          </p>

          <div className="flex items-center justify-center gap-5 text-xs text-slate-400">
            <Link to="/login" className="transition hover:text-brand-700">
              Privacy
            </Link>

            <Link to="/login" className="transition hover:text-brand-700">
              Terms
            </Link>

            <span>Made for Students</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
