"use client";

import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import React, { useState, useEffect } from "react";
import { auth } from "../lib/firebase";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import LoginForm from "./LoginForm";
import { PaymentProvider } from "./context/PaymentContext";

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
        <style>{`
          /* Responsive header and content styling */
          .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: #fff;
            border-bottom: 2px solid #d32f2f;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          }
          
          .main-content {
            padding-top: 180px;
          }
          
          /* IRS e-file badge styling - smaller logo */
          .irs-badge {
            background-color: #005EA2;         /* IRS blue */
            color: #ffffff;
            border: 3px solid #ffffff;
            border-radius: 10px;
            width: 140px;
            padding: 12px 8px;
            text-align: center;
            font-family: Arial, sans-serif;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
          }

          .irs-badge-text {
            font-size: 14px;
            font-weight: bold;
            margin: 6px 0;
          }

          .irs-badge-logo {
            max-width: 80px;
            height: auto;
          }
          
          @media (max-width: 768px) {
            .website-banner h1 {
              font-size: 1.5rem !important;
              padding: 12px 0 4px 0 !important;
            }
            
            .website-banner .subtitle {
              font-size: 0.9rem !important;
              margin-top: -2px !important;
            }
            
            /* Mobile IRS badge positioning - smaller */
            .irs-badge {
              position: relative !important;
              left: auto !important;
              top: auto !important;
              transform: none !important;
              margin: 12px auto 0 auto !important;
              width: 120px !important;
              padding: 8px 6px !important;
            }
            
            .irs-badge-text {
              font-size: 12px !important;
              margin: 4px 0 !important;
            }
            
            .irs-badge-logo {
              max-width: 60px !important;
            }
            
            .auth-section {
              margin: 0 16px 12px 16px !important;
              font-size: 0.8rem !important;
            }
            
            .auth-section button {
              padding: 4px 8px !important;
              font-size: 0.8rem !important;
            }
            
            .navigation {
              padding: 0 16px !important;
              height: 40px !important;
              font-size: 0.9rem !important;
            }
            
            .main-content {
              padding-top: 220px !important;
            }
          }
          
          @media (max-width: 480px) {
            .website-banner h1 {
              font-size: 1.2rem !important;
              padding: 8px 0 2px 0 !important;
              letter-spacing: 0.2px !important;
            }
            
            .website-banner .subtitle {
              font-size: 0.8rem !important;
            }
            
            /* Smaller mobile IRS badge */
            .irs-badge {
              width: 100px !important;
              padding: 6px 4px !important;
            }
            
            .irs-badge-text {
              font-size: 10px !important;
              margin: 3px 0 !important;
            }
            
            .irs-badge-logo {
              max-width: 45px !important;
            }
            
            .auth-section {
              margin: 0 8px 8px 8px !important;
              flex-direction: column !important;
              gap: 8px !important;
            }
            
            .navigation {
              padding: 0 8px !important;
              height: 36px !important;
              font-size: 0.85rem !important;
              gap: 16px !important;
            }
            
            .main-content {
              padding-top: 200px !important;
            }
          }
        `}</style>
      </head>
      <body style={{ margin: 0, paddingTop: 0, backgroundColor: '#ffffff' }}>
        {/* --- Fixed Header Container --- */}
        <div className="fixed-header">
          {/* --- Website Banner --- */}
          <div
            className="website-banner"
            style={{
              textAlign: "center",
              margin: 0,
              padding: "16px 0 6px 0",
              background: "#fff",
              position: "relative",
              minHeight: "90px" // Reduced from 120px
            }}
          >
            <h1 style={{ margin: 0, color: "#d32f2f", fontWeight: 700, fontSize: "2.1rem", letterSpacing: 0.5 }}>
              Website Under Development!
            </h1>
            <div className="subtitle" style={{ fontWeight: 500, marginTop: -4, fontSize: "1.1rem", color: "#222" }}>
              By Eirth Technologies, PLLC
            </div>
            
            {/* IRS e-file badge */}
            <div className="irs-badge" style={{ 
              position: "absolute", 
              left: "20px", 
              top: "10px", // Move down from top to prevent cutoff
              transform: "none" // Remove transform to prevent positioning issues
            }}>
              <div className="irs-badge-text">AUTHORIZED</div>
              <img 
                src="/10311g2a.gif" 
                alt="IRS e-file logo" 
                className="irs-badge-logo"
                onError={(e) => {
                  // Show fallback text if image doesn't exist
                  const target = e.currentTarget;
                  const parent = target.parentElement;
                  if (parent) {
                    target.style.display = 'none';
                    // Add fallback text if not already added
                    if (!parent.querySelector('.fallback-logo')) {
                      const fallback = document.createElement('div');
                      fallback.className = 'fallback-logo irs-badge-text';
                      fallback.textContent = 'IRS e-file';
                      fallback.style.cssText = 'margin: 10px 0; font-size: 16px; border: 1px solid white; padding: 8px; border-radius: 4px;';
                      target.parentNode?.insertBefore(fallback, target.nextSibling);
                    }
                  }
                }}
              />
              <div className="irs-badge-text">PROVIDER</div>
            </div>
          </div>

          {/* --- Auth Status & Login/Logout --- */}
          <div className="auth-section" style={{ textAlign: 'right', margin: '0 32px 20px 32px' }}>
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
            className="navigation"
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
            {/* Admin Panel link - only visible to admin users */}
            {user?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL && (
              <a href="/admin" style={{ color: "#dc3545", textDecoration: "none", fontWeight: "600" }}>
                🔐 Admin Panel
              </a>
            )}
          </nav>
        </div>

        {/* --- Main Content with top padding to account for fixed header --- */}
        <div className="main-content">
          <PaymentProvider>
            {children}
          </PaymentProvider>
        </div>
      </body>
    </html>
  );
}