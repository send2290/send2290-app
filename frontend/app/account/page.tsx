/**
 * ACCOUNT OVERVIEW PAGE
 * Route: /account
 * Purpose: Main account dashboard with options for filings and settings
 */
"use client";

import { useState, useEffect } from "react";
import { auth } from "../../lib/firebase";
import { onAuthStateChanged, User } from "firebase/auth";

export default function AccountOverviewPage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <h1>Account Access</h1>
        <p>Please log in to access your account dashboard.</p>
        <a 
          href="/" 
          style={{ 
            color: "#1565c0", 
            textDecoration: "none",
            padding: "8px 16px",
            border: "1px solid #1565c0",
            borderRadius: "4px",
            display: "inline-block",
            marginTop: "16px"
          }}
        >
          ← Back to Home
        </a>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: 20, 
      fontFamily: "Segoe UI, sans-serif",
      maxWidth: 800,
      margin: "0 auto"
    }}>
      <h1 style={{ color: "#d32f2f", marginBottom: 20 }}>Account Dashboard</h1>
      
      <div style={{ 
        background: "#f8f9fa", 
        padding: 20, 
        borderRadius: 8, 
        marginBottom: 20,
        border: "1px solid #ddd"
      }}>
        <h3 style={{ margin: "0 0 12px 0" }}>Welcome back!</h3>
        <p style={{ margin: "0 0 8px 0", color: "#666" }}>
          <strong>Email:</strong> {user.email}
        </p>
        <p style={{ margin: 0, color: "#666" }}>
          <strong>Account ID:</strong> {user.uid.substring(0, 8)}...
        </p>
      </div>

      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", 
        gap: 20,
        marginBottom: 20
      }}>
        <div style={{ 
          background: "white", 
          padding: 20, 
          borderRadius: 8, 
          border: "1px solid #ddd",
          textAlign: "center"
        }}>
          <h3 style={{ color: "#4caf50", margin: "0 0 12px 0" }}>📄 My Filings</h3>
          <p style={{ color: "#666", marginBottom: 16 }}>
            View and download your submitted Form 2290 documents
          </p>
          <a 
            href="/account/filings"
            style={{
              display: "inline-block",
              padding: "10px 20px",
              backgroundColor: "#4caf50",
              color: "white",
              textDecoration: "none",
              borderRadius: 4,
              fontWeight: 500
            }}
          >
            View Filings
          </a>
        </div>

        <div style={{ 
          background: "white", 
          padding: 20, 
          borderRadius: 8, 
          border: "1px solid #ddd",
          textAlign: "center"
        }}>
          <h3 style={{ color: "#2196f3", margin: "0 0 12px 0" }}>⚙️ Account Settings</h3>
          <p style={{ color: "#666", marginBottom: 16 }}>
            Manage your email, password, and account preferences
          </p>
          <a 
            href="/account/settings"
            style={{
              display: "inline-block",
              padding: "10px 20px",
              backgroundColor: "#2196f3",
              color: "white",
              textDecoration: "none",
              borderRadius: 4,
              fontWeight: 500
            }}
          >
            Manage Settings
          </a>
        </div>
      </div>

      <div style={{ textAlign: "center", marginTop: 30 }}>
        <a 
          href="/" 
          style={{ 
            color: "#666", 
            textDecoration: "none",
            fontSize: "0.9rem"
          }}
        >
          ← Back to Form 2290 Submission
        </a>
      </div>
    </div>
  );
}
