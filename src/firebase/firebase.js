import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyCHXMD_hYm_ZeHTAKGGMotJ5yaLP5diYBs",
  authDomain: "ecorefill-911ba.firebaseapp.com",
  projectId: "ecorefill-911ba",
  storageBucket: "ecorefill-911ba.firebasestorage.app",
  messagingSenderId: "121994549339",
  appId: "1:121994549339:web:a2ec7e198e08936228477e"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const db = getFirestore(app);