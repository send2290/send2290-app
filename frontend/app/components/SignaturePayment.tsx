import React, { ChangeEvent } from 'react';
import { FormData } from '../types/form';

interface SignaturePaymentProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
  todayStr: string;
}

export const SignaturePayment: React.FC<SignaturePaymentProps> = ({ formData, handleChange, todayStr }) => {
  const sectionStyle = {
    background: '#f8f9fa',
    border: '1px solid #e9ecef',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '20px'
  } as React.CSSProperties;

  const inputStyle = {
    padding: '12px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    fontSize: '1rem',
    backgroundColor: '#fff',
    color: '#000',
    minWidth: '200px',
    flex: '1'
  } as React.CSSProperties;

  const selectStyle = {
    ...inputStyle,
    cursor: 'pointer'
  } as React.CSSProperties;

  const disabledInputStyle = {
    ...inputStyle,
    backgroundColor: '#f5f5f5',
    color: '#666',
    cursor: 'not-allowed'
  } as React.CSSProperties;

  const labelStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '1rem',
    cursor: 'pointer',
    padding: '8px 12px',
    borderRadius: '6px',
    backgroundColor: '#fff',
    border: '1px solid #ddd',
    transition: 'all 0.2s ease'
  } as React.CSSProperties;

  const checkboxStyle = {
    width: '18px',
    height: '18px',
    cursor: 'pointer'
  } as React.CSSProperties;

  return (
    <>
      {/* Signature Section */}
      <div style={sectionStyle}>
        <h2 style={{ marginBottom: '16px', color: '#343a40', fontSize: '1.4rem' }}>✍️ Signature</h2>
        <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
          <input 
            name="signature" 
            placeholder="Signature" 
            value={formData.signature} 
            onChange={handleChange}
            style={inputStyle}
          />
          <input 
            name="printed_name" 
            placeholder="Printed Name" 
            value={formData.printed_name} 
            onChange={handleChange}
            style={inputStyle}
          />
          <input
            type="date"
            name="signature_date"
            value={formData.signature_date}
            readOnly
            disabled
            style={disabledInputStyle}
            title="Date is automatically set to today"
          />
        </div>
      </div>

      {/* Payment Method Section */}
      <div style={sectionStyle}>
        <h2 style={{ marginBottom: '16px', color: '#343a40', fontSize: '1.4rem' }}>💳 Payment Method</h2>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '16px' }}>
          <label style={labelStyle}>
            <input 
              type="checkbox" 
              name="payEFTPS" 
              checked={formData.payEFTPS} 
              onChange={handleChange}
              style={checkboxStyle}
            />
            <span>EFTPS (Electronic Federal Tax Payment)</span>
          </label>
          <label style={labelStyle}>
            <input 
              type="checkbox" 
              name="payCard" 
              checked={formData.payCard} 
              onChange={handleChange}
              style={checkboxStyle}
            />
            <span>Credit/Debit Card</span>
          </label>
        </div>

        {/* EFTPS Payment Fields */}
        {formData.payEFTPS && (
          <div style={{ 
            background: '#e3f2fd', 
            padding: '16px', 
            borderRadius: '8px',
            border: '1px solid #2196f3',
            marginTop: '16px'
          }}>
            <h4 style={{ marginBottom: '12px', color: '#1565c0' }}>EFTPS Payment Details</h4>
            <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
              <input 
                name="eftps_routing" 
                placeholder="Routing Number (9 digits)" 
                pattern="\d{9}"
                maxLength={9}
                inputMode="numeric"
                value={formData.eftps_routing} 
                onChange={handleChange}
                style={inputStyle}
              />
              <input 
                name="eftps_account" 
                placeholder="Account Number" 
                value={formData.eftps_account} 
                onChange={handleChange}
                style={inputStyle}
              />
              <select
                name="account_type"
                value={formData.account_type || ''}
                onChange={handleChange}
                style={selectStyle}
              >
                <option value="">Select Account Type</option>
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
                style={inputStyle}
              />
              <input
                name="taxpayer_phone"
                placeholder="Daytime Phone (10 digits)"
                pattern="\d{10}"
                maxLength={10}
                inputMode="numeric"
                value={formData.taxpayer_phone || ''}
                onChange={handleChange}
                style={inputStyle}
              />
            </div>
          </div>
        )}

        {/* Credit/Debit Card Payment Fields */}
        {formData.payCard && (
          <div style={{ 
            background: '#f3e5f5', 
            padding: '16px', 
            borderRadius: '8px',
            border: '1px solid #9c27b0',
            marginTop: '16px'
          }}>
            <h4 style={{ marginBottom: '12px', color: '#7b1fa2' }}>Credit/Debit Card Details</h4>
            <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
              <input 
                name="card_holder" 
                placeholder="Cardholder Name" 
                value={formData.card_holder} 
                onChange={handleChange}
                style={inputStyle}
              />
              <input 
                name="card_number" 
                placeholder="Card Number" 
                value={formData.card_number} 
                onChange={handleChange}
                style={inputStyle}
              />
              <input 
                name="card_exp" 
                placeholder="MM/YY" 
                value={formData.card_exp} 
                onChange={handleChange}
                style={inputStyle}
              />
              <input 
                name="card_cvv" 
                placeholder="CVV" 
                value={formData.card_cvv} 
                onChange={handleChange}
                style={inputStyle}
              />
            </div>
          </div>
        )}
      </div>
    </>
  );
};
