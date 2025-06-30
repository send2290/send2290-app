/**
 * MY FILINGS PAGE
 * Route: /account/filings  
 * Purpose: Display user's submitted Form 2290 documents
 */
"use client";

import { useState, useEffect } from "react";
import { auth } from "../../../lib/firebase";
import { onAuthStateChanged, User } from "firebase/auth";

type Filing = {
  id: string;
  business_name: string;
  ein: string;
  created_at: string;
  month: string;
  total_vehicles: number;
  total_tax: number;
  status: string;
};

export default function MyFilingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Determine API base URL
  const isBrowser = typeof window !== 'undefined'
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : ''
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi

  useEffect(() => {
    console.log('MY FILINGS page loaded at /account/filings');
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        fetchFilings(currentUser);
      } else {
        setLoading(false);
      }
    });

    return () => unsubscribe();
  }, []);

  const fetchFilings = async (currentUser: User) => {
    try {
      setLoading(true);
      setError(null);
      
      const token = await currentUser.getIdToken();
      const response = await fetch(`${API_BASE}/user/submissions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch filings: ${response.statusText}`);
      }

      const data = await response.json();
      setFilings(data.submissions || []);
    } catch (err) {
      console.error('Error fetching filings:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (submissionId: string, fileType: 'pdf' | 'xml') => {
    if (!user) return;

    try {
      const token = await user.getIdToken();
      const response = await fetch(`${API_BASE}/user/submissions/${submissionId}/download/${fileType}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `form2290-${submissionId}.${fileType}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      alert(`Download failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatMonth = (monthCode: string) => {
    if (!monthCode || monthCode.length !== 6) return monthCode;
    const year = monthCode.substring(0, 4);
    const month = monthCode.substring(4, 6);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${monthNames[parseInt(month) - 1]} ${year}`;
  };

  if (loading) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <h1>My Filings</h1>
        <p>Loading your filings...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
        <h1>My Filings</h1>
        <p>Please log in to view your filings.</p>
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
      maxWidth: 1000,
      margin: "0 auto"
    }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ color: "#d32f2f", marginBottom: 8 }}>My Filings</h1>
        <p style={{ color: "#666", margin: 0 }}>
          View and download your submitted Form 2290 documents
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
          <strong>Account:</strong> {user.email}
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={() => user && fetchFilings(user)}
            style={{
              padding: "8px 16px",
              backgroundColor: "#4caf50",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: "0.9rem"
            }}
          >
            🔄 Refresh
          </button>
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
      </div>

      {error && (
        <div style={{ 
          background: "#f8d7da", 
          color: "#721c24", 
          padding: 16, 
          borderRadius: 8, 
          marginBottom: 20,
          border: "1px solid #f5c6cb"
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {filings.length === 0 ? (
        <div style={{ 
          textAlign: "center", 
          padding: 40,
          background: "#f8f9fa",
          borderRadius: 8,
          border: "1px solid #ddd"
        }}>
          <h3 style={{ color: "#666", marginBottom: 16 }}>No Filings Found</h3>
          <p style={{ color: "#666", marginBottom: 20 }}>
            You haven't submitted any Form 2290 documents yet.
          </p>
          <a 
            href="/"
            style={{
              display: "inline-block",
              padding: "12px 24px",
              backgroundColor: "#4caf50",
              color: "white",
              textDecoration: "none",
              borderRadius: 4,
              fontWeight: 500
            }}
          >
            Submit Your First Form 2290
          </a>
        </div>
      ) : (
        <div style={{ 
          background: "white",
          borderRadius: 8,
          border: "1px solid #ddd",
          overflow: "hidden"
        }}>
          <div style={{ 
            background: "#f8f9fa", 
            padding: 16, 
            borderBottom: "1px solid #ddd",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <h3 style={{ margin: 0 }}>📄 Your Submissions</h3>
            <span style={{ color: "#666", fontSize: "0.9rem" }}>
              Total: {filings.length} filing{filings.length !== 1 ? 's' : ''}
            </span>
          </div>
          
          <div style={{ overflowX: "auto" }}>
            <table style={{ 
              width: "100%", 
              borderCollapse: "collapse",
              fontSize: "0.9rem"
            }}>
              <thead>
                <tr style={{ background: "#f8f9fa" }}>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Business Name</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>EIN</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Period</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Vehicles</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Tax Amount</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Submitted</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #ddd" }}>Downloads</th>
                </tr>
              </thead>
              <tbody>
                {filings.map((filing) => (
                  <tr key={filing.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: 12 }}>
                      {filing.business_name.length > 25 
                        ? `${filing.business_name.substring(0, 25)}...`
                        : filing.business_name
                      }
                    </td>
                    <td style={{ padding: 12 }}>***{filing.ein.slice(-4)}</td>
                    <td style={{ padding: 12 }}>{formatMonth(filing.month)}</td>
                    <td style={{ padding: 12 }}>{filing.total_vehicles}</td>
                    <td style={{ padding: 12 }}>${filing.total_tax}</td>
                    <td style={{ padding: 12 }}>{formatDate(filing.created_at)}</td>
                    <td style={{ padding: 12 }}>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          onClick={() => downloadFile(filing.id, 'pdf')}
                          style={{
                            padding: "4px 8px",
                            backgroundColor: "#dc3545",
                            color: "white",
                            border: "none",
                            borderRadius: 4,
                            cursor: "pointer",
                            fontSize: "0.8rem"
                          }}
                          title="Download PDF"
                        >
                          📄 PDF
                        </button>
                        <button
                          onClick={() => downloadFile(filing.id, 'xml')}
                          style={{
                            padding: "4px 8px",
                            backgroundColor: "#6c757d",
                            color: "white",
                            border: "none",
                            borderRadius: 4,
                            cursor: "pointer",
                            fontSize: "0.8rem"
                          }}
                          title="Download XML"
                        >
                          📋 XML
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ 
        textAlign: "center", 
        marginTop: 30,
        paddingTop: 20,
        borderTop: "1px solid #eee"
      }}>
        <a 
          href="/" 
          style={{ 
            color: "#4caf50", 
            textDecoration: "none",
            fontWeight: 500
          }}
        >
          ➕ Submit New Form 2290
        </a>
      </div>
    </div>
  );
}
