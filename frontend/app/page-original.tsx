"use client";
import { useRef } from 'react';
import { auth } from '../lib/firebase';
import LoginModal from './LoginModal';
import ReCaptchaComponent, { ReCaptchaRef } from './components/ReCaptcha';
import { useForm2290 } from './hooks/useForm2290';
import { createFormHandler } from './utils/formHandlers';
import { createSubmissionHandler } from './utils/submissionHandler';
import { BusinessInfo } from './components/BusinessInfo';
import { ReturnFlags } from './components/ReturnFlags';
import { OfficerInfo } from './components/OfficerInfo';
import { PreparerSection } from './components/PreparerSection';
import { VehicleManagement } from './components/VehicleManagement';
import { TaxComputationTable } from './components/TaxComputationTable';
import { SignaturePayment } from './components/SignaturePayment';
import { AdminSubmissions } from './components/AdminSubmissions';
import { weightCategories } from './constants/formData';

// Re-export weightCategories for backward compatibility
export { weightCategories };

export default function Form2290() {
  // Debug the API base URL
  const isBrowser = typeof window !== 'undefined';
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : '';
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi;
  
  console.log("🔗 API_BASE:", API_BASE);

  const todayStr = new Date().toISOString().split('T')[0];

  // Use the custom hook for form management
  const {
    formData,
    setFormData,
    totalTax,
    captchaToken,
    setCaptchaToken,
    captchaError,
    setCaptchaError,
    addVehicle,
    removeVehicle,
    categoryData,
    grandTotals,
    totalVINs,
    lodgingCount,
    taxableVehiclesCount,
    suspendedCount,
    suspendedLoggingCount,
    suspendedNonLoggingCount,
  } = useForm2290();

  // Login UI states
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingEmail, setPendingEmail] = useState('');

  // CAPTCHA ref
  const captchaRef = useRef<ReCaptchaRef>(null);

  // Create form handler
  const handleChange = createFormHandler(formData, setFormData, todayStr);

  // CAPTCHA handlers
  const handleCaptchaChange = (token: string | null) => {
    setCaptchaToken(token);
    setCaptchaError('');
  };

  const handleCaptchaExpired = () => {
    setCaptchaToken(null);
    setCaptchaError('CAPTCHA expired. Please complete it again.');
  };

  const handleCaptchaError = () => {
    setCaptchaToken(null);
    setCaptchaError('CAPTCHA error. Please try again.');
  };

  // Create submission handler
  const handleSubmit = createSubmissionHandler(
    formData,
    totalTax,
    captchaToken,
    captchaRef,
    setCaptchaToken,
    categoryData,
    grandTotals,
    API_BASE
  );

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
          .vehicle-row button,
          .vehicle-row textarea {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 1rem;
          }
          .vehicle-row label {
            width: 100%;
            font-size: 1rem;
            margin-bottom: 8px;
          }
          .vehicle-row {
            margin-bottom: 18px !important;
          }
          .form-container input:not([type="checkbox"]),
          .form-container select,
          .form-container textarea {
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
          
          /* Enhanced vehicle sections on mobile */
          .vehicle-row > div {
            width: 100% !important;
          }
          
          .vehicle-row > div > div {
            flex-direction: column !important;
            gap: 8px !important;
          }
        }
      `}</style>
      <div className="form-container">
        {/* Login Modal for existing users */}
        {showLoginModal && (
          <LoginModal email={pendingEmail} onClose={() => setShowLoginModal(false)} />
        )}

        <BusinessInfo formData={formData} handleChange={handleChange} />
        
        <ReturnFlags formData={formData} handleChange={handleChange} />
        
        <OfficerInfo formData={formData} handleChange={handleChange} />
        
        <PreparerSection 
          formData={formData} 
          handleChange={handleChange} 
          todayStr={todayStr} 
        />

        <VehicleManagement 
          formData={formData}
          handleChange={handleChange}
          addVehicle={addVehicle}
          removeVehicle={removeVehicle}
        />

        <TaxComputationTable 
          categoryData={categoryData}
          grandTotals={grandTotals}
          totalVINs={totalVINs}
          formData={formData}
          suspendedLoggingCount={suspendedLoggingCount}
          suspendedNonLoggingCount={suspendedNonLoggingCount}
          taxableVehiclesCount={taxableVehiclesCount}
        />

        <SignaturePayment 
          formData={formData}
          handleChange={handleChange}
          todayStr={todayStr}
        />

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
              padding: '12px 24px',
              border: 'none',
              borderRadius: 4,
              backgroundColor: captchaToken ? '#28a745' : '#cccccc', 
              color: '#fff', 
              fontSize: '1.1rem',
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

        {/* Admin Section */}
        {auth.currentUser?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL && (
          <AdminSubmissions API_BASE={API_BASE} />
        )}
      </div>
    </>
  );
}
    used_on_july:      '202507',
    address_change:    false,
    amended_return:    false,
    vin_correction:    false,
    final_return:      false,
    
    // Amendment-related fields
    amended_month:     '',
    reasonable_cause_explanation: '',
    
    // VIN correction fields
    vin_correction_explanation: '',
    
    // Special conditions
    special_conditions: '',
    
    // Business Officer Information (required for signing)
    officer_name:      '', // Person who signs the return
    officer_title:     '', // Title (President, Owner, Manager, etc.)
    officer_ssn:       '', // Officer's Social Security Number (required by IRS)
    taxpayer_pin:      '', // 5-digit PIN for electronic signature
    tax_credits:       0,  // Tax credits to apply against liability
    
    // Enhanced disposals/credits
    has_disposals:     false,
    
    include_preparer:  false,
    preparer_name:           '',
    preparer_ptin:           '',
    preparer_self_employed:  true,
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
    
    // Enhanced payment fields
    eftps_routing:  '',
    eftps_account:  '',
    account_type:   '',
    payment_date:   '',
    taxpayer_phone: '',
    
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

  // IRS Partial-period tax tables (from official IRS Form 2290 instructions)
  // Regular vehicles (non-logging) - Table I
  const partialPeriodTaxRegular: Record<string, Record<number, number>> = {
    A: { 8: 91.67, 9: 83.33, 10: 75.00, 11: 66.67, 12: 58.33, 1: 50.00, 2: 41.67, 3: 33.33, 4: 25.00, 5: 16.67, 6: 8.33 },
    B: { 8: 111.83, 9: 101.67, 10: 91.50, 11: 81.33, 12: 71.17, 1: 61.00, 2: 50.83, 3: 40.67, 4: 30.50, 5: 20.33, 6: 10.17 },
    C: { 8: 132.00, 9: 120.00, 10: 108.00, 11: 96.00, 12: 84.00, 1: 72.00, 2: 60.00, 3: 48.00, 4: 36.00, 5: 24.00, 6: 12.00 },
    D: { 8: 152.17, 9: 138.33, 10: 124.50, 11: 110.67, 12: 96.83, 1: 83.00, 2: 69.17, 3: 55.33, 4: 41.50, 5: 27.67, 6: 13.83 },
    E: { 8: 172.33, 9: 156.67, 10: 141.00, 11: 125.33, 12: 109.67, 1: 94.00, 2: 78.33, 3: 62.67, 4: 47.00, 5: 31.33, 6: 15.67 },
    F: { 8: 192.50, 9: 175.00, 10: 157.50, 11: 140.00, 12: 122.50, 1: 105.00, 2: 87.50, 3: 70.00, 4: 52.50, 5: 35.00, 6: 17.50 },
    G: { 8: 212.67, 9: 193.33, 10: 174.00, 11: 154.67, 12: 135.33, 1: 116.00, 2: 96.67, 3: 77.33, 4: 58.00, 5: 38.67, 6: 19.33 },
    H: { 8: 232.83, 9: 211.67, 10: 190.50, 11: 169.33, 12: 148.17, 1: 127.00, 2: 105.83, 3: 84.67, 4: 63.50, 5: 42.33, 6: 21.17 },
    I: { 8: 253.00, 9: 230.00, 10: 207.00, 11: 184.00, 12: 161.00, 1: 138.00, 2: 115.00, 3: 92.00, 4: 69.00, 5: 46.00, 6: 23.00 },
    J: { 8: 273.17, 9: 248.33, 10: 223.50, 11: 198.67, 12: 173.83, 1: 149.00, 2: 124.17, 3: 99.33, 4: 74.50, 5: 49.67, 6: 24.83 },
    K: { 8: 293.33, 9: 266.67, 10: 240.00, 11: 213.33, 12: 186.67, 1: 160.00, 2: 133.33, 3: 106.67, 4: 80.00, 5: 53.33, 6: 26.67 },
    L: { 8: 313.50, 9: 285.00, 10: 256.50, 11: 228.00, 12: 199.50, 1: 171.00, 2: 142.50, 3: 114.00, 4: 85.50, 5: 57.00, 6: 28.50 },
    M: { 8: 333.67, 9: 303.33, 10: 273.00, 11: 242.67, 12: 212.33, 1: 182.00, 2: 151.67, 3: 121.33, 4: 91.00, 5: 60.67, 6: 30.33 },
    N: { 8: 353.83, 9: 321.67, 10: 289.50, 11: 257.33, 12: 225.17, 1: 193.00, 2: 160.83, 3: 128.67, 4: 96.50, 5: 64.33, 6: 32.17 },
    O: { 8: 374.00, 9: 340.00, 10: 306.00, 11: 272.00, 12: 238.00, 1: 204.00, 2: 170.00, 3: 136.00, 4: 102.00, 5: 68.00, 6: 34.00 },
    P: { 8: 394.17, 9: 358.33, 10: 322.50, 11: 286.67, 12: 250.83, 1: 215.00, 2: 179.17, 3: 143.33, 4: 107.50, 5: 71.67, 6: 35.83 },
    Q: { 8: 414.33, 9: 376.67, 10: 339.00, 11: 301.33, 12: 263.67, 1: 226.00, 2: 188.33, 3: 150.67, 4: 113.00, 5: 75.33, 6: 37.67 },
    R: { 8: 434.50, 9: 395.00, 10: 355.50, 11: 316.00, 12: 276.50, 1: 237.00, 2: 197.50, 3: 158.00, 4: 118.50, 5: 79.00, 6: 39.50 },
    S: { 8: 454.67, 9: 413.33, 10: 372.00, 11: 330.67, 12: 289.33, 1: 248.00, 2: 206.67, 3: 165.33, 4: 124.00, 5: 82.67, 6: 41.33 },
    T: { 8: 474.83, 9: 431.67, 10: 388.50, 11: 345.33, 12: 302.17, 1: 259.00, 2: 215.83, 3: 172.67, 4: 129.50, 5: 86.33, 6: 43.17 },
    U: { 8: 495.00, 9: 450.00, 10: 405.00, 11: 360.00, 12: 315.00, 1: 270.00, 2: 225.00, 3: 180.00, 4: 135.00, 5: 90.00, 6: 45.00 },
    V: { 8: 504.17, 9: 458.33, 10: 412.50, 11: 366.67, 12: 320.83, 1: 275.00, 2: 229.17, 3: 183.33, 4: 137.50, 5: 91.67, 6: 45.83 }
  }

  // Logging vehicles (reduced rates) - Table II  
  const partialPeriodTaxLogging: Record<string, Record<number, number>> = {
    A: { 8: 68.75, 9: 62.49, 10: 56.25, 11: 50.00, 12: 43.74, 1: 37.50, 2: 31.25, 3: 24.99, 4: 18.75, 5: 12.50, 6: 6.24 },
    B: { 8: 83.87, 9: 76.25, 10: 68.62, 11: 60.99, 12: 53.37, 1: 45.75, 2: 38.12, 3: 30.50, 4: 22.87, 5: 15.24, 6: 7.62 },
    C: { 8: 99.00, 9: 90.00, 10: 81.00, 11: 72.00, 12: 63.00, 1: 54.00, 2: 45.00, 3: 36.00, 4: 27.00, 5: 18.00, 6: 9.00 },
    D: { 8: 114.12, 9: 103.74, 10: 93.37, 11: 83.00, 12: 72.62, 1: 62.25, 2: 51.87, 3: 41.49, 4: 31.12, 5: 20.75, 6: 10.37 },
    E: { 8: 129.24, 9: 117.50, 10: 105.75, 11: 93.99, 12: 82.25, 1: 70.50, 2: 58.74, 3: 47.00, 4: 35.25, 5: 23.49, 6: 11.75 },
    F: { 8: 144.37, 9: 131.25, 10: 118.12, 11: 105.00, 12: 91.87, 1: 78.75, 2: 65.62, 3: 52.50, 4: 39.37, 5: 26.25, 6: 13.12 },
    G: { 8: 159.50, 9: 144.99, 10: 130.50, 11: 116.00, 12: 101.49, 1: 87.00, 2: 72.50, 3: 57.99, 4: 43.50, 5: 29.00, 6: 14.49 },
    H: { 8: 174.62, 9: 158.75, 10: 142.87, 11: 126.99, 12: 111.12, 1: 95.25, 2: 79.37, 3: 63.50, 4: 47.62, 5: 31.74, 6: 15.87 },
    I: { 8: 189.75, 9: 172.50, 10: 155.25, 11: 138.00, 12: 120.75, 1: 103.50, 2: 86.25, 3: 69.00, 4: 51.75, 5: 34.50, 6: 17.25 },
    J: { 8: 204.87, 9: 186.24, 10: 167.62, 11: 149.00, 12: 130.37, 1: 111.75, 2: 93.12, 3: 74.49, 4: 55.87, 5: 37.25, 6: 18.62 },
    K: { 8: 219.99, 9: 200.00, 10: 180.00, 11: 159.99, 12: 140.00, 1: 120.00, 2: 99.99, 3: 80.00, 4: 60.00, 5: 39.99, 6: 20.00 },
    L: { 8: 235.12, 9: 213.75, 10: 192.37, 11: 171.00, 12: 149.62, 1: 128.25, 2: 106.87, 3: 85.50, 4: 64.12, 5: 42.75, 6: 21.37 },
    M: { 8: 250.25, 9: 227.49, 10: 204.75, 11: 182.00, 12: 159.24, 1: 136.50, 2: 113.75, 3: 90.99, 4: 68.25, 5: 45.50, 6: 22.74 },
    N: { 8: 265.37, 9: 241.25, 10: 217.12, 11: 192.99, 12: 168.87, 1: 144.75, 2: 120.62, 3: 96.50, 4: 72.37, 5: 48.24, 6: 24.12 },
    O: { 8: 280.50, 9: 255.00, 10: 229.50, 11: 204.00, 12: 178.50, 1: 153.00, 2: 127.50, 3: 102.00, 4: 76.50, 5: 51.00, 6: 25.50 },
    P: { 8: 295.62, 9: 268.74, 10: 241.87, 11: 215.00, 12: 188.12, 1: 161.25, 2: 134.37, 3: 107.49, 4: 80.62, 5: 53.75, 6: 26.87 },
    Q: { 8: 310.74, 9: 282.50, 10: 254.25, 11: 225.99, 12: 197.75, 1: 169.50, 2: 141.24, 3: 113.00, 4: 84.75, 5: 56.49, 6: 28.25 },
    R: { 8: 325.87, 9: 296.25, 10: 266.62, 11: 237.00, 12: 207.37, 1: 177.75, 2: 148.12, 3: 118.50, 4: 88.87, 5: 59.25, 6: 29.62 },
    S: { 8: 341.00, 9: 309.99, 10: 279.00, 11: 248.00, 12: 216.99, 1: 186.00, 2: 155.00, 3: 123.99, 4: 93.00, 5: 62.00, 6: 30.99 },
    T: { 8: 356.12, 9: 323.75, 10: 291.37, 11: 258.99, 12: 226.62, 1: 194.25, 2: 161.87, 3: 129.50, 4: 97.12, 5: 64.74, 6: 32.37 },
    U: { 8: 371.25, 9: 337.50, 10: 303.75, 11: 270.00, 12: 236.25, 1: 202.50, 2: 168.75, 3: 135.00, 4: 101.25, 5: 67.50, 6: 33.75 },
    V: { 8: 378.12, 9: 343.74, 10: 309.37, 11: 275.00, 12: 240.62, 1: 206.25, 2: 171.87, 3: 137.49, 4: 103.12, 5: 68.75, 6: 34.37 }
  }

  useEffect(() => {
    let total = 0
    formData.vehicles.forEach(v => {
      const mon = parseInt(v.used_month.slice(-2), 10) || 0
      if (!mon || v.is_suspended || v.is_agricultural) return
      const catObj = weightCategories.find(w => w.value === v.category)
      if (!catObj) return
      
      // Use lookup tables for partial-period or annual rates
      let rate = 0
      if (mon === 7) {
        // Annual tax (July only)
        rate = v.is_logging ? loggingRates[v.category] : catObj.tax
      } else {
        // Partial-period tax (all months except July) - use lookup tables
        if (v.is_logging) {
          rate = partialPeriodTaxLogging[v.category]?.[mon] || 0
        } else {
          rate = partialPeriodTaxRegular[v.category]?.[mon] || 0
        }
      }
      
      total += rate
    })
    setTotalTax(total)
  }, [formData.vehicles])

  const handleChange = (e: ChangeEvent<HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement>) => {
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
          preparer_self_employed: true,
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
        
        // Handle mutually exclusive checkboxes and automatic category updates
        if (field === 'is_agricultural' && checked) {
          vv.is_suspended = false
          vv.mileage_5000_or_less = false
          vv.category = 'W'
        }
        if (field === 'is_suspended' && checked) {
          vv.is_agricultural = false
          vv.mileage_5000_or_less = false
          vv.category = 'W'
        }
        if (field === 'mileage_5000_or_less' && checked) {
          vv.is_agricultural = false
          vv.is_suspended = false
          vv.category = 'W'
          console.log(`Setting vehicle ${idx} category to W due to mileage_5000_or_less`)
        }
        
        // If all checkboxes are unchecked and category is W, reset category
        if (!vv.is_agricultural && !vv.is_suspended && !vv.mileage_5000_or_less && vv.category === 'W') {
          vv.category = ''
        }
      } else if (type === 'number') {
        vv[field] = value ? parseFloat(value) : undefined
      } else {
        vv[field] = value as any
        
        // Handle category dropdown changes - uncheck relevant checkboxes when category changes away from W
        if (field === 'category') {
          if (value !== 'W') {
            vv.is_agricultural = false
            vv.is_suspended = false
            vv.mileage_5000_or_less = false
          }
        }
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
    const finalValue = type === 'checkbox' ? checked : 
                      (type === 'number' && name === 'tax_credits') ? (value ? parseFloat(value) : 0) :
                      value;
    
    setFormData({
      ...formData,
      [name]: finalValue,
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
          // Initialize enhanced fields
          disposal_date: undefined,
          disposal_reason: undefined,
          disposal_amount: undefined,
          sale_to_private_party: false,
          tgw_increased: false,
          tgw_increase_month: undefined,
          tgw_previous_category: undefined,
          vin_corrected: false,
          vin_correction_reason: undefined,
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
  const taxableVehiclesCount = formData.vehicles.filter(v => {
    console.log(`Vehicle with VIN ${v.vin}: category='${v.category}', mileage_5000_or_less=${v.mileage_5000_or_less}, is_agricultural=${v.is_agricultural}, is_suspended=${v.is_suspended}`)
    return v.category !== 'W'
  }).length
  console.log(`Total taxable vehicles: ${taxableVehiclesCount}`)
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length
  const suspendedLoggingCount = formData.vehicles.filter(v => (v.is_suspended || v.is_agricultural) && v.is_logging).length
  const suspendedNonLoggingCount = formData.vehicles.filter(v => (v.is_suspended || v.is_agricultural) && !v.is_logging).length

  // Enhanced category-based calculations (similar to IRS Form 2290 Tax Computation table)
  const calculateCategoryCounts = () => {
    const categoryData: Record<string, {
      regularCount: number,
      loggingCount: number,
      regularTotalTax: number,
      loggingTotalTax: number,
      regularAnnualTax: number,
      loggingAnnualTax: number,
      regularPartialTax: number,
      loggingPartialTax: number,
      // Dynamic partial-period rates based on actual vehicle months
      partialPeriodRates: { regular: number, logging: number }
    }> = {}

    // Initialize all categories
    weightCategories.forEach(cat => {
      categoryData[cat.value] = {
        regularCount: 0,
        loggingCount: 0,
        regularTotalTax: 0,
        loggingTotalTax: 0,
        regularAnnualTax: 0,
        loggingAnnualTax: 0,
        regularPartialTax: 0,
        loggingPartialTax: 0,
        partialPeriodRates: { regular: 0, logging: 0 }
      }
    })

    // Calculate partial-period rates dynamically for each category
    // Based on the actual months of vehicles in that category
    weightCategories.forEach(cat => {
      // For category W, include all vehicles assigned to W regardless of agricultural/suspended status
      // For other categories, exclude agricultural and suspended vehicles
      const categoryVehicles = cat.value === 'W' 
        ? formData.vehicles.filter(v => v.category === cat.value)
        : formData.vehicles.filter(v => v.category === cat.value && !v.is_suspended && !v.is_agricultural)
      
      if (categoryVehicles.length > 0) {
        // Find partial-period vehicles in this category
        const partialPeriodVehicles = categoryVehicles.filter(v => {
          const mon = parseInt(v.used_month.slice(-2), 10)
          return mon && mon !== 7 // All months except July are partial-period
        })
        
        if (partialPeriodVehicles.length > 0) {
          // Use the earliest partial-period month for this category
          const partialPeriodMonths = partialPeriodVehicles.map(v => parseInt(v.used_month.slice(-2), 10))
          const representativeMonth = Math.min(...partialPeriodMonths)
          
          // Check if this category has regular vehicles with partial-period months
          const hasRegularPartial = partialPeriodVehicles.some(v => !v.is_logging)
          const hasLoggingPartial = partialPeriodVehicles.some(v => v.is_logging)
          
          // Only set rates for applicable vehicle types
          categoryData[cat.value].partialPeriodRates = {
            regular: hasRegularPartial ? (partialPeriodTaxRegular[cat.value]?.[representativeMonth] || 0) : 0,
            logging: hasLoggingPartial ? (partialPeriodTaxLogging[cat.value]?.[representativeMonth] || 0) : 0
          }
        } else {
          // No partial-period vehicles in this category
          categoryData[cat.value].partialPeriodRates = {
            regular: 0,
            logging: 0
          }
        }
      } else {
        // No vehicles in this category at all
        categoryData[cat.value].partialPeriodRates = {
          regular: 0,
          logging: 0
        }
      }
    })

    // Now process vehicles and calculate actual taxes using lookup tables
    formData.vehicles.forEach(v => {
      if (!v.category) return
      
      // For category W, include agricultural and suspended vehicles but don't calculate tax
      // For other categories, exclude agricultural and suspended vehicles
      if (v.category !== 'W' && (v.is_suspended || v.is_agricultural)) return
      
      const mon = parseInt(v.used_month.slice(-2), 10) || 0
      if (!mon) return

      const catObj = weightCategories.find(w => w.value === v.category)
      if (!catObj) return

      const isLogging = v.is_logging
      const isAnnualTax = mon === 7  // Only July = annual tax
      
      let taxAmount = 0
      // Category W (suspended/agricultural) always has $0 tax
      if (v.category === 'W') {
        taxAmount = 0
      } else if (isAnnualTax) {
        // Annual tax (July only)
        taxAmount = isLogging ? loggingRates[v.category] : catObj.tax
      } else {
        // Partial-period tax (all months except July) - use lookup tables
        if (isLogging) {
          taxAmount = partialPeriodTaxLogging[v.category]?.[mon] || 0
        } else {
          taxAmount = partialPeriodTaxRegular[v.category]?.[mon] || 0
        }
      }

      if (isLogging) {
        categoryData[v.category].loggingCount++
        categoryData[v.category].loggingTotalTax += taxAmount
        
        if (isAnnualTax) {
          categoryData[v.category].loggingAnnualTax += taxAmount
        } else {
          categoryData[v.category].loggingPartialTax += taxAmount
        }
      } else {
        categoryData[v.category].regularCount++
        categoryData[v.category].regularTotalTax += taxAmount
        
        if (isAnnualTax) {
          categoryData[v.category].regularAnnualTax += taxAmount
        } else {
          categoryData[v.category].regularPartialTax += taxAmount
        }
      }
    })

    return categoryData
  }

  const categoryData = calculateCategoryCounts()

  // Calculate grand totals
  const grandTotals = {
    regularVehicles: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularCount, 0),
    loggingVehicles: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingCount, 0),
    regularTotalTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularTotalTax, 0),
    loggingTotalTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingTotalTax, 0),
    regularAnnualTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularAnnualTax, 0),
    loggingAnnualTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingAnnualTax, 0),
    regularPartialTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularPartialTax, 0),
    loggingPartialTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingPartialTax, 0)
  }

  const validateBeforeSubmit = (): string | null => {
    // CAPTCHA validation first
    if (!captchaToken) return 'Please complete the CAPTCHA verification'
    
    if (!formData.business_name.trim()) return 'Business Name is required'
    if (!/^\d{2}-\d{7}$/.test(formData.ein)) return 'EIN must be 9 digits in format XX-XXXXXXX'
    
    // IRS Business Rule: EIN cannot be all 9s (R0000-021)
    const einDigitsOnly = formData.ein.replace(/-/g, '');
    if (einDigitsOnly === '999999999') return 'EIN cannot be all 9s'
    
    // Address length validation (IRS requirement: max 35 chars per line)
    if (formData.address.length > 35) return 'Address line 1 cannot exceed 35 characters'
    if (formData.address_line2 && formData.address_line2.length > 35) return 'Address line 2 cannot exceed 35 characters'
    
    // Business officer information validation
    if (!formData.officer_name.trim()) return 'Officer name is required for signing'
    if (!formData.officer_title.trim()) return 'Officer title is required (e.g., President, Owner, Manager)'
    if (!/^\d{3}-?\d{2}-?\d{4}$/.test(formData.officer_ssn)) return 'Officer SSN must be in format XXX-XX-XXXX or XXXXXXXXX'
    if (!/^\d{5}$/.test(formData.taxpayer_pin)) return 'Taxpayer PIN must be exactly 5 digits'
    
    // IRS Business Rule: Taxpayer PIN cannot be all zeros (R0000-031, R0000-084-01)
    if (formData.taxpayer_pin === '00000') return 'Taxpayer PIN cannot be all zeros'
    
    // Tax credits validation (if provided)
    const taxCreditsValue = typeof formData.tax_credits === 'number' ? formData.tax_credits : parseFloat(formData.tax_credits) || 0;
    if (taxCreditsValue < 0) return 'Tax credits cannot be negative'
    
    // IRS Business Rule F2290-004-01: Credits cannot exceed total tax
    if (taxCreditsValue > totalTax) return 'Tax credits cannot exceed total tax amount'
    
    // Amendment validation
    if (formData.amended_return && !formData.amended_month) {
      return 'Month being amended is required for amended returns'
    }
    
    // IRS Business Rule F2290-003-01: TGW increase requires amended return
    const hasTGWIncrease = formData.vehicles.some(v => v.tgw_increased)
    if (hasTGWIncrease && !formData.amended_return) {
      return 'Amended return must be checked when any vehicle has weight category increase'
    }
    
    // VIN correction validation
    if (formData.vin_correction && !formData.vin_correction_explanation.trim()) {
      return 'VIN correction explanation is required'
    }
    
    // IRS Business Rule F2290-032-01: VIN correction requires at least one VIN
    if (formData.vin_correction && formData.vehicles.length === 0) {
      return 'At least one vehicle is required when VIN correction is checked'
    }
    
    // IRS Business Rule F2290-033-01: Amended return requires at least one VIN
    if (formData.amended_return && formData.vehicles.length === 0) {
      return 'At least one vehicle is required for amended returns'
    }
    
    // IRS Business Rule F2290-027-01: Non-final returns require at least one VIN
    if (!formData.final_return && formData.vehicles.length === 0) {
      return 'At least one vehicle is required unless this is a final return'
    }
    
    if (formData.include_preparer) {
      if (!formData.preparer_name.trim())      return 'Preparer Name is required'
      if (!formData.preparer_ptin.trim())      return 'Preparer PTIN is required'
      if (!formData.date_prepared)             return 'Date Prepared is required'
      if (!formData.preparer_firm_name.trim()) return 'Firm Name is required'
      if (!/^\d{2}-\d{7}$/.test(formData.preparer_firm_ein)) return 'Firm EIN must be 9 digits in format XX-XXXXXXX'
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
      if (!/^\d{9}$/.test(formData.eftps_routing)) return 'Routing number must be 9 digits'
      if (!formData.eftps_account.trim()) return 'Account number is required'
      if (!formData.account_type) return 'Account type is required'
      if (!formData.payment_date) return 'Payment date is required'
      if (!/^\d{10}$/.test(formData.taxpayer_phone)) return 'Taxpayer phone must be 10 digits'
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
      
      // Enhanced vehicle validation
      if (v.disposal_date && !v.disposal_reason) {
        return `Disposal reason is required for vehicle #${idx + 1}`
      }
      if (v.tgw_increased && (!v.tgw_increase_month || !v.tgw_previous_category)) {
        return `Weight increase details are required for vehicle #${idx + 1}`
      }
      if (v.vin_corrected && !v.vin_correction_reason?.trim()) {
        return `VIN correction reason is required for vehicle #${idx + 1}`
      }
      
      // IRS Business Rule: Category W vehicles must select either agricultural or non-agricultural
      if (v.category === 'W' && !v.is_agricultural && !v.mileage_5000_or_less) {
        return `Vehicle #${idx + 1} (Category W) must select either "Agricultural ≤7,500 mi" or "Non-Agricultural ≤5,000 mi"`
      }
    }
    
    // IRS Business Rule F2290-017: VIN duplicate validation
    const vins = formData.vehicles.map(v => v.vin.trim().toUpperCase()).filter(vin => vin)
    const uniqueVINs = new Set(vins)
    if (vins.length !== uniqueVINs.size) {
      return 'Duplicate VINs are not allowed - each vehicle must have a unique VIN'
    }
    
    // IRS Business Rule F2290-008-01: 5000 mile limit requires Category W
    const has5000MileVehicles = formData.vehicles.some(v => v.mileage_5000_or_less)
    const hasCategoryW = formData.vehicles.some(v => v.category === 'W')
    if (has5000MileVehicles && !hasCategoryW) {
      return 'When 5000 mile limit is used, at least one vehicle must be Category W (Suspended)'
    }
    
    // IRS Business Rule F2290-068: Payment method required when balance due > 0
    const balanceDue = Math.max(0, totalTax - (typeof formData.tax_credits === 'number' ? formData.tax_credits : parseFloat(formData.tax_credits) || 0))
    if (balanceDue > 0 && !formData.payEFTPS && !formData.payCard) {
      return 'Payment method (EFTPS or Credit/Debit Card) is required when balance is due'
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
      // Include the calculated category data from frontend
      const totalTax = grandTotals.regularTotalTax + grandTotals.loggingTotalTax;
      const additionalTax = 0.00; // Placeholder for future implementation
      const totalTaxWithAdditional = totalTax + additionalTax;
      const credits = typeof formData.tax_credits === 'number' ? formData.tax_credits : parseFloat(formData.tax_credits) || 0;
      const balanceDue = Math.max(0, totalTaxWithAdditional - credits);
      
      const submissionData = {
        ...formData,
        // Ensure numeric fields are properly converted
        tax_credits: credits,
        count_w_suspended_logging: formData.vehicles.filter(v => (v.is_agricultural || v.mileage_5000_or_less) && v.is_logging).length,
        count_w_suspended_non_logging: formData.vehicles.filter(v => (v.is_agricultural || v.mileage_5000_or_less) && !v.is_logging).length,
        captchaToken: captchaToken,
        // Add the calculated category data and totals
        categoryData: categoryData,
        grandTotals: grandTotals,
        // Add Part I tax summary values (matching form_positions.json field names)
        partI: {
          line2_tax: totalTax,                    // Line 2: Tax (from Schedule 1, line c.)
          line3_increase: additionalTax,          // Line 3: Additional tax (attach explanation)
          line4_total: totalTaxWithAdditional,    // Line 4: Total tax (add lines 2 and 3)
          line5_credits: credits,                 // Line 5: Credits
          line6_balance: balanceDue               // Line 6: Balance due (subtract line 5 from line 4)
        }
      };
      
      console.log("🚗 Form data being sent:", JSON.stringify(submissionData, null, 2)); // Debug line
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
        body: JSON.stringify(submissionData),
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
        console.log("📋 JSON response received:", jsonData);
        
        // Use the simplified message from the backend
        const message = jsonData.redirect_message || "Visit My Filings section to see your files.";
        alert(`✅ ${jsonData.message || "Form submitted successfully"} - ${message}`);
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
          .vehicle-row button,
          .vehicle-row textarea {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 1rem;
          }
          .vehicle-row label {
            width: 100%;
            font-size: 1rem;
            margin-bottom: 8px;
          }
          .vehicle-row {
            margin-bottom: 18px !important;
          }
          .form-container input:not([type="checkbox"]),
          .form-container select,
          .form-container textarea {
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
          
          /* Enhanced vehicle sections on mobile */
          .vehicle-row > div {
            width: 100% !important;
          }
          
          .vehicle-row > div > div {
            flex-direction: column !important;
            gap: 8px !important;
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
            placeholder="EIN (XX-XXXXXXX)"
            value={formData.ein}
            onChange={(e) => {
              // Auto-format EIN with hyphen
              let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
              if (value.length >= 2) {
                value = value.substring(0, 2) + '-' + value.substring(2, 9);
              }
              // Update the form data
              const syntheticEvent = {
                ...e,
                target: { ...e.target, name: 'ein', value: value }
              };
              handleChange(syntheticEvent as any);
            }}
            pattern="\d{2}-\d{7}"
            maxLength={10}
            inputMode="numeric"
            title="9 digits in format XX-XXXXXXX"
            required
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
            <label key={flag} style={{ 
              ...labelSmall, 
              cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer',
              opacity: flag === 'amended_return' ? 0.5 : 1
            }}>
              <input 
                type="checkbox" 
                name={flag} 
                checked={(formData as any)[flag]} 
                onChange={handleChange}
                disabled={flag === 'amended_return'}
                style={{ 
                  cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer'
                }}
              />
              <span style={{ 
                cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer'
              }}>
                {flag.replace(/_/g,' ')}
                {flag === 'amended_return' && ' (Coming Soon)'}
              </span>
            </label>
          ))}
        </div>

        {/* Amended Return Details */}
        {formData.amended_return && (
          <div style={{ marginTop: 20, padding: 16, border: '1px solid #ffc107', borderRadius: 4, backgroundColor: '#fff3cd' }}>
            <h3>📝 Amended Return Details</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select 
                name="amended_month" 
                value={formData.amended_month || ''} 
                onChange={handleChange}
                required
              >
                <option value="">Select Month Being Amended</option>
                {months.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
              <textarea
                name="reasonable_cause_explanation"
                placeholder="Explain reason for amendment (if late filing or other reasonable cause)"
                value={formData.reasonable_cause_explanation || ''}
                onChange={handleChange}
                rows={3}
                style={{ minWidth: '300px', resize: 'vertical' }}
              />
            </div>
          </div>
        )}

        {/* VIN Correction Details */}
        {formData.vin_correction && (
          <div style={{ marginTop: 20, padding: 16, border: '1px solid #17a2b8', borderRadius: 4, backgroundColor: '#d1ecf1' }}>
            <h3>🔧 VIN Correction Explanation</h3>
            <textarea
              name="vin_correction_explanation"
              placeholder="Explain the VIN corrections being made (include old and new VINs if applicable)..."
              value={formData.vin_correction_explanation || ''}
              onChange={handleChange}
              rows={4}
              required
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>
        )}

        {/* Special Conditions */}
        <h2 style={{ marginTop: 20 }}>Special Conditions (Optional)</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <textarea
            name="special_conditions"
            placeholder="Describe any special conditions that apply to this return..."
            value={formData.special_conditions || ''}
            onChange={handleChange}
            rows={2}
            style={{ minWidth: '400px', resize: 'vertical' }}
          />
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
            name="officer_ssn" 
            placeholder="Officer SSN (XXX-XX-XXXX)" 
            value={formData.officer_ssn} 
            onChange={(e) => {
              // Auto-format SSN with hyphens
              let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
              if (value.length >= 3) {
                value = value.substring(0, 3) + '-' + value.substring(3);
              }
              if (value.length >= 6) {
                value = value.substring(0, 6) + '-' + value.substring(6, 10);
              }
              // Update the form data
              const syntheticEvent = {
                ...e,
                target: { ...e.target, name: 'officer_ssn', value: value }
              };
              handleChange(syntheticEvent as any);
            }}
            pattern="\d{3}-\d{2}-\d{4}"
            maxLength={11}
            required
            title="Social Security Number of the officer signing the return (format: XXX-XX-XXXX)"
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
        <h2 style={{ marginTop: 20 }}>Tax Credits & Disposals</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input 
            name="tax_credits" 
            type="number"
            min="0"
            step="0.01"
            placeholder="Tax Credits Amount"
            value={formData.tax_credits === 0 ? '' : formData.tax_credits.toString()} 
            onChange={handleChange}
            onWheel={(e) => e.currentTarget.blur()}
            title="Amount of tax credits to apply against tax liability"
          />
          <label style={{ ...labelSmall, cursor: 'pointer' }}>
            <input
              type="checkbox"
              name="has_disposals"
              checked={formData.has_disposals || false}
              onChange={handleChange}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ cursor: 'pointer' }}>Include Vehicle Disposals/Sales</span>
          </label>
          <span style={{ fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>
            Enter any tax credits and mark vehicles disposed below
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
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
              <label style={labelSmall}>
                <input
                  type="checkbox"
                  name="preparer_self_employed"
                  checked={formData.preparer_self_employed}
                  onChange={handleChange}
                />
                <span style={{ cursor: 'pointer' }}>Self Employed</span>
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <input name="preparer_firm_name" placeholder="Firm Name" value={formData.preparer_firm_name} onChange={handleChange} required />
              <input
                name="preparer_firm_ein"
                placeholder="Firm EIN (XX-XXXXXXX)"
                value={formData.preparer_firm_ein}
                onChange={(e) => {
                  // Auto-format EIN with hyphen
                  let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
                  if (value.length >= 2) {
                    value = value.substring(0, 2) + '-' + value.substring(2, 9);
                  }
                  // Update the form data
                  const syntheticEvent = {
                    ...e,
                    target: { ...e.target, name: 'preparer_firm_ein', value: value }
                  };
                  handleChange(syntheticEvent as any);
                }}
                pattern="\d{2}-\d{7}"
                maxLength={10}
                inputMode="numeric"
                title="9 digits in format XX-XXXXXXX"
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
          <div key={i} className="vehicle-row" style={{ 
            display: 'flex', 
            gap: 8, 
            alignItems: 'flex-start', 
            marginBottom: 16,
            padding: 12,
            border: '1px solid #ddd',
            borderRadius: 4,
            backgroundColor: v.is_suspended || v.is_agricultural ? '#f8f9fa' : 'white',
            flexWrap: 'wrap'
          }}>
            {/* Basic vehicle info - top row */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: '100%', marginBottom: 8 }}>
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
                style={{ minWidth: 150 }}
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
                style={{ minWidth: 180 }}
              >
                <option value="">Select Weight</option>
                {weightCategories.map((w) => (
                  <option key={w.value} value={w.value}>{w.label}</option>
                ))}
              </select>
              <button
                type="button"
                style={{ ...btnSmall, backgroundColor: '#d32f2f', color: '#fff' }}
                onClick={() => removeVehicle(i)}
              >
                Remove
              </button>
            </div>

            {/* Checkboxes - second row */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', width: '100%', marginBottom: 8 }}>
              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_is_logging`} 
                  checked={v.is_logging} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Logging Vehicle</span>
              </label>
              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_is_agricultural`} 
                  checked={v.is_agricultural} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Agricultural ≤7,500 mi</span>
              </label>
              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_mileage_5000_or_less`} 
                  checked={v.mileage_5000_or_less} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Non-Agricultural ≤5,000 mi</span>
              </label>
            </div>

            {/* Advanced options - expandable section */}
            <div style={{ width: '100%', borderTop: '1px solid #eee', paddingTop: 8 }}>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                <label style={{ ...labelSmall, cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    name={`vehicle_${i}_disposal_date`} 
                    checked={!!v.disposal_date} 
                    onChange={(e) => {
                      const vehicles = [...formData.vehicles];
                      vehicles[i] = {
                        ...vehicles[i],
                        disposal_date: e.target.checked ? todayStr : undefined,
                        disposal_reason: e.target.checked ? vehicles[i].disposal_reason : undefined,
                        disposal_amount: e.target.checked ? vehicles[i].disposal_amount : undefined
                      };
                      setFormData({ ...formData, vehicles });
                    }}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ cursor: 'pointer' }}>Vehicle Disposed/Sold</span>
                </label>

                <label style={{ 
                  ...labelSmall, 
                  cursor: 'not-allowed',
                  opacity: 0.5
                }}>
                  <input 
                    type="checkbox" 
                    name={`vehicle_${i}_tgw_increased`} 
                    checked={v.tgw_increased || false} 
                    onChange={handleChange}
                    disabled
                    style={{ cursor: 'not-allowed' }}
                  />
                  <span style={{ cursor: 'not-allowed' }}>Weight Category Increased (Coming Soon)</span>
                </label>

                <label style={{ ...labelSmall, cursor: 'pointer', display: 'none' }}>
                  <input 
                    type="checkbox" 
                    name={`vehicle_${i}_is_suspended`} 
                    checked={v.is_suspended || false} 
                    onChange={handleChange}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ cursor: 'pointer' }}>Suspended Vehicle</span>
                </label>

                <label style={{ ...labelSmall, cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    name={`vehicle_${i}_vin_corrected`} 
                    checked={v.vin_corrected || false} 
                    onChange={handleChange}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ cursor: 'pointer' }}>VIN Corrected</span>
                </label>

                <label style={{ ...labelSmall, cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    name={`vehicle_${i}_sale_to_private_party`} 
                    checked={v.sale_to_private_party || false} 
                    onChange={handleChange}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ cursor: 'pointer' }}>Sold to Private Party</span>
                </label>
              </div>

              {/* Disposal details */}
              {v.disposal_date && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#fff3cd', borderRadius: 4 }}>
                  <input
                    type="date"
                    name={`vehicle_${i}_disposal_date`}
                    value={v.disposal_date || ''}
                    onChange={handleChange}
                    max={todayStr}
                    placeholder="Disposal Date"
                    required
                  />
                  <select
                    name={`vehicle_${i}_disposal_reason`}
                    value={v.disposal_reason || ''}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Disposal Reason</option>
                    <option value="Sold">Sold</option>
                    <option value="Destroyed">Destroyed</option>
                    <option value="Stolen">Stolen</option>
                    <option value="Transferred">Transferred</option>
                    <option value="Traded">Traded</option>
                  </select>
                  <input
                    type="number"
                    name={`vehicle_${i}_disposal_amount`}
                    placeholder="Disposal Amount ($)"
                    min="0"
                    step="0.01"
                    value={v.disposal_amount || ''}
                    onChange={handleChange}
                    onWheel={(e) => e.currentTarget.blur()}
                  />
                </div>
              )}

              {/* Weight increase details */}
              {v.tgw_increased && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#d1ecf1', borderRadius: 4 }}>
                  <select
                    name={`vehicle_${i}_tgw_increase_month`}
                    value={v.tgw_increase_month || ''}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Month Weight Increased</option>
                    {months.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                  <select
                    name={`vehicle_${i}_tgw_previous_category`}
                    value={v.tgw_previous_category || ''}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Previous Weight Category</option>
                    {weightCategories.filter(w => w.value !== 'W').map((w) => (
                      <option key={w.value} value={w.value}>{w.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* VIN correction details */}
              {v.vin_corrected && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#f8d7da', borderRadius: 4 }}>
                  <input
                    name={`vehicle_${i}_vin_correction_reason`}
                    placeholder="Explain the VIN correction..."
                    value={v.vin_correction_reason || ''}
                    onChange={handleChange}
                    style={{ minWidth: '300px' }}
                    required
                  />
                </div>
              )}
            </div>
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
        </div>

        {/* Tax Computation Table (Similar to IRS Form 2290 Page 2) */}
        <div style={{ 
          background: '#f9f9f9', 
          border: '2px solid #333', 
          borderRadius: '8px', 
          padding: '16px',
          marginTop: '20px',
          marginBottom: '20px'
        }}>
          <h3 style={{ textAlign: 'center', margin: '0 0 16px 0', color: '#333' }}>
            Tax Computation by Category
          </h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ 
              width: '100%', 
              borderCollapse: 'collapse',
              fontSize: '0.9rem',
              background: 'white'
            }}>
              <thead>
                <tr style={{ background: '#e9ecef' }}>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                    Category
                  </th>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                    Taxable Gross Weight<br/>(in pounds)
                  </th>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                    (1) Annual Tax<br/>(vehicles first used during July)
                  </th>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                    (2) Partial-period Tax<br/>(vehicles first used after July)<br/>See tables at end of instructions
                  </th>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                    (3) Number of Vehicles
                  </th>
                  <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                    (4) Amount of Tax<br/>(col. (1) or (2) multiplied by col. (3))
                  </th>
                </tr>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem' }}></th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem' }}></th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (a) Vehicles<br/>except logging*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (b) Logging<br/>vehicles*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (a) Vehicles<br/>except logging*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (b) Logging<br/>vehicles*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (a) Vehicles<br/>except logging*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    (b) Logging<br/>vehicles*
                  </th>
                  <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                    Amount of Tax
                  </th>
                </tr>
              </thead>
              <tbody>
                {weightCategories.filter(cat => {
                  // Only show categories that have vehicles (including W if there are vehicles)
                  const data = categoryData[cat.value];
                  return data.regularCount > 0 || data.loggingCount > 0;
                }).map((cat) => {
                  const data = categoryData[cat.value];
                  const hasData = data.regularCount > 0 || data.loggingCount > 0;
                  
                  return (
                    <tr key={cat.value} style={{ 
                      background: cat.value === 'W' ? '#f8d7da' : '#fff3cd',  // Special styling for category W
                      opacity: 1
                    }}>
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                        {cat.value}
                      </td>
                      <td style={{ border: '1px solid #333', padding: '6px', fontSize: '0.8rem' }}>
                        {cat.value === 'W' ? 'Tax-Suspended Vehicles' : (cat.label.match(/\((.*?)\)/)?.[1] || cat.label)}
                      </td>
                      {/* Annual Tax Rates */}
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                        {cat.value === 'W' ? 'No tax due' : `$${cat.tax.toFixed(2)}`}
                      </td>
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                        {cat.value === 'W' ? 'No tax due' : `$${(loggingRates[cat.value] || 0).toFixed(2)}`}
                      </td>
                      {/* Partial Tax Rates - only show if there are partial-period vehicles in this category */}
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                        {cat.value === 'W' ? 'No tax due' : (data.partialPeriodRates.regular > 0 ? `$${data.partialPeriodRates.regular.toFixed(2)}` : '')}
                      </td>
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                        {cat.value === 'W' ? 'No tax due' : (data.partialPeriodRates.logging > 0 ? `$${data.partialPeriodRates.logging.toFixed(2)}` : '')}
                      </td>
                      {/* Vehicle Counts */}
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                        {data.regularCount || ''}
                      </td>
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                        {data.loggingCount || ''}
                      </td>
                      {/* Total Tax Amount */}
                      <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                        {cat.value === 'W' ? '$0.00' : ((data.regularTotalTax + data.loggingTotalTax) > 0 ? `$${(data.regularTotalTax + data.loggingTotalTax).toFixed(2)}` : '')}
                      </td>
                    </tr>
                  );
                })}
                
                {/* Totals Row */}
                <tr style={{ background: '#d4edda', fontWeight: 'bold' }}>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                    <strong>TOTALS</strong>
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                    -
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                    -
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center', fontSize: '0.9rem' }}>
                    (See individual rows)
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center', fontSize: '0.9rem' }}>
                    (See individual rows)
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                    {grandTotals.regularVehicles}
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                    {grandTotals.loggingVehicles}
                  </td>
                  <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                    ${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}
                  </td>
                </tr>
                
              </tbody>
            </table>
          </div>

          {/* Part I Tax Summary Section */}
          <div style={{ marginTop: '16px', padding: '12px', background: '#e9ecef', borderRadius: '4px' }}>
            <h4 style={{ margin: '0 0 12px 0', color: '#333' }}>Part I - Tax Summary</h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', fontSize: '0.95rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
                <span>1. Total number of vehicles reported (from Schedule 1)</span>
                <strong>{totalVINs}</strong>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
                <span>2. Tax (from Schedule 1, line c.)</span>
                <strong>${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}</strong>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
                <span>3. Additional tax (attach explanation)</span>
                <strong>$0.00</strong>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '2px solid #333' }}>
                <span><strong>4. Total tax (add lines 2 and 3)</strong></span>
                <strong>${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}</strong>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
                <span>5. Credits</span>
                <strong>${(typeof formData.tax_credits === 'number' ? formData.tax_credits : parseFloat(formData.tax_credits) || 0).toFixed(2)}</strong>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '2px solid #333', background: '#fff3cd' }}>
                <span><strong>6. Balance due (subtract line 5 from line 4)</strong></span>
                <strong>${Math.max(0, (grandTotals.regularTotalTax + grandTotals.loggingTotalTax) - (typeof formData.tax_credits === 'number' ? formData.tax_credits : parseFloat(formData.tax_credits) || 0)).toFixed(2)}</strong>
              </div>
            </div>
            
            {/* Quick Stats */}
            <div style={{ marginTop: '12px', padding: '8px', background: 'white', borderRadius: '4px' }}>
              <h5 style={{ margin: '0 0 8px 0', color: '#333' }}>Vehicle Summary:</h5>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '6px', fontSize: '0.85rem' }}>
                <div>🪵 <strong>Logging Vehicles:</strong> {grandTotals.loggingVehicles}</div>
                <div>🚫 <strong>Suspended (Logging):</strong> {suspendedLoggingCount}</div>
                <div>🚫 <strong>Suspended (Non-Logging):</strong> {suspendedNonLoggingCount}</div>
                <div>🎯 <strong>Taxable Vehicles:</strong> {taxableVehiclesCount}</div>
              </div>
            </div>
            
            {/* Tax Breakdown */}
            {(grandTotals.regularAnnualTax > 0 || grandTotals.loggingAnnualTax > 0 || grandTotals.regularPartialTax > 0 || grandTotals.loggingPartialTax > 0) && (
              <div style={{ marginTop: '8px', padding: '8px', background: 'white', borderRadius: '4px' }}>
                <h5 style={{ margin: '0 0 8px 0', color: '#333' }}>Tax Breakdown:</h5>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '6px', fontSize: '0.8rem' }}>
                  {grandTotals.regularAnnualTax > 0 && (
                    <div>🗓️ Annual (Regular): ${grandTotals.regularAnnualTax.toFixed(2)}</div>
                  )}
                  {grandTotals.loggingAnnualTax > 0 && (
                    <div>🗓️ Annual (Logging): ${grandTotals.loggingAnnualTax.toFixed(2)}</div>
                  )}
                  {grandTotals.regularPartialTax > 0 && (
                    <div>📅 Partial (Regular): ${grandTotals.regularPartialTax.toFixed(2)}</div>
                  )}
                  {grandTotals.loggingPartialTax > 0 && (
                    <div>📅 Partial (Logging): ${grandTotals.loggingPartialTax.toFixed(2)}</div>
                  )}
                </div>
              </div>
            )}
          </div>
          
          <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '8px', fontStyle: 'italic' }}>
            * Logging vehicles are vehicles used for logging purposes and qualify for reduced tax rates.
          </div>
        </div>

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
            <input 
              name="eftps_routing" 
              placeholder="Routing Number (9 digits)" 
              pattern="\d{9}"
              maxLength={9}
              inputMode="numeric"
              value={formData.eftps_routing} 
              onChange={handleChange} 
              required
            />
            <input 
              name="eftps_account" 
              placeholder="Account Number" 
              value={formData.eftps_account} 
              onChange={handleChange} 
              required
            />
            <select
              name="account_type"
              value={formData.account_type || ''}
              onChange={handleChange}
              required
            >
              <option value="">Account Type</option>
              <option value="Checking">Checking</option>
              <option value="Savings">Savings</option>
            </select>
            <input
              name="payment_date"
              type="date"
              min={todayStr}
              value={formData.payment_date || ''}
              onChange={handleChange}
              title="Requested payment date"
              required
            />
            <input
              name="taxpayer_phone"
              placeholder="Daytime Phone (10 digits)"
              pattern="\d{10}"
              maxLength={10}
              inputMode="numeric"
              value={formData.taxpayer_phone || ''}
              onChange={handleChange}
              required
            />
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