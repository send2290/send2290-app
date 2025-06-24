'use client'

import { useState } from 'react'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from 'firebase/auth'
import { auth } from '../lib/firebase'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage('')

    try {
      if (isCreating) {
        // ── CREATE ACCOUNT FLOW ──
        await createUserWithEmailAndPassword(auth, email, password)
        alert('✅ Account created successfully! You can now sign in.')
        setIsCreating(false)
        setEmail('')
        setPassword('')
        return
      }

      // ── SIGN IN FLOW ──
      const userCred = await signInWithEmailAndPassword(auth, email, password)
      const idToken = await userCred.user.getIdToken()

      // Call your protected endpoint using env var
      const apiBase = process.env.NEXT_PUBLIC_API_URL
      if (!apiBase) {
        throw new Error('Missing NEXT_PUBLIC_API_URL environment variable')
      }

      const res = await fetch(`${apiBase}/protected`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${idToken}` },
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Error ${res.status}: ${errText}`)
      }

      const data = await res.json()
      setMessage(data.message || '✅ Signed in successfully!')
    } catch (err: any) {
      console.error(err)
      setMessage(err.message || '❌ Authentication failed')
    }
  }

  return (
    <div className="bg-white p-6 rounded shadow-md w-full max-w-sm mx-auto">
      <h2 className="text-2xl font-bold mb-4 text-center">
        {isCreating ? 'Create Account' : 'Sign In'}
      </h2>

      <form onSubmit={handleSubmit}>
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
          {isCreating ? 'Create Account' : 'Sign In'}
        </button>
      </form>

      <button
        onClick={() => {
          setIsCreating(prev => !prev)
          setMessage('')
        }}
        className="mt-4 text-center text-sm text-blue-600 underline w-full"
      >
        {isCreating
          ? 'Already have an account? Sign In'
          : "Don't have an account? Create one"}
      </button>

      {message && (
        <p className="mt-4 text-center text-sm text-gray-700 bg-gray-100 rounded p-2">
          {message}
        </p>
      )}
    </div>
  )
}
