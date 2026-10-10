import UploadForm from './components/UploadForm'
import './App.css'

function App() {
  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Scrap-Sync: E-Waste Bidding Marketplace</h1>
      <p>Upload e-waste images for AI-powered valuation</p>
      <UploadForm idToken={null} />
    </div>
  )
}

export default App
