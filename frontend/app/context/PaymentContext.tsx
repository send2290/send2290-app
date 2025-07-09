// Payment context for Stripe integration
"use client";
import { createContext, useContext, useEffect, useState } from 'react';
import { loadStripe, Stripe } from '@stripe/stripe-js';

interface PaymentContextType {
  stripe: Stripe | null;
  isLoading: boolean;
  error: string | null;
  publishableKey: string | null;
  submissionFee: number;
}

const PaymentContext = createContext<PaymentContextType | undefined>(undefined);

export function PaymentProvider({ children }: { children: React.ReactNode }) {
  const [stripe, setStripe] = useState<Stripe | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publishableKey, setPublishableKey] = useState<string | null>(null);
  const [submissionFee, setSubmissionFee] = useState(4500); // $45.00 in cents

  useEffect(() => {
    const initializeStripe = async () => {
      try {
        // Get Stripe config from backend
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000'}/payment/config`);
        if (!response.ok) {
          throw new Error('Failed to load payment configuration');
        }
        
        const config = await response.json();
        setPublishableKey(config.publishableKey);
        setSubmissionFee(config.price);
        
        // Only initialize Stripe if not in dev mode
        if (!config.dev_mode && config.publishableKey !== 'pk_dev_mode_testing') {
          const stripeInstance = await loadStripe(config.publishableKey);
          setStripe(stripeInstance);
        } else {
          // In dev mode, set a null stripe instance
          setStripe(null);
        }
      } catch (err: any) {
        setError(err.message);
        console.error('Failed to initialize Stripe:', err);
      } finally {
        setIsLoading(false);
      }
    };

    initializeStripe();
  }, []);

  return (
    <PaymentContext.Provider value={{
      stripe,
      isLoading,
      error,
      publishableKey,
      submissionFee
    }}>
      {children}
    </PaymentContext.Provider>
  );
}

export function usePayment() {
  const context = useContext(PaymentContext);
  if (context === undefined) {
    throw new Error('usePayment must be used within a PaymentProvider');
  }
  return context;
}
