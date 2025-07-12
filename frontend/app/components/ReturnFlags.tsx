import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';
import { months } from '../constants/formData';

interface ReturnFlagsProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
}

export const ReturnFlags: React.FC<ReturnFlagsProps> = ({ formData, handleChange }) => {
  const labelSmall = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.8rem',
    fontWeight: '500'
  } as React.CSSProperties;

  return (
    <>
      <h2>Return Flags</h2>
      {/* Return Flags */}
      <div style={{ display: 'grid', gap: '6px', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', marginTop: 6 }}>
        {['address_change','amended_return','vin_correction','final_return'].map(flag => (
          <label key={flag} style={{ 
            ...labelSmall, 
            cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer',
            opacity: flag === 'amended_return' ? 0.5 : 1,
            padding: '6px',
            border: '1px solid #e1e8ed',
            borderRadius: '4px',
            backgroundColor: (formData as any)[flag] ? '#e3f2fd' : '#f8f9fa',
            borderColor: (formData as any)[flag] ? '#007bff' : '#e1e8ed',
            transition: 'all 0.2s ease-in-out'
          }}>
            <input 
              type="checkbox" 
              name={flag} 
              checked={(formData as any)[flag]} 
              onChange={handleChange}
              disabled={flag === 'amended_return'}
              style={{ 
                cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer'
              }}
            />
            <span style={{ 
              cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer'
            }}>
              {flag.replace(/_/g,' ').replace(/\b\w/g, l => l.toUpperCase())}
              {flag === 'amended_return' && ' (Coming Soon)'}
            </span>
          </label>
        ))}
      </div>

      {/* Amended Return Details */}
      {formData.amended_return && (
        <div style={{ marginTop: 8, padding: 8, border: '1px solid #ffc107', borderRadius: 3, backgroundColor: '#fff3cd' }}>
          <h3>Amended Return Details</h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <select 
              name="amended_month" 
              value={formData.amended_month || ''} 
              onChange={handleChange}
            >
              <option value="">Select Month Being Amended</option>
              {months.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <textarea
              name="reasonable_cause_explanation"
              placeholder="Explain reason for amendment (if late filing or other reasonable cause)"
              value={formData.reasonable_cause_explanation || ''}
              onChange={handleChange}
              rows={2}
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>
        </div>
      )}

      {/* VIN Correction Details */}
      {formData.vin_correction && (
        <div style={{ marginTop: 8, padding: 8, border: '1px solid #17a2b8', borderRadius: 3, backgroundColor: '#d1ecf1' }}>
          <h3>🔧 VIN Correction Explanation</h3>
          <textarea
            name="vin_correction_explanation"
            placeholder="Explain the VIN corrections being made (include old and new VINs if applicable)..."
            value={formData.vin_correction_explanation || ''}
            onChange={handleChange}
            rows={4}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </div>
      )}

      {/* Special Conditions */}
      <h2 style={{ marginTop: 12 }}>
        <label style={{ ...labelSmall, cursor: 'pointer' }}>
          <input 
            type="checkbox" 
            name="include_special_conditions" 
            checked={formData.include_special_conditions || false} 
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>Special Conditions (Optional)</span>
        </label>
      </h2>
      {formData.include_special_conditions && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <textarea
            name="special_conditions"
            placeholder="Describe any special conditions that apply to this return..."
            value={formData.special_conditions || ''}
            onChange={handleChange}
            rows={1}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </div>
      )}
    </>
  );
};
