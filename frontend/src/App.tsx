import { useState } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import UserIdGate, { getUserId, clearUserId } from "./components/UserIdGate";
import "./App.css";

export default function App() {
  const [userId, setUserId] = useState<string | null>(getUserId);

  if (!userId) {
    return <UserIdGate onConfirm={setUserId} />;
  }

  return (
    <BrowserRouter>
      <nav className="navbar">
        <NavLink to="/" className="navbar-brand">
          <div className="navbar-logo">A</div>
          <span className="navbar-title">AIDA</span>
        </NavLink>
        <NavLink to="/" end className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}>
          Upload
        </NavLink>
        <NavLink to="/chat" className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}>
          Chat
        </NavLink>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.8rem", color: "#64748b" }}>👤 {userId}</span>
          <button
            className="navbar-link"
            style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b", fontSize: "0.8rem" }}
            onClick={() => { clearUserId(); setUserId(null); }}
          >
            Switch
          </button>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<UploadPage userId={userId} />} />
        <Route path="/chat" element={<ChatPage userId={userId} />} />
      </Routes>
    </BrowserRouter>
  );
}

