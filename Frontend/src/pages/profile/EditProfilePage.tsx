
// import { useEffect, useState, type FormEvent } from "react";
// import { Link, useNavigate } from "react-router-dom";
// import {
//   ArrowLeft,
//   LoaderCircle,
//   Save,
//   UserRound,
//   CalendarDays,
//   Phone,
//   MapPin,
//   FileText,
// } from "lucide-react";

// import DashboardLayout from "../../components/dashboard/DashboardLayout";
// import profileService from "../../services/profileService";
// import type { UserProfile } from "../../types/profile";

// import {
//   LayoutDashboard,
//   ClipboardList,
//   GraduationCap,
//   CircleUserRound,
// } from "lucide-react";

// const navItems = [
//   { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
//   { label: "My Activities", path: "/dashboard/activities", icon: ClipboardList },
//   { label: "Certificates", path: "/dashboard/certificates", icon: GraduationCap },
//   { label: "My Profile", path: "/dashboard/profile", icon: CircleUserRound },
// ];

// export default function EditProfilePage() {
//   const navigate = useNavigate();

//   const [loading, setLoading] = useState(true);
//   const [saving, setSaving] = useState(false);
//   const [error, setError] = useState("");
//   const [success, setSuccess] = useState("");

//   const [formData, setFormData] = useState({
//     full_name: "",
//     username: "",
//     date_of_birth: "",
//     bio: "",
//     phone_number: "",
//     country: "",
//   });

//   useEffect(() => {
//     const loadProfile = async () => {
//       try {
//         const profile: UserProfile =
//           await profileService.getMyProfile();

//         setFormData({
//           full_name: profile.full_name || "",
//           username: profile.username || "",
//           date_of_birth: profile.date_of_birth || "",
//           bio: profile.bio || "",
//           phone_number: profile.phone_number || "",
//           country: profile.country || "",
//         });
//       } catch (err) {
//         console.error("Profile loading error:", err);
//         setError("Unable to load profile information.");
//       } finally {
//         setLoading(false);
//       }
//     };

//     loadProfile();
//   }, []);

//   const handleChange = (
//     event: React.ChangeEvent<
//       HTMLInputElement | HTMLTextAreaElement
//     >
//   ) => {
//     const { name, value } = event.target;

//     setFormData((previous) => ({
//       ...previous,
//       [name]: value,
//     }));
//   };

//   const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
//     event.preventDefault();

//     setSaving(true);
//     setError("");
//     setSuccess("");

//     try {
//       await profileService.updateProfile(formData);

//       setSuccess("Your profile has been updated successfully.");

//       setTimeout(() => {
//         navigate("/dashboard/profile");
//       }, 1000);
//     } catch (err) {
//       console.error("Profile update error:", err);
//       setError("Unable to update profile. Please check your information.");
//     } finally {
//       setSaving(false);
//     }
//   };

//   if (loading) {
//     return (
//       <DashboardLayout
//         role="user"
//         title="Edit Profile"
//         subtitle="Update your personal information."
//         navItems={navItems}
//       >
//         <div className="flex justify-center py-16">
//           <LoaderCircle
//             size={32}
//             className="animate-spin text-[#315C4A]"
//           />
//         </div>
//       </DashboardLayout>
//     );
//   }

//   return (
//     <DashboardLayout
//       role="user"
//       title="Edit Profile"
//       subtitle="Keep your personal information up to date."
//       navItems={navItems}
//     >
//       <div className="mx-auto max-w-3xl space-y-6">

//         <Link
//           to="/dashboard/profile"
//           className="inline-flex items-center gap-2 text-sm font-medium text-[#315C4A] hover:underline"
//         >
//           <ArrowLeft size={17} />
//           Back to Profile
//         </Link>

//         <section className="rounded-xl border border-[#E1EAE4] bg-white p-6 sm:p-8">
//           <div className="mb-6">
//             <h2 className="text-xl font-bold text-gray-800">
//               Personal Information
//             </h2>

//             <p className="mt-1 text-sm text-gray-500">
//               Update the information displayed on your profile.
//             </p>
//           </div>

//           {error && (
//             <div className="mb-5 rounded-lg bg-red-50 p-3 text-sm text-red-600">
//               {error}
//             </div>
//           )}

//           {success && (
//             <div className="mb-5 rounded-lg bg-green-50 p-3 text-sm text-green-700">
//               {success}
//             </div>
//           )}

//           <form onSubmit={handleSubmit} className="space-y-5">

//             {/* Full Name */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 Full Name
//               </label>

//               <div className="relative">
//                 <UserRound
//                   size={18}
//                   className="absolute left-3 top-3 text-gray-400"
//                 />

//                 <input
//                   type="text"
//                   name="full_name"
//                   value={formData.full_name}
//                   onChange={handleChange}
//                   required
//                   placeholder="Enter your full name"
//                   className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
//                 />
//               </div>
//             </div>

//             {/* Username */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 Username
//               </label>

//               <input
//                 type="text"
//                 name="username"
//                 value={formData.username}
//                 onChange={handleChange}
//                 required
//                 placeholder="Enter your username"
//                 className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-[#315C4A]"
//               />
//             </div>

//             {/* Date of Birth */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 Date of Birth
//               </label>

//               <div className="relative">
//                 <CalendarDays
//                   size={18}
//                   className="absolute left-3 top-3 text-gray-400"
//                 />

//                 <input
//                   type="date"
//                   name="date_of_birth"
//                   value={formData.date_of_birth}
//                   onChange={handleChange}
//                   className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
//                 />
//               </div>
//             </div>

//             {/* Phone Number */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 Phone Number
//               </label>

//               <div className="relative">
//                 <Phone
//                   size={18}
//                   className="absolute left-3 top-3 text-gray-400"
//                 />

//                 <input
//                   type="tel"
//                   name="phone_number"
//                   value={formData.phone_number}
//                   onChange={handleChange}
//                   placeholder="Enter your phone number"
//                   className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
//                 />
//               </div>
//             </div>

//             {/* Country */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 Country
//               </label>

//               <div className="relative">
//                 <MapPin
//                   size={18}
//                   className="absolute left-3 top-3 text-gray-400"
//                 />

//                 <input
//                   type="text"
//                   name="country"
//                   value={formData.country}
//                   onChange={handleChange}
//                   placeholder="Enter your country"
//                   className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
//                 />
//               </div>
//             </div>

//             {/* Bio */}
//             <div>
//               <label className="mb-2 block text-sm font-medium text-gray-700">
//                 About Me
//               </label>

//               <div className="relative">
//                 <FileText
//                   size={18}
//                   className="absolute left-3 top-3 text-gray-400"
//                 />

//                 <textarea
//                   name="bio"
//                   value={formData.bio}
//                   onChange={handleChange}
//                   rows={4}
//                   maxLength={500}
//                   placeholder="Write something about yourself..."
//                   className="w-full resize-none rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
//                 />
//               </div>

//               <p className="mt-1 text-right text-xs text-gray-400">
//                 {formData.bio.length}/500 characters
//               </p>
//             </div>

//             {/* Buttons */}
//             <div className="flex flex-wrap justify-end gap-3 border-t border-gray-100 pt-5">
//               <Link
//                 to="/dashboard/profile"
//                 className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 transition hover:bg-gray-50"
//               >
//                 Cancel
//               </Link>

//               <button
//                 type="submit"
//                 disabled={saving}
//                 className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#264A3B] disabled:cursor-not-allowed disabled:opacity-60"
//               >
//                 {saving ? (
//                   <LoaderCircle size={17} className="animate-spin" />
//                 ) : (
//                   <Save size={17} />
//                 )}

//                 {saving ? "Saving..." : "Save Changes"}
//               </button>
//             </div>
//           </form>
//         </section>
//       </div>
//     </DashboardLayout>
//   );
// }


import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  LoaderCircle,
  Save,
  UserRound,
  CalendarDays,
  Phone,
  MapPin,
  FileText,
  Code,
  Lightbulb,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import profileService from "../../services/profileService";
import type { UserProfile } from "../../types/profile";

const navItems = [
  { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { label: "Explore Activities", path: "/dashboard/activities", icon: ClipboardList },
  { label: "Certificates", path: "/dashboard/achievements", icon: GraduationCap },
  { label: "My Profile", path: "/dashboard/profile", icon: CircleUserRound },
];

// Keep the navigation icons in one import.
import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

interface ProfileFormData {
  full_name: string;
  username: string;
  date_of_birth: string;
  bio: string;
  phone_number: string;
  country: string;
  skills: string;
  interests: string;
}

const splitValues = (value: string): string[] => {
  return [
    ...new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    ),
  ];
};

export default function EditProfilePage() {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [formData, setFormData] = useState<ProfileFormData>({
    full_name: "",
    username: "",
    date_of_birth: "",
    bio: "",
    phone_number: "",
    country: "",
    skills: "",
    interests: "",
  });

  useEffect(() => {
    let active = true;

    const loadProfile = async () => {
      try {
        const profile: UserProfile = await profileService.getMyProfile();

        if (!active) return;

        setFormData({
          full_name: profile.full_name || "",
          username: profile.username || "",
          date_of_birth: profile.date_of_birth || "",
          bio: profile.bio || "",
          phone_number: profile.phone_number || "",
          country: profile.country || "",
          skills: (profile.skills ?? []).join(", "),
          interests: (profile.interests ?? []).join(", "),
        });
      } catch (err) {
        console.error("Profile loading error:", err);

        if (active) {
          setError("Unable to load profile information. Please try again.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadProfile();

    return () => {
      active = false;
    };
  }, []);

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = event.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const updatedData = {
        full_name: formData.full_name.trim(),
        username: formData.username.trim(),

        // Do not send an empty date string to Django's DateField.
        ...(formData.date_of_birth
          ? { date_of_birth: formData.date_of_birth }
          : {}),

        bio: formData.bio.trim(),
        phone_number: formData.phone_number.trim(),
        country: formData.country.trim(),

        // Convert comma-separated text into arrays.
        skills: splitValues(formData.skills),
        interests: splitValues(formData.interests),
      };

      await profileService.updateProfile(updatedData);

      setSuccess("Your profile has been updated successfully.");

      window.setTimeout(() => {
        navigate("/dashboard/profile");
      }, 1000);
    } catch (err) {
      console.error("Profile update error:", err);
      setError(
        "Unable to update your profile. Please check your information and try again."
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout
        role="user"
        title="Edit Profile"
        subtitle="Update your personal information, skills and interests."
        navItems={navItems}
      >
        <div className="flex justify-center py-16">
          <LoaderCircle
            size={32}
            className="animate-spin text-[#315C4A]"
          />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="user"
      title="Edit Profile"
      subtitle="Keep your personal information, skills and interests up to date."
      navItems={navItems}
    >
      <div className="mx-auto max-w-3xl space-y-6">
        <Link
          to="/dashboard/profile"
          className="inline-flex items-center gap-2 text-sm font-medium text-[#315C4A] hover:underline"
        >
          <ArrowLeft size={17} />
          Back to Profile
        </Link>

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Personal Information */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6 sm:p-8">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-gray-800">
                Personal Information
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Update the personal information displayed on your profile.
              </p>
            </div>

            <div className="space-y-5">
              {/* Full Name */}
              <div>
                <label
                  htmlFor="full_name"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  Full Name
                </label>

                <div className="relative">
                  <UserRound
                    size={18}
                    className="absolute left-3 top-3 text-gray-400"
                  />
                  <input
                    id="full_name"
                    type="text"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    required
                    placeholder="Enter your full name"
                    className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
                  />
                </div>
              </div>

              {/* Username */}
              <div>
                <label
                  htmlFor="username"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  Username
                </label>

                <input
                  id="username"
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  placeholder="Enter your username"
                  className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-[#315C4A]"
                />
              </div>

              {/* Date of Birth */}
              <div>
                <label
                  htmlFor="date_of_birth"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  Date of Birth
                </label>

                <div className="relative">
                  <CalendarDays
                    size={18}
                    className="absolute left-3 top-3 text-gray-400"
                  />
                  <input
                    id="date_of_birth"
                    type="date"
                    name="date_of_birth"
                    value={formData.date_of_birth}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
                  />
                </div>
              </div>

              {/* Phone Number */}
              <div>
                <label
                  htmlFor="phone_number"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  Phone Number
                </label>

                <div className="relative">
                  <Phone
                    size={18}
                    className="absolute left-3 top-3 text-gray-400"
                  />
                  <input
                    id="phone_number"
                    type="tel"
                    name="phone_number"
                    value={formData.phone_number}
                    onChange={handleChange}
                    placeholder="Enter your phone number"
                    className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
                  />
                </div>
              </div>

              {/* Country */}
              <div>
                <label
                  htmlFor="country"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  Country
                </label>

                <div className="relative">
                  <MapPin
                    size={18}
                    className="absolute left-3 top-3 text-gray-400"
                  />
                  <input
                    id="country"
                    type="text"
                    name="country"
                    value={formData.country}
                    onChange={handleChange}
                    placeholder="Enter your country"
                    className="w-full rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
                  />
                </div>
              </div>

              {/* Bio */}
              <div>
                <label
                  htmlFor="bio"
                  className="mb-2 block text-sm font-medium text-gray-700"
                >
                  About Me
                </label>

                <div className="relative">
                  <FileText
                    size={18}
                    className="absolute left-3 top-3 text-gray-400"
                  />
                  <textarea
                    id="bio"
                    name="bio"
                    value={formData.bio}
                    onChange={handleChange}
                    rows={4}
                    maxLength={500}
                    placeholder="Write something about yourself..."
                    className="w-full resize-none rounded-lg border border-gray-200 py-3 pl-10 pr-4 text-sm outline-none transition focus:border-[#315C4A]"
                  />
                </div>

                <p className="mt-1 text-right text-xs text-gray-400">
                  {formData.bio.length}/500 characters
                </p>
              </div>
            </div>
          </section>

          {/* Skills */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6 sm:p-8">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-[#E8F1EC] p-3">
                <Code size={21} className="text-[#315C4A]" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-gray-800">
                  My Skills
                </h2>
                <p className="mt-1 text-sm text-gray-500">
                  Add the skills you have learned or developed.
                </p>
              </div>
            </div>

            <label
              htmlFor="skills"
              className="mb-2 block text-sm font-medium text-gray-700"
            >
              Skills
            </label>

            <textarea
              id="skills"
              name="skills"
              value={formData.skills}
              onChange={handleChange}
              rows={4}
              placeholder="e.g. React, Python, HTML, CSS, Django"
              className="w-full resize-none rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-[#315C4A]"
            />

            <p className="mt-2 text-xs text-gray-500">
              Separate each skill with a comma.
            </p>

            {splitValues(formData.skills).length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {splitValues(formData.skills).map((skill) => (
                  <span
                    key={skill}
                    className="rounded-full border border-[#D5E5DA] bg-[#F3F8F5] px-3 py-1.5 text-xs font-medium text-[#315C4A]"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* Interests */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6 sm:p-8">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-[#E8F1EC] p-3">
                <Lightbulb size={21} className="text-[#315C4A]" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-gray-800">
                  My Interests
                </h2>
                <p className="mt-1 text-sm text-gray-500">
                  Tell others about the areas you are interested in.
                </p>
              </div>
            </div>

            <label
              htmlFor="interests"
              className="mb-2 block text-sm font-medium text-gray-700"
            >
              Interests
            </label>

            <textarea
              id="interests"
              name="interests"
              value={formData.interests}
              onChange={handleChange}
              rows={4}
              placeholder="e.g. Web Development, Artificial Intelligence, UI/UX Design"
              className="w-full resize-none rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-[#315C4A]"
            />

            <p className="mt-2 text-xs text-gray-500">
              Separate each interest with a comma.
            </p>

            {splitValues(formData.interests).length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {splitValues(formData.interests).map((interest) => (
                  <span
                    key={interest}
                    className="rounded-full border border-[#DCE5F2] bg-[#F3F7FC] px-3 py-1.5 text-xs font-medium text-[#315C4A]"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* Buttons */}
          <div className="flex flex-wrap justify-end gap-3 rounded-xl border border-[#E1EAE4] bg-white p-5">
            <Link
              to="/dashboard/profile"
              className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 transition hover:bg-gray-50"
            >
              Cancel
            </Link>

            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#264A3B] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? (
                <LoaderCircle size={17} className="animate-spin" />
              ) : (
                <Save size={17} />
              )}
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}