// lib/firebaseAdmin.ts
import * as admin from 'firebase-admin'

const serviceAccount = JSON.parse(process.env.FIREBASE_ADMIN_KEY_JSON || '{}')

export function initAdmin() {
  if (!admin.apps.length) {
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount),
    })
  }
}
