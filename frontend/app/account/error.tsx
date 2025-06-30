/**
 * ERROR PAGE
 * This handles errors in the account section
 */
"use client";

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Account page error:', error);
  }, [error]);

  return (
    <div style={{ 
      padding: 40, 
      fontFamily: "Segoe UI, sans-serif",
      textAlign: "center",
      maxWidth: 600,
      margin: "0 auto"
    }}>
      <h2 style={{ color: "#d32f2f", marginBottom: 16 }}>Something went wrong!</h2>
      <p style={{ color: "#666", marginBottom: 24 }}>
        There was an error loading your account page.
      </p>
      <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
        <button
          onClick={reset}
          style={{
            padding: "10px 20px",
            backgroundColor: "#1565c0",
            color: "white",
            border: "none",
            borderRadius: 4,
            cursor: "pointer"
          }}
        >
          Try again
        </button>
        <a 
          href="/"
          style={{
            display: "inline-block",
            padding: "10px 20px",
            backgroundColor: "#6c757d",
            color: "white",
            textDecoration: "none",
            borderRadius: 4
          }}
        >
          Go to Home
        </a>
      </div>
    </div>
  );
}
