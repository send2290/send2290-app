import { initializeApp } from "firebase/app"
import { getAuth } from "firebase/auth"

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyB-GOco8BVXsmuZ162C5wAn8KEOuvh2qMg",
  authDomain: "send2290-6c1a5.firebaseapp.com",
  projectId: "send2290-6c1a5",
  storageBucket: "send2290-6c1a5.firebasestorage.app",
  messagingSenderId: "421801300736",
  appId: "1:421801300736:web:a0085d6c161f11179559e5"
}

// Initialize Firebase
const app = initializeApp(firebaseConfig)

// ✅ Add this line to enable Firebase Authentication
export const auth = getAuth(app)
