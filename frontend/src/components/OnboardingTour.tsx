import { useState, useEffect } from "react";

const STORAGE_KEY = "aida_tour_seen";

export function hasTourBeenSeen(): boolean {
  return localStorage.getItem(STORAGE_KEY) === "1";
}

interface Step {
  icon: string;
  title: string;
  body: string;
  navTarget: "upload" | "chat" | null;
  /** % offset from card left edge where the upward arrow sits */
  arrowLeft: string;
}

const STEPS: Step[] = [
  {
    icon: "👋",
    title: "Welcome to AIDA",
    body: "AIDA is your personal AI document assistant. Ask questions about any document you upload — AIDA finds the relevant passages and answers directly from them.",
    navTarget: null,
    arrowLeft: "50%",
  },
  {
    icon: "📄",
    title: "Step 1 — Upload a document",
    body: "Go to the Upload page and drop in a PDF or text file. Your documents are stored privately under your user ID — other users can't see them unless you mark them public.",
    navTarget: "upload",
    arrowLeft: "38%",
  },
  {
    icon: "💬",
    title: "Step 2 — Ask questions",
    body: "Switch to Chat and type any question. AIDA retrieves the most relevant passages and generates a grounded answer. It won't make things up — if the answer isn't in your documents, it'll say so.",
    navTarget: "chat",
    arrowLeft: "54%",
  },
];

interface Props {
  onDismiss: () => void;
}

export default function OnboardingTour({ onDismiss }: Props) {
  const [step, setStep] = useState(0);
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  // Highlight the relevant nav button by adding a body class
  useEffect(() => {
    document.body.classList.remove("tour-highlight-upload", "tour-highlight-chat");
    if (current.navTarget === "upload") document.body.classList.add("tour-highlight-upload");
    if (current.navTarget === "chat") document.body.classList.add("tour-highlight-chat");
    return () => {
      document.body.classList.remove("tour-highlight-upload", "tour-highlight-chat");
    };
  }, [step, current.navTarget]);

  const handleNext = () => {
    if (isLast) {
      localStorage.setItem(STORAGE_KEY, "1");
      onDismiss();
    } else {
      setStep((s) => s + 1);
    }
  };

  const handleSkip = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    onDismiss();
  };

  const isAnchored = current.navTarget !== null;

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "rgba(0,0,0,0.55)",
      zIndex: 1000,
      display: "flex",
      // Steps pointing at nav buttons: anchor card below the navbar
      alignItems: isAnchored ? "flex-start" : "center",
      justifyContent: isAnchored ? "flex-start" : "center",
      padding: isAnchored ? "64px 1rem 1rem 12px" : "1rem",
    }}>
      <div style={{
        position: "relative",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow-lg)",
        width: "100%",
        maxWidth: 400,
        padding: "2rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
      }}>
        {/* Upward-pointing CSS triangle arrow aimed at the nav button */}
        {isAnchored && (
          <div style={{
            position: "absolute",
            top: -13,
            left: current.arrowLeft,
            transform: "translateX(-50%)",
            width: 0,
            height: 0,
            borderLeft: "9px solid transparent",
            borderRight: "9px solid transparent",
            borderBottom: "13px solid var(--surface)",
            filter: "drop-shadow(0 -2px 1px rgba(0,0,0,0.15))",
          }} />
        )}
        {/* Step icon + header */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>{current.icon}</div>
          <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "var(--text-h)" }}>
            {current.title}
          </h2>
        </div>

        {/* Body */}
        <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.65, color: "var(--text)", textAlign: "center" }}>
          {current.body}
        </p>

        {/* Step dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: "0.4rem" }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: 8, height: 8,
              borderRadius: "50%",
              background: i === step ? "var(--accent)" : "var(--border)",
              transition: "background 0.2s",
            }} />
          ))}
        </div>

        {/* Buttons */}
        <div style={{ display: "flex", gap: "0.75rem" }}>
          {!isLast && (
            <button
              onClick={handleSkip}
              style={{
                flex: 1,
                padding: "0.6rem",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--text)",
                fontSize: "0.875rem",
                cursor: "pointer",
              }}
            >
              Skip
            </button>
          )}
          <button
            onClick={handleNext}
            style={{
              flex: 2,
              padding: "0.6rem",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--accent)",
              color: "white",
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {isLast ? "Got it, let's go!" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}
