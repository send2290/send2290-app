import { auth } from '../../lib/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { checkUserExists, createUserAndSendPassword } from '../../lib/authUtils';
import { FormData, GrandTotals, CategoryData } from '../types/form';
import { validateBeforeSubmit } from './formUtils';

export const createSubmissionHandler = (
  formData: FormData,
  totalTax: number,
  totalDisposalCredits: number,
  captchaToken: string | null,
  captchaRef: React.RefObject<any>,
  setCaptchaToken: (token: string | null) => void,
  categoryData: Record<string, CategoryData>,
  grandTotals: GrandTotals,
  API_BASE: string,
  onPaymentRequired?: (onPaymentSuccess: (paymentIntentId: string) => void) => void
) => {
  return async (paymentIntentId?: string) => {
    // 1) run client-side validation FIRST
    const err = validateBeforeSubmit(formData, totalTax, captchaToken, totalDisposalCredits);
    if (err) { 
      alert(err); 
      return; 
    }

    // 2) require email
    if (!formData.email.trim()) {
      alert('Email is required');
      return;
    }

    // 3) Check/create account if not signed in
    if (!auth.currentUser) {
      let exists = false;
      try {
        exists = await checkUserExists(formData.email);
      } catch (e: any) {
        if (e?.status === 404) {
          exists = false;
        } else {
          alert("Error checking user: " + (e?.message || JSON.stringify(e)));
          return;
        }
      }

      if (!exists) {
        try {
          const didCreate = await createUserAndSendPassword(formData.email);
          if (didCreate) {
            alert("Account created! Check your email for your password.");
          } else {
            alert("Failed to create account. Please try again.");
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
            alert("Account created, but welcome email could not be sent. Please contact support.");
          } else {
            alert("Error creating account: " + (e?.message || JSON.stringify(e)));
          }
          // Do not return; continue to submission
        }
      } else {
        // User already exists – skipping creation
      }
    }

    // Check if payment is required and not provided
    if (!paymentIntentId && onPaymentRequired) {
      // Trigger payment modal
      onPaymentRequired((newPaymentIntentId: string) => {
        // Recursively call this function with the payment intent ID
        createSubmissionHandler(
          formData, totalTax, totalDisposalCredits, captchaToken, 
          captchaRef, setCaptchaToken, categoryData, grandTotals, API_BASE
        )(newPaymentIntentId);
      });
      return;
    }

    // 4) Submit and download PDF (which also generates XML)
    try {
      // Include the calculated category data from frontend
      const totalTaxAmount = grandTotals.regularTotalTax + grandTotals.loggingTotalTax;
      const additionalTax = 0.00; // Placeholder for future implementation
      const totalTaxWithAdditional = totalTaxAmount + additionalTax;
      // Use calculated disposal credits instead of static tax_credits
      const credits = totalDisposalCredits;
      const balanceDue = Math.max(0, totalTaxWithAdditional - credits);
      
      // Handle captcha token for localhost development
      const isLocalhost = typeof window !== 'undefined' && 
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
      const finalCaptchaToken = isLocalhost ? 'localhost-dev-token' : captchaToken;

      const submissionData = {
        ...formData,
        // Ensure numeric fields are properly converted
        disposal_credits: credits, // Use disposal_credits instead of tax_credits
        count_w_suspended_logging: formData.vehicles.filter(v => v.category === 'W' && v.is_logging).length,
        count_w_suspended_non_logging: formData.vehicles.filter(v => v.category === 'W' && !v.is_logging).length,
        captchaToken: finalCaptchaToken,
        payment_intent_id: paymentIntentId, // Include payment verification
        // Add the calculated category data and totals
        categoryData: categoryData,
        grandTotals: grandTotals,
        // Add Part I tax summary values (matching form_positions.json field names)
        partI: {
          line2_tax: totalTaxAmount,                    // Line 2: Tax (from Schedule 1, line c.)
          line3_increase: additionalTax,          // Line 3: Additional tax (attach explanation)
          line4_total: totalTaxWithAdditional,    // Line 4: Total tax (add lines 2 and 3)
          line5_credits: credits,                 // Line 5: Credits (from vehicle disposals)
          line6_balance: balanceDue               // Line 6: Balance due (subtract line 5 from line 4)
        }
      };
      
      // Check if user is authenticated before getting token
      if (!auth.currentUser) {
        throw new Error("Authentication required. Please refresh the page and try again.");
      }
      
      const token = await auth.currentUser.getIdToken();
      
      const response = await fetch(`${API_BASE}/build-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(submissionData),
      });

      if (!response.ok) {
        let errorMsg = response.statusText;
        try {
          const errorData = await response.json();
          errorMsg = errorData.message || errorData.error || errorMsg;
        } catch {
          // Non-JSON response, use statusText
        }
        
        // Handle specific authorization errors
        if (response.status === 401) {
          throw new Error(errorMsg || "Authentication required. Please refresh the page and try again.");
        }
        
        alert(`Submission failed: ${errorMsg}`);
        return;
      }

      // Check content type to determine if it's a file download or JSON response
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        // JSON response - multiple months scenario
        const jsonData = await response.json();
        
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
      console.error("Submission error:", error);
      alert(`Network error: ${error.message}`);
    }
  };
};
