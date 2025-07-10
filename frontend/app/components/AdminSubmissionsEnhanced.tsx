import React, { useState } from 'react';
import { auth } from '../../lib/firebase';
import { AdminSubmission, AdminSubmissionFile } from '../types/form';
import { formatDate, formatMonth } from '../utils/formUtils';

interface AdminSubmissionsProps {
  API_BASE: string;
}

interface PaymentIntent {
  id: string;
  payment_intent_id: string;
  user_uid: string;
  user_email: string;
  amount_dollars: number;
  status: string;
  used_for_preview: boolean;
  used_for_submission: boolean;
  submission_id?: number;
  created_at: string;
  updated_at: string;
}

interface UserDetails {
  user_uid: string;
  user_email: string;
  total_submissions: number;
  total_payments: number;
  total_amount_paid: number;
  submissions: any[];
  payments: PaymentIntent[];
}

export const AdminSubmissions: React.FC<AdminSubmissionsProps> = ({ API_BASE }) => {
  // Tab management
  const [activeTab, setActiveTab] = useState<'submissions' | 'payments' | 'users'>('submissions');
  
  // Submissions data
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [selectedSubmission, setSelectedSubmission] = useState<number | null>(null);
  const [submissionFiles, setSubmissionFiles] = useState<AdminSubmissionFile[]>([]);
  
  // Payment data
  const [payments, setPayments] = useState<PaymentIntent[]>([]);
  
  // User details
  const [userDetails, setUserDetails] = useState<UserDetails | null>(null);
  const [showUserModal, setShowUserModal] = useState(false);
  
  // General state
  const [loading, setLoading] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  
  // Filters
  const [userFilter, setUserFilter] = useState('');
  const [emailFilter, setEmailFilter] = useState('');

  const fetchSubmissions = async () => {
    setLoading(true);
    try {
      const token = await auth.currentUser?.getIdToken();
      const params = new URLSearchParams();
      if (userFilter) params.append('user_filter', userFilter);
      if (emailFilter) params.append('email_filter', emailFilter);
      
      const response = await fetch(`${API_BASE}/admin/submissions?${params}`, {
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

  const fetchPayments = async () => {
    setLoading(true);
    try {
      const token = await auth.currentUser?.getIdToken();
      const params = new URLSearchParams();
      if (userFilter) params.append('user_filter', userFilter);
      if (emailFilter) params.append('email_filter', emailFilter);
      
      const response = await fetch(`${API_BASE}/admin/payment-history?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setPayments(data.payments || []);
      } else {
        console.error('Failed to fetch payments');
      }
    } catch (error) {
      console.error('Error fetching payments:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserDetails = async (userIdentifier: string) => {
    setLoading(true);
    try {
      const token = await auth.currentUser?.getIdToken();
      const response = await fetch(`${API_BASE}/admin/user-details/${encodeURIComponent(userIdentifier)}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUserDetails(data);
        setShowUserModal(true);
      } else {
        console.error('Failed to fetch user details');
        alert('User not found');
      }
    } catch (error) {
      console.error('Error fetching user details:', error);
      alert('Error fetching user details');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab: 'submissions' | 'payments' | 'users') => {
    setActiveTab(tab);
    if (tab === 'submissions') {
      fetchSubmissions();
    } else if (tab === 'payments') {
      fetchPayments();
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
          🔐 Enhanced Admin Panel
        </h3>
        <button
          onClick={() => {
            setShowAdmin(!showAdmin);
            if (!showAdmin && activeTab === 'submissions' && submissions.length === 0) {
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
          {/* Tab Navigation */}
          <div style={{ 
            display: 'flex', 
            marginBottom: '20px', 
            borderBottom: '2px solid #dee2e6' 
          }}>
            {[
              { key: 'submissions', label: '📋 Submissions', count: submissions.length },
              { key: 'payments', label: '💳 Payment History', count: payments.length },
              { key: 'users', label: '👤 User Lookup', count: null }
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => handleTabChange(tab.key as any)}
                style={{
                  padding: '10px 20px',
                  border: 'none',
                  borderBottom: activeTab === tab.key ? '3px solid #dc3545' : '3px solid transparent',
                  backgroundColor: activeTab === tab.key ? '#fff' : '#f8f9fa',
                  color: activeTab === tab.key ? '#dc3545' : '#666',
                  cursor: 'pointer',
                  fontWeight: activeTab === tab.key ? 'bold' : 'normal',
                  marginRight: '8px'
                }}
              >
                {tab.label} {tab.count !== null && `(${tab.count})`}
              </button>
            ))}
          </div>

          {/* Filter Controls */}
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            marginBottom: '16px',
            flexWrap: 'wrap',
            alignItems: 'center'
          }}>
            <input
              type="text"
              placeholder="Filter by User ID..."
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                minWidth: '200px'
              }}
            />
            <input
              type="email"
              placeholder="Filter by Email..."
              value={emailFilter}
              onChange={(e) => setEmailFilter(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                minWidth: '200px'
              }}
            />
            <button
              onClick={() => {
                if (activeTab === 'submissions') fetchSubmissions();
                else if (activeTab === 'payments') fetchPayments();
              }}
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
              {loading ? 'Loading...' : '🔍 Apply Filters'}
            </button>
            <button
              onClick={() => {
                setUserFilter('');
                setEmailFilter('');
                if (activeTab === 'submissions') fetchSubmissions();
                else if (activeTab === 'payments') fetchPayments();
              }}
              style={{
                padding: '8px 16px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              🗑️ Clear Filters
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === 'submissions' && (
            <div>
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
                          <td style={{ padding: '8px' }}>
                            <button
                              onClick={() => fetchUserDetails(submission.user_email)}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#007bff',
                                textDecoration: 'underline',
                                cursor: 'pointer',
                                fontSize: '0.85rem'
                              }}
                            >
                              {submission.user_email}
                            </button>
                          </td>
                          <td style={{ padding: '8px' }}>{submission.business_name.substring(0, 20)}...</td>
                          <td style={{ padding: '8px' }}>***{submission.ein.slice(-4)}</td>
                          <td style={{ padding: '8px' }}>{formatMonth(submission.month)}</td>
                          <td style={{ padding: '8px' }}>{submission.total_vehicles}</td>
                          <td style={{ padding: '8px' }}>${submission.total_tax}</td>
                          <td style={{ padding: '8px' }}>{formatDate(submission.created_at)}</td>
                          <td style={{ padding: '8px' }}>
                            <div style={{ display: 'flex', gap: '4px' }}>
                              <button
                                onClick={() => downloadFile(parseInt(submission.id), 'pdf')}
                                style={{
                                  padding: '4px 8px',
                                  backgroundColor: '#dc3545',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem'
                                }}
                              >
                                📄 PDF
                              </button>
                              <button
                                onClick={() => downloadFile(parseInt(submission.id), 'xml')}
                                style={{
                                  padding: '4px 8px',
                                  backgroundColor: '#6c757d',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem'
                                }}
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
            </div>
          )}

          {activeTab === 'payments' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                <button
                  onClick={fetchPayments}
                  disabled={loading}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#17a2b8',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: loading ? 'not-allowed' : 'pointer'
                  }}
                >
                  {loading ? 'Loading...' : '🔄 Refresh Payments'}
                </button>
                <span style={{ fontSize: '0.9rem', color: '#666' }}>
                  Total: {payments.length} payments
                </span>
              </div>

              {payments.length > 0 ? (
                <div style={{ 
                  maxHeight: '400px', 
                  overflowY: 'auto', 
                  border: '1px solid #ddd', 
                  borderRadius: '4px' 
                }}>
                  <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                    <thead style={{ background: '#e9ecef', position: 'sticky', top: 0 }}>
                      <tr>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Payment ID</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>User Email</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Amount</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Status</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Used For</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Submission</th>
                        <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payments.map((payment) => (
                        <tr key={payment.id} style={{ borderBottom: '1px solid #eee' }}>
                          <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                            {payment.payment_intent_id.substring(0, 20)}...
                          </td>
                          <td style={{ padding: '8px' }}>
                            <button
                              onClick={() => fetchUserDetails(payment.user_email)}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#007bff',
                                textDecoration: 'underline',
                                cursor: 'pointer',
                                fontSize: '0.85rem'
                              }}
                            >
                              {payment.user_email}
                            </button>
                          </td>
                          <td style={{ padding: '8px', fontWeight: 'bold' }}>
                            ${payment.amount_dollars.toFixed(2)}
                          </td>
                          <td style={{ padding: '8px' }}>
                            <span style={{
                              padding: '2px 6px',
                              borderRadius: '3px',
                              fontSize: '0.75rem',
                              backgroundColor: payment.status === 'succeeded' ? '#d4edda' : 
                                              payment.status === 'pending' ? '#fff3cd' : '#f8d7da',
                              color: payment.status === 'succeeded' ? '#155724' : 
                                     payment.status === 'pending' ? '#856404' : '#721c24'
                            }}>
                              {payment.status}
                            </span>
                          </td>
                          <td style={{ padding: '8px' }}>
                            <div style={{ fontSize: '0.75rem' }}>
                              {payment.used_for_preview && <span style={{ color: '#007bff' }}>📄 Preview</span>}
                              {payment.used_for_preview && payment.used_for_submission && <br />}
                              {payment.used_for_submission && <span style={{ color: '#28a745' }}>✅ Submit</span>}
                            </div>
                          </td>
                          <td style={{ padding: '8px' }}>
                            {payment.submission_id ? (
                              <span style={{ color: '#007bff' }}>#{payment.submission_id}</span>
                            ) : (
                              <span style={{ color: '#6c757d' }}>-</span>
                            )}
                          </td>
                          <td style={{ padding: '8px' }}>{payment.created_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: '#666', fontStyle: 'italic' }}>
                  No payments found. Click "Refresh Payments" to load data.
                </p>
              )}
            </div>
          )}

          {activeTab === 'users' && (
            <div>
              <div style={{ 
                background: '#fff', 
                padding: '20px', 
                borderRadius: '4px', 
                border: '1px solid #ddd' 
              }}>
                <h4 style={{ margin: '0 0 16px 0', color: '#495057' }}>👤 User Lookup</h4>
                <p style={{ margin: '0 0 16px 0', color: '#666', fontSize: '0.9rem' }}>
                  Search for a specific user by their email address or User ID to view their complete history.
                </p>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
                  <input
                    type="text"
                    placeholder="Enter email address or User ID..."
                    style={{
                      padding: '10px 12px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      flex: 1,
                      fontSize: '1rem'
                    }}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        const input = e.target as HTMLInputElement;
                        if (input.value.trim()) {
                          fetchUserDetails(input.value.trim());
                        }
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const input = document.querySelector('input[placeholder*="email address"]') as HTMLInputElement;
                      if (input?.value.trim()) {
                        fetchUserDetails(input.value.trim());
                      }
                    }}
                    disabled={loading}
                    style={{
                      padding: '10px 20px',
                      backgroundColor: '#007bff',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: loading ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {loading ? 'Searching...' : '🔍 Search User'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* User Details Modal */}
          {showUserModal && userDetails && (
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
                padding: '24px',
                borderRadius: '8px',
                maxWidth: '800px',
                width: '90%',
                maxHeight: '80%',
                overflow: 'auto'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ margin: 0, color: '#dc3545' }}>👤 User Details</h3>
                  <button
                    onClick={() => setShowUserModal(false)}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '1.5rem',
                      cursor: 'pointer',
                      color: '#666'
                    }}
                  >
                    ×
                  </button>
                </div>
                
                {/* User Summary */}
                <div style={{ 
                  background: '#f8f9fa', 
                  padding: '16px', 
                  borderRadius: '4px', 
                  marginBottom: '20px',
                  border: '1px solid #dee2e6'
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                    <div>
                      <strong>Email:</strong> {userDetails.user_email}
                    </div>
                    <div>
                      <strong>User ID:</strong> {userDetails.user_uid.substring(0, 12)}...
                    </div>
                    <div>
                      <strong>Total Submissions:</strong> {userDetails.total_submissions}
                    </div>
                    <div>
                      <strong>Total Payments:</strong> {userDetails.total_payments}
                    </div>
                    <div>
                      <strong>Amount Paid:</strong> ${userDetails.total_amount_paid.toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* Submissions */}
                <h4 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '8px' }}>
                  📋 Submissions ({userDetails.submissions.length})
                </h4>
                {userDetails.submissions.length > 0 ? (
                  <div style={{ marginBottom: '24px', maxHeight: '200px', overflow: 'auto' }}>
                    <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: '#f8f9fa' }}>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>ID</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Business</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Month</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Vehicles</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Tax</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userDetails.submissions.map((submission) => (
                          <tr key={submission.id}>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{submission.id}</td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{submission.business_name}</td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{submission.month}</td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{submission.total_vehicles}</td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>${submission.total_tax}</td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{submission.created_at}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: '#666', fontStyle: 'italic', marginBottom: '24px' }}>No submissions found.</p>
                )}

                {/* Payments */}
                <h4 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '8px' }}>
                  💳 Payment History ({userDetails.payments.length})
                </h4>
                {userDetails.payments.length > 0 ? (
                  <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                    <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: '#f8f9fa' }}>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Amount</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Status</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Used For</th>
                          <th style={{ padding: '8px', textAlign: 'left', border: '1px solid #dee2e6' }}>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userDetails.payments.map((payment) => (
                          <tr key={payment.id}>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6', fontWeight: 'bold' }}>
                              ${payment.amount_dollars.toFixed(2)}
                            </td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: '3px',
                                fontSize: '0.75rem',
                                backgroundColor: payment.status === 'succeeded' ? '#d4edda' : '#f8d7da',
                                color: payment.status === 'succeeded' ? '#155724' : '#721c24'
                              }}>
                                {payment.status}
                              </span>
                            </td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>
                              {payment.used_for_preview && '📄 Preview'}
                              {payment.used_for_preview && payment.used_for_submission && ', '}
                              {payment.used_for_submission && '✅ Submit'}
                            </td>
                            <td style={{ padding: '8px', border: '1px solid #dee2e6' }}>{payment.created_at}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: '#666', fontStyle: 'italic' }}>No payments found.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
