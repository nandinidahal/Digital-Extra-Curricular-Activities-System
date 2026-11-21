
// import api from "./api";

// import type {
//   UserProfile,
//   AccountInformation,
//   PrivacySettings,
//   EmailChangeResponse,
//   MessageResponse,
// } from "../types/profile";

// const profileService = {
//   async getMyProfile(): Promise<UserProfile> {
//     const { data } = await api.get("/profile/me/");
//     return data;
//   },

//   async updateProfile(
//     payload: Partial<{
//       full_name: string;
//       username: string;
//       date_of_birth: string;
//       bio: string;
//       phone_number: string;
//       country: string;
//     }>
//   ): Promise<UserProfile> {
//     const { data } = await api.patch("/profile/me/update/", payload);
//     return data;
//   },

//   async uploadProfilePicture(file: File): Promise<MessageResponse> {
//     const formData = new FormData();
//     formData.append("profile_picture", file);

//     const { data } = await api.post(
//       "/profile/me/upload-picture/",
//       formData
//     );

//     return data;
//   },

//   async removeProfilePicture(): Promise<MessageResponse> {
//     const { data } = await api.delete("/profile/me/remove-picture/");
//     return data;
//   },

//   async getPrivacySettings() {
//     const { data } = await api.get("/profile/me/settings/");
//     return data;
//   },

//   async updatePrivacySettings(
//     payload: Partial<PrivacySettings>
//   ) {
//     const { data } = await api.patch("/profile/me/settings/", payload);
//     return data;
//   },

//   async getAccountInformation(): Promise<AccountInformation> {
//     const { data } = await api.get("/profile/me/account/");
//     return data;
//   },

//   async requestEmailChange(
//     new_email: string,
//     current_password: string
//   ): Promise<EmailChangeResponse> {
//     const { data } = await api.post("/profile/me/email/change/", {
//       new_email,
//       current_password,
//     });

//     return data;
//   },

//   async confirmEmailChange(otp: string): Promise<MessageResponse> {
//     const { data } = await api.post("/profile/me/email/confirm/", {
//       otp,
//     });

//     return data;
//   },

//   async deactivateAccount(
//     current_password: string,
//     confirm: boolean
//   ): Promise<MessageResponse> {
//     const { data } = await api.post("/profile/me/deactivate/", {
//       current_password,
//       confirm,
//     });

//     return data;
//   },
// };

// export default profileService;


import api from "./api";

import type {
  UserProfile,
  AccountInformation,
  PrivacySettings,
  EmailChangeResponse,
  MessageResponse,
} from "../types/profile";

interface UpdateProfilePayload {
  full_name?: string;
  username?: string;
  date_of_birth?: string;
  bio?: string;
  phone_number?: string;
  country?: string;
  skills?: string[];
  interests?: string[];
}

const profileService = {
  // Get logged-in user's profile
  async getMyProfile(): Promise<UserProfile> {
    const { data } = await api.get("/profile/me/");
    return data;
  },

  // Update profile information, skills, and interests
  async updateProfile(
    payload: Partial<UpdateProfilePayload>
  ): Promise<UserProfile> {
    const { data } = await api.patch(
      "/profile/me/update/",
      payload
    );

    return data;
  },

  // Upload profile picture
  async uploadProfilePicture(file: File): Promise<MessageResponse> {
    const formData = new FormData();
    formData.append("profile_picture", file);

    const { data } = await api.post(
      "/profile/me/upload-picture/",
      formData
    );

    return data;
  },

  // Remove profile picture
  async removeProfilePicture(): Promise<MessageResponse> {
    const { data } = await api.delete(
      "/profile/me/remove-picture/"
    );

    return data;
  },

  // Get privacy settings
  async getPrivacySettings(): Promise<PrivacySettings> {
    const { data } = await api.get("/profile/me/settings/");
    return data;
  },

  // Update privacy settings
  async updatePrivacySettings(
    payload: Partial<PrivacySettings>
  ): Promise<PrivacySettings> {
    const { data } = await api.patch(
      "/profile/me/settings/",
      payload
    );

    return data;
  },

  // Get account information
  async getAccountInformation(): Promise<AccountInformation> {
    const { data } = await api.get("/profile/me/account/");
    return data;
  },

  // Request email change
  async requestEmailChange(
    new_email: string,
    current_password: string
  ): Promise<EmailChangeResponse> {
    const { data } = await api.post(
      "/profile/me/email/change/",
      {
        new_email,
        current_password,
      }
    );

    return data;
  },

  // Confirm email change
  async confirmEmailChange(
    otp: string
  ): Promise<MessageResponse> {
    const { data } = await api.post(
      "/profile/me/email/confirm/",
      {
        otp,
      }
    );

    return data;
  },

  // Deactivate account
  async deactivateAccount(
    current_password: string,
    confirm: boolean
  ): Promise<MessageResponse> {
    const { data } = await api.post(
      "/profile/me/deactivate/",
      {
        current_password,
        confirm,
      }
    );

    return data;
  },
};

export default profileService;
