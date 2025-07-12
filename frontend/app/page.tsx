"use client";
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '../lib/firebase';
import LoginModal from './LoginModal';
import { useForm2290 } from './hooks/useForm2290';
import { createFormHandler } from './utils/formHandlers';
import { calculateDisposalCredit, validateMainPageBeforeProceeding } from './utils/formUtils';
import { BusinessInfo } from './components/BusinessInfo';
import { ReturnFlags } from './components/ReturnFlags';
import { OfficerInfo } from './components/OfficerInfo';
import { PreparerSection } from './components/PreparerSection';
import { VehicleManagement } from './components/VehicleManagement';
import { weightCategories } from './constants/formData';

// Re-export weightCategories for backward compatibility
export { weightCategories };

export default function Form2290() {
  const router = useRouter();
  
  // Set up API base URL
  const isBrowser = typeof window !== 'undefined';
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : '';
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi;
    // State for localhost detection to avoid hydration issues
  const [isLocalhost, setIsLocalhost] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(true);

  // Check if we're on localhost after component mounts
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      setIsLocalhost(hostname === 'localhost' || hostname === '127.0.0.1');
    }
  }, []);

  const todayStr = new Date().toISOString().split('T')[0];

  // Use the custom hook for form management
  const {
    formData,
    setFormData,
    totalTax,
    totalDisposalCredits,
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

  // Load saved form data from localStorage after hook is initialized
  useEffect(() => {
    try {
      const storedData = localStorage.getItem('form2290Data');
      if (storedData) {
        const data = JSON.parse(storedData);
        if (data.formData) {
          // Recalculate disposal credits for vehicles that have disposal dates but no credits
          const formDataWithCredits = {
            ...data.formData,
            vehicles: data.formData.vehicles.map((vehicle: any) => {
              if (vehicle.disposal_date && vehicle.disposal_credit === undefined) {
                const credit = calculateDisposalCredit(vehicle, vehicle.disposal_date);
                return {
                  ...vehicle,
                  disposal_credit: credit
                };
              }
              return vehicle;
            })
          };
          
          // Restore the form data
          setFormData(formDataWithCredits);
        }
      }
    } catch (error) {
      console.error('Error loading saved form data:', error);
    } finally {
      setIsLoadingData(false);
    }
  }, [setFormData]);

  // Auto-save form data whenever it changes (but not while loading)
  useEffect(() => {
    if (!isLoadingData && formData && (formData.business_name || formData.ein || formData.vehicles.length > 0)) {
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
    }
  }, [isLoadingData, formData, categoryData, grandTotals, totalVINs, totalDisposalCredits, totalTax, taxableVehiclesCount, suspendedLoggingCount, suspendedNonLoggingCount]);

  // Login UI states
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingEmail, setPendingEmail] = useState('');

  // Create form handler
  const handleChange = createFormHandler(formData, setFormData, todayStr);

  // Handle proceeding to filing page
  const handleProceedToFiling = () => {
    // Use the main page validation function that only validates fields available on this page
    const validationError = validateMainPageBeforeProceeding(formData);
    
    if (validationError) {
      alert(`Please fix the following issue before proceeding:\n\n${validationError}`);
      return;
    }
    
    // Validate email if user is not logged in
    if (!auth.currentUser) {
      if (!formData.email || !formData.email.trim()) {
        alert('Email address is required to proceed to filing. Please enter your email address.');
        return;
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
        alert('Please enter a valid email address.');
        return;
      }
    }
    
    // Save form data to localStorage (auto-save should handle this, but ensure it's saved)
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
    
    // Navigate to filing page
    router.push('/file');
  };

  // Handle clearing saved data
  const handleClearData = () => {
    if (confirm('Are you sure you want to clear all form data? This action cannot be undone.')) {
      localStorage.removeItem('form2290Data');
      window.location.reload(); // Reload to reset form
    }
  };

  return (
    <>
      <style>{`
        .form-container {
          max-width: 1000px;
          width: 100%;
          margin: 0 auto;
          padding: 24px 12px 12px 12px;
          /* Added extra top padding for better spacing from navigation */
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
          background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
          min-height: 100vh;
        }
        
        /* Section styling */
        .form-container > div:not(.ready-to-file) {
          background: white;
          border-radius: 6px;
          padding: 12px;
          margin-bottom: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 1px rgba(0, 0, 0, 0.1);
          border: 1px solid rgba(0, 0, 0, 0.05);
          transition: box-shadow 0.2s ease-in-out;
        }
        
        .form-container > div:hover:not(.ready-to-file) {
          box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1), 0 3px 6px rgba(0, 0, 0, 0.08);
        }
        
        /* Headings */
        .form-container h2 {
          color: #2c3e50;
          font-size: 1.1rem;
          font-weight: 600;
          margin: 0 0 8px 0;
          padding-bottom: 4px;
          border-bottom: 2px solid #007bff;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        
        .form-container h3 {
          color: #34495e;
          font-size: 0.9rem;
          font-weight: 500;
          margin: 6px 0 4px 0;
        }
        
        /* Form inputs */
        .form-container input:not([type="checkbox"]):not([type="radio"]),
        .form-container textarea {
          padding: 6px 8px;
          border: 1px solid #e1e8ed;
          border-radius: 4px;
          font-size: 0.75rem;
          transition: all 0.2s ease-in-out;
          background: white;
          color: #2c3e50;
          font-family: inherit;
          line-height: 1.2;
          height: 32px;
          box-sizing: border-box;
          min-height: 32px;
          max-height: 32px;
        }
        
        /* Default select styling - 32px for most selects */
        .form-container select {
          padding: 6px 8px;
          border: 1px solid #e1e8ed;
          border-radius: 4px;
          font-size: 0.75rem;
          transition: all 0.2s ease-in-out;
          background: white;
          color: #2c3e50;
          font-family: inherit;
          line-height: 1.2;
          height: 32px;
          box-sizing: border-box;
          min-height: 32px;
          max-height: 32px;
        }
        
        /* Vehicle select styling - 38px for better text visibility */
        .vehicle-row select {
          height: 38px !important;
          min-height: 38px !important;
          max-height: 38px !important;
          padding: 8px 8px !important;
          line-height: 1.4 !important;
        }
        
        /* Special handling for textarea to allow multiple lines */
        .form-container textarea {
          height: auto;
          min-height: 32px;
          max-height: none;
          resize: vertical;
          font-size: 0.8rem;
        }
        
        .form-container input:not([type="checkbox"]):not([type="radio"]):focus,
        .form-container select:focus,
        .form-container textarea:focus {
          outline: none;
          border-color: #007bff;
          box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
          transform: translateY(-1px);
        }
        
        .form-container input:not([type="checkbox"]):not([type="radio"]):hover,
        .form-container select:hover,
        .form-container textarea:hover {
          border-color: #007bff;
        }
        
        /* Buttons */
        .form-container button {
          padding: 6px 12px;
          border: none;
          border-radius: 4px;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease-in-out;
          font-family: inherit;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        
        .form-container button:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        .form-container button:active {
          transform: translateY(0);
        }
        
        /* Primary buttons */
        .form-container button[style*="background-color: #007bff"],
        .form-container button[style*="backgroundColor: #007bff"] {
          background: linear-gradient(135deg, #007bff 0%, #0056b3 100%) !important;
          color: white;
          border: none;
        }
        
        /* Secondary buttons */
        .form-container button[style*="background: #28a745"],
        .form-container button[style*="backgroundColor: #28a745"] {
          background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%) !important;
          color: white;
        }
        
        /* Danger buttons */
        .form-container button[style*="background: #dc3545"],
        .form-container button[style*="backgroundColor: #dc3545"] {
          background: linear-gradient(135deg, #dc3545 0%, #c82333 100%) !important;
          color: white;
        }
        
        /* Checkbox styling for all screen sizes */
        .form-container input[type="checkbox"] {
          width: 18px !important;
          height: 18px !important;
          min-width: 18px !important;
          margin-right: 10px;
          cursor: pointer;
          accent-color: #007bff;
          pointer-events: auto;
          position: relative;
          z-index: 1;
          -webkit-appearance: checkbox !important;
          -moz-appearance: checkbox !important;
          appearance: checkbox !important;
          background: white !important;
          border: 2px solid #007bff !important;
          padding: 0 !important;
          font-size: inherit !important;
          line-height: normal !important;
          display: inline-block !important;
          vertical-align: middle !important;
          transform: none !important;
          border-radius: 4px !important;
        }
        
        .form-container input[type="checkbox"]:focus {
          outline: 2px solid #007bff !important;
          outline-offset: 2px !important;
        }
        
        .form-container label {
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 10px;
          user-select: none;
          pointer-events: auto;
          position: relative;
          font-weight: 500;
          color: #2c3e50;
          padding: 8px 0;
        }
        
        /* Ensure checkbox labels have proper spacing and hover effects */
        .form-container label:hover {
          color: #007bff;
        }
        
        /* Loading indicator styling */
        .form-container > div[style*="background: #e3f2fd"] {
          background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%) !important;
          border: 1px solid #2196f3;
          box-shadow: 0 2px 4px rgba(33, 150, 243, 0.1);
        }
        
        @media (max-width: 768px) {
          .form-container {
            max-width: 100vw;
            padding: 20px 12px 12px 12px;
            /* Added extra top padding for mobile spacing */
            background: #f8f9fa;
            overflow-x: hidden;
            width: calc(100vw - 24px);
            margin: 0 auto;
          }
          
          .form-container > div:not(.ready-to-file) {
            padding: 8px;
            margin-bottom: 6px;
            border-radius: 4px;
          }
          
          .form-container h2 {
            font-size: 1rem;
            margin-bottom: 6px;
            padding-bottom: 3px;
            border-bottom: 1px solid #007bff;
          }
          
          /* Mobile grid layouts */
          .form-container div[style*="display: grid"] {
            grid-template-columns: 1fr !important;
            gap: 6px !important;
          }
          
          /* Override any specific grid layouts on mobile */
          .form-container div[style*="gridTemplateColumns"] {
            grid-template-columns: 1fr !important;
          }
          
          .form-container div[style*="grid-template-columns"] {
            grid-template-columns: 1fr !important;
          }
          
          /* Force single column for all grid children */
          .form-container div[style*="gridColumn"] {
            grid-column: span 1 !important;
          }
          
          .form-container div[style*="grid-column"] {
            grid-column: span 1 !important;
          }
          
          /* Mobile input styling */
          .form-container input:not([type="checkbox"]),
          .form-container select,
          .form-container textarea {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 16px !important; /* Prevent zoom on iOS */
            padding: 12px 16px !important;
            margin-bottom: 4px;
            box-sizing: border-box;
            height: 48px !important;
            min-height: 48px !important;
            max-height: 48px !important;
          }
          
          /* Special handling for mobile textarea */
          .form-container textarea {
            height: auto !important;
            min-height: 48px !important;
            max-height: none !important;
          }
          
          /* Mobile button improvements */
          .form-container button {
            width: 100% !important;
            font-size: 1.1rem !important;
            padding: 16px 20px !important;
            margin: 8px 0 !important;
            border-radius: 8px !important;
          }
          
          /* Mobile label improvements */
          .form-container label {
            padding: 12px 8px !important;
            min-height: 48px !important; /* Better touch target */
            font-size: 1rem !important;
            border-radius: 8px !important;
            margin: 4px 0 !important;
          }
          
          /* Enhanced mobile checkbox styling */
          .form-container input[type="checkbox"] {
            width: 22px !important;
            height: 22px !important;
            min-width: 22px !important;
            margin-right: 12px !important;
          }
          
          /* Vehicle row mobile improvements */
          .vehicle-row {
            flex-direction: column !important;
            align-items: stretch !important;
            gap: 12px !important;
            padding: 16px !important;
            margin-bottom: 16px !important;
          }
          
          .vehicle-row input:not([type="checkbox"]),
          .vehicle-row select,
          .vehicle-row button,
          .vehicle-row textarea {
            width: 100% !important;
            min-width: 0 !important;
            font-size: 16px !important;
            margin-bottom: 8px !important;
          }
          
          .vehicle-row label {
            width: 100% !important;
            font-size: 1rem !important;
            margin-bottom: 8px !important;
          }
          
          .vehicle-row > div {
            width: 100% !important;
          }
          
          .vehicle-row > div > div {
            flex-direction: column !important;
            gap: 12px !important;
          }
          
          /* Ready to file section mobile */
          .ready-to-file {
            padding: 20px !important;
            margin-top: 20px !important;
          }
          
          .ready-to-file h3 {
            font-size: 1.3rem !important;
          }
          
          .ready-to-file p {
            font-size: 1rem !important;
            margin-bottom: 16px !important;
          }
          
          .ready-to-file div[style*="display: flex"] {
            flex-direction: column !important;
            gap: 12px !important;
          }
          
          .ready-to-file button {
            width: 100% !important;
            padding: 16px 20px !important;
            font-size: 1.1rem !important;
          }
          
          /* Recaptcha mobile scaling */
          .form-container .g-recaptcha {
            transform: scale(0.9);
            transform-origin: 0 0;
            margin-bottom: 12px;
          }
          
          /* Form section spacing on mobile */
          .form-container > div > div[style*="margin"] {
            margin: 12px 0 !important;
          }
          
          /* Special mobile styling for preparer and consent sections */
          .form-container div[style*="backgroundColor: #f8f9fa"] {
            padding: 16px !important;
            margin-top: 12px !important;
            border-radius: 8px !important;
          }
          
          /* Mobile-specific fixes for flex layouts */
          .form-container > div > div[style*="display: flex"] {
            flex-direction: column !important;
            gap: 12px !important;
            align-items: stretch !important;
          }
          
          .form-container > div > div[style*="display: flex"] > input,
          .form-container > div > div[style*="display: flex"] > select {
            width: 100% !important;
            min-width: 0 !important;
            flex: none !important;
            box-sizing: border-box !important;
          }
          
          /* Ensure all form elements stay within viewport */
          .form-container * {
            max-width: 100% !important;
            box-sizing: border-box !important;
          }
        }
        
        /* Special styling for the Ready to File section */
        .ready-to-file {
          background: white !important;
          color: #2c3e50 !important;
          border: 1px solid rgba(0, 0, 0, 0.05) !important;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        .ready-to-file h3 {
          color: #2c3e50 !important;
        }
        
        .ready-to-file p {
          color: #34495e !important;
        }
        
        /* Vehicle row styling */
        .vehicle-row {
          background: white !important;
          border: 1px solid #e1e8ed !important;
          border-radius: 6px !important;
          padding: 8px !important;
          margin-bottom: 8px !important;
          transition: all 0.2s ease-in-out !important;
        }
        
        .vehicle-row:hover {
          border-color: #007bff !important;
          box-shadow: 0 4px 12px rgba(0, 123, 255, 0.1) !important;
        }
        
        /* Flex layout improvements */
        .form-container div[style*="display: flex"] {
          gap: 12px;
        }
        
        /* Input groups - desktop only */
        @media (min-width: 769px) {
          .form-container > div > div[style*="display: flex"] {
            flex-wrap: wrap;
            gap: 16px;
            align-items: flex-start;
          }
          
          .form-container > div > div[style*="display: flex"] > input,
          .form-container > div > div[style*="display: flex"] > select {
            flex: 1;
            min-width: 200px;
          }
        }
      `}</style>
      <div className="form-container">
        {/* Login Modal for existing users */}
        {showLoginModal && (
          <LoginModal email={pendingEmail} onClose={() => setShowLoginModal(false)} />
        )}

        {/* Data Loading Indicator */}
        {isLoadingData && (
          <div style={{ 
            background: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)', 
            padding: '12px', 
            marginBottom: '12px',
            borderRadius: '6px',
            textAlign: 'center',
            color: '#1565c0',
            fontSize: '0.9rem',
            fontWeight: '500',
            border: '1px solid #2196f3',
            boxShadow: '0 2px 4px rgba(33, 150, 243, 0.1)'
          }}>
            📄 Loading saved form data...
          </div>
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

        {/* Proceed to Filing Section */}
        <div className="ready-to-file" style={{ 
          background: 'white', 
          border: '1px solid rgba(0, 0, 0, 0.05)', 
          borderRadius: '8px', 
          padding: '16px',
          marginTop: '12px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.1)',
          color: '#2c3e50'
        }}>
          <h3 style={{ color: '#2c3e50', marginBottom: '8px', fontSize: '1.1rem', fontWeight: '600' }}>
            🚀 Ready to File?
          </h3>
          <p style={{ margin: '0 0 12px 0', color: '#34495e', fontSize: '0.9rem' }}>
            Review your tax computation and complete your filing with secure payment processing.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              style={{ 
                padding: '10px 20px',
                border: '1px solid #007bff',
                borderRadius: '6px',
                backgroundColor: '#007bff',
                color: 'white', 
                fontSize: '0.9rem',
                cursor: 'pointer',
                fontWeight: '600',
                boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
              }}
              onClick={handleProceedToFiling}
            >
              📋 Proceed to Filing
            </button>
            <button
              type="button"
              style={{ 
                padding: '10px 20px',
                border: '1px solid #6c757d',
                borderRadius: '6px',
                backgroundColor: 'transparent',
                color: '#6c757d', 
                fontSize: '0.9rem',
                cursor: 'pointer',
                fontWeight: '500'
              }}
              onClick={handleClearData}
            >
              🗑️ Clear Form
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
