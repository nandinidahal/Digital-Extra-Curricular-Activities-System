/**
 * Client-side pre-checks that mirror the backend limits, so users get instant feedback.
 * The backend re-validates the real file content; these checks are only a convenience.
 */
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const IMAGE_ACCEPT = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";
export const EVIDENCE_ACCEPT = `${IMAGE_ACCEPT},.pdf,application/pdf`;

export const LIMITS = {
  profilePicture: 2 * 1024 * 1024, // PROFILE_PICTURE_MAX_BYTES
  profileCover: 5 * 1024 * 1024, // PROFILE_COVER_MAX_BYTES
  postImage: 5 * 1024 * 1024, // SOCIAL_IMAGE_MAX_BYTES
  postImages: 6, // SOCIAL_MAX_IMAGES_PER_POST
  announcementCover: 5 * 1024 * 1024,
  evidenceImage: 5 * 1024 * 1024,
  evidencePdf: 10 * 1024 * 1024,
  evidenceFiles: 10,
  messageImage: 5 * 1024 * 1024,
  messageFile: 10 * 1024 * 1024,
  messageAttachments: 5,
};

const mb = (bytes: number) => `${Math.round(bytes / (1024 * 1024))} MB`;

export function checkImage(file: File, maxBytes: number): string | null {
  if (!IMAGE_TYPES.includes(file.type)) return `${file.name}: please choose a JPEG, PNG or WebP image.`;
  if (file.size > maxBytes) return `${file.name}: images can be at most ${mb(maxBytes)}.`;
  return null;
}

export function checkImageOrPdf(file: File, maxImage: number, maxPdf: number): string | null {
  if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
    return file.size > maxPdf ? `${file.name}: PDFs can be at most ${mb(maxPdf)}.` : null;
  }
  return checkImage(file, maxImage);
}

export function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (Number(c) ^ (Math.random() * 16) >> (Number(c) / 4)).toString(16),
  );
}
