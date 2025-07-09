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
    fontSize: '0.9rem'
  } as React.CSSProperties;

  return (
    <>
      {/* Return Flags */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 12 }}>
        {['address_change','amended_return','vin_correction','final_return'].map(flag => (
          <label key={flag} style={{ 
            ...labelSmall, 
            cursor: flag === 'amended_return' ? 'not-allowed' : 'pointer',
            opacity: flag === 'amended_return' ? 0.5 : 1
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
              {flag.replace(/_/g,' ')}
              {flag === 'amended_return' && ' (Coming Soon)'}
            </span>
          </label>
        ))}
      </div>

      {/* Amended Return Details */}
      {formData.amended_return && (
        <div style={{ marginTop: 20, padding: 16, border: '1px solid #ffc107', borderRadius: 4, backgroundColor: '#fff3cd' }}>
          <h3>📝 Amended Return Details</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
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
              rows={3}
              style={{ minWidth: '300px', resize: 'vertical' }}
            />
          </div>
        </div>
      )}

      {/* VIN Correction Details */}
      {formData.vin_correction && (
        <div style={{ marginTop: 20, padding: 16, border: '1px solid #17a2b8', borderRadius: 4, backgroundColor: '#d1ecf1' }}>
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
      <h2 style={{ marginTop: 20 }}>Special Conditions (Optional)</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <textarea
          name="special_conditions"
          placeholder="Describe any special conditions that apply to this return..."
          value={formData.special_conditions || ''}
          onChange={handleChange}
          rows={2}
          style={{ minWidth: '400px', resize: 'vertical' }}
        />
      </div>
    </>
  );
};
