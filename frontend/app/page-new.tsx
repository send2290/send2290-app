"use client";
import { useState, useRef } from 'react';
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
