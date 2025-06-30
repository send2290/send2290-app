/**
 * ACCOUNT SETTINGS PAGE
 * Route: /account/settings
 * Purpose: Manage email, password, and account preferences  
 */
"use client";

import { useState, useEffect } from "react";
import { auth } from "../../../lib/firebase";
import { onAuthStateChanged, User, updatePassword, updateEmail, reauthenticateWithCredential, EmailAuthProvider } from "firebase/auth";

export default function AccountSettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  
  // Form states
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [newEmail, setNewEmail] = useState('');

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      if (currentUser && currentUser.email) {
        setNewEmail(currentUser.email);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user || !user.email) {
      showMessage('error', 'No user logged in');
      return;
    }

    if (newPassword !== confirmPassword) {
      showMessage('error', 'New passwords do not match');
      return;
    }

    if (newPassword.length < 6) {
      showMessage('error', 'Password must be at least 6 characters');
      return;
    }

    setUpdating(true);

    try {
      // Re-authenticate user before updating password
      const credential = EmailAuthProvider.credential(user.email, currentPassword);
      await reauthenticateWithCredential(user, credential);
      
      // Update password
      await updatePassword(user, newPassword);
      
      showMessage('success', 'Password updated successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      console.error('Password update error:', error);
      
      if (error.code === 'auth/wrong-password') {
        showMessage('error', 'Current password is incorrect');
      } else if (error.code === 'auth/weak-password') {
        showMessage('error', 'Password is too weak');
      } else {
        showMessage('error', `Failed to update password: ${error.message}`);
      }
    } finally {
      setUpdating(false);
    }
  };

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user || !user.email) {
      showMessage('error', 'No user logged in');
      return;
    }

    if (!currentPassword) {
      showMessage('error', 'Current password is required to change email');
      return;
    }

    if (newEmail === user.email) {
      showMessage('error', 'New email is the same as current email');
      return;
    }

    setUpdating(true);

    try {
      // Re-authenticate user before updating email
      const credential = EmailAuthProvider.credential(user.email, currentPassword);
      await reauthenticateWithCredential(user, credential);
      
      // Update email
      await updateEmail(user, newEmail);
      
      showMessage('success', 'Email updated successfully. Please verify your new email address.');
      setCurrentPassword('');
    } catch (error: any) {
      console.error('Email update error:', error);
      
      if (error.code === 'auth/wrong-password') {
        showMessage('error', 'Current password is incorrect');
      } else if (error.code === 'auth/email-already-in-use') {
        showMessage('error', 'This email is already in use by another account');
      } else if (error.code === 'auth/invalid-email') {
        showMessage('error', 'Invalid email address');
      } else {
        showMessage('error', `Failed to update email: ${error.message}`);
      }
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <h1>Account Settings</h1>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <h1>Account Settings</h1>
        <p>Please log in to access account settings.</p>
        <div style={{ marginTop: 20 }}>
          <a 
            href="/account" 
            style={{ 
              color: "#1565c0", 
              textDecoration: "none",
              padding: "8px 16px",
              border: "1px solid #1565c0",
              borderRadius: "4px",
              display: "inline-block",
              marginRight: "12px"
            }}
          >
            ← Back to Account
          </a>
          <a 
            href="/" 
            style={{ 
              color: "#1565c0", 
              textDecoration: "none"
            }}
          >
            Go to Home Page
          </a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: 20, 
      fontFamily: "Segoe UI, sans-serif",
      maxWidth: 600,
      margin: "0 auto"
    }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ color: "#d32f2f", marginBottom: 8 }}>Account Settings</h1>
        <p style={{ color: "#666", margin: 0 }}>
          Manage your email, password, and account preferences
        </p>
      </div>

      <div style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center", 
        marginBottom: 20,
        padding: 16,
        background: "#f8f9fa",
        borderRadius: 8,
        border: "1px solid #ddd"
      }}>
        <div>
          <strong>Current Account:</strong> {user.email}
          <br />
          <small style={{ color: "#666" }}>
            Account ID: {user.uid.substring(0, 8)}...
          </small>
        </div>
        <a 
          href="/account"
          style={{
            padding: "8px 16px",
            backgroundColor: "#6c757d",
            color: "white",
            textDecoration: "none",
            borderRadius: 4,
            fontSize: "0.9rem"
          }}
        >
          ← Back to Account
        </a>
      </div>

      {message && (
        <div style={{ 
          background: message.type === 'success' ? "#d4edda" : "#f8d7da", 
          color: message.type === 'success' ? "#155724" : "#721c24", 
          padding: 16, 
          borderRadius: 8, 
          marginBottom: 20,
          border: `1px solid ${message.type === 'success' ? "#c3e6cb" : "#f5c6cb"}`
        }}>
          {message.text}
        </div>
      )}

      <div style={{ 
        display: "grid", 
        gap: 30
      }}>
        {/* Change Email Section */}
        <div style={{ 
          background: "white", 
          padding: 24, 
          borderRadius: 8, 
          border: "1px solid #ddd"
        }}>
          <h3 style={{ margin: "0 0 16px 0", color: "#2196f3" }}>📧 Change Email Address</h3>
          <form onSubmit={handleEmailUpdate}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
                New Email Address:
              </label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: 10,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                  fontSize: "1rem"
                }}
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
                Current Password (required):
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: 10,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                  fontSize: "1rem"
                }}
              />
            </div>
            <button
              type="submit"
              disabled={updating}
              style={{
                padding: "10px 20px",
                backgroundColor: updating ? "#6c757d" : "#2196f3",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: updating ? "not-allowed" : "pointer",
                fontSize: "1rem"
              }}
            >
              {updating ? "Updating..." : "Update Email"}
            </button>
          </form>
        </div>

        {/* Change Password Section */}
        <div style={{ 
          background: "white", 
          padding: 24, 
          borderRadius: 8, 
          border: "1px solid #ddd"
        }}>
          <h3 style={{ margin: "0 0 16px 0", color: "#ff9800" }}>🔒 Change Password</h3>
          <form onSubmit={handlePasswordUpdate}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
                Current Password:
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: 10,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                  fontSize: "1rem"
                }}
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
                New Password:
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                style={{
                  width: "100%",
                  padding: 10,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                  fontSize: "1rem"
                }}
              />
              <small style={{ color: "#666" }}>Minimum 6 characters</small>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
                Confirm New Password:
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: 10,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                  fontSize: "1rem"
                }}
              />
            </div>
            <button
              type="submit"
              disabled={updating}
              style={{
                padding: "10px 20px",
                backgroundColor: updating ? "#6c757d" : "#ff9800",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: updating ? "not-allowed" : "pointer",
                fontSize: "1rem"
              }}
            >
              {updating ? "Updating..." : "Update Password"}
            </button>
          </form>
        </div>

        {/* Account Information */}
        <div style={{ 
          background: "#f8f9fa", 
          padding: 24, 
          borderRadius: 8, 
          border: "1px solid #ddd"
        }}>
          <h3 style={{ margin: "0 0 16px 0", color: "#6c757d" }}>ℹ️ Account Information</h3>
          <div style={{ display: "grid", gap: 12 }}>
            <div>
              <strong>Account Created:</strong> {user.metadata.creationTime ? new Date(user.metadata.creationTime).toLocaleDateString() : 'Unknown'}
            </div>
            <div>
              <strong>Last Sign In:</strong> {user.metadata.lastSignInTime ? new Date(user.metadata.lastSignInTime).toLocaleDateString() : 'Unknown'}
            </div>
            <div>
              <strong>Email Verified:</strong> {user.emailVerified ? '✅ Yes' : '❌ No'}
            </div>
            <div>
              <strong>Provider:</strong> {user.providerData[0]?.providerId || 'Email/Password'}
            </div>
          </div>
        </div>
      </div>

      <div style={{ 
        textAlign: "center", 
        marginTop: 30,
        paddingTop: 20,
        borderTop: "1px solid #eee"
      }}>
        <a 
          href="/account/filings" 
          style={{ 
            color: "#4caf50", 
            textDecoration: "none",
            marginRight: 20
          }}
        >
          📄 View My Filings
        </a>
        <a 
          href="/" 
          style={{ 
            color: "#4caf50", 
            textDecoration: "none"
          }}
        >
          ➕ Submit New Form 2290
        </a>
      </div>
    </div>
  );
}
