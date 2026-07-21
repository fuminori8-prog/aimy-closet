import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'

const firebaseConfig = {
  apiKey: 'AIzaSyBwwrz2Pm85qqiaGthp7kWH_dj_grxKyeg',
  authDomain: 'aimy-closet.firebaseapp.com',
  projectId: 'aimy-closet',
  storageBucket: 'aimy-closet.firebasestorage.app',
  messagingSenderId: '924654277251',
  appId: '1:924654277251:web:99f2b30d75c50fb66a41b6',
}

const app = initializeApp(firebaseConfig)

export const auth = getAuth(app)
export const db = getFirestore(app)
