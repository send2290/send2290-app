"use client";
import { useState, useRef, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { auth } from '../../lib/firebase';
import ReCaptchaComponent, { ReCaptchaRef } from '../components/ReCaptcha';
import PaymentModal from '../components/PaymentModal';
import FormPreviewModal from '../components/FormPreviewModal';
import { TaxComputationTable } from '../components/TaxComputationTable';
import { SignaturePayment } from '../components/SignaturePayment';
import { createSubmissionHandler } from '../utils/submissionHandler';
import { calculateDisposalCredit } from '../utils/formUtils';
import { FormData, CategoryData, GrandTotals } from '../types/form';

export default function FilePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Set up API base URL
  const isBrowser = typeof window !== 'undefined';
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : '';
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi;
  
  // State for localhost detection
  const [isLocalhost, setIsLocalhost] = useState(false);
  
  // Payment state
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null);
  
  // CAPTCHA state
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState('');
  const [validationError, setValidationError] = useState('');
  const captchaRef = useRef<ReCaptchaRef>(null);
  
  // Form data from URL params or localStorage
  const [formData, setFormData] = useState<FormData | null>(null);
  const [categoryData, setCategoryData] = useState<Record<string, CategoryData>>({});
  const [grandTotals, setGrandTotals] = useState<GrandTotals>({
    regularVehicles: 0,
    loggingVehicles: 0,
    regularTotalTax: 0,
    loggingTotalTax: 0,
    regularAnnualTax: 0,
    loggingAnnualTax: 0,
    regularPartialTax: 0,
    loggingPartialTax: 0
  });
  const [totalVINs, setTotalVINs] = useState(0);
  const [totalDisposalCredits, setTotalDisposalCredits] = useState(0);
  const [totalTax, setTotalTax] = useState(0);
  const [taxableVehiclesCount, setTaxableVehiclesCount] = useState(0);
  const [suspendedLoggingCount, setSuspendedLoggingCount] = useState(0);
  const [suspendedNonLoggingCount, setSuspendedNonLoggingCount] = useState(0);
  
  const todayStr = new Date().toISOString().split('T')[0];
  const filingFee = 45.00;
  
  // Check if we're on localhost after component mounts
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      setIsLocalhost(hostname === 'localhost' || hostname === '127.0.0.1');
    }
  }, []);
  
  // Load form data from localStorage or URL params
  useEffect(() => {
    try {
      const storedData = localStorage.getItem('form2290Data');
      if (storedData) {
        const data = JSON.parse(storedData);
        setFormData(data.formData);
        setCategoryData(data.categoryData || {});
        setGrandTotals(data.grandTotals || {
          regularVehicles: 0,
          loggingVehicles: 0,
          regularTotalTax: 0,
          loggingTotalTax: 0,
          regularAnnualTax: 0,
          loggingAnnualTax: 0,
          regularPartialTax: 0,
          loggingPartialTax: 0
        });
        setTotalVINs(data.totalVINs || 0);
        setTotalTax(data.totalTax || 0);
        setTaxableVehiclesCount(data.taxableVehiclesCount || 0);
        setSuspendedLoggingCount(data.suspendedLoggingCount || 0);
        setSuspendedNonLoggingCount(data.suspendedNonLoggingCount || 0);
        
        // Recalculate disposal credits from vehicle data
        if (data.formData && data.formData.vehicles) {
          console.log('All vehicles from localStorage:', data.formData.vehicles);
          
          // First, ensure all vehicles with disposal dates have calculated disposal_credit
          const vehiclesWithCredits = data.formData.vehicles.map((vehicle: any) => {
            if (vehicle.disposal_date && !vehicle.disposal_credit) {
              const credit = calculateDisposalCredit(vehicle, vehicle.disposal_date);
              console.log(`Recalculating disposal credit for vehicle ${vehicle.vin}: $${credit}`);
              return { ...vehicle, disposal_credit: credit };
            }
            return vehicle;
          });
          
          // Update form data with recalculated credits
          setFormData(prev => prev ? { ...prev, vehicles: vehiclesWithCredits } : prev);
          
          const calculatedDisposalCredits = vehiclesWithCredits.reduce((sum: number, vehicle: any) => {
            console.log('Vehicle disposal credit check:', {
              vin: vehicle.vin,
              disposal_credit: vehicle.disposal_credit,
              disposal_date: vehicle.disposal_date,
              category: vehicle.category,
              used_month: vehicle.used_month
            });
            return sum + (vehicle.disposal_credit || 0);
          }, 0);
          console.log('Total calculated disposal credits:', calculatedDisposalCredits);
          console.log('Stored totalDisposalCredits from localStorage:', data.totalDisposalCredits);
          
          // Use the higher of calculated vs stored to ensure we don't lose credits
          const finalDisposalCredits = Math.max(calculatedDisposalCredits, data.totalDisposalCredits || 0);
          setTotalDisposalCredits(finalDisposalCredits);
          
          // Save the updated data back to localStorage
          const updatedDataToSave = {
            ...data,
            formData: { ...data.formData, vehicles: vehiclesWithCredits },
            totalDisposalCredits: finalDisposalCredits
          };
          localStorage.setItem('form2290Data', JSON.stringify(updatedDataToSave));
        } else {
          console.log('No vehicle data found, using stored value:', data.totalDisposalCredits);
          setTotalDisposalCredits(data.totalDisposalCredits || 0);
        }
      } else {
        // If no data found, redirect back to form
        router.push('/');
      }
    } catch (error) {
      console.error('Error loading form data:', error);
      router.push('/');
    }
  }, [router]);
  
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
  
  // Payment handlers
  const handlePaymentRequired = (onPaymentSuccess: (paymentIntentId: string) => void) => {
    setShowPaymentModal(true);
    // Store the success callback for later use
    (window as any).pendingPaymentCallback = onPaymentSuccess;
  };

  const handlePaymentSuccess = (newPaymentIntentId: string) => {
    setPaymentIntentId(newPaymentIntentId);
    setShowPaymentModal(false);
    
    // Call the pending callback if it exists
    const callback = (window as any).pendingPaymentCallback;
    if (callback) {
      callback(newPaymentIntentId);
      delete (window as any).pendingPaymentCallback;
    }
  };

  const handlePaymentCancel = () => {
    setShowPaymentModal(false);
    setIsSubmitting(false);
    delete (window as any).pendingPaymentCallback;
  };
  
  // Form change handler for signature/payment section
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    if (!formData) return;
    
    // Clear validation error when user makes changes (preserve form data)
    setValidationError('');
    
    const { name, value, type } = e.target;
    const newValue = type === 'checkbox' ? (e.target as HTMLInputElement).checked : value;
    
    setFormData(prev => {
      if (!prev) return prev;
      const updatedData = { ...prev, [name]: newValue };
      
      // Auto-save the updated form data to localStorage
      const dataToSave = {
        formData: updatedData,
        categoryData,
        grandTotals,
        totalVINs,
        totalDisposalCredits,
        totalTax,
        taxableVehiclesCount,
        suspendedLoggingCount,
        suspendedNonLoggingCount
      };
      localStorage.setItem('form2290Data', JSON.stringify(dataToSave));
      
      return updatedData;
    });
  };
  
  // Create submission handler
  const handleSubmit = async () => {
    if (!formData) return;
    
    // Simple validation for filing page (only signature and payment fields)
    let validationErrorMsg = '';
    
    // Validate signature and printed name
    if (!formData.signature.trim()) {
      validationErrorMsg = 'Signature is required';
    } else if (!formData.printed_name.trim()) {
      validationErrorMsg = 'Printed name is required';
    } 
    // Validate payment method selection
    else if (!formData.payEFTPS && !formData.payCard) {
      validationErrorMsg = 'Please select a payment method (EFTPS or Credit/Debit Card)';
    }
    // Validate EFTPS fields if EFTPS is selected
    else if (formData.payEFTPS) {
      if (!formData.eftps_routing || !/^\d{9}$/.test(formData.eftps_routing)) {
        validationErrorMsg = 'Valid 9-digit routing number is required for EFTPS';
      } else if (!formData.eftps_account.trim()) {
        validationErrorMsg = 'Account number is required for EFTPS';
      } else if (!formData.account_type) {
        validationErrorMsg = 'Account type is required for EFTPS';
      } else if (!formData.payment_date) {
        validationErrorMsg = 'Payment date is required for EFTPS';
      } else if (!formData.taxpayer_phone || !/^\d{10}$/.test(formData.taxpayer_phone)) {
        validationErrorMsg = 'Valid 10-digit phone number is required for EFTPS';
      }
    }
    // Validate CAPTCHA
    else if (!captchaToken) {
      const isLocalhost = typeof window !== 'undefined' && 
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
      if (!isLocalhost) {
        validationErrorMsg = 'Please complete the CAPTCHA verification';
      }
    }
    
    if (validationErrorMsg) {
      setValidationError(validationErrorMsg);
      
      // IMPORTANT: Make sure form data is preserved even with validation errors
      const dataToSave = {
        formData,
        categoryData,
        grandTotals,
        totalVINs,
        totalDisposalCredits,
        totalTax,
        taxableVehiclesCount,
        suspendedLoggingCount,
        suspendedNonLoggingCount
      };
      localStorage.setItem('form2290Data', JSON.stringify(dataToSave));
      
      return; // Stop here and don't proceed with submission
    }
    
    // Clear validation error only when validation passes
    setValidationError('');
    
    setIsSubmitting(true);
    try {
      // Create the submission handler but don't let it do its own validation
      const submitForm = createSubmissionHandler(
        formData,
        totalTax,
        totalDisposalCredits,
        captchaToken,
        captchaRef,
        setCaptchaToken,
        categoryData,
        grandTotals,
        API_BASE,
        handlePaymentRequired
      );
      
      await submitForm(paymentIntentId || undefined);
      // Clear stored data after successful submission
      localStorage.removeItem('form2290Data');
    } catch (error: any) {
      console.error('Submission error:', error);
      setValidationError(error?.message || 'Submission failed. Please try again.');
      
      // Preserve form data even when submission fails
      const dataToSave = {
        formData,
        categoryData,
        grandTotals,
        totalVINs,
        totalDisposalCredits,
        totalTax,
        taxableVehiclesCount,
        suspendedLoggingCount,
        suspendedNonLoggingCount
      };
      localStorage.setItem('form2290Data', JSON.stringify(dataToSave));
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleBackToForm = () => {
    router.push('/');
  };
  
  if (!formData) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Loading form data...</p>
      </div>
    );
  }

  return (
    <>
      <style>{`
        .file-container {
          max-width: 900px;
          width: 100%;
          margin: 0 auto;
          padding: 20px;
          font-family: 'Segoe UI', sans-serif;
        }
        
        .summary-section {
          background: #f8f9fa;
          border: 2px solid #007bff;
          border-radius: 8px;
          padding: 20px;
          margin: 20px 0;
        }
        
        .fee-breakdown {
          background: white;
          border: 1px solid #ddd;
          border-radius: 6px;
          padding: 16px;
          margin: 16px 0;
        }
        
        .fee-line {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid #eee;
        }
        
        .fee-line:last-child {
          border-bottom: none;
          font-weight: bold;
          font-size: 1.1rem;
          color: #007bff;
        }
        
        .back-button {
          background: #6c757d;
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 4px;
          cursor: pointer;
          margin-right: 12px;
        }
        
        .back-button:hover {
          background: #5a6268;
        }
        
        @media (max-width: 600px) {
          .file-container {
            padding: 8px;
          }
          
          .fee-line {
            flex-direction: column;
            gap: 4px;
          }
          
          .submit-actions {
            flex-direction: column;
          }
          
          .submit-actions button {
            min-width: unset !important;
            width: 100%;
          }
        }
      `}</style>
      
      <div className="file-container">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
          <button 
            type="button" 
            className="back-button"
            onClick={handleBackToForm}
          >
            ← Back to Form
          </button>
          <h1 style={{ margin: 0, flex: 1, textAlign: 'center' }}>
            Review & File Form 2290
          </h1>
        </div>
        
        {/* Tax Computation Table */}
        <TaxComputationTable 
          categoryData={categoryData}
          grandTotals={grandTotals}
          totalVINs={totalVINs}
          formData={formData}
          suspendedLoggingCount={suspendedLoggingCount}
          suspendedNonLoggingCount={suspendedNonLoggingCount}
          taxableVehiclesCount={taxableVehiclesCount}
          totalDisposalCredits={totalDisposalCredits}
        />
        
        {/* Filing Fee Summary */}
        <div className="summary-section">
          <h3 style={{ margin: '0 0 16px 0', textAlign: 'center', color: '#007bff' }}>
            Filing Summary
          </h3>
          
          <div className="fee-breakdown">
            <div className="fee-line">
              <span>Tax Due:</span>
              <span>${totalTax.toFixed(2)}</span>
            </div>
            {totalDisposalCredits > 0 && (
              <div className="fee-line">
                <span>Disposal Credits:</span>
                <span>-${totalDisposalCredits.toFixed(2)}</span>
              </div>
            )}
            <div className="fee-line">
              <span>Filing Fee:</span>
              <span>${filingFee.toFixed(2)}</span>
            </div>
            <div className="fee-line">
              <span>Total Amount:</span>
              <span>${(Math.max(0, totalTax - totalDisposalCredits) + filingFee).toFixed(2)}</span>
            </div>
          </div>
          
          <div style={{ 
            background: '#e3f2fd', 
            padding: '12px', 
            borderRadius: '4px',
            fontSize: '0.9rem',
            color: '#1565c0'
          }}>
            <strong>Note:</strong> The $45.00 filing fee covers electronic submission to the IRS. 
            Your tax payment will be processed separately during submission.
            {/* Debug info - remove in production */}
            <div style={{ marginTop: '8px', fontSize: '0.8rem', opacity: 0.7 }}>
              Debug: Tax=${totalTax.toFixed(2)}, Credits=${totalDisposalCredits.toFixed(2)}, 
              Net Tax=${Math.max(0, totalTax - totalDisposalCredits).toFixed(2)}
              <br />
              Vehicles with disposal: {formData?.vehicles?.filter(v => v.disposal_date).length || 0}
              <br />
              Vehicle disposal details: {JSON.stringify(formData?.vehicles?.map(v => ({
                vin: v.vin.slice(-4),
                hasDisposal: !!v.disposal_date,
                credit: v.disposal_credit || 0
              })) || [])}
            </div>
          </div>
        </div>
        
        {/* Signature Section */}
        <SignaturePayment 
          formData={formData}
          handleChange={handleChange}
          todayStr={todayStr}
        />

        {/* CAPTCHA Section */}
        <h2 style={{ marginTop: 20 }}>Security Verification</h2>
        <div style={{ marginTop: 12 }}>
          {process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY && !isLocalhost ? (
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
              color: '#2e7d32', 
              padding: '12px', 
              backgroundColor: '#e8f5e8', 
              border: '1px solid #2e7d32', 
              borderRadius: '4px',
              fontSize: '0.9rem'
            }}>
              ℹ️ reCAPTCHA is disabled for localhost development. In production, set NEXT_PUBLIC_RECAPTCHA_SITE_KEY.
              <div style={{ marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => setCaptchaToken('dev-bypass-token')}
                  style={{
                    padding: '6px 12px',
                    background: '#4caf50',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '0.85rem'
                  }}
                >
                  Enable Submission (Dev Mode)
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Submit Actions */}
        <div className="submit-actions" style={{ marginTop: 20, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {validationError && (
            <div style={{
              width: '100%',
              padding: '12px',
              background: '#f8d7da',
              border: '1px solid #f5c6cb',
              borderRadius: '4px',
              color: '#721c24',
              marginBottom: '12px'
            }}>
              ⚠️ {validationError}
            </div>
          )}
          
          <button
            type="button"
            style={{ 
              padding: '12px 24px',
              border: '1px solid #007bff',
              borderRadius: 4,
              backgroundColor: '#fff', 
              color: '#007bff', 
              fontSize: '1rem',
              cursor: 'pointer',
              fontWeight: '500',
              transition: 'all 0.2s',
              minWidth: '200px'
            }}
            onClick={() => setShowPreviewModal(true)}
            onMouseOver={(e) => {
              e.currentTarget.style.backgroundColor = '#f8f9fa';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.backgroundColor = '#fff';
            }}
          >
            📄 Preview Form 2290
          </button>
          
          <button
            type="button"
            style={{ 
              padding: '12px 24px',
              border: 'none',
              borderRadius: 4,
              backgroundColor: (captchaToken && !isSubmitting) ? '#28a745' : '#cccccc', 
              color: '#fff', 
              fontSize: '1.1rem',
              cursor: (captchaToken && !isSubmitting) ? 'pointer' : 'not-allowed',
              opacity: (captchaToken && !isSubmitting) ? 1 : 0.6,
              flex: '1',
              minWidth: '200px'
            }}
            onClick={handleSubmit}
            disabled={!captchaToken || isSubmitting}
          >
            {isSubmitting ? 'Processing...' : `SUBMIT FORM 2290 ($${(Math.max(0, totalTax - totalDisposalCredits) + filingFee).toFixed(2)})`}
          </button>
          
          {!captchaToken && (
            <div style={{ 
              alignSelf: 'center',
              color: '#666', 
              fontSize: '0.85rem',
              fontStyle: 'italic',
              flex: '1',
              minWidth: '200px'
            }}>
              Complete CAPTCHA to enable submission
            </div>
          )}
        </div>
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        onPaymentSuccess={handlePaymentSuccess}
        onCancel={handlePaymentCancel}
        isSubmitting={isSubmitting}
      />

      {/* Preview Modal */}
      <FormPreviewModal
        isOpen={showPreviewModal}
        onClose={() => setShowPreviewModal(false)}
        formData={formData}
        categoryData={categoryData}
        grandTotals={grandTotals}
        totalVINs={totalVINs}
        totalDisposalCredits={totalDisposalCredits}
        totalTax={totalTax}
        taxableVehiclesCount={taxableVehiclesCount}
        suspendedLoggingCount={suspendedLoggingCount}
        suspendedNonLoggingCount={suspendedNonLoggingCount}
      />
    </>
  );
}
