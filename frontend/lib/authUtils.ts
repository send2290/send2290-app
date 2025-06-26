// frontend/lib/authUtils.ts

import { 
  getAuth, 
  fetchSignInMethodsForEmail, 
  createUserWithEmailAndPassword 
} from 'firebase/auth'
import emailjs from '@emailjs/browser'

// ── Initialize EmailJS (once) ───────────────────────────────────────
if (process.env.NEXT_PUBLIC_EMAILJS_USER_ID) {
  emailjs.init(process.env.NEXT_PUBLIC_EMAILJS_USER_ID)
}

// ── 1) Password Generator ────────────────────────────────────────────
export function generatePassword(length = 12): string {
  const charset =
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()'
  let password = ''
  for (let i = 0; i < length; i++) {
    const randomIndex = Math.floor(Math.random() * charset.length)
    password += charset[randomIndex]
  }
  return password
}

// ── 2) Check if an email already has an account ──────────────────────
export async function checkUserExists(email: string): Promise<boolean> {
  const auth = getAuth()
  const methods = await fetchSignInMethodsForEmail(auth, email)
  return methods.length > 0
}

// ── 3) Create new user & email them their password ───────────────────
export async function createUserAndSendPassword(
  email: string
): Promise<boolean> {
  const auth     = getAuth()
  const password = generatePassword()

  try {
    // a) create in Firebase Auth
    const userCred = await createUserWithEmailAndPassword(
      auth,
      email,
      password
    )

    // b) send via EmailJS
    const templateParams = {
      to_email:            email,
      password:  password,
      user_uid:            userCred.user.uid,
    }

    await emailjs.send(
      process.env.NEXT_PUBLIC_EMAILJS_SERVICE_ID!,
      process.env.NEXT_PUBLIC_EMAILJS_TEMPLATE_ID!,
      templateParams
    )

    return true

  } catch (e: any) {
    // if they signed up in the meantime, skip email
    if (e.code === 'auth/email-already-in-use') {
      return false
    }
    // otherwise re-throw
    throw e
  }
}
