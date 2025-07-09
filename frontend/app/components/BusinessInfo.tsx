import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';
import { auth } from '../../lib/firebase';

interface BusinessInfoProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
}

export const BusinessInfo: React.FC<BusinessInfoProps> = ({ formData, handleChange }) => {
  return (
    <>
      <h2>Business Info</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative' }}>
          <input
            name="email"
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={handleChange}
            disabled={!!auth.currentUser}
            style={{
              backgroundColor: auth.currentUser ? '#f5f5f5' : 'white',
              color: auth.currentUser ? '#666' : 'black',
              cursor: auth.currentUser ? 'not-allowed' : 'text'
            }}
          />
          {auth.currentUser && (
            <span style={{ 
              fontSize: '0.8rem', 
              color: '#666', 
              fontStyle: 'italic',
              marginLeft: '4px'
            }}>
              (from account)
            </span>
          )}
        </div>
        <input 
          name="business_name" 
          placeholder="Business Name (Line 1)" 
          value={formData.business_name} 
          onChange={handleChange} 
          maxLength={60} 
        />
        <input 
          name="business_name_line2" 
          placeholder="Business Name (Line 2 - Optional)" 
          value={formData.business_name_line2} 
          onChange={handleChange} 
          maxLength={60}
        />
        <input
          name="ein"
          placeholder="EIN (XX-XXXXXXX)"
          value={formData.ein}
          onChange={(e) => {
            // Auto-format EIN with hyphen
            let value = e.target.value.replace(/\D/g, ''); // Remove all non-digits
            if (value.length >= 2) {
              value = value.substring(0, 2) + '-' + value.substring(2, 9);
            }
            // Update the form data
            const syntheticEvent = {
              ...e,
              target: { ...e.target, name: 'ein', value: value }
            };
            handleChange(syntheticEvent as any);
          }}
          pattern="\d{2}-\d{7}"
          maxLength={10}
          inputMode="numeric"
          title="9 digits in format XX-XXXXXXX"
        />
        <input 
          name="address" 
          placeholder="Address (Line 1 - Max 35 chars)" 
          value={formData.address} 
          onChange={handleChange} 
          maxLength={35}
          title="Maximum 35 characters per IRS requirements"
        />
        <input 
          name="address_line2" 
          placeholder="Address (Line 2 - Optional, Max 35 chars)" 
          value={formData.address_line2} 
          onChange={handleChange} 
          maxLength={35}
          title="Maximum 35 characters per IRS requirements"
        />
        <input name="city" placeholder="City" value={formData.city} onChange={handleChange} />
        <input name="state" placeholder="State (2 letters)" value={formData.state} onChange={handleChange} maxLength={2} />
        <input
          name="zip"
          placeholder="ZIP"
          pattern="\d{5}"
          maxLength={5}
          inputMode="numeric"
          title="5 digits"
          value={formData.zip}
          onChange={handleChange}
        />
      </div>
    </>
  );
};
