"use client";
import { useState, useRef, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { auth } from '../../lib/firebase';
import { onAuthStateChanged, User } from 'firebase/auth';
import { checkUserExists, createUserAndSendPassword } from '../../lib/authUtils';
import ReCaptchaComponent, { ReCaptchaRef } from '../components/ReCaptcha';
import PaymentModal from '../components/PaymentModal';
import { TaxComputationTable } from '../components/TaxComputationTable';
import { SignaturePayment } from '../components/SignaturePayment';
import { createSubmissionHandler } from '../utils/submissionHandler';
import { calculateDisposalCredit } from '../utils/formUtils';
import { FormData, CategoryData, GrandTotals } from '../types/form';

export default function FilePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Authentication state
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  
  // Check if current user is admin
  const isAdmin = user?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL;
  
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
  
  // Authentication effect
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setAuthLoading(false);
    });
    
    return () => unsubscribe();
  }, []);
  
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
          // First, ensure all vehicles with disposal dates have calculated disposal_credit
          const vehiclesWithCredits = data.formData.vehicles.map((vehicle: any) => {
            if (vehicle.disposal_date && !vehicle.disposal_credit) {
              const credit = calculateDisposalCredit(vehicle, vehicle.disposal_date);
              return { ...vehicle, disposal_credit: credit };
            }
            return vehicle;
          });
          
          // Update form data with recalculated credits
          setFormData(prev => prev ? { ...prev, vehicles: vehiclesWithCredits } : prev);
          
          const calculatedDisposalCredits = vehiclesWithCredits.reduce((sum: number, vehicle: any) => {
            return sum + (vehicle.disposal_credit || 0);
          }, 0);
          
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

  // Preview handler - directly opens payment modal
  const handlePreviewClick = () => {
    if (!formData) return;
    
    // Check authentication first
    if (authLoading) {
      setValidationError('Please wait for authentication to complete');
      return;
    }
    
    if (!user) {
      setValidationError('Please sign in to preview the form');
      return;
    }
    
    // Clear any existing errors
    setValidationError('');
    
    // Set up payment callback to generate preview after payment
    const onPaymentSuccess = async (paymentIntentId: string) => {
      try {
        setIsSubmitting(true);
        
        // Prepare the data payload
        const previewData = {
          ...formData,
          categoryData,
          grandTotals,
          totalVINs,
          totalDisposalCredits,
          totalTax,
          taxableVehiclesCount,
          suspendedLoggingCount,
          suspendedNonLoggingCount,
          payment_intent_id: paymentIntentId
        };

        // Get auth token
        const token = await user.getIdToken();

        // Make request to preview endpoint
        const response = await fetch(`${API_BASE}/preview-pdf`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(previewData)
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to generate preview');
        }

        // Check if response is JSON (multiple files) or PDF (single file)
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
          // Multiple files response
          const result = await response.json();
          
          if (result.multiple_files && result.files) {
            // Handle multiple files - download each one
            for (const file of result.files) {
              // Download each file separately
              const fileResponse = await fetch(`${API_BASE}${file.download_url}`, {
                method: 'GET',
                headers: {
                  'Authorization': `Bearer ${token}`
                }
              });
              
              if (fileResponse.ok) {
                const blob = await fileResponse.blob();
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = file.filename;
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
              }
            }
            
            // Show success message via alert
            alert(`✅ Successfully generated ${result.files.length} paid preview PDF(s) for different months.`);
          }
        } else {
          // Single file response - download the PDF directly
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `form2290_paid_preview.pdf`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);

          // Optionally open in new tab for viewing
          const viewUrl = window.URL.createObjectURL(blob);
          window.open(viewUrl, '_blank');
          
          // Show success message via alert
          alert('✅ Paid preview PDF generated successfully!');
        }

      } catch (err: any) {
        console.error('Preview generation error:', err);
        setValidationError(err.message || 'Failed to generate preview');
      } finally {
        setIsSubmitting(false);
      }
    };
    
    // Open payment modal with preview callback
    handlePaymentRequired(onPaymentSuccess);
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
    
    // Check authentication first
    if (authLoading) {
      setValidationError('Please wait for authentication to complete');
      return;
    }
    
    // Simple validation for filing page (only signature and payment fields)
    let validationErrorMsg = '';
    
    // Validate email if user is not logged in
    if (!user) {
      if (!formData.email || !formData.email.trim()) {
        validationErrorMsg = 'Email address is required';
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
        validationErrorMsg = 'Please enter a valid email address';
      }
    }
    // Validate signature and printed name
    else if (!formData.signature.trim()) {
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

  // Show loading state while checking authentication
  if (authLoading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Checking authentication...</p>
      </div>
    );
  }

  return (
    <>
      <div className="file-container">
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          marginBottom: '20px',
          padding: '16px',
          background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
          borderRadius: '8px',
          color: '#495057',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)',
          border: '1px solid #dee2e6'
        }}>
          <button 
            type="button" 
            className="back-button"
            onClick={handleBackToForm}
            style={{
              padding: '8px 14px',
              background: '#6c757d',
              border: '1px solid #5a6268',
              borderRadius: '6px',
              color: 'white',
              cursor: 'pointer',
              fontSize: '0.9rem',
              fontWeight: '500',
              transition: 'all 0.2s ease'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = '#5a6268';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = '#6c757d';
            }}
          >
            ← Back to Form
          </button>
          <h1 style={{ 
            margin: '0', 
            flex: '1', 
            textAlign: 'center',
            fontSize: '1.5rem',
            fontWeight: '600',
            color: '#495057'
          }}>
            📋 Review & File Form 2290
          </h1>
        </div>
        
        {/* Tax Computation Table - Only show for admin */}
        {isAdmin && (
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
        )}
        
        {/* Filing Fee Summary */}
        <div className="summary-section" style={{ 
          background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '16px',
          border: '1px solid #dee2e6',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
        }}>
          <h3 style={{ 
            margin: '0 0 12px 0', 
            textAlign: 'center', 
            color: '#495057',
            fontSize: '1.25rem',
            fontWeight: '600'
          }}>
            📊 Filing Summary
          </h3>
          
          <div className="fee-breakdown" style={{ 
            display: 'grid',
            gap: '8px',
            fontSize: '0.9rem'
          }}>
            <div className="fee-line" style={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              padding: '6px 0',
              borderBottom: '1px solid rgba(73, 80, 87, 0.1)'
            }}>
              <span style={{ fontWeight: '500' }}>Total Vehicles:</span>
              <span style={{ fontWeight: '600', color: '#495057' }}>{totalVINs}</span>
            </div>
            <div className="fee-line" style={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              padding: '6px 0',
              borderBottom: '1px solid rgba(73, 80, 87, 0.1)'
            }}>
              <span style={{ fontWeight: '500' }}>Taxable Vehicles:</span>
              <span style={{ fontWeight: '600', color: '#495057' }}>{taxableVehiclesCount}</span>
            </div>
            <div className="fee-line" style={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              padding: '6px 0',
              borderBottom: '1px solid rgba(73, 80, 87, 0.1)'
            }}>
              <span style={{ fontWeight: '500' }}>Tax Due:</span>
              <span style={{ fontWeight: '600', color: '#495057' }}>${totalTax.toFixed(2)}</span>
            </div>
            {totalDisposalCredits > 0 && (
              <div className="fee-line" style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: '1px solid rgba(73, 80, 87, 0.1)'
              }}>
                <span style={{ fontWeight: '500' }}>Disposal Credits:</span>
                <span style={{ fontWeight: '600', color: '#dc3545' }}>-${totalDisposalCredits.toFixed(2)}</span>
              </div>
            )}
            <div className="fee-line" style={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              padding: '6px 0',
              borderBottom: '1px solid rgba(73, 80, 87, 0.1)'
            }}>
              <span style={{ fontWeight: '500' }}>Filing Fee:</span>
              <span style={{ fontWeight: '600', color: '#495057' }}>${filingFee.toFixed(2)}</span>
            </div>
            <div className="fee-line" style={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              padding: '10px 8px',
              fontSize: '1rem',
              backgroundColor: 'rgba(73, 80, 87, 0.05)',
              marginTop: '6px',
              borderRadius: '6px',
              border: '1px solid rgba(73, 80, 87, 0.1)'
            }}>
              <span style={{ fontWeight: '700' }}>Total Amount:</span>
              <span style={{ fontWeight: '700', color: '#495057' }}>${(Math.max(0, totalTax - totalDisposalCredits) + filingFee).toFixed(2)}</span>
            </div>
          </div>
          
          <div style={{ 
            background: '#e3f2fd', 
            padding: '12px', 
            borderRadius: '6px',
            fontSize: '0.85rem',
            color: '#1565c0',
            marginTop: '12px',
            border: '1px solid #bbdefb'
          }}>
            <strong>Note:</strong> The $45.00 filing fee covers electronic submission to the IRS. 
            Your tax payment will be processed separately during submission.
          </div>
        </div>
        
        {/* Signature Section */}
        <SignaturePayment 
          formData={formData}
          handleChange={handleChange}
          todayStr={todayStr}
        />

        {/* CAPTCHA Section */}
        <div style={{ 
          background: '#f8f9fa',
          border: '1px solid #e9ecef',
          borderRadius: '6px',
          padding: '16px',
          marginBottom: '16px'
        }}>
          <h2 style={{ 
            marginBottom: '12px',
            color: '#495057',
            fontSize: '1.2rem',
            fontWeight: '600'
          }}>
            🔒 Security Verification
          </h2>
          <div>
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
                    fontSize: '0.95rem', 
                    marginTop: '12px',
                    fontWeight: '500',
                    padding: '8px 12px',
                    backgroundColor: '#ffebee',
                    borderRadius: '6px',
                    border: '1px solid #ef5350'
                  }}>
                    ⚠️ {captchaError}
                  </div>
                )}
                {!captchaToken && (
                  <div style={{ 
                    color: '#666', 
                    fontSize: '0.9rem', 
                    marginTop: '8px',
                    fontStyle: 'italic',
                    padding: '8px 12px',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '6px'
                  }}>
                    Please complete the CAPTCHA verification above to submit your form.
                  </div>
                )}
              </>
            ) : (
              <div style={{ 
                color: '#2e7d32', 
                padding: '16px', 
                backgroundColor: '#e8f5e8', 
                border: '1px solid #4caf50', 
                borderRadius: '8px',
                fontSize: '0.95rem'
              }}>
                ℹ️ reCAPTCHA is disabled for localhost development. In production, set NEXT_PUBLIC_RECAPTCHA_SITE_KEY.
                <div style={{ marginTop: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setCaptchaToken('dev-bypass-token')}
                    style={{
                      padding: '8px 16px',
                      background: '#4caf50',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      fontWeight: '500',
                      transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.backgroundColor = '#45a049';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.backgroundColor = '#4caf50';
                    }}
                  >
                    Enable Submission (Dev Mode)
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Submit Actions */}
        <div className="submit-actions" style={{ 
          marginTop: '16px', 
          display: 'flex', 
          gap: '12px', 
          flexWrap: 'wrap',
          alignItems: 'center' 
        }}>
          
          {/* Authentication Status */}
          {!authLoading && (
            <div style={{
              width: '100%',
              padding: '10px 12px',
              background: user ? '#d4edda' : '#fff3cd',
              border: `1px solid ${user ? '#c3e6cb' : '#ffeaa7'}`,
              borderRadius: '6px',
              color: user ? '#155724' : '#856404',
              fontSize: '0.85rem',
              marginBottom: '10px',
              fontWeight: '500'
            }}>
              🔐 {user ? `Signed in as: ${user.email}` : 'Authentication required - account will be created automatically during submission'}
            </div>
          )}
          
          {validationError && (
            <div style={{
              width: '100%',
              padding: '12px 14px',
              background: '#f8d7da',
              border: '1px solid #f5c6cb',
              borderRadius: '6px',
              color: '#721c24',
              marginBottom: '12px',
              fontSize: '0.85rem',
              fontWeight: '500'
            }}>
              ⚠️ {validationError}
            </div>
          )}
          
          <button
            type="button"
            style={{ 
              padding: '12px 20px',
              border: '2px solid #007bff',
              borderRadius: '6px',
              backgroundColor: '#fff', 
              color: '#007bff', 
              fontSize: '0.9rem',
              cursor: 'pointer',
              fontWeight: '600',
              transition: 'all 0.2s ease',
              minWidth: '200px',
              boxShadow: '0 1px 3px rgba(0, 123, 255, 0.1)'
            }}
            onClick={handlePreviewClick}
            onMouseOver={(e) => {
              e.currentTarget.style.backgroundColor = '#f8f9fa';
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 2px 6px rgba(0, 123, 255, 0.15)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.backgroundColor = '#fff';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 123, 255, 0.1)';
            }}
          >
            📄 Pay & Preview Form 2290 ($45.00)
          </button>
          
          <button
            type="button"
            style={{ 
              padding: '12px 20px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: (!authLoading && captchaToken && !isSubmitting) ? '#28a745' : '#cccccc', 
              color: '#fff', 
              fontSize: '1rem',
              cursor: (!authLoading && captchaToken && !isSubmitting) ? 'pointer' : 'not-allowed',
              opacity: (!authLoading && captchaToken && !isSubmitting) ? 1 : 0.6,
              flex: '1',
              minWidth: '200px',
              fontWeight: '600',
              transition: 'all 0.2s ease',
              boxShadow: (!authLoading && captchaToken && !isSubmitting) ? '0 1px 3px rgba(40, 167, 69, 0.2)' : 'none'
            }}
            onClick={handleSubmit}
            disabled={authLoading || !captchaToken || isSubmitting}
            onMouseOver={(e) => {
              if (!authLoading && captchaToken && !isSubmitting) {
                e.currentTarget.style.backgroundColor = '#218838';
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(40, 167, 69, 0.3)';
              }
            }}
            onMouseOut={(e) => {
              if (!authLoading && captchaToken && !isSubmitting) {
                e.currentTarget.style.backgroundColor = '#28a745';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(40, 167, 69, 0.2)';
              }
            }}
          >
            {isSubmitting ? '⏳ Processing...' : 
             authLoading ? '🔍 Checking Authentication...' :
             `🚀 SUBMIT FORM 2290 ($${(Math.max(0, totalTax - totalDisposalCredits) + filingFee).toFixed(2)})`}
          </button>
          
          {(!captchaToken || authLoading) && (
            <div style={{ 
              alignSelf: 'center',
              color: '#666', 
              fontSize: '0.8rem',
              fontStyle: 'italic',
              flex: '1',
              minWidth: '180px',
              textAlign: 'center',
              padding: '6px 10px',
              backgroundColor: '#f8f9fa',
              borderRadius: '4px',
              border: '1px solid #e9ecef'
            }}>
              {authLoading ? '🔍 Checking authentication...' : '🔒 Complete CAPTCHA to enable submission'}
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
    </>
  );
}
