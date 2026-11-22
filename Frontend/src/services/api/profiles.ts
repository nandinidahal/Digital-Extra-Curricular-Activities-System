/** Profiles module: /api/profiles/ */
import type { OwnProfile, Profile, ProfilePrivacy } from "@/types/api";
import { api, toFormData } from "./client";

export type ProfileUpdate = Partial<
  Pick<OwnProfile, "headline" | "bio" | "institution" | "education_level" | "field_of_study" | "interests" | "skills" | "location" | "website" | "linkedin_url" | "github_url" | "portfolio_url">
>;

export const profilesApi = {
  me: () => api.get<{ profile: OwnProfile }>("/profiles/me/"),
  update: (body: ProfileUpdate) => api.patch<{ profile: OwnProfile }>("/profiles/me/", body),
  updatePrivacy: (body: Partial<ProfilePrivacy>) => api.patch<{ profile: OwnProfile }>("/profiles/me/privacy/", body),
  uploadPicture: (file: File) => api.post<{ profile: OwnProfile }>("/profiles/me/picture/", toFormData({ image: file })),
  removePicture: () => api.delete<{ profile: OwnProfile }>("/profiles/me/picture/"),
  uploadCover: (file: File) => api.post<{ profile: OwnProfile }>("/profiles/me/cover/", toFormData({ image: file })),
  removeCover: () => api.delete<{ profile: OwnProfile }>("/profiles/me/cover/"),
  get: (userId: string) => api.get<{ profile: Profile }>(`/profiles/${userId}/`),
};
