import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const SUGGESTIONS_PAR_DEFAUT = [
  "Qui est Arthur Mady ?",
  "Quels services propose-t-il ?",
  "Quel est son parcours professionnel ?",
];

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [afficherResume, setAfficherResume] = useState(true);
  const [darkMode, setDarkMode] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [suggestions, setSuggestions] = useState(SUGGESTIONS_PAR_DEFAUT);
  const messagesEndRef = useRef(null);
  const API_URL = import.meta.env.VITE_API_URL;

  // Applique/enlève la classe "light" sur <html> selon le mode
  useEffect(() => {
    document.documentElement.classList.toggle("light", !darkMode);
  }, [darkMode]);

  // Scroll automatique vers le dernier message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);


  const envoyerQuestion = async (texteManuel) => {
    const texteAEnvoyer = (texteManuel ?? question).trim();
    if (!texteAEnvoyer || loading) return; // garde anti double-envoi

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

  const gererTouche = (e) => {
    if (e.key === "Enter" && !loading) envoyerQuestion();
  };

  return (
    <div className="flex h-screen text-foreground">
      {/* ---------- ZONE PRINCIPALE ---------- */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h1 className="text-lg font-semibold">Assistant d'Arthur Mady</h1>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="cursor-pointer rounded-lg border border-border px-3 py-1.5 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200"
            >
              {darkMode ? "Mode clair" : "Mode sombre"}
            </button>

            <a href="/cv_arthur_mady_freelance.pdf" target="_blank" rel="noopener noreferrer">
              <button className="cursor-pointer rounded-lg bg-accent text-on-accent px-4 py-1.5 text-sm font-medium hover:opacity-90 transition-opacity duration-200">
                Voir mon CV
              </button>
            </a>

            <button
              onClick={() => setAfficherResume(!afficherResume)}
              className="cursor-pointer rounded-lg border border-border px-3 py-1.5 text-sm text-muted hover:text-foreground hover:border-accent transition-colors duration-200"
            >
              {afficherResume ? "Masquer résumé" : "Afficher résumé"}
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <p className="text-muted text-sm">Bonjour, je suis l'assistant d'Arthur Mady. Je suis là pour répondre à toutes les questions que vous pouvez avoir sur lui.</p>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex items-end gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "bot" && (
                <img
                  src="/happy.png"
                  alt="Assistant d'Arthur Mady"
                  className="w-14 h-14 rounded-full shrink-0 mb-1 object-cover"
                />
              )}
              <div
                className={`max-w-[70%] rounded-2xl px-4 py-2.5 text-base leading-relaxed ${
                  msg.role === "user"
                    ? "bg-accent text-on-accent"
                    : "bg-card text-foreground border border-border"
                }`}
              >
                {msg.role === "bot" ? (
                  <div className={`prose prose-base max-w-none ${darkMode ? "prose-invert" : ""}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-end gap-2 justify-start">
              <img
                src="/thinking.png"
                alt="Assistant d'Arthur Mady"
                className="w-14 h-14 rounded-full shrink-0 mb-1 object-cover"
              />

              <div className="bg-card border border-border rounded-2xl px-4 py-2.5 flex items-center gap-3">
                <span className="text-sm text-muted">
                  Je fouille dans les informations que j'ai
                </span>

                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce [animation-delay:-0.3s]"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce [animation-delay:-0.15s]"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce"></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions de questions */}
        {suggestions.length > 0 && !loading && (
          <div className="px-6 pb-2 flex flex-wrap gap-2">
            {suggestions.map((texte, index) => (
              <button
                key={index}
                onClick={() => envoyerSuggestion(texte)}
                className="cursor-pointer rounded-full border border-border bg-card text-sm text-foreground px-3.5 py-1.5 hover:border-accent hover:text-accent transition-colors duration-200"
              >
                {texte}
              </button>
            ))}
          </div>
        )}

        {/* Zone de saisie */}
        <div className="border-t border-border px-6 py-4">
          <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5 focus-within:border-accent transition-colors duration-200">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={gererTouche}
              placeholder="Posez votre question..."
              disabled={loading}
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-muted disabled:opacity-50"
            />
            <button
              onClick={() => envoyerQuestion()}
              disabled={loading || !question.trim()}
              className="cursor-pointer rounded-lg bg-accent text-on-accent px-4 py-1.5 text-sm font-medium hover:opacity-90 transition-opacity duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Envoyer
            </button>
          </div>
        </div>
      </div>

      {/* ---------- SIDEBAR RÉSUMÉ ---------- */}
      {afficherResume && (
        <aside className="w-72 shrink-0 border-l border-border bg-card px-4 py-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
            Résumé
          </h2>
          {resumes.length === 0 ? (
            <p className="text-sm text-muted">Aucun résumé pour l'instant.</p>
          ) : (
            <ul className="space-y-2">
              {resumes.map((point, index) => (
                <li key={index} className="text-sm text-foreground leading-relaxed">
                  {point}
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}
    </div>
  );
}

export default App;