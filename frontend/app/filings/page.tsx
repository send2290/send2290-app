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

export default function FilingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);

  // Move API_BASE outside of useEffect so it's available in JSX
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

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
    if (user) {
      setLoading(true);
      user.getIdToken().then((token) => {
        fetch(`${API_BASE}/user/documents`, {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then((res) => res.json())
          .then((data) => {
            // Your backend returns submissions with nested documents
            // Flatten this to match your frontend expectation
            const allDocs: Document[] = [];
            if (data.submissions) {
              data.submissions.forEach((submission: any) => {
                submission.documents.forEach((doc: any) => {
                  allDocs.push({
                    filing_id: submission.id.toString(),
                    type: doc.type,
                    uploaded_at: submission.created_at,
                    url: doc.url
                  });
                });
              });
            }
            setDocs(allDocs);
            setLoading(false);
          })
          .catch((error) => {
            console.error("Error fetching documents:", error);
            setLoading(false);
          });
      });
    }
  }, [user, API_BASE]);

  if (!user) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">My Filings</h1>
        <p className="text-gray-600">Please log in to view your filings.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">My Filings</h1>
      
      {loading && (
        <div className="flex items-center justify-center py-8">
          <p className="text-gray-600">Loading your documents…</p>
        </div>
      )}

      {!loading && docs.length === 0 && (
        <div className="bg-gray-50 p-8 rounded-lg text-center">
          <p className="text-gray-600 text-lg">No documents found</p>
          <p className="text-gray-500 mt-2">Generate an XML or PDF first to see your filings here!</p>
        </div>
      )}

      {!loading && docs.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Filing ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Download
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {docs.map((doc, idx) => (
                <tr key={`${doc.filing_id || idx}-${doc.type}-${idx}`} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {new Date(doc.uploaded_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {doc.filing_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 uppercase">
                    {doc.type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                    >
                      Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
