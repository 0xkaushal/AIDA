import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: "1rem 2rem", background: "#1a1a2e", display: "flex", gap: "2rem", alignItems: "center" }}>
        <span style={{ color: "white", fontWeight: "bold", fontSize: "1.2rem" }}>AIDA</span>
        <Link to="/" style={{ color: "#a0c4ff", textDecoration: "none" }}>Upload</Link>
        <Link to="/chat" style={{ color: "#a0c4ff", textDecoration: "none" }}>Chat</Link>
      </nav>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

