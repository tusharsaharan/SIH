import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
// Geometric fallback for the Fractul voice — downloaded, self-hosted, offline-safe.
// If licensed Fractul woff2 files are added under src/assets/fonts, the
// @font-face rules in index.css take precedence automatically.
import '@fontsource/space-grotesk/300.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
