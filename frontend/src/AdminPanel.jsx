import { useState, useEffect } from "react";

function parseUserAgent(ua) {
  if (!ua) return null;
  let browser = "unknown";
  if (ua.includes("Firefox/")) browser = "Firefox";
  else if (ua.includes("Edg/")) browser = "Edge";
  else if (ua.includes("Chrome/")) browser = "Chrome";
  else if (ua.includes("Safari/") && !ua.includes("Chrome")) browser = "Safari";

  let os = "unknown";
  if (ua.includes("Windows NT 10")) os = "Windows 10+";
  else if (ua.includes("Windows")) os = "Windows";
  else if (ua.includes("Mac OS X")) os = "macOS";
  else if (ua.includes("Linux") && !ua.includes("Android")) os = "Linux";
  else if (ua.includes("Android")) os = "Android";
  else if (ua.includes("iPhone") || ua.includes("iPad")) os = "iOS";

  let device = "desktop";
  if ((ua.includes("Mobile") || ua.includes("Android")) && !ua.includes("Tablet")) device = "mobile";
  else if (ua.includes("iPhone") || ua.includes("iPad")) device = "mobile";

  return `${browser} on ${os} — ${device}`;
}

async function authFetch(url, options = {}) {
  return fetch(url, { ...options, credentials: "include" });
}

function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`cursor-pointer px-3 py-1.5 md:px-4 md:py-2 text-xs md:text-sm font-medium rounded-lg transition-colors duration-200 whitespace-nowrap ${
        active
          ? "bg-accent text-on-accent"
          : "text-muted hover:text-foreground hover:bg-card"
      }`}
    >
      {label}
    </button>
  );
}

function LoginForm({ onLogin }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(false);
    try {
      const res = await fetch("/admin/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (data.ok) {
        onLogin();
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <form onSubmit={submit} className="bg-card border border-border rounded-2xl p-6 md:p-8 w-full max-w-sm space-y-4">
        <h2 className="text-lg font-semibold text-foreground text-center">Connexion Admin</h2>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mot de passe"
          autoFocus
          className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted outline-none focus:border-accent transition-colors"
        />
        {error && <p className="text-sm text-destructive">Mot de passe incorrect</p>}
        <button
          type="submit"
          disabled={loading || !password}
          className="cursor-pointer w-full rounded-lg bg-accent text-on-accent px-4 py-2.5 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? "Connexion..." : "Se connecter"}
        </button>
      </form>
    </div>
  );
}

function StatsTab() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    authFetch("/admin/stats")
      .then((r) => r.json())
      .then(setStats);
  }, []);

  if (!stats) return <p className="text-muted text-sm">Chargement...</p>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 md:gap-4">
      {[
        { label: "Sessions", value: stats.total_sessions },
        { label: "Messages totaux", value: stats.total_messages },
        { label: "Requêtes utilisateur", value: stats.total_user_queries },
      ].map((item) => (
        <div key={item.label} className="bg-card border border-border rounded-xl p-4">
          <p className="text-2xl font-bold text-foreground">{item.value}</p>
          <p className="text-sm text-muted mt-1">{item.label}</p>
        </div>
      ))}
    </div>
  );
}

function SessionsTab() {
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(null);

  const load = () => {
    authFetch("/admin/sessions")
      .then((r) => r.json())
      .then(setSessions);
  };

  useEffect(load, []);

  const viewSession = (id) => {
    authFetch(`/admin/sessions/${id}`)
      .then((r) => r.json())
      .then(setSelected);
  };

  const deleteSession = async (id) => {
    if (!confirm("Supprimer cette session ?")) return;
    await authFetch(`/admin/sessions/${id}`, { method: "DELETE" });
    setSelected(null);
    load();
  };

  const formatDate = (ts) => new Date(ts * 1000).toLocaleString("fr-FR");

  if (selected) {
    return (
      <div>
        <button
          onClick={() => setSelected(null)}
          className="cursor-pointer text-sm text-accent hover:underline mb-4"
        >
          ← Retour à la liste
        </button>
        {selected.user_agent && (
          <p className="text-xs text-muted mb-3">
            User-Agent : {parseUserAgent(selected.user_agent) || selected.user_agent}
          </p>
        )}
        <div className="space-y-2">
          {selected.messages?.map((msg, i) => (
            <div
              key={i}
              className={`rounded-xl px-3 py-2 md:px-4 md:py-2.5 max-w-[90%] md:max-w-[80%] ${
                msg.role === "user"
                  ? "bg-accent text-on-accent ml-auto"
                  : "bg-card border border-border text-foreground"
              }`}
              style={{ textAlign: msg.role === "user" ? "right" : "left", color: msg.role === "user" ? "#000000" : undefined }}
            >
              <p className="text-base">{msg.content}</p>
              <p className="text-xs mt-1" style={{ color: msg.role === "user" ? "#000000" : undefined }}>{formatDate(msg.timestamp)}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      {sessions.length === 0 ? (
        <p className="text-muted text-sm">Aucune session.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className="flex flex-col sm:flex-row sm:items-center justify-between bg-card border border-border rounded-xl px-3 py-3 md:px-4 gap-2"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {s.session_id}
                </p>
                <p className="text-xs text-muted">
                  {formatDate(s.created_at)} — {s.message_count} messages
                </p>
                {s.user_agent && (
                  <p className="text-xs text-muted mt-0.5">
                    {parseUserAgent(s.user_agent) || s.user_agent}
                  </p>
                )}
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => viewSession(s.session_id)}
                  className="cursor-pointer text-xs text-accent hover:underline"
                >
                  Voir
                </button>
                <button
                  onClick={() => deleteSession(s.session_id)}
                  className="cursor-pointer text-xs text-destructive hover:underline"
                >
                  Supprimer
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DataTab() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const load = () => {
    authFetch("/admin/data")
      .then((r) => r.json())
      .then(setFiles);
  };

  useEffect(load, []);

  const upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    await authFetch("/admin/data", { method: "POST", body: form });
    setUploading(false);
    load();
  };

  const deleteFile = async (name) => {
    if (!confirm(`Supprimer ${name} ?`)) return;
    await authFetch(`/admin/data/${name}`, { method: "DELETE" });
    load();
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    return (bytes / 1024).toFixed(1) + " KB";
  };

  return (
    <div>
      <div className="flex items-center gap-4 mb-4">
        <label className="cursor-pointer rounded-lg bg-accent text-on-accent px-4 py-1.5 text-sm font-medium hover:opacity-90 transition-opacity">
          {uploading ? "Envoi..." : "Uploader un JSON"}
          <input type="file" accept=".json" onChange={upload} className="hidden" />
        </label>
      </div>

      {files.length === 0 ? (
        <p className="text-muted text-sm">Aucun fichier.</p>
      ) : (
        <div className="space-y-2">
          {files.map((f) => (
            <div
              key={f.name}
              className="flex flex-col sm:flex-row sm:items-center justify-between bg-card border border-border rounded-xl px-3 py-3 md:px-4 gap-2"
            >
              <div>
                <p className="text-sm font-medium text-foreground">{f.name}</p>
                <p className="text-xs text-muted">
                  {formatSize(f.size)} — {new Date(f.modified * 1000).toLocaleString("fr-FR")}
                </p>
              </div>
              <button
                onClick={() => deleteFile(f.name)}
                className="cursor-pointer text-xs text-destructive hover:underline"
              >
                Supprimer
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GitHubTab() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const refresh = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await authFetch("/admin/refresh-github", { method: "POST" });
      const data = await res.json();
      setResult(data);
    } catch {
      setResult({ error: "Erreur lors du refresh" });
    }
    setLoading(false);
  };

  return (
    <div>
      <button
        onClick={refresh}
        disabled={loading}
        className="cursor-pointer rounded-lg bg-accent text-on-accent px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {loading ? "Chargement..." : "Rafraîchir les données GitHub"}
      </button>

      {result && (
        <div className="mt-4 bg-card border border-border rounded-xl p-4">
          {result.error ? (
            <p className="text-sm text-destructive">{result.error}</p>
          ) : (
            <p className="text-sm text-foreground">
              {result.repos_count} repos récupérés → {result.file}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminPanel() {
  const [tab, setTab] = useState("stats");
  const [loggedIn, setLoggedIn] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    authFetch("/admin/stats")
      .then((r) => {
        if (r.ok) setLoggedIn(true);
      })
      .finally(() => setChecking(false));
  }, []);

  const logout = async () => {
    await authFetch("/admin/logout", { method: "POST" });
    setLoggedIn(false);
  };

  if (checking) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted text-sm">Chargement...</p>
      </div>
    );
  }

  if (!loggedIn) {
    return <LoginForm onLogin={() => setLoggedIn(true)} />;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between px-4 py-3 md:px-6 md:py-4 border-b border-border">
        <h1 className="text-base md:text-lg font-semibold">Panel Admin</h1>
        <div className="flex gap-4">
          <button
            onClick={logout}
            className="cursor-pointer text-sm text-muted hover:text-foreground"
          >
            Déconnexion
          </button>
        </div>
      </header>

      <div className="px-4 py-3 md:px-6 md:py-4">
        <div className="flex gap-1.5 md:gap-2 mb-4 md:mb-6 border-b border-border pb-3 overflow-x-auto">
          <TabButton label="Stats" active={tab === "stats"} onClick={() => setTab("stats")} />
          <TabButton label="Sessions" active={tab === "sessions"} onClick={() => setTab("sessions")} />
          <TabButton label="Données" active={tab === "data"} onClick={() => setTab("data")} />
          <TabButton label="GitHub" active={tab === "github"} onClick={() => setTab("github")} />
        </div>

        {tab === "stats" && <StatsTab />}
        {tab === "sessions" && <SessionsTab />}
        {tab === "data" && <DataTab />}
        {tab === "github" && <GitHubTab />}
      </div>
    </div>
  );
}
