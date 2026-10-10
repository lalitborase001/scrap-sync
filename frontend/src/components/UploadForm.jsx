import { useState } from "react";

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setStatus("uploading");

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
      setStatus("error");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        onChange={(e) => setFile(e.target.files[0] ?? null)}
      />
      <button type="submit" disabled={!file || status === "uploading"}>
        {status === "uploading" ? "Analyzing..." : "Upload e-waste lot"}
      </button>

      {status === "error" && <p>Something went wrong. Please try again.</p>}
      {status === "done" && result && (
        <div>
          <p>Lot {result.lot_id}</p>
          <p>Items: {JSON.stringify(result.items)}</p>
          <p>Estimated value: ₹{Number(result.estimated_value).toLocaleString("en-IN")}</p>
        </div>
      )}
    </form>
  );
}