"use client";

import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import React, { useState, useEffect } from "react";
import { auth } from "../lib/firebase";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import LoginForm from "./LoginForm";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Auth state & logout
  const [user, setUser] = useState<any>(null);
  const [showLogin, setShowLogin] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, u => {
      setUser(u);
    });
    return unsubscribe;
  }, []);

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch (e) {
      alert('Logout failed');
    }
  };

  const handleProfileClick = () => {
    console.log('Profile button clicked - navigating to /account');
    console.log('Current URL:', window.location.href);
    router.push('/account');
    setTimeout(() => {
      console.log('After navigation, URL is:', window.location.href);
    }, 100);
  };

  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
        <meta name="theme-color" content="#ffffff" />
        <title>Form 2290 - Send2290.com</title>
      </head>
      <body style={{ margin: 0, paddingTop: 0, backgroundColor: '#ffffff' }}>
        {/* --- Fixed Header Container --- */}
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 1000,
            background: "#fff",
            borderBottom: "2px solid #d32f2f",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
          }}
        >
          {/* --- Website Banner --- */}
          <div
            style={{
              textAlign: "center",
              margin: 0,
              padding: "20px 0 6px 0",
              background: "#fff",
            }}
          >
            <h1 style={{ margin: 0, color: "#d32f2f", fontWeight: 700, fontSize: "2.1rem", letterSpacing: 0.5 }}>
              Website Under Development!
            </h1>
            <div style={{ fontWeight: 500, marginTop: -4, fontSize: "1.1rem", color: "#222" }}>
              By Majd Consulting, PLLC
            </div>
          </div>

          {/* --- Auth Status & Login/Logout --- */}
          <div style={{ textAlign: 'right', margin: '0 32px 20px 32px' }}>
            {user ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
                <span style={{ color: '#666', fontSize: '0.9rem' }}>
                  Logged in as: <strong>{user.email}</strong>
                </span>
                <button
                  onClick={handleProfileClick}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 4,
                    backgroundColor: '#4caf50',
                    color: '#fff',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                    textDecoration: 'none',
                    display: 'inline-block'
                  }}
                >
                  Dashboard
                </button>
                <button
                  onClick={handleLogout}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 4,
                    backgroundColor: '#d32f2f',
                    color: '#fff',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.9rem'
                  }}
                >
                  Logout
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
                <span style={{ color: '#666', fontSize: '0.9rem' }}>Not logged in</span>
                <button
                  onClick={() => setShowLogin(prev => !prev)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 4,
                    backgroundColor: '#1565c0',
                    color: '#fff',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.9rem'
                  }}
                >
                  {showLogin ? 'Hide Login' : 'Login'}
                </button>
              </div>
            )}
          </div>

          {/* --- Embedded Login Form --- */}
          {showLogin && !user && (
            <div style={{ maxWidth: 420, margin: '0 auto 30px auto', padding: '0 32px' }}>
              <LoginForm />
            </div>
          )}

          {/* --- Navigation Bar --- */}
          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: 24,
              padding: "0 32px",
              height: 48,
              background: "#fff",
              borderTop: "1px solid #eee",
              fontSize: "1.1rem",
              fontWeight: 500,
            }}
          >
            <a href="/" style={{ color: "#222", textDecoration: "none" }}>Home</a>
            <a href="/account/filings" style={{ color: "#222", textDecoration: "none" }}>My Filings</a>
          </nav>
        </div>

        {/* --- Main Content with top padding to account for fixed header --- */}
        <div style={{ paddingTop: "200px" }}>
          {children}
        </div>
      </body>
    </html>
  );
}