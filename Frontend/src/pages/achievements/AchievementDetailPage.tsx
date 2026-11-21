
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarDays,
  Download,
  Edit,
  FileText,
  MapPin,
  Building2,
  Trash2,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import AchievementStatus from "../../components/achievements/AchievementStatus";
import achievementService from "../../services/achievementService";
import type { Achievement } from "../../types/achievement";

import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

const navItems = [
  { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { label: "My Activities", path: "/dashboard/activities", icon: ClipboardList },
  { label: "Certificates", path: "/dashboard/certificates", icon: GraduationCap },
  { label: "My Profile", path: "/dashboard/profile", icon: CircleUserRound },
];

export default function AchievementDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [achievement, setAchievement] = useState<Achievement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const loadAchievement = async () => {
      try {
        if (!id || !Number.isInteger(Number(id)) || Number(id) <= 0) {
          setError("Invalid achievement ID.");
          return;
        }

        const data = await achievementService.getMyAchievement(Number(id));
        setAchievement(data);
      } catch (err) {
        console.error("Failed to load achievement:", err);
        setError("Unable to load this achievement.");
      } finally {
        setLoading(false);
      }
    };

    loadAchievement();
  }, [id]);

  const handleDownload = async (
    document: Achievement["documents"][number]
  ) => {
    try {
      setDownloadingId(document.id);
      await achievementService.downloadDocument(document);
    } catch (err) {
      console.error("Document download failed:", err);
      window.alert("Unable to download this document. Please try again.");
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async () => {
    if (!id || !window.confirm("Are you sure you want to delete this achievement? This action cannot be undone.")) {
      return;
    }

    try {
      setDeleting(true);
      await achievementService.deleteAchievement(Number(id));
      navigate("/dashboard/achievements");
    } catch (err) {
      console.error("Failed to delete achievement:", err);
      window.alert("Unable to delete this achievement.");
      setDeleting(false);
    }
  };

  return (
    <DashboardLayout
      role="user"
      title="Achievement Details"
      subtitle="View your achievement and uploaded documents."
      navItems={navItems}
    >
      <Link
        to="/dashboard/achievements"
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
      >
        <ArrowLeft size={17} />
        Back to Achievements
      </Link>

      {loading ? (
        <div className="py-16 text-center text-sm text-gray-500">
          Loading achievement...
        </div>
      ) : error || !achievement ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-600">
          {error || "Achievement not found."}
        </div>
      ) : (
        <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-[#315C4A]">
                {achievement.category.name}
              </p>

              <h2 className="mt-2 text-2xl font-bold text-gray-900">
                {achievement.title}
              </h2>

              <p className="mt-2 text-sm text-gray-500">
                Issued by {achievement.issuing_organization}
              </p>
            </div>

            <AchievementStatus
              visibility={achievement.visibility ?? "private"}
            />
          </div>

          <div className="mt-7 grid grid-cols-1 gap-5 border-y border-gray-100 py-6 sm:grid-cols-2">
            <div className="flex items-start gap-3">
              <CalendarDays size={19} className="mt-0.5 text-[#315C4A]" />
              <div>
                <p className="text-xs text-gray-400">Achievement Date</p>
                <p className="mt-1 text-sm font-medium">
                  {new Date(
                    `${achievement.achievement_date}T00:00:00`
                  ).toLocaleDateString()}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Building2 size={19} className="mt-0.5 text-[#315C4A]" />
              <div>
                <p className="text-xs text-gray-400">Issuing Organization</p>
                <p className="mt-1 text-sm font-medium">
                  {achievement.issuing_organization}
                </p>
              </div>
            </div>

            {achievement.location && (
              <div className="flex items-start gap-3">
                <MapPin size={19} className="mt-0.5 text-[#315C4A]" />
                <div>
                  <p className="text-xs text-gray-400">Location</p>
                  <p className="mt-1 text-sm font-medium">
                    {achievement.location}
                  </p>
                </div>
              </div>
            )}

            {achievement.certificate_number && (
              <div className="flex items-start gap-3">
                <FileText size={19} className="mt-0.5 text-[#315C4A]" />
                <div>
                  <p className="text-xs text-gray-400">Certificate Number</p>
                  <p className="mt-1 text-sm font-medium">
                    {achievement.certificate_number}
                  </p>
                </div>
              </div>
            )}
          </div>

          <section className="mt-6">
            <h3 className="font-bold">Description</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-gray-600">
              {achievement.description || "No description provided."}
            </p>
          </section>

          <section className="mt-8">
            <h3 className="font-bold">Uploaded Documents</h3>

            {achievement.documents.length === 0 ? (
              <p className="mt-3 text-sm text-gray-500">
                No documents uploaded.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {achievement.documents.map((document) => (
                  <div
                    key={document.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-100 p-4"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <FileText size={22} className="shrink-0 text-[#315C4A]" />

                      <div className="min-w-0">
                        <p className="break-all text-sm font-semibold">
                          {document.document_name}
                        </p>
                        <p className="mt-1 text-xs capitalize text-gray-500">
                          {document.document_type} ·{" "}
                          {(document.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDownload(document)}
                      disabled={downloadingId === document.id}
                      className="inline-flex items-center gap-2 rounded-lg border border-[#315C4A] px-3 py-2 text-sm font-semibold text-[#315C4A] hover:bg-[#E8F1EC] disabled:opacity-50"
                    >
                      <Download size={16} />
                      {downloadingId === document.id
                        ? "Downloading..."
                        : "Download"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="mt-8 flex flex-wrap gap-3 border-t border-gray-100 pt-6">
            <button
              onClick={() =>
                navigate(`/dashboard/achievements/${achievement.id}/edit`)
              }
              className="inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-3 text-sm font-semibold text-white hover:bg-[#254938]"
            >
              <Edit size={16} />
              Edit Achievement
            </button>

            <button
              onClick={handleDelete}
              disabled={deleting}
              className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-5 py-3 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              <Trash2 size={16} />
              {deleting ? "Deleting..." : "Delete Achievement"}
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
