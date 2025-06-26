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
          padding: 20,
          borderRadius: 8,
          minWidth: 300,
        }}
      >
        <h2>Login Required</h2>
        <p>Email: {email}</p>
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={handleLogin}>Login</button>
        </div>
      </div>
    </div>
  );
}
