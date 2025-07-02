"use client";
import { useState, useEffect, ChangeEvent, useRef } from 'react'
import { auth } from '../lib/firebase'
import { onAuthStateChanged } from 'firebase/auth'
import LoginModal from './LoginModal'
import { checkUserExists, createUserAndSendPassword } from '../lib/authUtils'
import { DateTime } from "luxon";
import ReCaptchaComponent, { ReCaptchaRef } from './components/ReCaptcha'

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
  // Debug the API base URL
  const isBrowser = typeof window !== 'undefined'
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : ''
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi
  
  console.log("🔗 API_BASE:", API_BASE); // Add this debug line

  // Always get today's date in America/New_York (Eastern) as YYYY-MM-DD
  const easternToday = DateTime.now().setZone("America/New_York").toISODate();

  // Form state (added `email` and missing IRS compliance fields)
  const [formData, setFormData] = useState({
    email:             '',
    business_name:     '',
    business_name_line2: '', // Optional second line for business name
    ein:               '',
    address:           '',
    address_line2:     '', // Optional second line for address (max 35 chars each line)
    city:              '',
    state:             '',
    zip:               '',
    tax_year:          '2025',
    used_on_july:      '202507',
    address_change:    false,
    amended_return:    false,
    vin_correction:    false,
    final_return:      false,
    // Business Officer Information (required for signing)
    officer_name:      '', // Person who signs the return
    officer_title:     '', // Title (President, Owner, Manager, etc.)
    taxpayer_pin:      '', // 5-digit PIN for electronic signature
    tax_credits:       0,  // Tax credits to apply against liability
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

  // CAPTCHA state and ref
  const [captchaToken, setCaptchaToken] = useState<string | null>(null)
  const [captchaError, setCaptchaError] = useState<string>('')
  const captchaRef = useRef<ReCaptchaRef>(null)

  // Auto-populate email when user logs in
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user && user.email) {
        setFormData(prev => ({
          ...prev,
          email: user.email
        }))
      }
    })
    return unsubscribe
  }, [])

  const [totalTax, setTotalTax] = useState(0)
  const todayStr = new Date().toISOString().split('T')[0]

  // Month options July 2025 → June 2026 (12 months)
  const months = Array.from({ length: 12 }).map((_, i) => {
    const monthIndex = (6 + i) % 12  // 6,7,8,9,10,11,0,1,2,3,4,5
    const year = monthIndex < 6 ? 2026 : 2025  // Jan-Jun = 2026, Jul-Dec = 2025
    const monthNumber = monthIndex + 1  // Convert to 1-based month
    
    return {
      label: new Date(year, monthIndex, 1).toLocaleString('default', { month: 'long', year: 'numeric' }),
      value: `${year}${String(monthNumber).padStart(2, '0')}`,
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

  // CAPTCHA handlers
  const handleCaptchaChange = (token: string | null) => {
    setCaptchaToken(token)
    setCaptchaError('')
  }

  const handleCaptchaExpired = () => {
    setCaptchaToken(null)
    setCaptchaError('CAPTCHA expired. Please complete it again.')
  }

  const handleCaptchaError = () => {
    setCaptchaToken(null)
    setCaptchaError('CAPTCHA error. Please try again.')
  }

  const totalVINs      = formData.vehicles.length
  const lodgingCount   = formData.vehicles.filter(v => v.is_logging).length
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length

  const validateBeforeSubmit = (): string | null => {
    // CAPTCHA validation first
    if (!captchaToken) return 'Please complete the CAPTCHA verification'
    
    if (!formData.business_name.trim()) return 'Business Name is required'
    if (!/^\d{9}$/.test(formData.ein))     return 'EIN must be 9 digits'
    
    // Address length validation (IRS requirement: max 35 chars per line)
    if (formData.address.length > 35) return 'Address line 1 cannot exceed 35 characters'
    if (formData.address_line2 && formData.address_line2.length > 35) return 'Address line 2 cannot exceed 35 characters'
    
    // Business officer information validation
    if (!formData.officer_name.trim()) return 'Officer name is required for signing'
    if (!formData.officer_title.trim()) return 'Officer title is required (e.g., President, Owner, Manager)'
    if (!/^\d{5}$/.test(formData.taxpayer_pin)) return 'Taxpayer PIN must be exactly 5 digits'
    
    // Tax credits validation (if provided)
    if (formData.tax_credits < 0) return 'Tax credits cannot be negative'
    
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
    for (let idx = 0; idx < formData.vehicles.length; idx++) {
      const v = formData.vehicles[idx];
      if (!v.vin.trim()) return `VIN is required for vehicle #${idx + 1}`;
      if (!v.used_month) return `Month is required for vehicle #${idx + 1}`;
      if (!v.category) return `Weight is required for vehicle #${idx + 1}`;
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
      console.log("🚗 Form data being sent:", JSON.stringify(formData, null, 2)); // Debug line
      console.log("🔗 Sending request to:", `${API_BASE}/build-pdf`); // Debug line
      console.log("🔐 Current user:", auth.currentUser?.email); // Debug line
      console.log("🤖 CAPTCHA token:", captchaToken ? "✅ Valid" : "❌ Missing"); // Debug line
      
      const token = await auth.currentUser!.getIdToken();
      console.log("🎟️ Token obtained:", token ? "✅ Yes" : "❌ No"); // Debug line
      
      const response = await fetch(`${API_BASE}/build-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          captchaToken: captchaToken // Include CAPTCHA token
        }),
      });

      console.log("📡 Response status:", response.status); // Debug line
      console.log("📡 Response headers:", Object.fromEntries(response.headers.entries())); // Debug line

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

      // Check content type to determine if it's a file download or JSON response
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        // JSON response - multiple months scenario
        const jsonData = await response.json();
        
        if (jsonData.success && jsonData.files && jsonData.files.length > 0) {
          console.log("📋 Multiple files response received:", jsonData);
          
          // Show success message without automatic downloads
          alert(`✅ Form submitted successfully! Generated ${jsonData.total_files} separate PDFs for different months. Visit My Filings section to see your files.`);
        } else {
          alert(`✅ Generated ${jsonData.files?.length || 0} separate filings for different months. Visit My Filings section to see your files.`);
        }
      } else {
        // File download - single PDF
        const blob = await response.blob();
        const contentDisposition = response.headers.get('content-disposition');
        
        // Extract filename from Content-Disposition header
        let filename = "form2290.pdf";
        if (contentDisposition) {
          const matches = contentDisposition.match(/filename="(.+)"/);
          if (matches) {
            filename = matches[1];
          }
        }
        
        // Download the file
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);

        alert("✅ Form submitted successfully! XML and PDF generated and downloaded.");
      }

      // Reset CAPTCHA after successful submission
      captchaRef.current?.reset();
      setCaptchaToken(null);
    } catch (error: any) {
      console.error("❌ Full error object:", error); // Enhanced debug
      console.error("❌ Error type:", typeof error); // Debug
      console.error("❌ Error name:", error.name); // Debug
      console.error("❌ Error message:", error.message); // Debug
      console.error("❌ Error stack:", error.stack); // Debug
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
          console.log("🔍 Admin panel received data:", data);
          console.log("📊 Number of submissions:", data.submissions?.length || 0);
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
      const monthNum = parseInt(monthCode.substring(4, 6), 10);
      
      // Handle invalid month numbers (like 13, 14, etc.)
      if (monthNum < 1 || monthNum > 12) {
        return `Invalid Month (${monthCode})`;
      }
      
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return `${monthNames[monthNum - 1]} ${year}`;
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

  // Responsive styles for mobile
  // Add this at the top of your return statement
  // (You can move it to _app.tsx or a global CSS file for site-wide effect)
  // This ensures all your pages using this component are mobile friendly
  return (
    <>
      <style>{`
        .form-container {
          max-width: 900px;
          width: 100%;
          margin: 0 auto;
          padding: 20px;
          font-family: 'Segoe UI', sans-serif;
        }
        
        /* Checkbox styling for all screen sizes */
        .form-container input[type="checkbox"] {
          width: 16px !important;
          height: 16px !important;
          min-width: 16px !important;
          margin-right: 8px;
          cursor: pointer;
          accent-color: #007bff;
          pointer-events: auto;
          position: relative;
          z-index: 1;
          -webkit-appearance: checkbox !important;
          -moz-appearance: checkbox !important;
          appearance: checkbox !important;
          background: white !important;
          border: 1px solid #666 !important;
          padding: 0 !important;
          font-size: inherit !important;
          line-height: normal !important;
          display: inline-block !important;
          vertical-align: middle !important;
          transform: none !important;
        }
        
        .form-container input[type="checkbox"]:focus {
          outline: 2px solid #007bff !important;
          outline-offset: 2px !important;
        }
        
        .form-container label {
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          user-select: none;
          pointer-events: auto;
          position: relative;
        }
        
        /* Ensure checkbox labels have proper spacing and hover effects */
        .form-container label:hover {
          opacity: 0.8;
        }
        
        @media (max-width: 600px) {
          .form-container {
            max-width: 100vw;
            padding: 8px;
          }
          .vehicle-row {
            flex-direction: column !important;
            align-items: stretch !important;
            gap: 6px !important;
          }
          .vehicle-row input:not([type="checkbox"]),
          .vehicle-row select,
          .vehicle-row button {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 1rem;
          }
          .vehicle-row label {
            width: 100%;
            font-size: 1rem;
          }
          .vehicle-row {
            margin-bottom: 18px !important;
          }
          .form-container input:not([type="checkbox"]),
          .form-container select {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 1rem;
          }
          .form-container button {
            width: 100%;
            font-size: 1.1rem;
          }
          .form-container .g-recaptcha {
            transform: scale(0.85);
            transform-origin: 0 0;
            margin-bottom: 10px;
          }
          
          /* Enhanced mobile checkbox styling */
          .form-container input[type="checkbox"] {
            width: 20px !important;
            height: 20px !important;
            min-width: 20px !important;
            margin-right: 12px;
          }
          
          /* Better spacing for checkbox labels on mobile */
          .form-container label {
            padding: 8px 0;
            min-height: 44px; /* Touch-friendly minimum height */
          }
        }
      `}</style>
      <div className="form-container">
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
              disabled={!!auth.currentUser}
              style={{
                backgroundColor: auth.currentUser ? '#f5f5f5' : 'white',
                color: auth.currentUser ? '#666' : 'black',
                cursor: auth.currentUser ? 'not-allowed' : 'text'
              }}
            />
            {auth.currentUser && (
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
          <input name="business_name" placeholder="Business Name (Line 1)" value={formData.business_name} onChange={handleChange} maxLength={60} />
          <input 
            name="business_name_line2" 
            placeholder="Business Name (Line 2 - Optional)" 
            value={formData.business_name_line2} 
            onChange={handleChange} 
            maxLength={60}
          />
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
          <input 
            name="address" 
            placeholder="Address (Line 1 - Max 35 chars)" 
            value={formData.address} 
            onChange={handleChange} 
            maxLength={35}
            title="Maximum 35 characters per IRS requirements"
          />
          <input 
            name="address_line2" 
            placeholder="Address (Line 2 - Optional, Max 35 chars)" 
            value={formData.address_line2} 
            onChange={handleChange} 
            maxLength={35}
            title="Maximum 35 characters per IRS requirements"
          />
          <input name="city" placeholder="City" value={formData.city} onChange={handleChange} />
          <input name="state" placeholder="State (2 letters)" value={formData.state} onChange={handleChange} maxLength={2} />
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
            <label key={flag} style={{ ...labelSmall, cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                name={flag} 
                checked={(formData as any)[flag]} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ cursor: 'pointer' }}>
                {flag.replace(/_/g,' ')}
              </span>
            </label>
          ))}
        </div>

        {/* Business Officer Information & Tax Credits */}
        <h2 style={{ marginTop: 20 }}>Business Officer Information</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input 
            name="officer_name" 
            placeholder="Officer Name (Required for signing)" 
            value={formData.officer_name} 
            onChange={handleChange} 
            required
            title="Name of the person authorized to sign this return"
          />
          <input 
            name="officer_title" 
            placeholder="Officer Title (e.g., President, Owner, Manager)" 
            value={formData.officer_title} 
            onChange={handleChange} 
            required
            title="Title of the person signing this return"
          />
          <input 
            name="taxpayer_pin" 
            placeholder="Taxpayer PIN (5 digits)" 
            pattern="\d{5}"
            maxLength={5}
            inputMode="numeric"
            title="5-digit PIN for electronic signature"
            value={formData.taxpayer_pin} 
            onChange={handleChange} 
            required
          />
        </div>
        
        {/* Tax Credits */}
        <h2 style={{ marginTop: 20 }}>Tax Credits (Optional)</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input 
            name="tax_credits" 
            type="number"
            min="0"
            step="0.01"
            placeholder="Tax Credits Amount"
            value={formData.tax_credits || ''} 
            onChange={handleChange}
            title="Amount of tax credits to apply against tax liability"
          />
          <span style={{ fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>
            Enter any tax credits to be applied against your tax liability
          </span>
        </div>

        {/* Paid Preparer */}
        <h2 style={{ marginTop: 20 }}>
          <label style={{ ...labelSmall, cursor: 'pointer' }}>
            <input
              type="checkbox"
              name="include_preparer"
              checked={formData.include_preparer}
              onChange={handleChange}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ cursor: 'pointer' }}>Include Paid Preparer</span>
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
          <label style={{ ...labelSmall, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              name="consent_to_disclose" 
              checked={formData.consent_to_disclose} 
              onChange={handleChange}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ cursor: 'pointer' }}>Consent to Disclose</span>
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
          <div key={i} className="vehicle-row" style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
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
              required
            />
            <select
              name={`vehicle_${i}_used_month`}
              value={v.used_month}
              onChange={handleChange}
              required
            >
              <option value="">Select Month</option>
              {months.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <select
              name={`vehicle_${i}_category`}
              value={v.category}
              onChange={handleChange}
              required
            >
              <option value="">Select Weight</option>
              {weightCategories.map((w) => (
                <option key={w.value} value={w.value}>{w.label}</option>
              ))}
            </select>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <span style={{ cursor: 'pointer' }}>Logging?</span>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_is_logging`} 
                checked={v.is_logging} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
            </label>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <span style={{ cursor: 'pointer' }}>Agricultural ≤7,000 mi</span>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_is_agricultural`} 
                checked={v.is_agricultural} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
            </label>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <span style={{ cursor: 'pointer' }}>Non-Agricultural ≤5,000 mi</span>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_is_suspended`} 
                checked={v.is_suspended} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
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
          <label style={{ ...labelSmall, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              name="payEFTPS" 
              checked={formData.payEFTPS} 
              onChange={handleChange}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ cursor: 'pointer' }}>EFTPS</span>
          </label>
          <label style={{ ...labelSmall, cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              name="payCard" 
              checked={formData.payCard} 
              onChange={handleChange}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ cursor: 'pointer' }}>Credit/Debit Card</span>
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

        {/* CAPTCHA Section */}
        <h2 style={{ marginTop: 20 }}>Security Verification</h2>
        <div style={{ marginTop: 12 }}>
          {process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ? (
            <>
              <ReCaptchaComponent
                ref={captchaRef}
                sitekey={process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY}
                onChange={handleCaptchaChange}
                onExpired={handleCaptchaExpired}
                onError={handleCaptchaError}
                theme="light"
                size="normal"
              />
              {captchaError && (
                <div style={{ 
                  color: '#d32f2f', 
                  fontSize: '0.9rem', 
                  marginTop: '8px',
                  fontWeight: '500'
                }}>
                  ⚠️ {captchaError}
                </div>
              )}
              {!captchaToken && (
                <div style={{ 
                  color: '#666', 
                  fontSize: '0.85rem', 
                  marginTop: '4px',
                  fontStyle: 'italic'
                }}>
                  Please complete the CAPTCHA verification above to submit your form.
                </div>
              )}
            </>
          ) : (
            <div style={{ 
              color: '#d32f2f', 
              padding: '12px', 
              backgroundColor: '#ffeaea', 
              border: '1px solid #d32f2f', 
              borderRadius: '4px',
              fontSize: '0.9rem'
            }}>
              ⚠️ CAPTCHA is not configured. Please set NEXT_PUBLIC_RECAPTCHA_SITE_KEY in your environment variables.
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
          <button
            type="button"
            style={{ 
              ...btnSmall, 
              backgroundColor: captchaToken ? '#28a745' : '#cccccc', 
              color: '#fff', 
              fontSize: '1.1rem', 
              padding: '12px 24px',
              cursor: captchaToken ? 'pointer' : 'not-allowed',
              opacity: captchaToken ? 1 : 0.6
            }}
            onClick={handleSubmit}
            disabled={!captchaToken}
          >
          SUBMIT FORM 2290
          </button>
          {!captchaToken && (
            <div style={{ 
              alignSelf: 'center',
              color: '#666', 
              fontSize: '0.85rem',
              fontStyle: 'italic'
            }}>
              Complete CAPTCHA to enable submission
            </div>
          )}
        </div>

        {/* --- Admin Section (add this after the logout button) --- */}
        {auth.currentUser?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL && (
          <AdminSubmissions />
        )}
      </div>
    </>
  )
}