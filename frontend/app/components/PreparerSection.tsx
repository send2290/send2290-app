import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';

interface PreparerSectionProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
  todayStr: string;
}

export const PreparerSection: React.FC<PreparerSectionProps> = ({ formData, handleChange, todayStr }) => {
  const labelSmall = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.8rem',
    fontWeight: '500'
  } as React.CSSProperties;

  return (
    <>
      {/* Paid Preparer */}
      <h2 style={{ marginTop: 12 }}>
        <label style={{ ...labelSmall, cursor: 'pointer', fontSize: '1.1rem' }}>
          <input
            type="checkbox"
            name="include_preparer"
            checked={formData.include_preparer}
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>Include Paid Preparer</span>
        </label>
      </h2>
      {formData.include_preparer && (
        <div style={{ 
          marginTop: '8px', 
          padding: '8px', 
          backgroundColor: '#f8f9fa', 
          borderRadius: '4px',
          border: '1px solid #e1e8ed'
        }}>
          <div style={{ display: 'grid', gap: '6px', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', marginBottom: '6px' }}>
            <input name="preparer_name" placeholder="Preparer Name" value={formData.preparer_name} onChange={handleChange} required />
            <input name="preparer_ptin" placeholder="PTIN" value={formData.preparer_ptin} onChange={handleChange} required />
            <input type="date" name="date_prepared" max={todayStr} value={formData.date_prepared} onChange={handleChange} required />
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{
              ...labelSmall,
              cursor: 'pointer',
              padding: '4px 6px',
              backgroundColor: formData.preparer_self_employed ? '#e3f2fd' : 'white',
              border: '1px solid #e1e8ed',
              borderRadius: '3px',
              borderColor: formData.preparer_self_employed ? '#007bff' : '#e1e8ed'
            }}>
              <input
                type="checkbox"
                name="preparer_self_employed"
                checked={formData.preparer_self_employed}
                onChange={handleChange}
              />
              <span style={{ cursor: 'pointer' }}>Self Employed</span>
            </label>
          </div>
          <div style={{ display: 'grid', gap: '6px', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', marginTop: '6px' }}>
            <input name="preparer_firm_name" placeholder="Firm Name" value={formData.preparer_firm_name} onChange={handleChange} required />
            <input
              name="preparer_firm_ein"
              placeholder="Firm EIN (XX-XXXXXXX)"
              value={formData.preparer_firm_ein}
              onChange={(e) => {
                // Auto-format EIN with hyphen
                let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
                if (value.length >= 2) {
                  value = value.substring(0, 2) + '-' + value.substring(2, 9);
                }
                // Update the form data
                const syntheticEvent = {
                  ...e,
                  target: { ...e.target, name: 'preparer_firm_ein', value: value }
                };
                handleChange(syntheticEvent as any);
              }}
              pattern="\d{2}-\d{7}"
              maxLength={10}
              inputMode="numeric"
              title="9 digits in format XX-XXXXXXX"
              required
            />
            <input name="preparer_firm_address" placeholder="Firm Address" value={formData.preparer_firm_address} onChange={handleChange} required />
            <input
              name="preparer_firm_citystatezip"
              placeholder="Firm City/State/ZIP"
              value={formData.preparer_firm_citystatezip}
              onChange={handleChange}
              required
            />
            <input
              type="tel"
              name="preparer_firm_phone"
              placeholder="Firm Phone (10 digits)"
              pattern="\d{10}"
              maxLength={10}
              inputMode="numeric"
              title="10 digits"
              value={formData.preparer_firm_phone}
              onChange={handleChange}
              required
            />
          </div>
        </div>
      )}

      {/* Third-Party Designee / Consent */}
      <h2 style={{ marginTop: 12 }}>
        <label style={{ ...labelSmall, cursor: 'pointer', fontSize: '1.1rem' }}>
          <input 
            type="checkbox" 
            name="consent_to_disclose" 
            checked={formData.consent_to_disclose} 
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>Consent to Disclose</span>
        </label>
      </h2>
      {formData.consent_to_disclose && (
        <div style={{ 
          marginTop: '8px', 
          padding: '8px', 
          backgroundColor: '#f8f9fa', 
          borderRadius: '4px',
          border: '1px solid #e1e8ed'
        }}>
          <div style={{ display: 'grid', gap: '6px', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
            <input name="designee_name" placeholder="Designee Name" value={formData.designee_name} onChange={handleChange} required />
            <input
              name="designee_phone"
              placeholder="Designee Phone (10 digits)"
              pattern="\d{10}"
              maxLength={10}
              inputMode="numeric"
              title="10 digits"
              value={formData.designee_phone}
              onChange={handleChange}
              required
            />
            <input name="designee_pin" placeholder="Designee PIN" value={formData.designee_pin} onChange={handleChange} required />
          </div>
        </div>
      )}
    </>
  );
};
