"use client";

import React, { useState, useEffect } from 'react';
import { auth } from '../../lib/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { AdminSubmissions } from '../components/AdminSubmissions';

export default function AdminPage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  // Show loading state
  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '50vh',
        fontSize: '1.2rem'
      }}>
        Loading...
      </div>
    );
  }

  // Check if user is admin
  const isAdmin = user?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL;

  if (!user) {
    return (
      <div style={{ 
        maxWidth: '800px', 
        margin: '0 auto', 
        padding: '40px 20px',
        textAlign: 'center'
      }}>
        <h1 style={{ color: '#dc3545', marginBottom: '20px' }}>🔐 Admin Access Required</h1>
        <p style={{ fontSize: '1.1rem', color: '#666' }}>
          Please log in with an admin account to access this page.
        </p>
        <a 
          href="/" 
          style={{ 
            display: 'inline-block', 
            marginTop: '20px', 
            padding: '12px 24px',
            backgroundColor: '#007bff',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '6px'
          }}
        >
          Return to Home
        </a>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div style={{ 
        maxWidth: '800px', 
        margin: '0 auto', 
        padding: '40px 20px',
        textAlign: 'center'
      }}>
        <h1 style={{ color: '#dc3545', marginBottom: '20px' }}>❌ Access Denied</h1>
        <p style={{ fontSize: '1.1rem', color: '#666', marginBottom: '10px' }}>
          You are logged in as: <strong>{user.email}</strong>
        </p>
        <p style={{ fontSize: '1rem', color: '#666' }}>
          This page is restricted to admin users only.
        </p>
        <a 
          href="/" 
          style={{ 
            display: 'inline-block', 
            marginTop: '20px', 
            padding: '12px 24px',
            backgroundColor: '#007bff',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '6px'
          }}
        >
          Return to Home
        </a>
      </div>
    );
  }

  // API base URL for admin components
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000';

  return (
    <div style={{ 
      maxWidth: '1400px', 
      margin: '0 auto', 
      padding: '20px'
    }}>
      <div style={{ 
        textAlign: 'center', 
        marginBottom: '30px',
        padding: '20px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px',
        border: '2px solid #dc3545'
      }}>
        <h1 style={{ 
          color: '#dc3545', 
          margin: '0 0 10px 0',
          fontSize: '2rem'
        }}>
          🔐 Admin Dashboard
        </h1>
        <p style={{ 
          margin: '0',
          fontSize: '1.1rem',
          color: '#666'
        }}>
          Welcome, <strong>{user.email}</strong> • Manage submissions, payments, and user data
        </p>
      </div>

      {/* Admin Submissions Component */}
      <AdminSubmissions API_BASE={API_BASE} />
    </div>
  );
}
