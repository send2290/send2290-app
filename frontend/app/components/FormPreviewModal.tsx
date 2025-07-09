"use client";
import { useState } from 'react';

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

  if (!isOpen) return null;

  const handleGeneratePreview = async () => {
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
        suspendedNonLoggingCount
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
          setSuccessMessage(`Successfully generated ${result.files.length} preview PDF(s) for different months.`);
        }
      } else {
        // Single file response - download the PDF directly
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'form2290_preview.pdf';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        // Optionally open in new tab for viewing
        const viewUrl = window.URL.createObjectURL(blob);
        window.open(viewUrl, '_blank');
        
        setSuccessMessage('Preview PDF generated successfully!');
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
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }
        
        .preview-modal {
          background: white;
          border-radius: 8px;
          max-width: 500px;
          width: 100%;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        
        .preview-modal-header {
          padding: 20px 24px;
          border-bottom: 1px solid #e0e0e0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        .preview-modal-title {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: #1a1a1a;
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
          border-radius: 50%;
        }
        
        .preview-modal-close:hover {
          background: #f0f0f0;
        }
        
        .preview-modal-body {
          padding: 24px;
        }
        
        .preview-info {
          background: #f8f9fa;
          border: 1px solid #e9ecef;
          border-radius: 6px;
          padding: 16px;
          margin-bottom: 20px;
        }
        
        .preview-info h4 {
          margin: 0 0 8px 0;
          color: #495057;
          font-size: 1rem;
        }
        
        .preview-info p {
          margin: 0;
          color: #6c757d;
          font-size: 0.9rem;
          line-height: 1.4;
        }
        
        .preview-summary {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-bottom: 20px;
        }
        
        .preview-summary-item {
          background: #fff;
          border: 1px solid #dee2e6;
          border-radius: 4px;
          padding: 12px;
          text-align: center;
        }
        
        .preview-summary-label {
          font-size: 0.8rem;
          color: #6c757d;
          margin-bottom: 4px;
        }
        
        .preview-summary-value {
          font-size: 1.1rem;
          font-weight: 600;
          color: #007bff;
        }
        
        .preview-modal-actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
        }
        
        .preview-btn {
          padding: 10px 20px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.95rem;
          font-weight: 500;
          transition: background-color 0.2s;
        }
        
        .preview-btn-secondary {
          background: #6c757d;
          color: white;
        }
        
        .preview-btn-secondary:hover {
          background: #5a6268;
        }
        
        .preview-btn-primary {
          background: #007bff;
          color: white;
        }
        
        .preview-btn-primary:hover {
          background: #0056b3;
        }
        
        .preview-btn:disabled {
          background: #cccccc;
          cursor: not-allowed;
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
        
        @media (max-width: 600px) {
          .preview-modal {
            margin: 10px;
            max-width: none;
          }
          
          .preview-summary {
            grid-template-columns: 1fr;
          }
          
          .preview-modal-actions {
            flex-direction: column;
          }
        }
      `}</style>
      
      <div className="preview-modal-overlay" onClick={onClose}>
        <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
          <div className="preview-modal-header">
            <h3 className="preview-modal-title">Form 2290 Preview</h3>
            <button className="preview-modal-close" onClick={onClose}>
              ×
            </button>
          </div>
          
          <div className="preview-modal-body">
            <div className="preview-info">
              <h4>📋 Preview Overview</h4>
              <p>
                Generate PDF preview(s) of your Form 2290 to review all data placement and formatting 
                before final submission. This preview uses the actual IRS form template with your data overlaid.
              </p>
              {formData?.vehicles && (() => {
                const months = new Set(formData.vehicles.map((v: any) => v.used_month || '2025-07'));
                return months.size > 1 ? (
                  <p style={{ marginTop: '8px', fontWeight: '500', color: '#007bff' }}>
                    📅 Your vehicles span {months.size} different months. You'll receive {months.size} separate PDF files.
                  </p>
                ) : null;
              })()}
            </div>
            
            <div className="preview-summary">
              <div className="preview-summary-item">
                <div className="preview-summary-label">Total Vehicles</div>
                <div className="preview-summary-value">{totalVINs}</div>
              </div>
              <div className="preview-summary-item">
                <div className="preview-summary-label">Tax Due</div>
                <div className="preview-summary-value">${totalTax.toFixed(2)}</div>
              </div>
              <div className="preview-summary-item">
                <div className="preview-summary-label">Disposal Credits</div>
                <div className="preview-summary-value">${totalDisposalCredits.toFixed(2)}</div>
              </div>
              <div className="preview-summary-item">
                <div className="preview-summary-label">Net Tax</div>
                <div className="preview-summary-value">
                  ${Math.max(0, totalTax - totalDisposalCredits).toFixed(2)}
                </div>
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
            
            <div className="preview-modal-actions">
              <button 
                className="preview-btn preview-btn-secondary" 
                onClick={onClose}
                disabled={isGenerating}
              >
                Cancel
              </button>
              <button 
                className="preview-btn preview-btn-primary" 
                onClick={handleGeneratePreview}
                disabled={isGenerating}
              >
                {isGenerating ? 'Generating...' : '📄 Generate Preview PDF'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
