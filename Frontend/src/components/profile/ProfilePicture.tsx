
import { useRef, useState } from "react";
import { Camera, Trash2, UserRound } from "lucide-react";
import profileService from "../../services/profileService";

type Props = {
  picture: string | null;
  onUpdated: (picture: string | null) => void;
};

export default function ProfilePicture({ picture, onUpdated }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError("");

    try {
      const result = await profileService.uploadProfilePicture(file);
      onUpdated(result.profile_picture_url ?? null);
    } catch {
      setError("Could not upload picture.");
    } finally {
      setLoading(false);
      event.target.value = "";
    }
  };

  const remove = async () => {
    setLoading(true);
    setError("");

    try {
      await profileService.removeProfilePicture();
      onUpdated(null);
    } catch {
      setError("Could not remove picture.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="grid h-28 w-28 place-items-center overflow-hidden rounded-full bg-[#E8F1EC]">
        {picture ? (
          <img
            src={picture}
            alt="Profile"
            className="h-full w-full object-cover"
          />
        ) : (
          <UserRound size={44} className="text-[#315C4A]" />
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={upload}
        className="hidden"
      />

      <div className="flex gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => inputRef.current?.click()}
          className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          <Camera size={16} />
          {loading ? "Please wait..." : "Upload"}
        </button>

        {picture && (
          <button
            type="button"
            disabled={loading}
            onClick={remove}
            className="flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm text-red-600"
          >
            <Trash2 size={16} />
            Remove
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
