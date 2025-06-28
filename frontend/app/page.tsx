"use client";
import { useState, useEffect, ChangeEvent } from 'react'
import { auth } from '../lib/firebase'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import LoginForm from './LoginForm'
import LoginModal from './LoginModal'
import { checkUserExists, createUserAndSendPassword } from '../lib/authUtils'
import { DateTime } from "luxon";

export const weightCategories = [
  { label: 'A (55,000 lbs)',          value: 'A', tax: 100.00 },
  { label: 'B (55,001 – 56,000 lbs)', value: 'B', tax: 122.00 },
  { label: 'C (56,001 – 57,000 lbs)', value: 'C', tax: 144.00 },
  { label: 'D (57,001 – 58,000 lbs)', value: 'D', tax: 166.00 },
  { label: 'E (58,001 – 59,000 lbs)', value: 'E', tax: 188.00 },
  { label: 'F (59,001 – 60,000 lbs)', value: 'F', tax: 210.00 },
  { label: 'G (60,001 – 61,000 lbs)', value: 'G', tax: 232.00 },
  { label: 'H (61,001 – 62,000 lbs)', value: 'H', tax: 254.00 },
  { label: 'I (62,001 – 63,000 lbs)', value: 'I', tax: 276.00 },
  { label: 'J (63,001 – 64,000 lbs)', value: 'J', tax: 298.00 },
  { label: 'K (64,001 – 65,000 lbs)', value: 'K', tax: 320.00 },
  { label: 'L (65,001 – 66,000 lbs)', value: 'L', tax: 342.00 },
  { label: 'M (66,001 – 67,000 lbs)', value: 'M', tax: 364.00 },
  { label: 'N (67,001 – 68,000 lbs)', value: 'N', tax: 386.00 },
  { label: 'O (68,001 – 69,000 lbs)', value: 'O', tax: 408.00 },
  { label: 'P (69,001 – 70,000 lbs)', value: 'P', tax: 430.00 },
  { label: 'Q (70,001 – 71,000 lbs)', value: 'Q', tax: 452.00 },
  { label: 'R (71,001 – 72,000 lbs)', value: 'R', tax: 474.00 },
  { label: 'S (72,001 – 73,000 lbs)', value: 'S', tax: 496.00 },
  { label: 'T (73,001 – 74,000 lbs)', value: 'T', tax: 518.00 },
  { label: 'U (74,001 – 75,000 lbs)', value: 'U', tax: 540.00 },
  { label: 'V (over 75,000 lbs)',     value: 'V', tax: 550.00 },
  { label: 'W (Suspended)',           value: 'W', tax:   0.00 },
]

type Vehicle = {
  vin: string
  category: string
  used_month: string
  is_logging: boolean
  is_suspended: boolean
  is_agricultural: boolean
  mileage_5000_or_less: boolean
}

interface AdminSubmission {
  id: number;
  business_name: string;
  ein: string;
  created_at: string;
  month: string;
  user_uid: string;
  user_email: string;  // Add this line
  total_vehicles: number;
  total_tax: number;
}

interface AdminSubmissionFile {
  id: number;
  document_type: string;
  filename: string;
  s3_key: string;
  uploaded_at: string;
}

export default function Form2290() {
  // Always get today's date in America/New_York (Eastern) as YYYY-MM-DD
  const easternToday = DateTime.now().setZone("America/New_York").toISODate();

  // --- Auth state & logout ---
  const [user, setUser] = useState<any>(null)
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, u => {
      setUser(u)
      // Auto-populate email when user logs in
      if (u && u.email) {
        setFormData(prev => ({
          ...prev,
          email: u.email
        }))
      }
    })
    return unsubscribe
  }, [])
  const handleLogout = async () => {
    try {
      await signOut(auth)
    } catch (e) {
      alert('Logout failed')
    }
  }

  // Determine API base URL
  const isBrowser = typeof window !== 'undefined'
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : ''
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi

  // Form state (added `email`)
  const [formData, setFormData] = useState({
    email:             '',
    business_name:     '',
    ein:               '',
    address:           '',
    city:              '',
    state:             '',
    zip:               '',
    tax_year:          '2025',
    used_on_july:      '202507',
    address_change:    false,
    amended_return:    false,
    vin_correction:    false,
    final_return:      false,
    include_preparer:  false,
    preparer_name:           '',
    preparer_ptin:           '',
    date_prepared:           '',
    preparer_firm_name:      '',
    preparer_firm_ein:       '',
    preparer_firm_address:   '',
    preparer_firm_citystatezip: '',
    preparer_firm_phone:     '',
    consent_to_disclose: false,
    designee_name:       '',
    designee_phone:      '',
    designee_pin:        '',
    vehicles: [
      {
        vin: '',
        category: '',
        used_month: '',
        is_logging: false,
        is_suspended: false,
        is_agricultural: false,
        mileage_5000_or_less: false,
      },
    ] as Vehicle[],
    signature:      '',
    printed_name:   '',
    signature_date: easternToday,
    payEFTPS:       false,
    payCard:        false,
    eftps_routing:  '',
    eftps_account:  '',
    card_holder:    '',
    card_number:    '',
    card_exp:       '',
    card_cvv:       '',
  })

  // Login UI states
  const [showLogin, setShowLogin]           = useState(false)
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [pendingEmail, setPendingEmail]     = useState('')

  const [totalTax, setTotalTax] = useState(0)
  const todayStr = new Date().toISOString().split('T')[0]

  // Month options July→June
  const months = Array.from({ length: 12 }).map((_, i) => {
    const m = 6 + i
    return {
      label: new Date(2025, m, 1).toLocaleString('default', { month: 'long', year: 'numeric' }),
      value: `2025${String(m + 1).padStart(2, '0')}`,
    }
  })

  // Logging rates
  const loggingRates: Record<string, number> = {
    A:75, B:91.5, C:108, D:124.5, E:141, F:157.5,
    G:174, H:190.5, I:207, J:223.5, K:240, L:256.5,
    M:273, N:289.5, O:306, P:322.5, Q:339, R:355.5,
    S:372, T:388.5, U:405, V:412.5, W:0,
  }

  useEffect(() => {
    let total = 0
    formData.vehicles.forEach(v => {
      const mon = parseInt(v.used_month.slice(-2), 10) || 0
      if (!mon || v.is_suspended || v.is_agricultural) return
      const catObj = weightCategories.find(w => w.value === v.category)
      if (!catObj) return
      const rate = v.is_logging ? loggingRates[v.category] : catObj.tax
      const monthsLeft = mon >= 7 ? 12 : 13 - mon
      total += Number(((rate * monthsLeft) / 12).toFixed(2))
    })
    setTotalTax(total)
  }, [formData.vehicles])

  const handleChange = (e: ChangeEvent<HTMLInputElement|HTMLSelectElement>) => {
    const t = e.target as HTMLInputElement
    const { name, type, value, checked } = t

    // Include Paid Preparer toggle
    if (name === 'include_preparer') {
      if (!checked) {
        setFormData({
          ...formData,
          include_preparer: false,
          preparer_name: '',
          preparer_ptin: '',
          date_prepared: '',
          preparer_firm_name: '',
          preparer_firm_ein: '',
          preparer_firm_address: '',
          preparer_firm_citystatezip: '',
          preparer_firm_phone: '',
        })
      } else {
        setFormData({ ...formData, include_preparer: true })
      }
      return
    }

    // Consent to Disclose toggle
    if (name === 'consent_to_disclose') {
      if (!checked) {
        setFormData({
          ...formData,
          consent_to_disclose: false,
          designee_name: '',
          designee_phone: '',
          designee_pin: '',
        })
      } else {
        setFormData({ ...formData, consent_to_disclose: true })
      }
      return
    }

    // Vehicle fields
    if (name.startsWith('vehicle_')) {
      const [_, idxStr, ...fld] = name.split('_')
      const idx = parseInt(idxStr, 10)
      const field = fld.join('_') as keyof Vehicle
      const vehicles = [...formData.vehicles]
      const vv = { ...vehicles[idx] } as Record<string, any>
      if (type === 'checkbox') {
        vv[field] = checked as any
        if (field === 'is_agricultural' && checked) vv.is_suspended = false
        if (field === 'is_suspended' && checked) vv.is_agricultural = false
        vv.is_agricultural || vv.is_suspended
          ? (vv.category = 'W')
          : vv.category === 'W' && (vv.category = '')
      } else {
        vv[field] = value as any
      }
      vehicles[idx] = vv as Vehicle
      setFormData({ ...formData, vehicles })
      return
    }

    // Payment exclusivity
    if (name === 'payEFTPS') {
      setFormData({ ...formData, payEFTPS: checked, payCard: false })
      return
    }
    if (name === 'payCard') {
      setFormData({ ...formData, payCard: checked, payEFTPS: false })
      return
    }

    // Signature date guard
    if (name === 'signature_date' && value < todayStr) {
      alert('Signature date cannot be before today.')
      return
    }

    // Default update (now includes email)
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value,
    })
  }

  const addVehicle = () => {
    setFormData({
      ...formData,
      vehicles: [
        ...formData.vehicles,
        {
          vin: '',
          category: '',
          used_month: '',
          is_logging: false,
          is_suspended: false,
          is_agricultural: false,
          mileage_5000_or_less: false,
        },
      ],
    })
  }

  const removeVehicle = (i: number) => {
    setFormData({
      ...formData,
      vehicles: formData.vehicles.filter((_, j) => j !== i),
    })
  }

  const totalVINs      = formData.vehicles.length
  const lodgingCount   = formData.vehicles.filter(v => v.is_logging).length
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length

  const validateBeforeSubmit = (): string | null => {
    if (!formData.business_name.trim()) return 'Business Name is required'
    if (!/^\d{9}$/.test(formData.ein))     return 'EIN must be 9 digits'
    if (formData.include_preparer) {
      if (!formData.preparer_name.trim())      return 'Preparer Name is required'
      if (!formData.preparer_ptin.trim())      return 'Preparer PTIN is required'
      if (!formData.date_prepared)             return 'Date Prepared is required'
      if (!formData.preparer_firm_name.trim()) return 'Firm Name is required'
      if (!/^\d{9}$/.test(formData.preparer_firm_ein)) return 'Firm EIN must be 9 digits'
      if (!formData.preparer_firm_address.trim())      return 'Firm Address is required'
      if (!formData.preparer_firm_citystatezip.trim()) return 'Firm City/State/ZIP is required'
      if (!/^\d{10}$/.test(formData.preparer_firm_phone)) return 'Firm Phone must be 10 digits'
    }
    if (formData.consent_to_disclose) {
      if (!formData.designee_name.trim())       return 'Designee Name is required'
      if (!/^\d{10}$/.test(formData.designee_phone)) return 'Designee Phone must be 10 digits'
      if (!formData.designee_pin.trim())        return 'Designee PIN is required'
    }
    if (!formData.signature.trim())    return 'Signature is required'
    if (!formData.printed_name.trim()) return 'Printed Name is required'
    if (!formData.signature_date)      return 'Signature Date is required'
    if (!formData.payEFTPS && !formData.payCard) {
      return 'Select either EFTPS or Credit/Debit Card'
    }
    if (formData.payEFTPS) {
      if (!formData.eftps_routing.trim() || !formData.eftps_account.trim()) {
        return 'EFTPS routing and account are required'
      }
    }
    if (formData.payCard) {
      if (!formData.card_holder.trim() ||
          !formData.card_number.trim() ||
          !formData.card_exp.trim() ||
          !formData.card_cvv.trim()) {
        return 'All credit/debit card fields are required'
      }
    }
    return null
  }

  const handleSubmit = async () => {
    // 1) run client-side validation FIRST
    const err = validateBeforeSubmit()
    if (err) { alert(err); return }

    // 2) require email
    if (!formData.email.trim()) {
      alert('Email is required')
      return
    }

    // 3) Check/create account if not signed in
    if (!auth.currentUser) {
      let exists = false
      try {
        exists = await checkUserExists(formData.email)
      } catch (e: any) {
        if (e?.status === 404) {
          exists = false
        } else {
          alert("Error checking user: " + (e?.message || JSON.stringify(e)))
          return
        }
      }

      if (!exists) {
        try {
          const didCreate = await createUserAndSendPassword(formData.email)
          if (didCreate) {
            alert("Account created! Check your email for your password.")
          } else {
            console.log("⚠️ [Signup] createUserAndSendPassword returned false")
          }
          // Wait for Firebase to update the currentUser
          await new Promise(resolve => {
            const unsubscribe = onAuthStateChanged(auth, user => {
              if (user) {
                unsubscribe();
                resolve(true);
              }
            });
          });
        } catch (e: any) {
          if (e?.status === 404) {
            alert("Account created, but welcome email could not be sent. Please contact support.")
          } else {
            alert("Error creating account: " + (e?.message || JSON.stringify(e)))
          }
          // Do not return; continue to submission
        }
      } else {
        console.log("👤 [Signup] User already exists – skipping creation")
      }
    }

    // 4) Submit and download PDF (which also generates XML)
    try {
      const token = await auth.currentUser!.getIdToken();
      const response = await fetch(`${API_BASE}/build-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        let errorMsg = response.statusText;
        try {
          const errorData = await response.json();
          errorMsg = errorData.error || errorMsg;
        } catch {
          // Non-JSON response, use statusText
        }
        alert(`Submission failed: ${errorMsg}`);
        return;
      }

      // Download the PDF
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "form2290.pdf";
      a.click();
      URL.revokeObjectURL(url);

      alert("✅ Form submitted successfully! XML and PDF generated.");
    } catch (error: any) {
      alert(`Network error: ${error.message}`);
    }
  }

  // Admin Submissions component
  function AdminSubmissions() {
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
                        <td style={{ padding: '8px' }}>
                          <div style={{ display: 'flex', gap: '4px' }}>
                            <button
                              onClick={() => fetchSubmissionFiles(submission.id)}
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                backgroundColor: '#007bff',
                                color: 'white',
                                border: 'none',
                                borderRadius: '2px',
                                cursor: 'pointer'
                              }}
                            >
                              📄 Files
                            </button>
                            <button
                              onClick={() => downloadFile(submission.id, 'pdf')}
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                backgroundColor: '#dc3545',
                                color: 'white',
                                border: 'none',
                                borderRadius: '2px',
                                cursor: 'pointer'
                              }}
                            >
                              📥 PDF
                            </button>
                            <button
                              onClick={() => downloadFile(submission.id, 'xml')}
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                backgroundColor: '#6c757d',
                                color: 'white',
                                border: 'none',
                                borderRadius: '2px',
                                cursor: 'pointer'
                              }}
                            >
                              📥 XML
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
    )
  }

  // Styles
  const container: React.CSSProperties  = {
    maxWidth: 900,
    margin: '0 auto',
    padding: 20,
    fontFamily: 'Segoe UI, sans-serif'
  }
  const header: React.CSSProperties     = {
    textAlign: 'center',
    color: '#d32f2f'
  }
  const labelSmall: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.9rem'
  }
  const btnSmall: React.CSSProperties   = {
    padding: '6px 12px',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: '0.9rem'
  }

  return (
    <div style={container}>
      {/* --- Website Banner --- */}
      
      {/* --- Auth Status & Login/Logout --- */}
      <div style={{ textAlign: 'right', marginBottom: 20 }}>
        {user ? (
          <>
            Logged in as <strong>{user.email}</strong>{' '}
            <button
              onClick={handleLogout}
              style={{ ...btnSmall, backgroundColor: '#d32f2f', color: '#fff' }}
            >
              Logout
            </button>
          </>
        ) : (
          <span style={{ fontStyle: 'italic' }}>Not signed in</span>
        )}
      </div>

      {/* --- Login Toggle --- */}
      {!user && (
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <button
            onClick={() => setShowLogin(prev => !prev)}
            style={{ padding: '6px 12px', borderRadius: 4, backgroundColor: '#1565c0', color: '#fff', border: 'none' }}
          >
            {showLogin ? 'Hide Login' : 'Login or Create Account'}
          </button>
        </div>
      )}

      {/* --- Embedded Login Form --- */}
      {showLogin && !user && (
        <div style={{ maxWidth: 420, margin: '0 auto', marginBottom: 30 }}>
          <LoginForm />
        </div>
      )}

      {/* --- Login Modal for existing users --- */}
      {showLoginModal && (
        <LoginModal email={pendingEmail} onClose={() => setShowLoginModal(false)} />
      )}

      {/* Business Info (now includes Email at the start) */}
      <h2>Business Info</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative' }}>
          <input
            name="email"
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={handleChange}
            required
            disabled={!!user}
            style={{
              backgroundColor: user ? '#f5f5f5' : 'white',
              color: user ? '#666' : 'black',
              cursor: user ? 'not-allowed' : 'text'
            }}
          />
          {user && (
            <span style={{ 
              fontSize: '0.8rem', 
              color: '#666', 
              fontStyle: 'italic',
              marginLeft: '4px'
            }}>
              (from account)
            </span>
          )}
        </div>
        <input name="business_name" placeholder="Name" value={formData.business_name} onChange={handleChange} />
        <input
          name="ein"
          placeholder="EIN"
          pattern="\d{9}"
          maxLength={9}
          inputMode="numeric"
          title="9 digits"
          value={formData.ein}
          onChange={handleChange}
        />
        <input name="address" placeholder="Address" value={formData.address} onChange={handleChange} />
        <input name="city" placeholder="City" value={formData.city} onChange={handleChange} />
        <input name="state" placeholder="State" value={formData.state} onChange={handleChange} />
        <input
          name="zip"
          placeholder="ZIP"
          pattern="\d{5}"
          maxLength={5}
          inputMode="numeric"
          title="5 digits"
          value={formData.zip}
          onChange={handleChange}
        />
      </div>

      {/* Return Flags */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 12 }}>
        {['address_change','amended_return','vin_correction','final_return'].map(flag => (
          <label key={flag} style={labelSmall}>
            <input type="checkbox" name={flag} checked={(formData as any)[flag]} onChange={handleChange} />
            {flag.replace(/_/g,' ')}
          </label>
        ))}
      </div>

      {/* Paid Preparer */}
      <h2 style={{ marginTop: 20 }}>
        <label style={labelSmall}>
          <input
            type="checkbox"
            name="include_preparer"
            checked={formData.include_preparer}
            onChange={handleChange}
          />
          Include Paid Preparer
        </label>
      </h2>
      {formData.include_preparer && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input name="preparer_name" placeholder="Preparer Name" value={formData.preparer_name} onChange={handleChange} required />
            <input name="preparer_ptin" placeholder="PTIN" value={formData.preparer_ptin} onChange={handleChange} required />
            <input type="date" name="date_prepared" max={todayStr} value={formData.date_prepared} onChange={handleChange} required />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <input name="preparer_firm_name" placeholder="Firm Name" value={formData.preparer_firm_name} onChange={handleChange} required />
            <input
              name="preparer_firm_ein"
              placeholder="Firm EIN"
              pattern="\d{9}"
              maxLength={9}
              inputMode="numeric"
              title="9 digits"
              value={formData.preparer_firm_ein}
              onChange={handleChange}
              required
            />
            <input name="preparer_firm_address" placeholder="Firm Address" value={formData.preparer_firm_address} onChange={handleChange} required />
            <input
              name="preparer_firm_citystatezip"
              placeholder="Firm City/State/ZIP"
              value={formData.preparer_firm_citystatezip}
              onChange={handleChange}
              required
            />
            <input
              type="tel"
              name="preparer_firm_phone"
              placeholder="Firm Phone (10 digits)"
              pattern="\d{10}"
              maxLength={10}
              inputMode="numeric"
              title="10 digits"
              value={formData.preparer_firm_phone}
              onChange={handleChange}
              required
            />
          </div>
        </>
      )}

      {/* Third-Party Designee / Consent */}
      <h2 style={{ marginTop: 20 }}>
        <label style={labelSmall}>
          <input type="checkbox" name="consent_to_disclose" checked={formData.consent_to_disclose} onChange={handleChange} />
          Consent to Disclose
        </label>
      </h2>
      {formData.consent_to_disclose && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="designee_name" placeholder="Designee Name" value={formData.designee_name} onChange={handleChange} required />
          <input
            name="designee_phone"
            placeholder="Designee Phone (10 digits)"
            pattern="\d{10}"
            maxLength={10}
            inputMode="numeric"
            title="10 digits"
            value={formData.designee_phone}
            onChange={handleChange}
            required
          />
          <input name="designee_pin" placeholder="Designee PIN" value={formData.designee_pin} onChange={handleChange} required />
        </div>
      )}

      {/* Vehicles */}
      <h2 style={{ marginTop: 20 }}>Vehicles</h2>
      {formData.vehicles.map((v, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <input
            style={{ width: 180 }}
            type="text"
            name={`vehicle_${i}_vin`}
            placeholder="VIN"
            pattern="[A-Za-z0-9]{17}"
            maxLength={17}
            title="17 chars"
            value={v.vin}
            onChange={handleChange}
          />
          <select name={`vehicle_${i}_used_month`} value={v.used_month} onChange={handleChange}>
            <option value="">Select Month/Year</option>
            {months.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <select name={`vehicle_${i}_category`} value={v.category} onChange={handleChange}>
            <option value="">Weight Class</option>
            {weightCategories.map(w => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
          <label style={labelSmall}>
            Logging? <input type="checkbox" name={`vehicle_${i}_is_logging`} checked={v.is_logging} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Agricultural ≤7,000 mi <input type="checkbox" name={`vehicle_${i}_is_agricultural`} checked={v.is_agricultural} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Non-Agricultural ≤5,000 mi <input type="checkbox" name={`vehicle_${i}_is_suspended`} checked={v.is_suspended} onChange={handleChange} />
          </label>
          <button
            type="button"
            style={{ ...btnSmall, backgroundColor: '#d32f2f', color: '#fff' }}
            onClick={() => removeVehicle(i)}
          >
            Remove
          </button>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#1565c0', color: '#fff' }}
          onClick={addVehicle}
        >
          + Add Vehicle
        </button>
        <div>
          <strong>VINs:</strong> {totalVINs}
          <strong style={{ marginLeft: 12 }}>Logging:</strong> {lodgingCount}
          <strong style={{ marginLeft: 12 }}>Suspended:</strong> {suspendedCount}
        </div>
      </div>

      <h3>Total Tax: ${totalTax.toFixed(2)}</h3>

      {/* Signature */}
      <h2>Signature</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input name="signature" placeholder="Signature" value={formData.signature} onChange={handleChange} />
        <input name="printed_name" placeholder="Printed Name" value={formData.printed_name} onChange={handleChange} />
        <input
          type="date"
          name="signature_date"
          value={formData.signature_date}
          readOnly
          disabled
          style={{ background: "#eee", color: "#888" }}
        />
      </div>

      {/* Payment Method */}
      <h2 style={{ marginTop: 20 }}>Payment Method</h2>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 8 }}>
        <label>
          <input type="checkbox" name="payEFTPS" checked={formData.payEFTPS} onChange={handleChange} /> EFTPS
        </label>
        <label>
          <input type="checkbox" name="payCard" checked={formData.payCard} onChange={handleChange} /> Credit/Debit Card
        </label>
      </div>
      {formData.payEFTPS && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="eftps_routing" placeholder="Routing Number" value={formData.eftps_routing} onChange={handleChange} />
          <input name="eftps_account" placeholder="Account Number" value={formData.eftps_account} onChange={handleChange} />
        </div>
      )}
      {formData.payCard && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="card_holder" placeholder="Cardholder Name" value={formData.card_holder} onChange={handleChange} />
          <input name="card_number" placeholder="Card Number" value={formData.card_number} onChange={handleChange} />
          <input name="card_exp" placeholder="MM/YY" value={formData.card_exp} onChange={handleChange} />
          <input name="card_cvv" placeholder="CVV" value={formData.card_cvv} onChange={handleChange} />
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#28a745', color: '#fff', fontSize: '1.1rem', padding: '12px 24px' }}
          onClick={handleSubmit}
        >
          🚀 SUBMIT FORM 2290
        </button>
      </div>

      {/* --- Admin Section (add this after the logout button) --- */}
      {user?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL && (
        <AdminSubmissions />
      )}
    </div>
  )
}