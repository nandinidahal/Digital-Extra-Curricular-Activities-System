/**
 * Types that mirror the Django REST serializers of the DEAS backend.
 * Source of truth: Backend/<module>/serializers.py (see docs/API_INTEGRATION.md).
 */

// ---------------------------------------------------------------------------
// Envelope / pagination (accounts.responses.success_response + paginators)
// ---------------------------------------------------------------------------
export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
}

export interface ApiErrorBody {
  success: false;
  message: string;
  code: string;
  errors: Record<string, unknown>;
  retry_after?: number;
  [extra: string]: unknown;
}

export interface PageInfo {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
}

export interface Paginated<T> {
  results: T[];
  pagination: PageInfo;
}

/** Messaging history uses cursor pagination (no count/page). */
export interface CursorPaginated<T> {
  results: T[];
  pagination: { page_size: number; next: string | null; previous: string | null };
}

export type UUID = string;
export type ISODate = string;
export type Visibility = "public" | "members_only" | "private";

/** Person card shared by Social, Announcements, Achievements, Notifications, Messaging. */
export interface UserCard {
  id: UUID;
  username: string;
  full_name: string;
  profile_picture: string | null;
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------
export type Role = "user" | "coordinator" | "admin";

export interface User {
  id: UUID;
  username: string;
  full_name: string;
  email: string;
  phone_number: string;
  country: string;
  date_of_birth: string | null;
  role: Role;
  is_email_verified: boolean;
  created_at: ISODate;
}

export interface Tokens {
  access: string;
  refresh: string;
}

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------
export type EducationLevel = "" | "high_school" | "diploma" | "undergraduate" | "postgraduate" | "doctorate" | "other";

export interface ProfilePrivacy {
  profile_visibility: Visibility;
  show_institution: boolean;
  show_education: boolean;
  show_interests: boolean;
  show_skills: boolean;
  show_location: boolean;
  show_social_links: boolean;
}

export interface ProfileBase {
  user_id: UUID;
  username: string;
  full_name: string;
  profile_picture: string | null;
  cover_photo: string | null;
  headline: string;
  bio: string;
  institution?: string;
  education_level?: EducationLevel;
  field_of_study?: string;
  interests?: string[];
  skills?: string[];
  location?: string;
  website?: string;
  linkedin_url?: string;
  github_url?: string;
  portfolio_url?: string;
  is_owner: boolean;
  date_created: ISODate;
}

export interface OwnProfile extends Required<ProfileBase> {
  id: UUID;
  privacy: ProfilePrivacy;
  profile_completion: { percentage: number; completed_fields: string[]; missing_fields: string[] };
  updated_at: ISODate;
}

export type Profile = ProfileBase | OwnProfile;

// ---------------------------------------------------------------------------
// Friends
// ---------------------------------------------------------------------------
export type FriendshipStatus =
  | "self"
  | "friends"
  | "request_sent"
  | "request_received"
  | "blocked_by_me"
  | "blocked_you"
  | "not_friends";

export interface FriendCard {
  user_id: UUID;
  username: string;
  full_name: string;
  profile_picture: string | null;
  headline: string | null;
}

export interface Friend extends FriendCard {
  friendship_id: UUID;
  friendship_created_at: ISODate;
  friendship_status: "friends";
}

export interface DiscoverUser extends FriendCard {
  friendship_status: FriendshipStatus;
}

export interface BlockedUser extends FriendCard {
  blocked_at: ISODate;
}

export interface FriendRequest {
  id: UUID;
  sender_id: UUID;
  receiver_id: UUID;
  status: "pending" | "accepted" | "rejected" | "cancelled";
  created_at: ISODate;
  updated_at: ISODate;
  responded_at: ISODate | null;
  sender?: FriendCard;
  receiver?: FriendCard;
}

export interface Relationship {
  user_id: UUID;
  friendship_status: FriendshipStatus;
  is_friend: boolean;
  request_sent: boolean;
  request_received: boolean;
  request_id: UUID | null;
  blocked: boolean;
}

// ---------------------------------------------------------------------------
// Social
// ---------------------------------------------------------------------------
export type PostType = "general" | "activity" | "achievement" | "experience";
export type PostVisibility = "public" | "members_only" | "friends" | "private";

export interface PostMedia {
  id: UUID;
  url: string;
  width: number;
  height: number;
  position: number;
}

export interface SharedAnnouncementData {
  id: UUID;
  title: string;
  short_description: string;
  category: string | null;
  activity_type: ActivityType;
  location: string;
  start_datetime: ISODate | null;
  end_datetime: ISODate | null;
  registration_deadline: ISODate | null;
  cover_image: string | null;
}

export interface SharedAchievementData {
  id: UUID;
  title: string;
  achievement_type: AchievementType;
  level: AchievementLevel;
  position: string;
  organization: string;
  achievement_date: string;
  category: string | null;
  user: UserCard;
}

export type SharedResource =
  | { type: "announcement"; id: UUID | null; available: boolean; data: SharedAnnouncementData | null }
  | { type: "achievement"; id: UUID | null; available: boolean; data: SharedAchievementData | null };

export interface Post {
  id: UUID;
  author: UserCard;
  content: string;
  post_type: PostType;
  visibility: PostVisibility;
  media: PostMedia[];
  shared_type: "" | "announcement" | "achievement";
  shared_resource: SharedResource | null;
  like_count: number;
  comment_count: number;
  share_count: number;
  is_liked: boolean;
  is_owner: boolean;
  is_edited: boolean;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface Comment {
  id: UUID;
  post_id: UUID;
  parent_comment_id: UUID | null;
  depth: number;
  author: UserCard | null; // null for a deleted placeholder
  content: string;
  like_count: number;
  reply_count: number;
  is_liked: boolean;
  is_owner: boolean;
  is_edited: boolean;
  is_deleted: boolean;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface PostShare {
  id: UUID;
  caption: string;
  original_post_id: UUID;
  original_post: Post | null;
  original_post_available: boolean;
  created_at: ISODate;
}

export interface LikeState {
  like_count: number;
  is_liked: boolean;
}

export type SocialReportReason = "spam" | "harassment" | "inappropriate" | "false_information" | "bullying" | "other";

export interface SocialReport {
  id: UUID;
  content_type: "post" | "comment";
  target: { id: UUID; author_id: UUID; content: string; is_deleted: boolean; post_id: UUID };
  reporter: { id: UUID; username: string };
  reason: SocialReportReason;
  description: string;
  status: "pending" | "reviewing" | "resolved" | "dismissed";
  action_taken: "none" | "content_removed";
  review_comments: string;
  reviewed_by: { id: UUID; username: string } | null;
  reviewed_at: ISODate | null;
  created_at: ISODate;
}

// ---------------------------------------------------------------------------
// Announcements
// ---------------------------------------------------------------------------
export type ActivityType = "physical" | "online" | "hybrid";
export type AnnouncementStatus = "draft" | "published" | "archived";

export interface Category {
  id: UUID;
  name: string;
  slug: string;
  description?: string;
  is_active?: boolean;
}

export interface AnnouncementCard {
  id: UUID;
  title: string;
  slug: string;
  short_description: string;
  category: Category | null;
  activity_type: ActivityType;
  organizer_name: string;
  location: string;
  start_datetime: ISODate | null;
  end_datetime: ISODate | null;
  registration_deadline: ISODate | null;
  cover_image: string | null;
  status: AnnouncementStatus;
  visibility: Visibility;
  author: UserCard;
  is_bookmarked: boolean;
  is_owner: boolean;
  is_edited: boolean;
  published_at: ISODate | null;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface AnnouncementDetail extends AnnouncementCard {
  description: string;
  organizer_email: string | null;
  organizer_phone: string | null;
  contact_information: string | null;
  contact_details_hidden: boolean;
  online_link: string | null;
  registration_link: string;
  eligibility_criteria: string;
  requirements: string;
  requires_login_for_online_link: boolean;
  show_contact_details?: boolean;
  archived_at?: ISODate | null;
}

export interface AnnouncementBookmark {
  id: UUID;
  announcement_id: UUID;
  created_at: ISODate;
  available: boolean;
  announcement: AnnouncementCard | null;
}

export type AnnouncementReportReason =
  | "spam" | "misleading" | "inappropriate" | "fraudulent" | "harassment" | "incorrect" | "other";

export interface AnnouncementReport {
  id: UUID;
  announcement: { id: UUID; title: string; status: AnnouncementStatus; visibility: Visibility; author_id: UUID };
  reporter: { id: UUID; username: string };
  reason: AnnouncementReportReason;
  description: string;
  status: "pending" | "reviewed" | "resolved" | "rejected";
  action_taken: "none" | "archived";
  reviewed_by: { id: UUID; username: string } | null;
  review_comments: string;
  reviewed_at: ISODate | null;
  created_at: ISODate;
  updated_at: ISODate;
}

// ---------------------------------------------------------------------------
// Achievements
// ---------------------------------------------------------------------------
export type AchievementType =
  | "award" | "certificate" | "competition" | "participation" | "project"
  | "publication" | "scholarship" | "volunteering" | "leadership" | "other";
export type AchievementLevel = "institutional" | "local" | "national" | "international" | "other";
export type VerificationStatus = "pending" | "verified" | "rejected" | "more_information_required";

export interface Evidence {
  id: UUID;
  kind: "image" | "pdf";
  original_name: string;
  content_type: string;
  size: number;
  download_url: string | null;
  created_at: ISODate;
}

export interface Achievement {
  id: UUID;
  user: UserCard;
  title: string;
  description: string;
  category: Category | null;
  achievement_type: AchievementType;
  organization: string;
  event_name: string;
  related_announcement: { id: UUID | null; title: string | null; available: boolean } | null;
  achievement_date: string;
  location: string;
  level: AchievementLevel;
  position: string;
  skills: string[];
  visibility: Visibility;
  verification_status: VerificationStatus;
  is_featured: boolean;
  featured_at: ISODate | null;
  verified_at: ISODate | null;
  submitted_at?: ISODate;
  is_owner: boolean;
  created_at: ISODate;
  updated_at: ISODate;
  // owner / reviewers only
  rejection_reason?: string | null;
  verified_by?: { id: UUID; username: string } | null;
  evidence?: Evidence[];
}

export interface AchievementHistoryItem {
  id: UUID;
  decision: "submitted" | "resubmitted" | "verified" | "rejected" | "more_information_required" | "reverification_required";
  previous_status: string;
  new_status: string;
  comments: string;
  actor_role: "owner" | "reviewer" | "system";
  reviewer: { id: UUID; username: string; full_name: string } | null;
  created_at: ISODate;
}

export interface AchievementStats {
  total: number;
  pending: number;
  verified: number;
  rejected: number;
  more_information_required: number;
  featured: number;
  by_category: { category: string; slug: string | null; count: number }[];
  by_level: Record<string, number>;
  by_type: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Messaging
// ---------------------------------------------------------------------------
export interface MessagingState {
  can_message: boolean;
  reason: null | "blocked" | "user_unavailable" | "message_limit_reached" | "conversation_inactive";
  is_friend: boolean;
  messages_used: number | null;
  messages_allowed: number | null;
  messages_remaining: number | null;
}

export interface LastMessage {
  id: UUID;
  content: string | null;
  message_type: "text" | "image" | "file" | "system";
  sender_id: UUID | null;
  is_own: boolean;
  is_deleted: boolean;
  created_at: ISODate;
}

export interface Conversation {
  id: UUID;
  conversation_type: "direct" | "group";
  participant: (UserCard & { is_online: boolean | null; last_seen_at: ISODate | null }) | null;
  last_message: LastMessage | null;
  unread_count: number;
  is_muted: boolean;
  is_archived: boolean;
  last_read_at: ISODate | null;
  created_at: ISODate;
  updated_at: ISODate;
  messaging?: MessagingState;
}

export interface MessageAttachment {
  id: UUID;
  kind: "image" | "file";
  name: string;
  content_type: string;
  size: number;
  width: number | null;
  height: number | null;
  url: string;
}

export interface Message {
  id: UUID;
  conversation_id: UUID;
  sender: UserCard | null;
  is_own: boolean;
  message_type: "text" | "image" | "file" | "system";
  content: string | null;
  attachments: MessageAttachment[];
  reply_to: {
    id: UUID; sender_id: UUID | null; sender_username: string | null; message_type: string;
    content_preview: string | null; is_deleted: boolean; is_available: boolean;
  } | null;
  is_forwarded: boolean;
  status: "sent" | "delivered" | "read" | null;
  delivered_at: ISODate | null;
  read_at: ISODate | null;
  reactions: Record<string, number>;
  my_reaction: string | null;
  is_edited: boolean;
  edited_at: ISODate | null;
  is_deleted: boolean;
  deleted_at: ISODate | null;
  client_id: string | null;
  created_at: ISODate;
  updated_at: ISODate;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
export type NotificationCategory = "account" | "friends" | "messages" | "social" | "announcements" | "achievements" | "system";

export interface AppNotification {
  id: UUID;
  type: string;
  category: NotificationCategory;
  title: string;
  message: string;
  actor: UserCard | null;
  metadata: Record<string, unknown>;
  target_type: string;
  target_id: string;
  action_url: string;
  is_read: boolean;
  read_at: ISODate | null;
  created_at: ISODate;
  updated_at: ISODate;
  expires_at: ISODate | null;
}

export interface NotificationPreferences {
  friend_requests: boolean;
  social_interactions: boolean;
  messages: boolean;
  announcements: boolean;
  achievements: boolean;
  system_notifications: boolean;
  email_notifications: boolean;
  realtime_notifications: boolean;
  updated_at: ISODate;
  always_on: string[];
}
