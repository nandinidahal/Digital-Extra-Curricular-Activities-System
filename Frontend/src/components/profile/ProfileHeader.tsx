
import { UserRound } from "lucide-react";

type ProfileHeaderProps = {
  name: string;
  username: string;
  picture: string | null;
  role: string;
};

export default function ProfileHeader({
  name,
  username,
  picture,
  role,
}: ProfileHeaderProps) {
  return (
    <section className="rounded-2xl border border-[#E1EAE4] bg-white p-6">
      <div className="flex flex-col items-center gap-5 sm:flex-row">
        <div className="grid h-24 w-24 shrink-0 place-items-center overflow-hidden rounded-full bg-[#E8F1EC]">
          {picture ? (
            <img
              src={picture}
              alt="Profile"
              className="h-full w-full object-cover"
            />
          ) : (
            <UserRound size={42} className="text-[#315C4A]" />
          )}
        </div>

        <div className="text-center sm:text-left">
          <h2 className="text-2xl font-bold text-[#24352D]">
            {name || "Your Name"}
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            @{username}
          </p>

          <span className="mt-3 inline-block rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-semibold capitalize text-[#315C4A]">
            {role}
          </span>
        </div>
      </div>
    </section>
  );
}
