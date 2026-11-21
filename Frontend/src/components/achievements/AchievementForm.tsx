
import { useEffect, useState, type FormEvent } from "react";
import { LoaderCircle, Upload, X } from "lucide-react";

import achievementService from "../../services/achievementService";
import type {
  Achievement,
  AchievementCategory,
  AchievementFormData,
  AchievementDocument,
} from "../../types/achievement";

type Props = {
  initialData?: Achievement;
  onSubmit: (data: AchievementFormData) => Promise<void>;
  submitLabel: string;
};

export default function AchievementForm({
  initialData,
  onSubmit,
  submitLabel,
}: Props) {
  const [categories, setCategories] = useState<AchievementCategory[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState(initialData?.title ?? "");
  const [category, setCategory] = useState(
    initialData?.category.id.toString() ?? ""
  );
  const [description, setDescription] = useState(
    initialData?.description ?? ""
  );
  const [issuingOrganization, setIssuingOrganization] = useState(
    initialData?.issuing_organization ?? ""
  );
  const [achievementDate, setAchievementDate] = useState(
    initialData?.achievement_date ?? ""
  );
  const [certificateNumber, setCertificateNumber] = useState(
    initialData?.certificate_number ?? ""
  );
  const [location, setLocation] = useState(
    initialData?.location ?? ""
  );
  const [visibility, setVisibility] = useState<"public" | "private">(
    initialData?.visibility ?? "private"
  );

  const [certificate, setCertificate] = useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);
  const [removeDocumentIds, setRemoveDocumentIds] = useState<number[]>([]);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoadingCategories(true);
        const data = await achievementService.getCategories();
        setCategories(data);
      } catch (err) {
        console.error("Failed to load categories:", err);
        setError("Unable to load achievement categories.");
      } finally {
        setLoadingCategories(false);
      }
    };

    loadCategories();
  }, []);

  const existingDocuments: AchievementDocument[] =
    initialData?.documents ?? [];

  const certificateExists = existingDocuments.some(
    (doc) =>
      doc.document_type === "certificate" &&
      !removeDocumentIds.includes(doc.id)
  );

  const remainingSupportingDocuments = existingDocuments.filter(
    (doc) =>
      doc.document_type === "supporting" &&
      !removeDocumentIds.includes(doc.id)
  );

  const addSupportingFiles = (files: FileList | null) => {
    if (!files) return;

    setSupportingDocuments((current) => [
      ...current,
      ...Array.from(files),
    ]);
  };

  const removeNewSupportingFile = (index: number) => {
    setSupportingDocuments((current) =>
      current.filter((_, fileIndex) => fileIndex !== index)
    );
  };

  const toggleRemoveDocument = (id: number) => {
    setRemoveDocumentIds((current) =>
      current.includes(id)
        ? current.filter((documentId) => documentId !== id)
        : [...current, id]
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    const willHaveCertificate =
      certificate !== null || (certificateExists && !certificate);

    const willHaveSupportingDocuments =
      remainingSupportingDocuments.length + supportingDocuments.length;

    // Your backend requires at least one document when creating an achievement.
    if (!initialData && !willHaveCertificate && !willHaveSupportingDocuments) {
      setError("Please upload a certificate or supporting document.");
      return;
    }

    // On edit, validate the final document count if documents are changed.
    const documentsTouched =
      certificate !== null ||
      supportingDocuments.length > 0 ||
      removeDocumentIds.length > 0;

    if (
      initialData &&
      documentsTouched &&
      !willHaveCertificate &&
      !willHaveSupportingDocuments
    ) {
      setError("An achievement must have at least one document.");
      return;
    }

    try {
      setSubmitting(true);

      await onSubmit({
        title: title.trim(),
        category: Number(category),
        description: description.trim(),
        issuing_organization: issuingOrganization.trim(),
        achievement_date: achievementDate,
        certificate_number: certificateNumber.trim(),
        location: location.trim(),
        visibility,
        certificate,
        supporting_documents: supportingDocuments,
        remove_document_ids: removeDocumentIds,
      });
    } catch (err) {
      console.error("Achievement submission failed:", err);
      setError("Unable to save the achievement. Please check your information and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "mt-2 w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-[#315C4A] focus:ring-2 focus:ring-[#315C4A]/10";

  const labelClass = "text-sm font-semibold text-gray-700";

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div>
          <label className={labelClass}>Achievement Title *</label>
          <input
            className={inputClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Web Development Competition"
            required
            maxLength={200}
          />
        </div>

        <div>
          <label className={labelClass}>Category *</label>
          <select
            className={inputClass}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            required
            disabled={loadingCategories}
          >
            <option value="">
              {loadingCategories ? "Loading categories..." : "Select category"}
            </option>

            {categories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass}>Issuing Organization *</label>
          <input
            className={inputClass}
            value={issuingOrganization}
            onChange={(e) => setIssuingOrganization(e.target.value)}
            placeholder="Organization or institution name"
            required
            maxLength={200}
          />
        </div>

        <div>
          <label className={labelClass}>Achievement Date *</label>
          <input
            type="date"
            className={inputClass}
            value={achievementDate}
            onChange={(e) => setAchievementDate(e.target.value)}
            max={new Date().toISOString().split("T")[0]}
            min="1900-01-01"
            required
          />
        </div>

        <div>
          <label className={labelClass}>Certificate Number</label>
          <input
            className={inputClass}
            value={certificateNumber}
            onChange={(e) => setCertificateNumber(e.target.value)}
            placeholder="Optional certificate number"
            maxLength={100}
          />
        </div>

        <div>
          <label className={labelClass}>Location</label>
          <input
            className={inputClass}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Kathmandu, Nepal"
            maxLength={200}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>Description</label>
        <textarea
          className={inputClass}
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe your achievement..."
        />
      </div>

      <div>
        <label className={labelClass}>Visibility</label>
        <select
          className={inputClass}
          value={visibility}
          onChange={(e) =>
            setVisibility(e.target.value as "public" | "private")
          }
        >
          <option value="private">Private - Only you can view it</option>
          <option value="public">Public - Other users can view it</option>
        </select>
      </div>

      <div className="rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900">Documents</h3>

        <p className="mt-1 text-sm text-gray-500">
          Upload a certificate or at least one supporting document.
          Your backend allows up to 6 documents per achievement by default.
        </p>

        {existingDocuments.length > 0 && (
          <div className="mt-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700">
              Existing documents
            </p>

            {existingDocuments.map((document) => {
              const markedForRemoval = removeDocumentIds.includes(document.id);

              return (
                <div
                  key={document.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-gray-50 p-3"
                >
                  <div className="min-w-0">
                    <p className="break-all text-sm font-medium">
                      {document.document_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {document.document_type}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleRemoveDocument(document.id)}
                    className="text-sm font-medium text-red-600 hover:underline"
                  >
                    {markedForRemoval ? "Keep document" : "Remove"}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-5">
          <label className={labelClass}>
            {certificateExists ? "Replace certificate" : "Certificate"}
          </label>

          <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-gray-300 p-4 hover:border-[#315C4A]">
            <Upload className="text-[#315C4A]" size={20} />
            <span className="text-sm text-gray-600">
              {certificate
                ? certificate.name
                : "Choose certificate file"}
            </span>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.webp"
              className="hidden"
              onChange={(e) =>
                setCertificate(e.target.files?.[0] ?? null)
              }
            />
          </label>

          {certificate && (
            <button
              type="button"
              onClick={() => setCertificate(null)}
              className="mt-2 text-xs text-red-600 hover:underline"
            >
              Remove selected replacement
            </button>
          )}
        </div>

        <div className="mt-5">
          <label className={labelClass}>Supporting Documents</label>

          <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-gray-300 p-4 hover:border-[#315C4A]">
            <Upload className="text-[#315C4A]" size={20} />
            <span className="text-sm text-gray-600">
              Choose one or more supporting files
            </span>
            <input
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.webp"
              className="hidden"
              onChange={(e) => {
                addSupportingFiles(e.target.files);
                e.currentTarget.value = "";
              }}
            />
          </label>

          {supportingDocuments.length > 0 && (
            <div className="mt-3 space-y-2">
              {supportingDocuments.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 p-3"
                >
                  <span className="break-all text-sm">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeNewSupportingFile(index)}
                    aria-label={`Remove ${file.name}`}
                    className="text-red-500"
                  >
                    <X size={17} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={submitting || loadingCategories || categories.length === 0}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#315C4A] px-6 py-3 text-sm font-semibold text-white hover:bg-[#254938] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting && <LoaderCircle size={17} className="animate-spin" />}
        {submitting ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
