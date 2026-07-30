"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import Modal from "../components/Modal";

export default function SettingsPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { showToast } = useToast();
  const router = useRouter();

  // ── Profile state ──────────────────────────────────────────
  const [username, setUsername] = useState(user?.username || "");
  const [email, setEmail] = useState(user?.email || "");
  const [profileSaving, setProfileSaving] = useState(false);

  // ── Password state ─────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  // ── Delete account state ───────────────────────────────────
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Auth guard
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    try {
      await api.updateUser({ username, email });
      showToast("success", "Profile updated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update profile";
      showToast("error", msg);
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setPasswordError("");

    if (newPassword.length < 6) {
      setPasswordError("New password must be at least 6 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    setPasswordSaving(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      showToast("success", "Password changed");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to change password";
      setPasswordError(msg);
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await api.deleteAccount();
      showToast("info", "Account deleted");
      await logout();
      router.push("/login");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete account";
      showToast("error", msg);
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  if (authLoading) {
    return (
      <div className="h-dvh flex items-center justify-center bg-background">
        <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  const inputClass = "w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder-text-secondary outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20";
  const labelClass = "block text-sm font-medium text-foreground mb-1";
  const sectionClass = "bg-surface border border-border rounded-xl p-6 space-y-4";
  const sectionTitleClass = "text-base font-semibold text-foreground";

  return (
    <div className="fixed inset-0 bg-background overflow-y-auto">
      {/* Header */}
      <header className="border-b border-border bg-surface">
        <div className="max-w-2xl mx-auto px-4 h-12 flex items-center gap-3">
          <button
            onClick={() => router.push("/")}
            className="p-1.5 rounded-lg hover:bg-sidebar transition-colors text-text-secondary hover:text-foreground"
            aria-label="Back to home"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <h1 className="text-sm font-semibold text-foreground">Settings</h1>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* ── Profile Section ─────────────────────────────────── */}
        <section className={sectionClass}>
          <h2 className={sectionTitleClass}>Profile</h2>
          <div className="space-y-3">
            <div>
              <label htmlFor="username" className={labelClass}>Username</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
                placeholder="Your username"
              />
            </div>
            <div>
              <label htmlFor="email" className={labelClass}>Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                placeholder="your@email.com"
              />
            </div>
          </div>
          <div className="flex justify-end pt-2">
            <button
              onClick={handleSaveProfile}
              disabled={profileSaving}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {profileSaving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </section>

        {/* ── Password Section ────────────────────────────────── */}
        <section className={sectionClass}>
          <h2 className={sectionTitleClass}>Password</h2>
          <div className="space-y-3">
            <div>
              <label htmlFor="current-password" className={labelClass}>Current password</label>
              <input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className={inputClass}
                placeholder="Enter current password"
              />
            </div>
            <div>
              <label htmlFor="new-password" className={labelClass}>New password</label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={inputClass}
                placeholder="At least 6 characters"
              />
            </div>
            <div>
              <label htmlFor="confirm-password" className={labelClass}>Confirm new password</label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={inputClass}
                placeholder="Repeat new password"
              />
            </div>
          </div>
          {passwordError && (
            <div className="text-sm text-danger bg-danger/10 rounded-lg px-3 py-2" role="alert">
              {passwordError}
            </div>
          )}
          <div className="flex justify-end pt-2">
            <button
              onClick={handleChangePassword}
              disabled={passwordSaving || !currentPassword || !newPassword || !confirmPassword}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {passwordSaving ? "Changing..." : "Change password"}
            </button>
          </div>
        </section>

        {/* ── Preferences Section ─────────────────────────────── */}
        <section className={sectionClass}>
          <h2 className={sectionTitleClass}>Preferences</h2>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-foreground">Theme</div>
              <div className="text-xs text-text-secondary mt-0.5">
                {theme === "dark" ? "Dark mode" : "Light mode"}
              </div>
            </div>
            <button
              onClick={toggleTheme}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
            >
              Switch to {theme === "dark" ? "light" : "dark"}
            </button>
          </div>
        </section>

        {/* ── Account Section ─────────────────────────────────── */}
        <section className={sectionClass}>
          <h2 className={sectionTitleClass}>Account</h2>
          <div className="space-y-2 text-sm text-text-secondary">
            <div className="flex justify-between">
              <span>Email</span>
              <span className="text-foreground">{user.email}</span>
            </div>
            <div className="flex justify-between">
              <span>Username</span>
              <span className="text-foreground">{user.username}</span>
            </div>
            <div className="flex justify-between">
              <span>Member since</span>
              <span className="text-foreground">
                {new Date(user.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
            </div>
          </div>
        </section>

        {/* ── Danger Zone ─────────────────────────────────────── */}
        <section className="border border-danger/30 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-danger">Danger Zone</h2>
          <p className="text-sm text-text-secondary">
            Once you delete your account, there is no going back. All your projects and data will be permanently removed.
          </p>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-danger text-white hover:bg-red-600 transition-colors"
          >
            Delete account
          </button>
        </section>
      </div>

      {/* ── Delete Confirmation Modal ─────────────────────────── */}
      <Modal open={showDeleteConfirm} onClose={() => !deleting && setShowDeleteConfirm(false)}>
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-foreground">Delete account?</h2>
          <p className="text-sm text-text-secondary">
            This will permanently delete your account and all associated projects. This action cannot be undone.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setShowDeleteConfirm(false)}
              disabled={deleting}
              className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface disabled:opacity-40 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteAccount}
              disabled={deleting}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-danger text-white hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {deleting ? "Deleting..." : "Delete my account"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
