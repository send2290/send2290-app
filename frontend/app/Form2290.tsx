// frontend/app/Form2290.tsx
"use client";

import React, { useEffect } from "react";

export default function Form2290() {
  // 🔍 Debug: verify env-vars are loaded in the browser console
  useEffect(() => {
    console.log("🔥 browser Firebase config:", {
      apiKey:     process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
      authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
      projectId:  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    });
  }, []);

  return (
    <div style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
      <h1>IRS Form 2290 Submission</h1>
      <p>This is a placeholder for your Form 2290 submission UI.</p>
    </div>
  );
}
