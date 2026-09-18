import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AdminPanel from "./AdminPanel";
import { Wobbi } from "../character";

function renderSummary(text) {
  return text.split("\n").map((line, i) => {
    const parts = line.split(/(\*\*.*?\*\*)/g).map((part, j) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={j}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
    return (
      <span key={i}>
        {i > 0 && <br />}
        {parts}
      </span>
    );
  });
}

const SUGGESTIONS_PAR_DEFAUT = [
  "Qui est Arthur Mady ?",
  "Quel est son parcours professionnel ?",
  "Que recherche-t-il comme poste ?",
];

function ChatApp() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem("chat_messages");
    return saved ? JSON.parse(saved) : [];
  });
  const [resumes, setResumes] = useState(() => {
    const saved = localStorage.getItem("chat_resumes");
    return saved ? JSON.parse(saved) : [];
  });
  const [loading, setLoading] = useState(false);
  const [longWait, setLongWait] = useState(false);
  const [afficherResume, setAfficherResume] = useState(true);
  const [darkMode, setDarkMode] = useState(false);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("chat_session_id"));
  const [suggestions, setSuggestions] = useState(() => {
    const saved = localStorage.getItem("chat_suggestions");
    return saved ? JSON.parse(saved) : SUGGESTIONS_PAR_DEFAUT;
  });
  const [showWelcome, setShowWelcome] = useState(() => !localStorage.getItem("chat_session_id"));
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const API_URL = "";

  // Applique/enlève la classe "light" sur <html> selon le mode
  useEffect(() => {
    document.documentElement.classList.toggle("light", !darkMode);
  }, [darkMode]);

  // Scroll automatique vers le dernier message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Timer longue attente
  useEffect(() => {
    if (!loading) {
      setLongWait(false);
      return;
    }
    const timer = setTimeout(() => setLongWait(true), 13000);
    return () => clearTimeout(timer);
  }, [loading]);

  // Sauvegarde dans localStorage à chaque changement
  useEffect(() => {
    localStorage.setItem("chat_messages", JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    localStorage.setItem("chat_resumes", JSON.stringify(resumes));
  }, [resumes]);

  useEffect(() => {
    localStorage.setItem("chat_suggestions", JSON.stringify(suggestions));
  }, [suggestions]);

  // Restauration de la session depuis le backend au montage
  useEffect(() => {
    const sid = localStorage.getItem("chat_session_id");
    if (!sid) return;

    fetch(`${API_URL}/session/${sid}`)
      .then((res) => {
        if (!res.ok) throw new Error("session not found");
        return res.json();
      })
      .then((data) => {
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
          setSessionId(data.session_id);
          if (data.summary) {
            setResumes([data.summary]);
          }
        }
      })
      .catch(() => {
        localStorage.removeItem("chat_session_id");
        localStorage.removeItem("chat_messages");
        localStorage.removeItem("chat_resumes");
        localStorage.removeItem("chat_suggestions");
      });
  }, []);


  const envoyerQuestion = async (texteManuel) => {
    const texteAEnvoyer = (texteManuel ?? question).trim();
    if (!texteAEnvoyer || loading) return;

    const nouveauMessageUser = { role: "user", content: texteAEnvoyer };
    setMessages((prev) => [...prev, nouveauMessageUser]);
    setQuestion("");
    setSuggestions([]);
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, query: texteAEnvoyer }),
      });

      if (!response.ok) {
        throw new Error(`Erreur serveur : ${response.status}`);
      }

      const data = await response.json();

      // On ne met à jour le session_id que si l'appel a réussi,
      // pour ne jamais écraser une session valide avec une erreur.
      setSessionId(data.session_id);
      localStorage.setItem("chat_session_id", data.session_id);

      setMessages((prev) => [...prev, { role: "bot", content: data.response }]);

      if (data.summary) {
        setResumes((prev) => [...prev, data.summary]);
      }

      setSuggestions(data.suggestions || []);
    } catch (error) {
      console.error("Erreur lors de l'appel à l'API :", error);
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Erreur : impossible de joindre le serveur." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const envoyerSuggestion = (texte) => {
    if (loading) return;
    envoyerQuestion(texte);
  };

  const nouvelleConversation = () => {
    localStorage.removeItem("chat_session_id");
    localStorage.removeItem("chat_messages");
    localStorage.removeItem("chat_resumes");
    localStorage.removeItem("chat_suggestions");
    setSessionId(null);
    setMessages([]);
    setResumes([]);
    setSuggestions(SUGGESTIONS_PAR_DEFAUT);
    setShowWelcome(true);
  };

  const gererTouche = (e) => {
    if (e.key === "Enter" && !loading) envoyerQuestion();
  };

  return (
    <div className="flex h-screen text-foreground" data-gaze-zone="">
      {/* ---------- ZONE PRINCIPALE ---------- */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-3 py-3 md:px-6 md:py-4 border-b border-border">
          <div className="flex items-center gap-2 md:gap-3">
            <Wobbi state="idle" size={40} interactive={false} />
            <h1 className="text-sm md:text-lg font-semibold truncate">MadyGPT<span className="hidden md:inline"> : l'assistant personnel d'Arthur Mady</span></h1>
          </div>

          <div className="flex items-center gap-1.5 md:gap-3">
            <button
              onClick={nouvelleConversation}
              className="cursor-pointer rounded-lg border border-border px-2 py-1.5 md:px-3 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200"
              title="Nouvelle conversation"
            >
              <span className="md:hidden">+</span>
              <span className="hidden md:inline">Nouvelle conversation</span>
            </button>

            <button
              onClick={() => setDarkMode(!darkMode)}
              className="cursor-pointer rounded-lg border border-border px-2 py-1.5 md:px-3 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200"
              title={darkMode ? "Mode clair" : "Mode sombre"}
            >
              <span className="md:hidden">{darkMode ? "\u2600" : "\u263E"}</span>
              <span className="hidden md:inline">{darkMode ? "Mode clair" : "Mode sombre"}</span>
            </button>

            <a href="/cv_arthur_mady_freelance.pdf" target="_blank" rel="noopener noreferrer">
              <button className="cursor-pointer rounded-lg bg-accent text-on-accent px-2.5 py-1.5 md:px-4 text-sm font-medium hover:opacity-90 transition-opacity duration-200">
                <span className="md:hidden">CV</span>
                <span className="hidden md:inline">Voir mon CV</span>
              </button>
            </a>

            <button
              onClick={() => setAfficherResume(!afficherResume)}
              className="cursor-pointer rounded-lg border border-border px-2 py-1.5 md:px-3 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200 hidden md:block"
              title={afficherResume ? "Masquer résumé" : "Afficher résumé"}
            >
              {afficherResume ? "Masquer résumé" : "Afficher résumé"}
            </button>

            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="cursor-pointer rounded-lg border border-border px-2 py-1.5 md:px-3 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200 md:hidden"
              title="Résumé"
            >
              ☰
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-3 py-3 md:px-6 md:py-4 space-y-3 md:space-y-4">
          {messages.length === 0 && (
            <p className="text-muted text-sm">Présentez-vous et entamez la discussion !</p>
          )}

          {messages.map((msg, index) => {
            const isLastBot = msg.role === "bot" && index === messages.length - 1;
            return (
              <div
                key={index}
                className={`flex items-end gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "bot" && (
                  <div className={`relative z-10 shrink-0 mb-1 ${isLastBot ? "" : "hidden"}`}>
                    <Wobbi state={isLastBot && question.length > 0 ? "sleeping" : "idle"} size={60} interactive={isLastBot} tabIndex={-1} onMouseDown={(e) => e.preventDefault()} className="md:hidden" style={{ transform: 'translateX(-8px)' }} />
                    <Wobbi state={isLastBot && question.length > 0 ? "sleeping" : "idle"} size={120} interactive={isLastBot} tabIndex={-1} onMouseDown={(e) => e.preventDefault()} className="hidden md:block" style={{ transform: 'translateX(-12px)' }} />
                  </div>
                )}
              <div
                className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-3 py-2 md:px-4 md:py-2.5 text-sm md:text-base leading-relaxed ${
                  msg.role === "user"
                    ? "bg-accent text-on-accent"
                    : "bg-card text-foreground border border-border"
                }`}
              >
                {msg.role === "bot" ? (
                  <div className={`chat-bubble prose prose-base max-w-none ${darkMode ? "prose-invert" : ""}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({node, ...props}) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
            );
          })}

          {loading && (
            <div className="flex items-end gap-2 justify-start">
              <div className="relative z-10 shrink-0 mb-1">
                <Wobbi state="thinking" size={60} interactive={false} className="md:hidden" style={{ transform: 'translateX(-8px)' }} />
                <Wobbi state="thinking" size={120} interactive={false} className="hidden md:block" style={{ transform: 'translateX(-12px)' }} />
              </div>

              <div className="bg-card border border-border rounded-2xl px-3 py-2 md:px-4 md:py-2.5 flex items-center gap-2 md:gap-3">
                <span className="text-xs md:text-sm text-muted">
                  {longWait ? "   J'ai bientôt la réponse, patientez encore un peu" : "   Je cherche"}
                </span>

                <div className="flex gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-accent animate-bounce [animation-delay:-0.3s]"></span>
                  <span className="w-2 h-2 rounded-full bg-accent animate-bounce [animation-delay:-0.15s]"></span>
                  <span className="w-2 h-2 rounded-full bg-accent animate-bounce"></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions de questions */}
        {suggestions.length > 0 && !loading && (
          <div className="px-3 pb-2 md:px-6 flex flex-wrap gap-1.5 md:gap-2">
            {suggestions.map((texte, index) => (
              <button
                key={index}
                onClick={() => envoyerSuggestion(texte)}
                className="cursor-pointer rounded-full bg-accent text-on-accent text-xs md:text-sm font-medium px-2.5 py-1 md:px-3.5 md:py-1.5 hover:opacity-80 transition-opacity duration-200"
              >
                {texte}
              </button>
            ))}
          </div>
        )}

        {/* Zone de saisie */}
        <div className="border-t border-border px-3 py-3 md:px-6 md:py-4">
          <div className="flex items-center gap-2 md:gap-3 rounded-xl border border-border bg-card px-3 py-2 md:px-4 md:py-2.5 focus-within:border-accent transition-colors duration-200">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={gererTouche}
              placeholder="Posez votre question..."
              disabled={loading}
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-foreground/50 disabled:opacity-50"
            />
            <button
              onClick={() => envoyerQuestion()}
              disabled={loading || !question.trim()}
              className="cursor-pointer rounded-lg bg-accent text-on-accent px-3 py-1.5 md:px-4 text-sm font-medium hover:opacity-90 transition-opacity duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Envoyer
            </button>
          </div>
        </div>
      </div>

      {/* ---------- SIDEBAR RÉSUMÉ ---------- */}
      {/* Overlay mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {afficherResume && (
        <aside className={`
          fixed inset-y-0 right-0 z-50 w-72 shrink-0 border-l border-border bg-card px-4 py-4 overflow-y-auto transition-transform duration-300
          md:static md:translate-x-0
          ${sidebarOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"}
        `}>
          <div className="flex items-center justify-between mb-3 md:block">
            <h2 className="text-sm font-semibold text-muted uppercase tracking-wide">
              Résumé
            </h2>
            <button
              onClick={() => setSidebarOpen(false)}
              className="cursor-pointer text-muted hover:text-foreground md:hidden text-lg"
            >
              ✕
            </button>
          </div>
          {resumes.length === 0 ? (
            <p className="text-sm text-muted">Aucun résumé pour l'instant.</p>
          ) : (
            <div className="space-y-3">
              {resumes.map((point, index) => (
                <div key={index} className="text-sm text-foreground leading-relaxed">
                  {renderSummary(point)}
                </div>
              ))}
            </div>
          )}
        </aside>
      )}

      {/* ---------- POPUP BIENVENUE ---------- */}
      {showWelcome && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="relative bg-card border border-border rounded-3xl shadow-2xl p-6 md:p-8 max-w-lg md:max-w-2xl w-full flex flex-col items-center gap-4 md:gap-6 animate-popup">
            <div className="w-24 h-24 md:w-40 md:h-40">
              <Wobbi state="idle" size={160} interactive={true} tabIndex={-1} role="img" />
            </div>

            <div className="relative bg-background border border-border rounded-2xl px-4 py-3 md:px-6 md:py-4 text-sm text-foreground leading-relaxed text-center">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[10px] border-l-transparent border-r-[10px] border-r-transparent border-b-[12px] border-b-border"></div>
              <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-b-[10px] border-b-background"></div>
              <p>
                <strong>Bienvenue !</strong><br />
                Je suis l'assistant personnel d'Arthur Mady.<br />
                <span className="hidden md:inline">Je peux répondre à toutes les questions que vous pouvez avoir sur lui.<br /></span>
                Vous pouvez poser vos propres questions ou utiliser une suggestion.
              </p>
            </div>

            <button
              onClick={() => setShowWelcome(false)}
              className="cursor-pointer rounded-xl bg-accent text-on-accent px-6 py-2.5 md:px-8 md:py-3 text-sm font-semibold hover:opacity-90 transition-opacity duration-200 shadow-lg"
            >
              Allons-y
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  if (window.location.pathname === "/admin") {
    return <AdminPanel />;
  }
  return <ChatApp />;
}