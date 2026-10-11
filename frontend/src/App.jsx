import { useState } from 'react'
import Navbar from './components/Navbar'
import UploadForm from './components/UploadForm'
import RecyclerDashboard from './components/RecyclerDashboard'
import './App.css'

function App() {
  const [currentView, setCurrentView] = useState('upload')

  return (
    <div style={{ backgroundColor: '#1a1a2e', minHeight: '100vh', color: '#fff' }}>
      <Navbar currentView={currentView} onViewChange={setCurrentView} />
      {currentView === 'upload' ? (
        <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
          <h1 style={{ marginBottom: '0.5rem' }}>Upload Scrap</h1>
          <p style={{ color: '#ccc', marginBottom: '2rem' }}>
            Upload e-waste images for AI-powered valuation
          </p>
          <UploadForm idToken={null} />
        </div>
      ) : (
        <RecyclerDashboard />
      )}
    </div>
  )
}

export default App
