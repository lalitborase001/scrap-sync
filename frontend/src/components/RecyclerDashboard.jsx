import { useState, useEffect } from "react";

const API_URL = "http://127.0.0.1:3000/lots";
const CLAIM_API_URL = "http://127.0.0.1:3000/claim";

export default function RecyclerDashboard() {
  const [lots, setLots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [claimStatus, setClaimStatus] = useState({}); // { [lotId]: 'idle' | 'loading' | 'claimed' | 'error' }
  const [claimedDetails, setClaimedDetails] = useState({}); // { [lotId]: responseData }

  useEffect(() => {
    fetchLots();
    // Poll for new lots every 10 seconds
    const interval = setInterval(fetchLots, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchLots = async () => {
    try {
      const res = await fetch(API_URL);
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      setLots(data.lots || []);
      setError(null);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch lots");
    } finally {
      setLoading(false);
    }
  };

  const handleClaimScrap = async (lotId) => {
    if (claimStatus[lotId] === "loading" || claimStatus[lotId] === "claimed") {
      return;
    }

    setClaimStatus((prev) => ({ ...prev, [lotId]: "loading" }));

    try {
      const res = await fetch(CLAIM_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ item_id: lotId, lot_id: lotId }),
      });

      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }

      const data = await res.json();
      setClaimStatus((prev) => ({ ...prev, [lotId]: "claimed" }));
      setClaimedDetails((prev) => ({ ...prev, [lotId]: data }));
    } catch (err) {
      console.error("Error claiming scrap:", err);
      setClaimStatus((prev) => ({ ...prev, [lotId]: "error" }));
      alert(`Could not claim scrap: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#ccc" }}>
        Loading lots...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#ff6b6b" }}>
        {error}
      </div>
    );
  }

  if (lots.length === 0) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#ccc" }}>
        No e-waste lots available yet. Upload some scrap to get started!
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
      <h2 style={{ color: "#fff", marginBottom: "2rem" }}>
        Available E-Waste Lots ({lots.length})
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1.5rem" }}>
        {lots.map((lot) => (
          <div
            key={lot.LotId}
            style={{
              backgroundColor: "#2a2a4e",
              borderRadius: "8px",
              padding: "1.5rem",
              border: "1px solid #4a4a6a",
              transition: "transform 0.2s, box-shadow 0.2s",
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = "translateY(-4px)";
              e.target.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = "translateY(0)";
              e.target.style.boxShadow = "none";
            }}
          >
            {/* Image display or styled generic e-waste placeholder */}
            <div
              style={{
                width: "100%",
                height: "180px",
                backgroundColor: "#1a1a2e",
                borderRadius: "6px",
                marginBottom: "1rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
              }}
            >
              {lot.image_base64 ? (
                <img
                  src={
                    lot.image_base64.startsWith("data:")
                      ? lot.image_base64
                      : `data:image/jpeg;base64,${lot.image_base64}`
                  }
                  alt={`E-waste lot #${lot.LotId}`}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    borderRadius: "6px",
                  }}
                  onError={(e) => {
                    // If image data is invalid, hide broken image
                    e.target.style.display = "none";
                  }}
                />
              ) : (
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: "6px",
                    background: "linear-gradient(135deg, #1e1b4b 0%, #172554 50%, #0f172a 100%)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "1rem",
                    position: "relative",
                    overflow: "hidden",
                    border: "1px dashed #3b82f6",
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: "-20px",
                      right: "-20px",
                      width: "80px",
                      height: "80px",
                      background: "radial-gradient(circle, rgba(74, 222, 128, 0.2) 0%, transparent 70%)",
                      borderRadius: "50%",
                    }}
                  />
                  <svg
                    width="48"
                    height="48"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#4ade80"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ marginBottom: "0.5rem", filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))" }}
                  >
                    <rect x="4" y="4" width="16" height="16" rx="2" />
                    <rect x="9" y="9" width="6" height="6" />
                    <line x1="9" y1="1" x2="9" y2="4" />
                    <line x1="15" y1="1" x2="15" y2="4" />
                    <line x1="9" y1="20" x2="9" y2="23" />
                    <line x1="15" y1="20" x2="15" y2="23" />
                    <line x1="20" y1="9" x2="23" y2="9" />
                    <line x1="20" y1="14" x2="23" y2="14" />
                    <line x1="1" y1="9" x2="4" y2="9" />
                    <line x1="1" y1="14" x2="4" y2="14" />
                  </svg>
                  <span style={{ color: "#93c5fd", fontSize: "0.85rem", fontWeight: "600", letterSpacing: "0.5px" }}>
                    E-Waste Lot Specimen
                  </span>
                  <span style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "2px" }}>
                    ♻️ Ready for Recovery
                  </span>
                </div>
              )}
            </div>

            <h3 style={{ color: "#fff", marginBottom: "0.5rem", fontSize: "1.1rem" }}>
              Lot #{lot.LotId.slice(0, 8)}
            </h3>

            <div style={{ marginBottom: "1rem" }}>
              <p style={{ color: "#ccc", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                <strong>Items:</strong>
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {lot.items.map((item, idx) => (
                  <span
                    key={idx}
                    style={{
                      backgroundColor: "#4a4a6a",
                      color: "#fff",
                      padding: "0.25rem 0.75rem",
                      borderRadius: "12px",
                      fontSize: "0.8rem",
                    }}
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <p style={{ color: "#ccc", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                <strong>Estimated Value:</strong>
              </p>
              <p style={{ color: "#4ade80", fontSize: "1.5rem", fontWeight: "bold", margin: 0 }}>
                ₹{Number(lot.estimated_value).toLocaleString("en-IN")}
              </p>
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <p style={{ color: "#6a6a8a", fontSize: "0.8rem", margin: 0 }}>
                Posted {new Date(lot.created_at * 1000).toLocaleString()}
              </p>
            </div>

            {(() => {
              const status = claimStatus[lot.LotId];
              const isClaimed = status === "claimed";
              const isLoading = status === "loading";
              const details = claimedDetails[lot.LotId];

              let buttonText = "Claim Scrap";
              let buttonBg = "#4ade80";
              let buttonHoverBg = "#22c55e";
              let buttonColor = "#1a1a2e";

              if (isLoading) {
                buttonText = "Sending SMS...";
                buttonBg = "#f59e0b";
                buttonHoverBg = "#d97706";
                buttonColor = "#ffffff";
              } else if (isClaimed) {
                buttonText = "SMS Sent!";
                buttonBg = "#10b981";
                buttonHoverBg = "#059669";
                buttonColor = "#ffffff";
              }

              return (
                <div>
                  <button
                    onClick={() => handleClaimScrap(lot.LotId)}
                    disabled={isLoading || isClaimed}
                    style={{
                      width: "100%",
                      padding: "0.75rem",
                      backgroundColor: buttonBg,
                      color: buttonColor,
                      border: "none",
                      borderRadius: "4px",
                      fontSize: "1rem",
                      fontWeight: "bold",
                      cursor: isClaimed ? "default" : isLoading ? "wait" : "pointer",
                      transition: "all 0.2s ease-in-out",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.5rem",
                      boxShadow: isClaimed ? "0 2px 8px rgba(16, 185, 129, 0.4)" : "none",
                    }}
                    onMouseEnter={(e) => {
                      if (!isClaimed && !isLoading) {
                        e.target.style.backgroundColor = buttonHoverBg;
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isClaimed && !isLoading) {
                        e.target.style.backgroundColor = buttonBg;
                      }
                    }}
                  >
                    {isLoading && (
                      <span
                        style={{
                          display: "inline-block",
                          width: "14px",
                          height: "14px",
                          border: "2px solid #ffffff",
                          borderTopColor: "transparent",
                          borderRadius: "50%",
                          animation: "spin 1s linear infinite",
                        }}
                      />
                    )}
                    {isClaimed && <span>✓</span>}
                    {buttonText}
                  </button>

                  {isClaimed && details && details.pickup_address && (
                    <div
                      style={{
                        marginTop: "0.75rem",
                        padding: "0.75rem",
                        backgroundColor: "rgba(16, 185, 129, 0.15)",
                        border: "1px solid #10b981",
                        borderRadius: "6px",
                        fontSize: "0.85rem",
                        color: "#e2e8f0",
                      }}
                    >
                      <div style={{ color: "#34d399", fontWeight: "bold", marginBottom: "0.25rem" }}>
                        📍 Pickup Address (SMS Dispatched):
                      </div>
                      <div style={{ color: "#cbd5e1" }}>{details.pickup_address}</div>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        ))}
      </div>
    </div>
  );
}
