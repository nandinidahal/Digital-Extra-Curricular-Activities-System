
import api from "./api";
import type {
  Achievement,
  AchievementCategory,
  AchievementFormData,
  PaginatedResponse,
} from "../types/achievement";

// Handle both normal arrays and paginated API responses.
function getResults<T>(
  response: T[] | PaginatedResponse<T>
): T[] {
  if (Array.isArray(response)) {
    return response;
  }

  return response.results ?? [];
}

// Convert achievement form data into FormData for file uploads.
function createAchievementFormData(
  data: AchievementFormData
): FormData {
  const formData = new FormData();

  formData.append("title", data.title);
  formData.append("category", String(data.category));
  formData.append("description", data.description);
  formData.append(
    "issuing_organization",
    data.issuing_organization
  );
  formData.append("achievement_date", data.achievement_date);
  formData.append("certificate_number", data.certificate_number);
  formData.append("location", data.location);
  formData.append("visibility", data.visibility);

  // Add certificate if selected.
  if (data.certificate) {
    formData.append("certificate", data.certificate);
  }

  // Add supporting documents.
  data.supporting_documents.forEach((file) => {
    formData.append("supporting_documents", file);
  });

  // Add document IDs to remove.
  data.remove_document_ids.forEach((id) => {
    formData.append("remove_document_ids", String(id));
  });

  return formData;
}

const achievementService = {
  // Get active achievement categories.
  async getCategories(): Promise<AchievementCategory[]> {
    const response = await api.get<AchievementCategory[]>(
      "/achievements/categories/"
    );

    return getResults(response.data);
  },

  // Get achievements belonging to the logged-in user.
  async getMyAchievements(): Promise<Achievement[]> {
    const response = await api.get<
      Achievement[] | PaginatedResponse<Achievement>
    >("/achievements/my/");

    return getResults(response.data);
  },

  // Get one achievement belonging to the logged-in user.
  async getMyAchievement(id: number): Promise<Achievement> {
    const response = await api.get<Achievement>(
      `/achievements/my/${id}/`
    );

    return response.data;
  },

  // Create a new achievement.
  async createAchievement(
    data: AchievementFormData
  ): Promise<Achievement> {
    const formData = createAchievementFormData(data);

    const response = await api.post<Achievement>(
      "/achievements/",
      formData
    );

    return response.data;
  },

  // Update an existing achievement.
  async updateAchievement(
    id: number,
    data: AchievementFormData
  ): Promise<Achievement> {
    const formData = createAchievementFormData(data);

    const response = await api.patch<Achievement>(
      `/achievements/${id}/`,
      formData
    );

    return response.data;
  },

  // Delete an achievement.
  async deleteAchievement(id: number): Promise<void> {
    await api.delete(`/achievements/${id}/`);
  },

  // Download a certificate or supporting document.
  async downloadDocument(
    achievementDocument: Achievement["documents"][number]
  ): Promise<void> {
    const response = await api.get(
      achievementDocument.download_url,
      {
        responseType: "blob",
      }
    );

    const blobUrl = window.URL.createObjectURL(
      new Blob([response.data], {
        type:
          achievementDocument.content_type ||
          "application/octet-stream",
      })
    );

    const link = window.document.createElement("a");

    link.href = blobUrl;
    link.download =
      achievementDocument.original_filename ||
      achievementDocument.document_name;

    window.document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(blobUrl);
  },
};

export default achievementService;
