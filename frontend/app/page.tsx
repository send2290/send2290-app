"use client";
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '../lib/firebase';
import LoginModal from './LoginModal';
import { useForm2290 } from './hooks/useForm2290';
import { createFormHandler } from './utils/formHandlers';
import { calculateDisposalCredit } from './utils/formUtils';
import { BusinessInfo } from './components/BusinessInfo';
import { ReturnFlags } from './components/ReturnFlags';
import { OfficerInfo } from './components/OfficerInfo';
import { PreparerSection } from './components/PreparerSection';
import { VehicleManagement } from './components/VehicleManagement';
import { AdminSubmissions } from './components/AdminSubmissions';
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
                console.log(`Calculated disposal credit for vehicle ${vehicle.vin}: $${credit}`);
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
      
      // Debug: Show what's being saved
      console.log('Auto-saving data:', {
        totalDisposalCredits,
        vehiclesWithDisposal: formData.vehicles.filter(v => v.disposal_date).length,
        vehicleCredits: formData.vehicles.map(v => ({ vin: v.vin.slice(-4), credit: v.disposal_credit }))
      });
      
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
    // Comprehensive validation before proceeding to filing
    const validationErrors: string[] = [];
    
    // Business information validation
    if (!formData.business_name.trim()) {
      validationErrors.push('Business Name is required');
    }
    
    if (!/^\d{2}-\d{7}$/.test(formData.ein)) {
      validationErrors.push('EIN must be 9 digits in format XX-XXXXXXX');
    }
    
    if (!formData.address.trim()) {
      validationErrors.push('Business Address is required');
    }
    
    if (!formData.city.trim()) {
      validationErrors.push('City is required');
    }
    
    if (!formData.state.trim() || formData.state.length !== 2) {
      validationErrors.push('State must be 2 letters');
    }
    
    if (!/^\d{5}$/.test(formData.zip)) {
      validationErrors.push('ZIP code must be 5 digits');
    }
    
    // Officer information validation
    if (!formData.officer_name.trim()) {
      validationErrors.push('Officer name is required');
    }
    
    if (!formData.officer_title.trim()) {
      validationErrors.push('Officer title is required (e.g., President, Owner, Manager)');
    }
    
    if (!/^\d{3}-?\d{2}-?\d{4}$/.test(formData.officer_ssn)) {
      validationErrors.push('Officer SSN must be in format XXX-XX-XXXX');
    }
    
    if (!/^\d{5}$/.test(formData.taxpayer_pin)) {
      validationErrors.push('Taxpayer PIN must be exactly 5 digits');
    }
    
    // Vehicle validation
    if (formData.vehicles.length === 0) {
      validationErrors.push('At least one vehicle is required');
    } else {
      // Validate each vehicle
      formData.vehicles.forEach((vehicle, index) => {
        if (!vehicle.vin.trim()) {
          validationErrors.push(`Vehicle ${index + 1}: VIN is required`);
        } else if (vehicle.vin.length < 17) {
          validationErrors.push(`Vehicle ${index + 1}: VIN must be 17 characters`);
        }
        
        if (!vehicle.category) {
          validationErrors.push(`Vehicle ${index + 1}: Weight category is required`);
        }
        
        if (!vehicle.used_month) {
          validationErrors.push(`Vehicle ${index + 1}: First use month is required`);
        }
      });
    }
    
    // Show validation errors if any
    if (validationErrors.length > 0) {
      const errorMessage = 'Please fix the following issues before proceeding:\n\n' + 
        validationErrors.map((error, index) => `${index + 1}. ${error}`).join('\n');
      alert(errorMessage);
      return;
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

        {/* Data Loading Indicator */}
        {isLoadingData && (
          <div style={{ 
            background: '#e3f2fd', 
            padding: '12px', 
            marginBottom: '16px',
            borderRadius: '4px',
            textAlign: 'center',
            color: '#1565c0',
            fontSize: '0.9rem'
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
        <div style={{ 
          background: '#f8f9fa', 
          border: '2px solid #007bff', 
          borderRadius: '8px', 
          padding: '20px',
          marginTop: '20px',
          textAlign: 'center'
        }}>
          <h3 style={{ color: '#007bff', marginBottom: '16px' }}>
            Ready to File?
          </h3>
          <p style={{ margin: '0 0 16px 0', color: '#666' }}>
            Review your tax computation and complete your filing with secure payment processing.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              style={{ 
                padding: '12px 24px',
                border: 'none',
                borderRadius: 4,
                backgroundColor: '#007bff',
                color: '#fff', 
                fontSize: '1.1rem',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
              onClick={handleProceedToFiling}
            >
              Proceed to Filing
            </button>
            <button
              type="button"
              style={{ 
                padding: '12px 24px',
                border: '1px solid #dc3545',
                borderRadius: 4,
                backgroundColor: 'transparent',
                color: '#dc3545', 
                fontSize: '1rem',
                cursor: 'pointer'
              }}
              onClick={handleClearData}
            >
              Clear Form
            </button>
          </div>
        </div>

        {/* Admin Section */}
        {auth.currentUser?.email === process.env.NEXT_PUBLIC_ADMIN_EMAIL && (
          <AdminSubmissions API_BASE={API_BASE} />
        )}
      </div>
    </>
  );
}
