/** Human labels for backend enum values. */
export const visibilityLabels = {
  public: "Public",
  members_only: "Members only",
  friends: "Friends",
  private: "Only me",
} as const;

export const activityTypeLabels = { physical: "In person", online: "Online", hybrid: "Hybrid" } as const;

export const postTypeLabels = {
  general: "General",
  activity: "Activity",
  achievement: "Achievement",
  experience: "Experience",
} as const;

export const achievementTypeLabels = {
  award: "Award",
  certificate: "Certificate",
  competition: "Competition",
  participation: "Participation",
  project: "Project",
  publication: "Publication",
  scholarship: "Scholarship",
  volunteering: "Volunteering",
  leadership: "Leadership",
  other: "Other",
} as const;

export const levelLabels = {
  institutional: "Institutional",
  local: "Local",
  national: "National",
  international: "International",
  other: "Other",
} as const;

export const verificationLabels = {
  pending: "Pending review",
  verified: "Verified",
  rejected: "Not verified",
  more_information_required: "More info needed",
} as const;

export const educationLabels = {
  "": "Not specified",
  high_school: "High school",
  diploma: "Diploma / college",
  undergraduate: "Undergraduate",
  postgraduate: "Postgraduate",
  doctorate: "Doctorate",
  other: "Other",
} as const;

export const socialReportReasons = {
  spam: "Spam",
  harassment: "Harassment",
  inappropriate: "Inappropriate content",
  false_information: "False information",
  bullying: "Bullying",
  other: "Other",
} as const;

export const announcementReportReasons = {
  spam: "Spam",
  misleading: "Misleading information",
  inappropriate: "Inappropriate content",
  fraudulent: "Fraudulent opportunity",
  harassment: "Harassment",
  incorrect: "Incorrect information",
  other: "Other",
} as const;
