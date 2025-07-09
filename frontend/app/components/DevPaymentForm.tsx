// Development mode payment component (bypasses Stripe when not configured)
"use client";
import React, { useState } from 'react';

interface DevPaymentFormProps {
  onPaymentSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export default function DevPaymentForm({ onPaymentSuccess, onCancel, isSubmitting }: DevPaymentFormProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsProcessing(true);
    
    // Simulate payment processing delay
    setTimeout(() => {
      onPaymentSuccess('dev_mode_fake_client_secret');
      setIsProcessing(false);
    }, 1000);
  };

  return (
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
        borderRadius: '8px',
        padding: '40px',
        maxWidth: '500px',
        width: '90%',
        textAlign: 'center'
      }}>
        <h3 style={{ margin: '0 0 20px 0', color: '#333' }}>
          Development Mode - Payment Simulation
        </h3>
        
        <div style={{ 
          backgroundColor: '#fff3cd', 
          border: '1px solid #ffeaa7', 
          borderRadius: '4px', 
          padding: '15px', 
          marginBottom: '20px',
          fontSize: '14px',
          color: '#856404'
        }}>
          <strong>⚠️ Development Mode</strong><br />
          This simulates the $45.00 payment process without charging a real card.
          Configure Stripe keys to enable actual payment processing.
        </div>
        
        <div style={{ marginBottom: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '4px' }}>
          <h4 style={{ margin: '0 0 10px 0' }}>Form Submission Service Fee</h4>
          <p style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#666' }}>
            Simulate payment of $45.00 for Form 2290 submission service.
          </p>
          <p style={{ margin: '0', fontSize: '14px', color: '#666', fontStyle: 'italic' }}>
            This does not include IRS tax payments (paid separately to IRS via EFTPS/Credit Card).
          </p>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div style={{ 
            display: 'flex', 
            gap: '10px', 
            justifyContent: 'center'
          }}>
            <button
              type="button"
              onClick={onCancel}
              disabled={isProcessing || isSubmitting}
              style={{
                padding: '12px 24px',
                backgroundColor: '#666',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: (isProcessing || isSubmitting) ? 'not-allowed' : 'pointer',
                opacity: (isProcessing || isSubmitting) ? 0.6 : 1
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isProcessing || isSubmitting}
              style={{
                padding: '12px 24px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: (isProcessing || isSubmitting) ? 'not-allowed' : 'pointer',
                opacity: (isProcessing || isSubmitting) ? 0.6 : 1
              }}
            >
              {isProcessing ? 'Processing...' : 'Simulate Payment ($45.00)'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
