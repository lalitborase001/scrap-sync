import { useState, useRef } from "react";

// TODO: after `sam deploy`, copy the AnalyzeApiUrl output into VITE_API_URL (or paste it here).
const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://127.0.0.1:3000/analyze";

// Read a File as raw base64 (strips the "data:...;base64," prefix).
const toBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

// idToken: the Cognito ID token of the signed-in user (e.g. from Amplify Auth).
export default function UploadForm({ idToken }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type.startsWith("image/")) {
        setFile(droppedFile);
      } else {
        setErrorMsg("Please upload an image file.");
        setStatus("error");
      }
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    
    // Size check: limit to 5MB to prevent issues
    if (file.size > 5 * 1024 * 1024) {
      setErrorMsg("File is too large. Please upload an image under 5MB.");
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setErrorMsg("");
    setResult(null);

    try {
      const headers = {
        "Content-Type": "application/json",
      };
      // Only add Authorization header if not using local API
      if (!API_URL.includes("127.0.0.1") && idToken) {
        headers.Authorization = idToken;
      }

      const res = await fetch(API_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({
          content_type: file.type,
          image_base64: await toBase64(file),
        }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      setResult(await res.json());
      setStatus("done");
    } catch (err) {
      console.error(err);
      setErrorMsg("Something went wrong with the upload. Please try again.");
      setStatus("error");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <div 
        className={`dropzone ${dragActive ? "active" : ""} ${file ? "has-file" : ""}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleChange}
          style={{ display: "none" }}
        />
        {file ? (
          <p className="file-info">Ready to upload: <strong>{file.name}</strong></p>
        ) : (
          <div className="upload-prompt">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="upload-icon"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            <p>Drag and drop an image here, or <span>click to browse</span></p>
          </div>
        )}
      </div>

      <button className="submit-button" type="submit" disabled={!file || status === "uploading"}>
        {status === "uploading" ? "Analyzing..." : "Upload e-waste lot"}
      </button>

      {status === "error" && <p className="error-message">{errorMsg}</p>}
      {status === "done" && result && (
        <div className="result-card">
          <h3>Analysis Complete</h3>
          <div className="result-row">
            <span className="result-label">Lot ID:</span>
            <span className="result-value">{result.lot_id}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Items identified:</span>
            <span className="result-value">
              {Array.isArray(result.items) ? result.items.join(", ") : JSON.stringify(result.items)}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Estimated value:</span>
            <span className="result-value">₹{Number(result.estimated_value).toLocaleString("en-IN")}</span>
          </div>
        </div>
      )}
    </form>
  );
}