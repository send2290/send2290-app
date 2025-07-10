"use client";
import { useState } from 'react';
import PaymentModal from './PaymentModal';

interface FormPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  formData: any;
  categoryData: any;
  grandTotals: any;
  totalVINs: number;
  totalDisposalCredits: number;
  totalTax: number;
  taxableVehiclesCount: number;
  suspendedLoggingCount: number;
  suspendedNonLoggingCount: number;
}

export default function FormPreviewModal({
  isOpen,
  onClose,
  formData,
  categoryData,
  grandTotals,
  totalVINs,
  totalDisposalCredits,
  totalTax,
  taxableVehiclesCount,
  suspendedLoggingCount,
  suspendedNonLoggingCount
}: FormPreviewModalProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handlePaymentSuccess = (newPaymentIntentId: string) => {
    setPaymentIntentId(newPaymentIntentId);
    setShowPaymentModal(false);
    // Automatically generate preview after payment
    handleGeneratePreview(newPaymentIntentId);
  };

  const handlePaymentCancel = () => {
    setShowPaymentModal(false);
  };

  const handleGeneratePreview = async (providedPaymentId?: string) => {
    setIsGenerating(true);
    setError('');
    setSuccessMessage('');

    try {
      // Set up API base URL
      const isBrowser = typeof window !== 'undefined';
      const defaultApi = isBrowser
        ? `${window.location.protocol}//${window.location.hostname}:5000`
        : '';
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi;

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
        // Include payment info if available
        payment_intent_id: providedPaymentId || paymentIntentId
      };

      // Get auth token
      const { auth } = await import('../../lib/firebase');
      const user = auth.currentUser;
      let token = '';
      if (user) {
        token = await user.getIdToken();
      }

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
          
          // Show success message
          const paymentStatus = result.payment_verified ? 'paid' : 'free';
          setSuccessMessage(`Successfully generated ${result.files.length} ${paymentStatus} preview PDF(s) for different months.`);
        }
      } else {
        // Single file response - download the PDF directly
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        const paymentStatus = (providedPaymentId || paymentIntentId) ? 'paid' : 'preview';
        link.download = `form2290_${paymentStatus}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        // Optionally open in new tab for viewing
        const viewUrl = window.URL.createObjectURL(blob);
        window.open(viewUrl, '_blank');
        
        const paymentType = (providedPaymentId || paymentIntentId) ? 'Paid preview' : 'Preview';
        setSuccessMessage(`${paymentType} PDF generated successfully!`);
      }

    } catch (err: any) {
      console.error('Preview generation error:', err);
      setError(err.message || 'Failed to generate preview');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <>
      <style>{`
        .preview-modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        
        .preview-modal-content {
          background: white;
          border-radius: 8px;
          width: 90%;
          max-width: 800px;
          max-height: 90vh;
          overflow: auto;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .preview-modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px;
          border-bottom: 1px solid #eee;
        }
        
        .preview-modal-title {
          margin: 0;
          color: #333;
          font-size: 1.5rem;
        }
        
        .preview-modal-close {
          background: none;
          border: none;
          font-size: 1.5rem;
          cursor: pointer;
          color: #666;
          padding: 0;
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        
        .preview-modal-close:hover {
          color: #333;
        }
        
        .preview-modal-body {
          padding: 20px;
        }
        
        .preview-info-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }
        
        .preview-info-card {
          background: #f8f9fa;
          border: 1px solid #e9ecef;
          border-radius: 6px;
          padding: 16px;
          text-align: center;
        }
        
        .preview-info-title {
          font-weight: bold;
          color: #495057;
          margin-bottom: 8px;
          font-size: 0.9rem;
        }
        
        .preview-info-value {
          font-size: 1.2rem;
          color: #007bff;
          font-weight: bold;
        }
        
        .preview-business-info {
          background: #f8f9fa;
          border: 1px solid #dee2e6;
          border-radius: 6px;
          padding: 16px;
          margin-bottom: 20px;
        }
        
        .preview-business-info h4 {
          margin: 0 0 12px 0;
          color: #495057;
        }
        
        .preview-business-details {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 8px;
          font-size: 0.9rem;
          color: #6c757d;
        }
        
        .preview-error {
          background: #f8d7da;
          border: 1px solid #f5c6cb;
          border-radius: 4px;
          padding: 12px;
          color: #721c24;
          margin-bottom: 16px;
        }
        
        .preview-success {
          background: #d4edda;
          border: 1px solid #c3e6cb;
          border-radius: 4px;
          padding: 12px;
          color: #155724;
          margin-bottom: 16px;
        }
        
        .preview-modal-actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          padding: 20px;
          border-top: 1px solid #eee;
          flex-wrap: wrap;
        }
        
        .preview-btn {
          padding: 12px 24px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 1rem;
          font-weight: 500;
          transition: all 0.2s;
          min-width: 120px;
        }
        
        .preview-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        
        .preview-btn-secondary {
          background: #6c757d;
          color: white;
        }
        
        .preview-btn-secondary:hover:not(:disabled) {
          background: #5a6268;
        }
        
        .preview-btn-primary {
          background: #007bff;
          color: white;
        }
        
        .preview-btn-primary:hover:not(:disabled) {
          background: #0056b3;
        }
        
        .preview-btn-success {
          background: #28a745;
          color: white;
        }
        
        .preview-btn-success:hover:not(:disabled) {
          background: #218838;
        }
        
        @media (max-width: 600px) {
          .preview-modal-content {
            width: 95%;
            margin: 10px;
          }
          
          .preview-info-grid {
            grid-template-columns: 1fr;
          }
          
          .preview-business-details {
            grid-template-columns: 1fr;
          }
          
          .preview-modal-actions {
            flex-direction: column;
          }
          
          .preview-btn {
            min-width: unset;
            width: 100%;
          }
        }
      `}</style>

      <div className="preview-modal-overlay">
        <div className="preview-modal-content">
          <div className="preview-modal-header">
            <h2 className="preview-modal-title">Form 2290 Preview</h2>
            <button 
              className="preview-modal-close" 
              onClick={onClose}
              disabled={isGenerating}
            >
              ×
            </button>
          </div>
          
          <div className="preview-modal-body">
            {/* Business Information */}
            <div className="preview-business-info">
              <h4>Business Information</h4>
              <div className="preview-business-details">
                <div><strong>Business Name:</strong> {formData?.business_name}</div>
                <div><strong>EIN:</strong> {formData?.ein}</div>
                <div><strong>Address:</strong> {formData?.address}, {formData?.city}, {formData?.state} {formData?.zip}</div>
                <div><strong>Tax Year:</strong> {formData?.tax_year}</div>
              </div>
            </div>
            
            {/* Summary Information */}
            <div className="preview-info-grid">
              <div className="preview-info-card">
                <div className="preview-info-title">Total Vehicles</div>
                <div className="preview-info-value">{totalVINs}</div>
              </div>
              <div className="preview-info-card">
                <div className="preview-info-title">Taxable Vehicles</div>
                <div className="preview-info-value">{taxableVehiclesCount}</div>
              </div>
              <div className="preview-info-card">
                <div className="preview-info-title">Tax Due</div>
                <div className="preview-info-value">${totalTax.toFixed(2)}</div>
              </div>
              <div className="preview-info-card">
                <div className="preview-info-title">Disposal Credits</div>
                <div className="preview-info-value">${totalDisposalCredits.toFixed(2)}</div>
              </div>
              <div className="preview-info-card">
                <div className="preview-info-title">Net Amount</div>
                <div className="preview-info-value">${Math.max(0, totalTax - totalDisposalCredits).toFixed(2)}</div>
              </div>
            </div>
            
            {error && (
              <div className="preview-error">
                ⚠️ {error}
              </div>
            )}
            
            {successMessage && (
              <div className="preview-success">
                ✅ {successMessage}
              </div>
            )}
          </div>
          
          <div className="preview-modal-actions">
            <button 
              className="preview-btn preview-btn-secondary" 
              onClick={onClose}
              disabled={isGenerating}
            >
              Cancel
            </button>
            
            {/* Free Preview Button */}
            <button 
              className="preview-btn preview-btn-primary" 
              onClick={() => handleGeneratePreview()}
              disabled={isGenerating}
            >
              {isGenerating ? 'Generating...' : '📄 Free Preview'}
            </button>
            
            {/* Paid Preview Button */}
            <button 
              className="preview-btn preview-btn-success" 
              onClick={() => setShowPaymentModal(true)}
              disabled={isGenerating}
            >
              💳 Pay & Preview ($45.00)
            </button>
          </div>
        </div>
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        onPaymentSuccess={handlePaymentSuccess}
        onCancel={handlePaymentCancel}
        isSubmitting={isGenerating}
      />
    </>
  );
}
