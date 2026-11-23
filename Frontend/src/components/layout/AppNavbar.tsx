
import { useQuery } from "@tanstack/react-query";
import {
  Award,
  Bell,
  Home,
  LogOut,
  Megaphone,
  MessageCircle,
  Settings,
  ShieldCheck,
  User,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { Avatar } from "@/components/common/Avatar";
import { CountBadge } from "@/components/common/Feedback";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { messagingApi } from "@/services/api/messaging";
import { notificationsApi } from "@/services/api/notifications";
import { cn } from "@/utils/cn";
import { Logo } from "./Logo";

const mainNav = [
  { to: "/home", label: "Home", icon: Home },
  { to: "/announcements", label: "Announcements", icon: Megaphone },
  { to: "/achievements", label: "Achievements", icon: Award },
  { to: "/friends", label: "Friends", icon: Users },
  { to: "/messages", label: "Messages", icon: MessageCircle },
];

export function useUnreadCounts() {
  const { status } = useAuth();
  const enabled = status === "authenticated";

  const notifications = useQuery({
    queryKey: qk.notificationsUnread,
    queryFn: async () =>
      (await notificationsApi.unreadCount()).data.unread_count,
    enabled,
    refetchInterval: 120_000,
  });

  const messages = useQuery({
    queryKey: qk.messagingUnread,
    queryFn: async () =>
      (await messagingApi.totalUnread()).data.unread_count,
    enabled,
    refetchInterval: 120_000,
  });

  return {
    notifications: notifications.data ?? 0,
    messages: messages.data ?? 0,
  };
}

function UserMenu() {
  const { user, profile, logout, isModerator } = useAuth();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const close = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);

    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const menuItem =
    "flex w-full items-center gap-3 px-4 py-2.5 text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900";

  const navigateTo = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex rounded-full transition hover:ring-2 hover:ring-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <Avatar
          src={profile?.profile_picture}
          name={user?.full_name}
          size="sm"
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-3 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
        >
          <Link
            to="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-3 border-b border-slate-100 px-4 py-3.5 transition hover:bg-slate-50"
          >
            <Avatar
              src={profile?.profile_picture}
              name={user?.full_name}
              size="md"
            />

            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">
                {user?.full_name}
              </p>
              <p className="truncate text-xs text-slate-500">
                @{user?.username}
              </p>
            </div>
          </Link>

          <div className="py-1.5">
            <button
              type="button"
              role="menuitem"
              className={menuItem}
              onClick={() => navigateTo("/profile")}
            >
              <User size={17} strokeWidth={1.8} />
              My Profile
            </button>

            <button
              type="button"
              role="menuitem"
              className={menuItem}
              onClick={() => navigateTo("/notifications")}
            >
              <Bell size={17} strokeWidth={1.8} />
              Notifications
            </button>

            <button
              type="button"
              role="menuitem"
              className={menuItem}
              onClick={() => navigateTo("/settings")}
            >
              <Settings size={17} strokeWidth={1.8} />
              Settings
            </button>

            {isModerator && (
              <button
                type="button"
                role="menuitem"
                className={menuItem}
                onClick={() => navigateTo("/moderation")}
              >
                <ShieldCheck size={17} strokeWidth={1.8} />
                Moderation
              </button>
            )}
          </div>

          <div className="border-t border-slate-100 py-1.5">
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-rose-600 transition-colors hover:bg-rose-50"
              onClick={() => {
                setOpen(false);
                void logout();
              }}
            >
              <LogOut size={17} strokeWidth={1.8} />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function IconLink({
  to,
  label,
  count,
  children,
}: {
  to: string;
  label: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      aria-label={count ? `${label} (${count} unread)` : label}
      className={({ isActive }) =>
        cn(
          "relative flex items-center justify-center rounded-lg p-2.5 transition-colors",
          isActive
            ? "bg-brand-50 text-brand-700"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        )
      }
    >
      {children}
      <CountBadge count={count} className="absolute -right-1 -top-1" />
    </NavLink>
  );
}

export function AppNavbar() {
  const counts = useUnreadCounts();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <div className="shrink-0">
          <Logo to="/home" />
        </div>

        {/* Desktop Navigation */}
        <nav
          aria-label="Main"
          className="hidden items-center gap-1 lg:flex"
        >
          {mainNav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "relative inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )
              }
            >
              <Icon size={18} strokeWidth={1.8} />
              {label}

              {to === "/messages" && (
                <CountBadge count={counts.messages} />
              )}
            </NavLink>
          ))}
        </nav>

        {/* Right Actions */}
        <div className="flex shrink-0 items-center gap-2">
          {/* Mobile Messages */}
          <div className="lg:hidden">
            <IconLink
              to="/messages"
              label="Messages"
              count={counts.messages}
            >
              <MessageCircle size={19} strokeWidth={1.8} />
            </IconLink>
          </div>

          {/* Notifications */}
          <IconLink
            to="/notifications"
            label="Notifications"
            count={counts.notifications}
          >
            <Bell size={19} strokeWidth={1.8} />
          </IconLink>

          {/* Profile */}
          <div className="ml-1 border-l border-slate-200 pl-3">
            <UserMenu />
          </div>
        </div>
      </div>
    </header>
  );
}

/** Bottom navigation for mobile and tablets. */
export function MobileTabBar() {
  const counts = useUnreadCounts();

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <div className="mx-auto grid max-w-lg grid-cols-5">
        {mainNav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "relative flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium transition-colors",
                isActive
                  ? "text-brand-700"
                  : "text-slate-500 hover:text-slate-800"
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    "flex items-center justify-center rounded-lg p-1 transition-colors",
                    isActive && "bg-brand-50"
                  )}
                >
                  <Icon size={20} strokeWidth={1.8} />
                </span>

                <span>
                  {label === "Announcements" ? "Events" : label}
                </span>

                {to === "/messages" && (
                  <CountBadge
                    count={counts.messages}
                    className="absolute right-[calc(50%-20px)] top-1"
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}


// import { useQuery } from "@tanstack/react-query";
// import {
//   Award, Bell, Home, LogOut, Megaphone, MessageCircle, Settings, ShieldCheck, User, Users,
// } from "lucide-react";
// import { useEffect, useRef, useState } from "react";
// import { Link, NavLink, useNavigate } from "react-router-dom";
// import { Avatar } from "@/components/common/Avatar";
// import { CountBadge } from "@/components/common/Feedback";
// import { useAuth } from "@/contexts/AuthContext";
// import { qk } from "@/hooks/queryKeys";
// import { messagingApi } from "@/services/api/messaging";
// import { notificationsApi } from "@/services/api/notifications";
// import { cn } from "@/utils/cn";
// import { Logo } from "./Logo";

// const mainNav = [
//   { to: "/home", label: "Home", icon: Home },
//   { to: "/announcements", label: "Announcements", icon: Megaphone },
//   { to: "/achievements", label: "Achievements", icon: Award },
//   { to: "/friends", label: "Friends", icon: Users },
//   { to: "/messages", label: "Messages", icon: MessageCircle },
// ];

// export function useUnreadCounts() {
//   const { status } = useAuth();
//   const enabled = status === "authenticated";
//   const notifications = useQuery({
//     queryKey: qk.notificationsUnread,
//     queryFn: async () => (await notificationsApi.unreadCount()).data.unread_count,
//     enabled,
//     refetchInterval: 120_000, // fallback when the WebSocket is down
//   });
//   const messages = useQuery({
//     queryKey: qk.messagingUnread,
//     queryFn: async () => (await messagingApi.totalUnread()).data.unread_count,
//     enabled,
//     refetchInterval: 120_000,
//   });
//   return { notifications: notifications.data ?? 0, messages: messages.data ?? 0 };
// }

// function UserMenu() {
//   const { user, profile, logout, isModerator } = useAuth();
//   const navigate = useNavigate();
//   const [open, setOpen] = useState(false);
//   const root = useRef<HTMLDivElement>(null);
//   useEffect(() => {
//     if (!open) return;
//     const close = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
//     const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
//     document.addEventListener("mousedown", close);
//     document.addEventListener("keydown", esc);
//     return () => {
//       document.removeEventListener("mousedown", close);
//       document.removeEventListener("keydown", esc);
//     };
//   }, [open]);
//   const item = "flex w-full items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50";
//   return (
//     <div ref={root} className="relative">
//       <button onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu" className="rounded-full transition hover:ring-4 hover:ring-slate-100">
//         <Avatar src={profile?.profile_picture} name={user?.full_name} size="sm" />
//       </button>
//       {open && (
//         <div role="menu" className="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-pop">
//           <Link to="/profile" onClick={() => setOpen(false)} className="flex items-center gap-3 border-b border-slate-100 px-4 py-3 hover:bg-slate-50">
//             <Avatar src={profile?.profile_picture} name={user?.full_name} size="md" />
//             <div className="min-w-0">
//               <p className="truncate font-semibold text-slate-900">{user?.full_name}</p>
//               <p className="truncate text-xs text-slate-500">@{user?.username}</p>
//             </div>
//           </Link>
//           <div className="py-1">
//             <button role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/profile"); }}><User className="h-4 w-4" /> My profile</button>
//             <button role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/notifications"); }}><Bell className="h-4 w-4" /> Notifications</button>
//             <button role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/settings"); }}><Settings className="h-4 w-4" /> Settings</button>
//             {isModerator && (
//               <button role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/moderation"); }}><ShieldCheck className="h-4 w-4" /> Moderation</button>
//             )}
//           </div>
//           <div className="border-t border-slate-100 py-1">
//             <button role="menuitem" className={cn(item, "text-rose-600")} onClick={() => { setOpen(false); void logout(); }}><LogOut className="h-4 w-4" /> Log out</button>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// }

// function IconLink({ to, label, count, children }: { to: string; label: string; count: number; children: React.ReactNode }) {
//   return (
//     <NavLink
//       to={to}
//       aria-label={count ? `${label} (${count} unread)` : label}
//       className={({ isActive }) => cn("relative rounded-full p-2.5 transition", isActive ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}
//     >
//       {children}
//       <CountBadge count={count} className="absolute -top-0.5 -right-0.5" />
//     </NavLink>
//   );
// }

// export function AppNavbar() {
//   const counts = useUnreadCounts();
//   return (
//     <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/90 backdrop-blur">
//       <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
//         <Logo to="/home" />
//         <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
//           {mainNav.map(({ to, label, icon: Icon }) => (
//             <NavLink
//               key={to}
//               to={to}
//               className={({ isActive }) =>
//                 cn("relative inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition", isActive ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")
//               }
//             >
//               <Icon className="h-[18px] w-[18px]" />
//               {label}
//               {to === "/messages" && <CountBadge count={counts.messages} />}
//             </NavLink>
//           ))}
//         </nav>
//         <div className="flex items-center gap-1.5">
//           <div className="flex lg:hidden">
//             <IconLink to="/messages" label="Messages" count={counts.messages}><MessageCircle className="h-5 w-5" /></IconLink>
//           </div>
//           <IconLink to="/notifications" label="Notifications" count={counts.notifications}><Bell className="h-5 w-5" /></IconLink>
//           <div className="ml-1 flex"><UserMenu /></div>
//         </div>
//       </div>
//     </header>
//   );
// }

// /** Bottom tab bar on phones and tablets. */
// export function MobileTabBar() {
//   const counts = useUnreadCounts();
//   return (
//     <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
//       <div className="mx-auto grid max-w-lg grid-cols-5">
//         {mainNav.map(({ to, label, icon: Icon }) => (
//           <NavLink
//             key={to}
//             to={to}
//             className={({ isActive }) => cn("relative flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium", isActive ? "text-brand-700" : "text-slate-500")}
//           >
//             <Icon className="h-5 w-5" />
//             {label === "Announcements" ? "Events" : label}
//             {to === "/messages" && <CountBadge count={counts.messages} className="absolute top-1 left-1/2 ml-1" />}
//           </NavLink>
//         ))}
//       </div>
//     </nav>
//   );
// }


