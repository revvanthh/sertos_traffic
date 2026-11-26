
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { setOptions } from '@googlemaps/js-api-loader'
import { getGoogleMapsApiKey } from './config/env'

import './index.css'
import App from './App.tsx'

// Configure Google Maps once, before React renders.
const apiKey = getGoogleMapsApiKey()

if (!apiKey) {
  console.warn('Google Maps API key is missing. Map features will show setup guidance or fallback to vector maps.')
} else {
  setOptions({
    key: apiKey,
    v: 'weekly',
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
