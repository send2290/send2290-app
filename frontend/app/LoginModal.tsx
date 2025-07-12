// app/LoginModal.tsx
"use client";

import { useState } from 'react';
import { signInWithEmailAndPassword, getAuth } from 'firebase/auth';

export default function LoginModal({
  email,
  onClose,
}: {
  email: string;
  onClose: () => void;
}) {
  const [password, setPassword] = useState('');
  const [error, setError]     = useState('');

  const handleLogin = async () => {
    try {
      const auth = getAuth();
      await signInWithEmailAndPassword(auth, email, password);
      onClose();
    } catch {
      setError('Login failed – check your password.');
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(0,0,0,0.6)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          backgroundColor: '#fff',
          padding: '32px',
          borderRadius: '16px',
          minWidth: '360px',
          maxWidth: '400px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          border: '1px solid #e5e7eb',
        }}
      >
        <h2 style={{ 
          margin: '0 0 24px 0', 
          fontSize: '24px', 
          fontWeight: '700', 
          color: '#374151',
          textAlign: 'center' 
        }}>
          Login Required
        </h2>
        <p style={{ 
          margin: '0 0 20px 0', 
          color: '#6b7280', 
          fontSize: '14px',
          textAlign: 'center' 
        }}>
          Email: <strong>{email}</strong>
        </p>
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          style={{ 
            width: '100%', 
            marginBottom: '20px',
            padding: '12px 16px',
            border: '2px solid #d1d5db',
            borderRadius: '8px',
            fontSize: '16px',
            transition: 'all 0.2s',
            outline: 'none',
            boxSizing: 'border-box'
          }}
          onFocus={(e) => {
            e.target.style.borderColor = '#3b82f6';
            e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = '#d1d5db';
            e.target.style.boxShadow = 'none';
          }}
        />
        {error && (
          <p style={{ 
            color: '#ef4444', 
            margin: '0 0 16px 0', 
            fontSize: '14px',
            textAlign: 'center' 
          }}>
            {error}
          </p>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button 
            onClick={onClose}
            style={{
              padding: '12px 24px',
              border: '2px solid #d1d5db',
              borderRadius: '8px',
              backgroundColor: 'white',
              color: '#374151',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s',
              outline: 'none'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f9fafb';
              e.currentTarget.style.borderColor = '#9ca3af';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'white';
              e.currentTarget.style.borderColor = '#d1d5db';
            }}
          >
            Cancel
          </button>
          <button 
            onClick={handleLogin}
            style={{
              padding: '12px 24px',
              border: 'none',
              borderRadius: '8px',
              background: 'linear-gradient(to right, #2563eb, #1d4ed8)',
              color: 'white',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s',
              outline: 'none',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'linear-gradient(to right, #1d4ed8, #1e40af)';
              e.currentTarget.style.transform = 'scale(1.02)';
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'linear-gradient(to right, #2563eb, #1d4ed8)';
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
            }}
          >
            Login
          </button>
        </div>
      </div>
    </div>
  );
}
