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
    <div className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-md mx-auto border border-gray-100">
      <h2 className="text-3xl font-bold mb-6 text-center text-gray-800">
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
            className="border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 p-3 w-full mb-4 rounded-lg transition-all duration-200 outline-none"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 p-3 w-full mb-6 rounded-lg transition-all duration-200 outline-none"
          />
          <button
            type="submit"
            className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-blue-300 focus:ring-opacity-50"
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => setShowReset(true)}
            className="mt-3 text-center text-sm text-blue-600 hover:text-blue-800 underline w-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-opacity-50 rounded py-1"
          >
            Forgot Password?
          </button>
          <button
            type="button"
            onClick={() => setShowRegister(true)}
            className="mt-2 text-center text-sm text-blue-600 hover:text-blue-800 underline w-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-opacity-50 rounded py-1"
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
            className="border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 p-3 w-full mb-4 rounded-lg transition-all duration-200 outline-none"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 p-3 w-full mb-6 rounded-lg transition-all duration-200 outline-none"
          />
          <button
            type="submit"
            className="w-full bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-green-300 focus:ring-opacity-50"
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
            className="mt-3 text-center text-sm text-blue-600 hover:text-blue-800 underline w-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-opacity-50 rounded py-1"
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
            className="border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 p-3 w-full mb-6 rounded-lg transition-all duration-200 outline-none"
          />
          <button
            type="submit"
            className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-blue-300 focus:ring-opacity-50"
          >
            Send Password Reset Email
          </button>
          <button
            type="button"
            onClick={() => setShowReset(false)}
            className="mt-3 text-center text-sm text-blue-600 hover:text-blue-800 underline w-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-opacity-50 rounded py-1"
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
