import { useState } from "react";

export default function Navbar({ currentView, onViewChange }) {
  return (
    <nav style={{
      backgroundColor: "#1a1a2e",
      padding: "1rem 2rem",
      borderBottom: "1px solid #4a4a6a",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <div style={{ color: "#fff", fontSize: "1.5rem", fontWeight: "bold" }}>
        Scrap-Sync
      </div>
      <div style={{ display: "flex", gap: "1rem" }}>
        <button
          onClick={() => onViewChange("upload")}
          style={{
            padding: "0.5rem 1.5rem",
            backgroundColor: currentView === "upload" ? "#4a4a6a" : "#2a2a4e",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            transition: "background-color 0.2s",
          }}
          onMouseEnter={(e) => e.target.style.backgroundColor = currentView === "upload" ? "#5a5a7a" : "#3a3a5e"}
          onMouseLeave={(e) => e.target.style.backgroundColor = currentView === "upload" ? "#4a4a6a" : "#2a2a4e"}
        >
          Upload Scrap
        </button>
        <button
          onClick={() => onViewChange("dashboard")}
          style={{
            padding: "0.5rem 1.5rem",
            backgroundColor: currentView === "dashboard" ? "#4a4a6a" : "#2a2a4e",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            transition: "background-color 0.2s",
          }}
          onMouseEnter={(e) => e.target.style.backgroundColor = currentView === "dashboard" ? "#5a5a7a" : "#3a3a5e"}
          onMouseLeave={(e) => e.target.style.backgroundColor = currentView === "dashboard" ? "#4a4a6a" : "#2a2a4e"}
        >
          Recycler Dashboard
        </button>
      </div>
    </nav>
  );
}
