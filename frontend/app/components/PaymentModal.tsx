// Payment component for form submission fee
"use client";
import React, { useState } from 'react';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { usePayment } from '../context/PaymentContext';
import { auth } from '../../lib/firebase';
import DevPaymentForm from './DevPaymentForm';

interface PaymentFormProps {
  onPaymentSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

function PaymentForm({ onPaymentSuccess, onCancel, isSubmitting }: PaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      const { error: submitError } = await elements.submit();
      if (submitError) {
        setError(submitError.message || 'Payment submission failed');
        setIsProcessing(false);
        return;
      }

      const { paymentIntent, error: confirmError } = await stripe.confirmPayment({
        elements,
        redirect: 'if_required'
      });

      if (confirmError) {
        setError(confirmError.message || 'Payment confirmation failed');
      } else if (paymentIntent && paymentIntent.status === 'succeeded') {
        onPaymentSuccess(paymentIntent.id);
      }
    } catch (err: any) {
      setError(err.message || 'Payment processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h3 style={{ margin: '0 0 10px 0', color: '#333' }}>
          Form Submission Service Fee
        </h3>
        <p style={{ margin: '0', color: '#666', fontSize: '14px' }}>
          Pay $45.00 to submit your Form 2290. This is our service fee for processing and submitting your form to the IRS.
        </p>
        <p style={{ margin: '10px 0 0 0', color: '#666', fontSize: '14px', fontStyle: 'italic' }}>
          Note: This does not include the tax payment due to the IRS, which you'll pay separately via EFTPS or Credit/Debit Card directly to the IRS.
        </p>
      </div>
      
      <PaymentElement />
      
      {error && (
        <div style={{ 
          color: 'red', 
          fontSize: '14px', 
          marginTop: '10px',
          padding: '10px',
          backgroundColor: '#fee',
          border: '1px solid #fcc',
          borderRadius: '4px'
        }}>
          {error}
        </div>
      )}
      
      <div style={{ 
        display: 'flex', 
        gap: '10px', 
        marginTop: '20px',
        justifyContent: 'flex-end'
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
            cursor: isProcessing || isSubmitting ? 'not-allowed' : 'pointer',
            opacity: isProcessing || isSubmitting ? 0.6 : 1
          }}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!stripe || isProcessing || isSubmitting}
          style={{
            padding: '12px 24px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: (!stripe || isProcessing || isSubmitting) ? 'not-allowed' : 'pointer',
            opacity: (!stripe || isProcessing || isSubmitting) ? 0.6 : 1
          }}
        >
          {isProcessing ? 'Processing...' : 'Pay $45.00'}
        </button>
      </div>
    </form>
  );
}

interface PaymentModalProps {
  isOpen: boolean;
  onPaymentSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export default function PaymentModal({ isOpen, onPaymentSuccess, onCancel, isSubmitting }: PaymentModalProps) {
  const { stripe, isLoading, error, submissionFee } = usePayment();
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState<boolean>(false);

  React.useEffect(() => {
    if (isOpen && !clientSecret) {
      createPaymentIntent();
    }
  }, [isOpen]);

  const createPaymentIntent = async () => {
    try {
      const user = auth.currentUser;
      if (!user) {
        setPaymentError('Please log in to continue');
        return;
      }

      const token = await user.getIdToken();
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000'}/payment/create-payment-intent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to create payment intent');
      }

      const data = await response.json();
      setClientSecret(data.client_secret);
      setDevMode(data.dev_mode || false);
    } catch (err: any) {
      setPaymentError(err.message);
    }
  };

  if (!isOpen) return null;

  // Show development mode payment form if in dev mode
  if (devMode || clientSecret === 'dev_mode_fake_client_secret') {
    return (
      <DevPaymentForm
        onPaymentSuccess={onPaymentSuccess}
        onCancel={onCancel}
        isSubmitting={isSubmitting}
      />
    );
  }

  if (isLoading) {
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
          maxWidth: '400px',
          textAlign: 'center'
        }}>
          Loading payment system...
        </div>
      </div>
    );
  }

  if (error || paymentError) {
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
          maxWidth: '400px',
          textAlign: 'center'
        }}>
          <h3 style={{ color: 'red', margin: '0 0 15px 0' }}>Payment Error</h3>
          <p style={{ margin: '0 0 20px 0' }}>{error || paymentError}</p>
          <button
            onClick={onCancel}
            style={{
              padding: '12px 24px',
              backgroundColor: '#666',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

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
        maxWidth: '500px',
        width: '90%',
        maxHeight: '90%',
        overflow: 'auto'
      }}>
        {stripe && clientSecret && (
          <Elements 
            stripe={stripe} 
            options={{
              clientSecret,
              appearance: {
                theme: 'stripe',
                variables: {
                  colorPrimary: '#007bff'
                }
              }
            }}
          >
            <PaymentForm 
              onPaymentSuccess={onPaymentSuccess}
              onCancel={onCancel}
              isSubmitting={isSubmitting}
            />
          </Elements>
        )}
      </div>
    </div>
  );
}
