'use client'

import { useState } from 'react'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
} from 'firebase/auth'
import { auth } from '../lib/firebase'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [resetSent, setResetSent] = useState(false)
  const [showReset, setShowReset] = useState(false)
  const [showRegister, setShowRegister] = useState(false)
  const [registerSuccess, setRegisterSuccess] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await signInWithEmailAndPassword(auth, email, password)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setRegisterSuccess(false)
    try {
      await createUserWithEmailAndPassword(auth, email, password)
      setRegisterSuccess(true)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setResetSent(false)
    try {
      await sendPasswordResetEmail(auth, email)
      setResetSent(true)
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="bg-white p-6 rounded shadow-md w-full max-w-sm mx-auto">
      <h2 className="text-2xl font-bold mb-4 text-center">
        {showReset
          ? 'Reset Password'
          : showRegister
          ? 'Create Account'
          : 'Sign In'}
      </h2>
      {!showReset && !showRegister && (
        <form onSubmit={handleLogin}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="border p-2 w-full mb-3 rounded"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="border p-2 w-full mb-4 rounded"
          />
          <button
            type="submit"
            className="bg-blue-600 text-white py-2 px-4 rounded w-full"
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => setShowReset(true)}
            className="mt-2 text-center text-sm text-blue-600 underline w-full"
          >
            Forgot Password?
          </button>
          <button
            type="button"
            onClick={() => setShowRegister(true)}
            className="mt-2 text-center text-sm text-blue-600 underline w-full"
          >
            Create Account
          </button>
          {error && <div className="text-red-500 text-sm mt-2">{error}</div>}
        </form>
      )}
      {showRegister && (
        <form onSubmit={handleRegister}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="border p-2 w-full mb-3 rounded"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="border p-2 w-full mb-4 rounded"
          />
          <button
            type="submit"
            className="bg-green-600 text-white py-2 px-4 rounded w-full"
          >
            Create Account
          </button>
          <button
            type="button"
            onClick={() => {
              setShowRegister(false)
              setRegisterSuccess(false)
              setError('')
            }}
            className="mt-2 text-center text-sm text-blue-600 underline w-full"
          >
            Back to Login
          </button>
          {registerSuccess && (
            <div className="text-green-500 text-sm mt-2">
              Account created! You are now signed in.
            </div>
          )}
          {error && <div className="text-red-500 text-sm mt-2">{error}</div>}
        </form>
      )}
      {showReset && (
        <form onSubmit={handleReset}>
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="border p-2 w-full mb-3 rounded"
          />
          <button
            type="submit"
            className="bg-blue-600 text-white py-2 px-4 rounded w-full"
          >
            Send Password Reset Email
          </button>
          <button
            type="button"
            onClick={() => setShowReset(false)}
            className="mt-2 text-center text-sm text-blue-600 underline w-full"
          >
            Back to Login
          </button>
          {resetSent && (
            <div className="text-green-500 text-sm mt-2">
              Password reset email sent!
            </div>
          )}
          {error && <div className="text-red-500 text-sm mt-2">{error}</div>}
        </form>
      )}
    </div>
  )
}
