"use client";

import { useState, useEffect } from "react";
import { auth } from "../../lib/firebase";
import { onAuthStateChanged, User } from "firebase/auth";

type Document = {
  filing_id: string;
  type: string;
  uploaded_at: string;
  url: string;
};

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [docs, setDocs]   = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);

  // 1) Track auth state
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      if (!u) setDocs([]);
    });
    return unsubscribe;
  }, []);

  // 2) When user logs in, fetch their docs
  useEffect(() => {
    if (!user) return;
    setLoading(true);
    user.getIdToken().then((token) => {
      fetch("http://localhost:5000/api/my-documents", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.json())
        .then((data) => {
          setDocs(data.documents || []);
        })
        .finally(() => setLoading(false));
    });
  }, [user]);

  if (!user) {
    return <p className="p-4">Please log in to view your filings.</p>;
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">My Filings</h1>

      {loading && <p>Loading your documents…</p>}

      {!loading && docs.length === 0 && (
        <p>No documents found—generate an XML or PDF first!</p>
      )}

      {!loading && docs.length > 0 && (
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2 text-left">Date</th>
              <th className="p-2 text-left">Filing ID</th>
              <th className="p-2 text-left">Type</th>
              <th className="p-2 text-left">Download</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc, idx) => (
              <tr key={`${doc.filing_id || idx}-${doc.type}-${idx}`}>
                <td className="p-2">{new Date(doc.uploaded_at).toLocaleString()}</td>
                <td className="p-2">{doc.filing_id}</td>
                <td className="p-2 uppercase">{doc.type}</td>
                <td className="p-2">
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Download
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
