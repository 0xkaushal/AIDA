import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import "./App.css";

export default function App() {
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
      </nav>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

