import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';

interface SignaturePaymentProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
  todayStr: string;
}

export const SignaturePayment: React.FC<SignaturePaymentProps> = ({ formData, handleChange, todayStr }) => {
  const labelSmall = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.9rem'
  } as React.CSSProperties;

  return (
    <>
      {/* Signature */}
      <h2>Signature</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input name="signature" placeholder="Signature" value={formData.signature} onChange={handleChange} />
        <input name="printed_name" placeholder="Printed Name" value={formData.printed_name} onChange={handleChange} />
        <input
          type="date"
          name="signature_date"
          value={formData.signature_date}
          readOnly
          disabled
          style={{ background: "#eee", color: "#888" }}
        />
      </div>

      {/* Payment Method */}
      <h2 style={{ marginTop: 20 }}>Payment Method</h2>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 8 }}>
        <label style={{ ...labelSmall, cursor: 'pointer' }}>
          <input 
            type="checkbox" 
            name="payEFTPS" 
            checked={formData.payEFTPS} 
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>EFTPS</span>
        </label>
        <label style={{ ...labelSmall, cursor: 'pointer' }}>
          <input 
            type="checkbox" 
            name="payCard" 
            checked={formData.payCard} 
            onChange={handleChange}
            style={{ cursor: 'pointer' }}
          />
          <span style={{ cursor: 'pointer' }}>Credit/Debit Card</span>
        </label>
      </div>
      {formData.payEFTPS && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input 
            name="eftps_routing" 
            placeholder="Routing Number (9 digits)" 
            pattern="\d{9}"
            maxLength={9}
            inputMode="numeric"
            value={formData.eftps_routing} 
            onChange={handleChange} 
            required
          />
          <input 
            name="eftps_account" 
            placeholder="Account Number" 
            value={formData.eftps_account} 
            onChange={handleChange} 
            required
          />
          <select
            name="account_type"
            value={formData.account_type || ''}
            onChange={handleChange}
            required
          >
            <option value="">Account Type</option>
            <option value="Checking">Checking</option>
            <option value="Savings">Savings</option>
          </select>
          <input
            name="payment_date"
            type="date"
            min={todayStr}
            value={formData.payment_date || ''}
            onChange={handleChange}
            title="Requested payment date"
            required
          />
          <input
            name="taxpayer_phone"
            placeholder="Daytime Phone (10 digits)"
            pattern="\d{10}"
            maxLength={10}
            inputMode="numeric"
            value={formData.taxpayer_phone || ''}
            onChange={handleChange}
            required
          />
        </div>
      )}
      {formData.payCard && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="card_holder" placeholder="Cardholder Name" value={formData.card_holder} onChange={handleChange} />
          <input name="card_number" placeholder="Card Number" value={formData.card_number} onChange={handleChange} />
          <input name="card_exp" placeholder="MM/YY" value={formData.card_exp} onChange={handleChange} />
          <input name="card_cvv" placeholder="CVV" value={formData.card_cvv} onChange={handleChange} />
        </div>
      )}
    </>
  );
};
