import React, { useState } from 'react';
import { auth } from '../../lib/firebase';
import { AdminSubmission, AdminSubmissionFile } from '../types/form';
import { formatDate, formatMonth } from '../utils/formUtils';

interface AdminSubmissionsProps {
  API_BASE: string;
}

export const AdminSubmissions: React.FC<AdminSubmissionsProps> = ({ API_BASE }) => {
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [selectedSubmission, setSelectedSubmission] = useState<number | null>(null);
  const [submissionFiles, setSubmissionFiles] = useState<AdminSubmissionFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);

  const fetchSubmissions = async () => {
    setLoading(true);
    try {
      const token = await auth.currentUser?.getIdToken();
      const response = await fetch(`${API_BASE}/admin/submissions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSubmissions(data.submissions || []);
      } else {
        console.error('Failed to fetch submissions');
      }
    } catch (error) {
      console.error('Error fetching submissions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSubmissionFiles = async (submissionId: number) => {
    try {
      const token = await auth.currentUser?.getIdToken();
      const response = await fetch(`${API_BASE}/admin/submissions/${submissionId}/files`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSubmissionFiles(data.files || []);
        setSelectedSubmission(submissionId);
      } else {
        console.error('Failed to fetch submission files');
      }
    } catch (error) {
      console.error('Error fetching submission files:', error);
    }
  };

  const downloadFile = async (submissionId: number, fileType: 'pdf' | 'xml') => {
    try {
      const token = await auth.currentUser?.getIdToken();
      const response = await fetch(`${API_BASE}/admin/submissions/${submissionId}/download/${fileType}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `submission-${submissionId}-form2290.${fileType}`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const errorData = await response.json();
        alert(`Download failed: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      alert(`Download error: ${error}`);
    }
  };

  return (
    <div style={{ 
      background: '#f8f9fa', 
      border: '2px solid #dc3545', 
      borderRadius: '8px', 
      padding: '16px', 
      marginBottom: '20px' 
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ color: '#dc3545', margin: 0 }}>
          🔐 Admin Panel - All Submissions
        </h3>
        <button
          onClick={() => {
            setShowAdmin(!showAdmin);
            if (!showAdmin && submissions.length === 0) {
              fetchSubmissions();
            }
          }}
          style={{
            padding: '6px 12px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {showAdmin ? 'Hide' : 'Show'} Admin Panel
        </button>
      </div>

      {showAdmin && (
        <div style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <button
              onClick={fetchSubmissions}
              disabled={loading}
              style={{
                padding: '8px 16px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Loading...' : '🔄 Refresh Submissions'}
            </button>
            <span style={{ fontSize: '0.9rem', color: '#666' }}>
              Total: {submissions.length} submissions
            </span>
          </div>

          {submissions.length > 0 ? (
            <div style={{ 
              maxHeight: '400px', 
              overflowY: 'auto', 
              border: '1px solid #ddd', 
              borderRadius: '4px' 
            }}>
              <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                <thead style={{ background: '#e9ecef', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>ID</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>User Email</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Business</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>EIN</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Month</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Vehicles</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Tax</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Created</th>
                    <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {submissions.map((submission) => (
                    <tr key={submission.id} style={{ borderBottom: '1px solid #eee' }}>
                      <td style={{ padding: '8px' }}>{submission.id}</td>
                      <td style={{ padding: '8px' }}>{submission.user_email || 'Unknown'}</td>
                      <td style={{ padding: '8px' }}>{submission.business_name.substring(0, 20)}...</td>
                      <td style={{ padding: '8px' }}>***{submission.ein.slice(-4)}</td>
                      <td style={{ padding: '8px' }}>{formatMonth(submission.month)}</td>
                      <td style={{ padding: '8px' }}>{submission.total_vehicles}</td>
                      <td style={{ padding: '8px' }}>${submission.total_tax}</td>
                      <td style={{ padding: '8px' }}>{formatDate(submission.created_at)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => downloadFile(submission.id, 'pdf')}
                            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                          >
                            📄 PDF
                          </button>
                          
                          <button
                            onClick={() => downloadFile(submission.id, 'xml')}
                            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-gray-600 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
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
          ) : (
            <p style={{ color: '#666', fontStyle: 'italic' }}>
              No submissions found. Click "Refresh Submissions" to load data.
            </p>
          )}

          {/* File Details Modal */}
          {selectedSubmission && submissionFiles.length > 0 && (
            <div style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1000
            }}>
              <div style={{
                backgroundColor: 'white',
                padding: '20px',
                borderRadius: '8px',
                maxWidth: '600px',
                width: '90%',
                maxHeight: '80%',
                overflow: 'auto'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h4>Files for Submission #{selectedSubmission}</h4>
                  <button
                    onClick={() => {
                      setSelectedSubmission(null);
                      setSubmissionFiles([]);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '1.5rem',
                      cursor: 'pointer'
                    }}
                  >
                    ×
                  </button>
                </div>
                <div>
                  {submissionFiles.map((file) => (
                    <div key={file.id} style={{
                      padding: '12px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      marginBottom: '8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div>
                        <strong>{file.document_type.toUpperCase()}</strong> - {file.filename}
                        <br />
                        <small style={{ color: '#666' }}>
                          Uploaded: {formatDate(file.uploaded_at)}
                        </small>
                      </div>
                      <button
                        onClick={() => downloadFile(selectedSubmission, file.document_type as 'pdf' | 'xml')}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#28a745',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        📥 Download
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
