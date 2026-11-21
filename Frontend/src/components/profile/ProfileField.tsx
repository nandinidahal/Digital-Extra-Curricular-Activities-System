
type ProfileFieldProps = {
  label: string;
  value: string | null | undefined;
};

export default function ProfileField({
  label,
  value,
}: ProfileFieldProps) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-400">
        {label}
      </p>

      <p className="mt-1 break-words text-sm font-medium text-[#24352D]">
        {value || "Not added yet"}
      </p>
    </div>
  );
}
