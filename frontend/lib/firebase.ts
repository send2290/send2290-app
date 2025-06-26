import { initializeApp } from "firebase/app"
import { getAuth }       from "firebase/auth"

// 🔍 Debug: verify env-vars are loaded in the browser console
console.log(
  "🔑 Firebase Config:",
  "apiKey=", process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  "authDomain=", process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
)

const firebaseConfig = {
  apiKey:            process.env.NEXT_PUBLIC_FIREBASE_API_KEY!,
  authDomain:        process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN!,
  projectId:         process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID!,
  storageBucket:     process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET!,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID!,
  appId:             process.env.NEXT_PUBLIC_FIREBASE_APP_ID!,
}

const app  = initializeApp(firebaseConfig)
export const auth = getAuth(app)
