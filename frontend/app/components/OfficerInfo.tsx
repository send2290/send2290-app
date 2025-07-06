import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';

interface OfficerInfoProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
}

export const OfficerInfo: React.FC<OfficerInfoProps> = ({ formData, handleChange }) => {
  const labelSmall = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.9rem'
  } as React.CSSProperties;

  return (
    <>
      {/* Business Officer Information & Tax Credits */}
      <h2 style={{ marginTop: 20 }}>Business Officer Information</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input 
          name="officer_name" 
          placeholder="Officer Name (Required for signing)" 
          value={formData.officer_name} 
          onChange={handleChange} 
          required
          title="Name of the person authorized to sign this return"
        />
        <input 
          name="officer_title" 
          placeholder="Officer Title (e.g., President, Owner, Manager)" 
          value={formData.officer_title} 
          onChange={handleChange} 
          required
          title="Title of the person signing this return"
        />
        <input 
          name="officer_ssn" 
          placeholder="Officer SSN (XXX-XX-XXXX)" 
          value={formData.officer_ssn} 
          onChange={(e) => {
            // Auto-format SSN with hyphens
            let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
            if (value.length >= 3) {
              value = value.substring(0, 3) + '-' + value.substring(3);
            }
            if (value.length >= 6) {
              value = value.substring(0, 6) + '-' + value.substring(6, 10);
            }
            // Update the form data
            const syntheticEvent = {
              ...e,
              target: { ...e.target, name: 'officer_ssn', value: value }
            };
            handleChange(syntheticEvent as any);
          }}
          pattern="\d{3}-\d{2}-\d{4}"
          maxLength={11}
          required
          title="Social Security Number of the officer signing the return (format: XXX-XX-XXXX)"
        />
        <input 
          name="taxpayer_pin" 
          placeholder="Taxpayer PIN (5 digits)" 
          pattern="\d{5}"
          maxLength={5}
          inputMode="numeric"
          title="5-digit PIN for electronic signature"
          value={formData.taxpayer_pin} 
          onChange={handleChange} 
          required
        />
      </div>
      
      {/* Tax Credits */}
      <h2 style={{ marginTop: 20 }}>Tax Credits & Disposals</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <input 
          name="tax_credits" 
          type="number"
          min="0"
          step="0.01"
          placeholder="Tax Credits Amount"
          value={formData.tax_credits === 0 ? '' : formData.tax_credits.toString()} 
          onChange={handleChange}
          onWheel={(e) => e.currentTarget.blur()}
          title="Amount of tax credits to apply against tax liability"
        />
        <label style={{ ...labelSmall, cursor: 'pointer' }}>
          <input
            type="checkbox"
            name="has_disposals"
            checked={formData.has_disposals || false}
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>Include Vehicle Disposals/Sales</span>
        </label>
        <span style={{ fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>
          Enter any tax credits and mark vehicles disposed below
        </span>
      </div>
    </>
  );
};
