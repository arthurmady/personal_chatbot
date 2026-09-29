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

function FactView({ content }) {
  const facts = Array.isArray(content?.facts) ? content.facts : null;

  if (!facts) {
    return (
      <p className="text-sm text-muted">
        Structure inattendue : pas de tableau « facts ».
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {facts.map((fact, i) => (
        <div key={fact.id || i} className="bg-background border border-border rounded-xl p-4">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-xs font-mono text-accent">{fact.id}</span>
            {(fact.tags || []).map((t) => (
              <span
                key={t}
                className="text-[11px] rounded-full bg-card border border-border px-2 py-0.5 text-muted"
              >
                {t}
              </span>
            ))}
          </div>
          <p className="text-sm text-foreground mb-1">
            <span className="text-muted">Essentiel : </span>
            {fact.essential}
          </p>
          {fact.plus && (
            <p className="text-sm text-foreground mb-1">
              <span className="text-muted">Plus : </span>
              {fact.plus}
            </p>
          )}
          {(fact.details || []).length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-border pt-2">
              {fact.details.map((d) => (
                <li key={d.id} className="text-sm text-foreground">
                  <span className="font-mono text-xs text-muted">[$id: {d.id}]</span>{" "}
                  {d.content}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

function DataFileView({ name, onBack }) {
  const [data, setData] = useState(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    authFetch(`/admin/data/${encodeURIComponent(name)}`)
      .then((r) => r.json())
      .then(setData);
  }, [name]);

  if (!data) return <p className="text-muted text-sm">Chargement...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={onBack}
          className="cursor-pointer text-sm text-accent hover:underline"
        >
          ← Retour à la liste
        </button>
        <button
          onClick={() => setShowRaw((v) => !v)}
          className="cursor-pointer text-xs text-muted hover:text-foreground"
        >
          {showRaw ? "Vue structurée" : "JSON brut"}
        </button>
      </div>

      <p className="text-sm font-medium text-foreground mb-3">{name}</p>

      {data.error && !data.content ? (
        <pre className="bg-card border border-border rounded-xl p-4 text-xs text-destructive overflow-auto">
          {data.raw}
        </pre>
      ) : showRaw ? (
        <pre className="bg-card border border-border rounded-xl p-4 text-xs text-foreground overflow-auto max-h-[70vh]">
          {JSON.stringify(data.content, null, 2)}
        </pre>
      ) : (
        <FactView content={data.content} />
      )}
    </div>
  );
}

const INPUT_CLASS =
  "rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground outline-none focus:border-accent";

function FactEditor({ factId, entry, onChange }) {
  const [newId, setNewId] = useState("");
  const [newQuestion, setNewQuestion] = useState("");
  const inputClass = INPUT_CLASS;

  const addDetail = () => {
    const id = newId.trim();
    const question = newQuestion.trim();
    if (!id || !question) return;
    onChange({ ...entry, details: { ...entry.details, [id]: question } });
    setNewId("");
    setNewQuestion("");
  };

  const removeDetail = (dId) => {
    const details = { ...entry.details };
    delete details[dId];
    onChange({ ...entry, details });
  };

  return (
    <div className="bg-background border border-border rounded-xl p-4">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-xs font-mono text-accent">{factId}</span>
        {(entry.tags || []).map((t) => (
          <span
            key={t}
            className="text-[11px] rounded-full bg-card border border-border px-2 py-0.5 text-muted"
          >
            {t}
          </span>
        ))}
      </div>

      <label className="block text-xs font-medium text-muted mb-1">
        Résumé — 1 idée par ligne
      </label>
      <textarea
        value={entry.summary_text}
        onChange={(e) => onChange({ ...entry, summary_text: e.target.value })}
        rows={2}
        className={`${inputClass} w-full mb-3 resize-y`}
      />

      <p className="text-xs font-medium text-muted mb-1">Questions détail</p>
      <div className="space-y-1.5 mb-2">
        {Object.entries(entry.details).map(([dId, question]) => (
          <div key={dId} className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted w-40 shrink-0 truncate">
              [$id: {dId}]
            </span>
            <input
              value={question}
              onChange={(e) =>
                onChange({ ...entry, details: { ...entry.details, [dId]: e.target.value } })
              }
              className={`${inputClass} flex-1 min-w-0`}
            />
            <button
              onClick={() => removeDetail(dId)}
              className="cursor-pointer text-xs text-destructive"
              title="Retirer ce détail"
            >
              Retirer
            </button>
          </div>
        ))}
        {Object.keys(entry.details).length === 0 && (
          <p className="text-muted text-xs">Aucun détail.</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <input
          value={newId}
          onChange={(e) => setNewId(e.target.value)}
          placeholder="id_détail"
          className={`${inputClass} w-40 font-mono text-xs`}
        />
        <input
          value={newQuestion}
          onChange={(e) => setNewQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addDetail();
          }}
          placeholder="Question ?"
          className={`${inputClass} flex-1 min-w-0`}
        />
        <button onClick={addDetail} className="cursor-pointer text-xs text-accent">
          Ajouter
        </button>
      </div>
    </div>
  );
}

function DerivedView({ name, onBack }) {
  const [data, setData] = useState(null);
  const [source, setSource] = useState(null);
  const [showRaw, setShowRaw] = useState(false);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    authFetch(`/admin/data/${encodeURIComponent(name)}/derived`)
      .then((r) => r.json())
      .then(setData);
    authFetch(`/admin/data/${encodeURIComponent(name)}`)
      .then((r) => r.json())
      .then(setSource);
  }, [name, tick]);

  if (!data) return <p className="text-muted text-sm">Chargement...</p>;

  const sourceFacts = Array.isArray(source?.content?.facts) ? source.content.facts : [];
  const generated = data.error ? {} : data.content?.facts || {};
  const editing = draft !== null;

  const startEdit = () => {
    const base = JSON.parse(JSON.stringify(generated));
    for (const f of sourceFacts) {
      if (!base[f.id]) {
        base[f.id] = { tags: f.tags || [], summary_keywords: [], details: {} };
      }
      const entry = base[f.id];
      if (!Array.isArray(entry.tags) || entry.tags.length === 0) entry.tags = f.tags || [];
      if (!entry.details) entry.details = {};
      for (const d of f.details || []) {
        if (!(d.id in entry.details)) entry.details[d.id] = "";
      }
    }
    const facts = {};
    for (const [fid, e] of Object.entries(base)) {
      facts[fid] = {
        tags: e.tags || [],
        summary_text: (e.summary_keywords || []).join("\n"),
        details: { ...(e.details || {}) },
      };
    }
    const tags = { ...(data.content?.tags || {}) };
    for (const f of sourceFacts) {
      for (const t of f.tags || []) {
        if (!(t in tags)) tags[t] = "";
      }
    }
    setSaveError("");
    setShowRaw(false);
    setDraft({ tags, facts });
  };

  const updateEntry = (fid, next) =>
    setDraft((prev) => ({ ...prev, facts: { ...prev.facts, [fid]: next } }));

  const updateTag = (tag, value) =>
    setDraft((prev) => ({ ...prev, tags: { ...prev.tags, [tag]: value } }));

  const cancelEdit = () => {
    setDraft(null);
    setSaveError("");
  };

  const regenerate = async () => {
    if (!confirm(`Régénérer ${name} ?\nLes modifications manuelles seront perdues.`)) return;
    setRegenerating(true);
    const res = await authFetch(`/admin/data/${encodeURIComponent(name)}/recompute`, {
      method: "POST",
    });
    const out = await res.json();
    if (out.error) {
      setRegenerating(false);
      alert(out.error);
      return;
    }
    const poll = async () => {
      const list = await authFetch("/admin/data").then((r) => r.json());
      const entry = Array.isArray(list) ? list.find((f) => f.name === name) : null;
      if (entry?.derived?.status === "running") {
        setTimeout(poll, 2000);
        return;
      }
      setRegenerating(false);
      setTick((t) => t + 1);
    };
    poll();
  };

  const save = async () => {
    setSaving(true);
    setSaveError("");
    const facts = {};
    for (const [fid, e] of Object.entries(draft.facts)) {
      facts[fid] = {
        tags: e.tags || [],
        summary_keywords: e.summary_text.split("\n").map((s) => s.trim()).filter(Boolean),
        details: Object.fromEntries(
          Object.entries(e.details || {}).filter(([, q]) => q && q.trim())
        ),
      };
    }
    const base = data.error ? {} : data.content || {};
    const res = await authFetch(`/admin/data/${encodeURIComponent(name)}/derived`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: { ...base, tags: draft.tags, facts } }),
    });
    const out = await res.json();
    setSaving(false);
    if (out.error) {
      setSaveError(out.error);
      return;
    }
    setDraft(null);
    setTick((t) => t + 1);
  };

  const header = (
    <div className="flex items-center justify-between mb-4">
      <button
        onClick={onBack}
        className="cursor-pointer text-sm text-accent hover:underline"
      >
        ← Retour à la liste
      </button>
      <div className="flex items-center gap-3">
        {editing ? (
          <>
            <button
              onClick={cancelEdit}
              className="cursor-pointer text-xs text-muted hover:text-foreground"
            >
              Annuler
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="cursor-pointer rounded-lg bg-accent text-on-accent px-3 py-1.5 text-xs font-medium hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Enregistrement..." : "Enregistrer"}
            </button>
          </>
        ) : (
          <>
            <button
              onClick={regenerate}
              disabled={regenerating}
              className="cursor-pointer text-xs text-accent hover:underline disabled:opacity-50"
            >
              {regenerating ? "Régénération..." : "Régénérer"}
            </button>
            <button
              onClick={startEdit}
              className="cursor-pointer text-xs text-accent hover:underline"
            >
              Modifier
            </button>
            {!data.error && (
              <button
                onClick={() => setShowRaw((v) => !v)}
                className="cursor-pointer text-xs text-muted hover:text-foreground"
              >
                {showRaw ? "Vue structurée" : "JSON brut"}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );

  if (editing) {
    return (
      <div>
        {header}
        {saveError && <p className="text-sm text-destructive mb-3">{saveError}</p>}
        <div className="bg-background border border-border rounded-xl p-4 mb-3">
          <p className="text-xs font-medium text-muted mb-2">
            Suggestions par tag — 1 question par tag
          </p>
          <div className="space-y-1.5">
            {Object.entries(draft.tags).map(([tag, question]) => (
              <div key={tag} className="flex items-center gap-2">
                <span className="text-xs font-mono text-accent w-48 shrink-0 truncate">
                  {tag}
                </span>
                <input
                  value={question}
                  onChange={(e) => updateTag(tag, e.target.value)}
                  placeholder="Question ?"
                  className={`${INPUT_CLASS} flex-1 min-w-0`}
                />
              </div>
            ))}
            {Object.keys(draft.tags).length === 0 && (
              <p className="text-muted text-xs">Aucun tag dans la source.</p>
            )}
          </div>
        </div>
        <div className="space-y-3">
          {Object.entries(draft.facts).map(([fid, entry]) => (
            <FactEditor
              key={fid}
              factId={fid}
              entry={entry}
              onChange={(next) => updateEntry(fid, next)}
            />
          ))}
        </div>
      </div>
    );
  }

  if (data.error) {
    return (
      <div>
        {header}
        <p className="text-sm text-muted mb-3">
          Aucun contenu généré pour {name}.
        </p>
        <button
          onClick={startEdit}
          className="cursor-pointer rounded-lg bg-accent text-on-accent px-4 py-1.5 text-sm font-medium hover:opacity-90"
        >
          Créer à la main
        </button>
      </div>
    );
  }

  const missingFacts = sourceFacts.filter((f) => !generated[f.id]);
  const generatedTags = data.content?.tags || {};
  const sourceTags = [];
  for (const f of sourceFacts) {
    for (const t of f.tags || []) {
      if (!sourceTags.includes(t)) sourceTags.push(t);
    }
  }
  const missingTags = sourceTags.filter((t) => !generatedTags[t]);
  const missingDetails = [];
  for (const f of sourceFacts) {
    const entry = generated[f.id];
    if (!entry) continue;
    for (const d of f.details || []) {
      if (!entry.details?.[d.id]) missingDetails.push(`${f.id} / ${d.id}`);
    }
  }
  const totalDetails = sourceFacts.reduce((n, f) => n + (f.details || []).length, 0);
  const complete =
    missingFacts.length === 0 && missingDetails.length === 0 && missingTags.length === 0;

  return (
    <div>
      {header}

      <p className="text-sm font-medium text-foreground mb-1">
        {name} →{" "}
        {data.content?.edited_at
          ? `modifié le ${new Date(data.content.edited_at * 1000).toLocaleString("fr-FR")}`
          : `généré le ${new Date((data.content?.generated_at || 0) * 1000).toLocaleString("fr-FR")}`}
      </p>

      {complete ? (
        <p className="text-xs text-muted mb-3">
          Complet : {Object.keys(generated).length} faits, {totalDetails} détails couverts,{" "}
          {Object.keys(generatedTags).length} tags avec question.
        </p>
      ) : (
        <div className="text-xs mb-3 space-y-1">
          {missingTags.length > 0 && (
            <p className="text-destructive">
              Tags sans question de suggestion : {missingTags.join(", ")}
            </p>
          )}
          {missingFacts.length > 0 && (
            <p className="text-destructive">
              Faits sans données générées : {missingFacts.map((f) => f.id).join(", ")}
            </p>
          )}
          {missingDetails.length > 0 && (
            <p className="text-destructive">
              Détails sans question : {missingDetails.join(", ")}
            </p>
          )}
        </div>
      )}

      {showRaw ? (
        <pre className="bg-card border border-border rounded-xl p-4 text-xs text-foreground overflow-auto max-h-[70vh]">
          {JSON.stringify(data.content, null, 2)}
        </pre>
      ) : (
        <div className="space-y-3">
          <div className="bg-card border border-border rounded-xl p-4">
            <p className="text-xs font-medium text-muted mb-2">Suggestions par tag</p>
            <ul className="space-y-1">
              {Object.entries(generatedTags).map(([tag, question]) => (
                <li key={tag} className="text-sm text-foreground">
                  <span className="font-mono text-xs text-accent">{tag}</span> — {question}
                </li>
              ))}
              {Object.keys(generatedTags).length === 0 && (
                <li className="text-muted text-xs">Aucune question de tag.</li>
              )}
            </ul>
          </div>

          {Object.entries(generated).map(([factId, entry]) => (
            <div key={factId} className="bg-background border border-border rounded-xl p-4">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-xs font-mono text-accent">{factId}</span>
                {(entry.tags || []).map((t) => (
                  <span
                    key={t}
                    className="text-[11px] rounded-full bg-card border border-border px-2 py-0.5 text-muted"
                  >
                    {t}
                  </span>
                ))}
              </div>

              <p className="text-xs font-medium text-muted mb-1">Résumé</p>
              <ul className="text-sm text-foreground mb-2">
                {(entry.summary_keywords || []).map((kw) => (
                  <li key={kw}>{kw}</li>
                ))}
              </ul>

              <p className="text-xs font-medium text-muted mb-1">Questions détail</p>
              <ul className="text-sm text-foreground space-y-0.5">
                {Object.entries(entry.details || {}).map(([dId, q]) => (
                  <li key={dId}>
                    <span className="font-mono text-xs text-muted">[$id: {dId}]</span> {q}
                  </li>
                ))}
                {Object.keys(entry.details || {}).length === 0 && (
                  <li className="text-muted text-xs">Aucun détail.</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DerivedBadge({ derived, onRetry }) {
  if (!derived) return null;
  const status = derived.status;

  if (status === "running") {
    return (
      <span className="text-[11px] rounded-full bg-card border border-border px-2 py-0.5 text-muted animate-pulse">
        Génération IA...
      </span>
    );
  }
  if (status === "ok") {
    return (
      <span className="flex items-center gap-2 text-[11px] rounded-full bg-card border border-border px-2 py-0.5 text-muted">
        Sugg. générées — {derived.fact_count} faits, {derived.tag_count || 0} tags
        <button onClick={onRetry} className="cursor-pointer text-accent underline">
          Régénérer
        </button>
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex items-center gap-2 text-[11px] text-destructive">
        Échec : {derived.error || "erreur inconnue"}
        <button onClick={onRetry} className="cursor-pointer underline">
          Relancer
        </button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2 text-[11px] text-muted">
      Non généré
      <button onClick={onRetry} className="cursor-pointer text-accent underline">
        Générer
      </button>
    </span>
  );
}

function DataTab() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = () => {
    authFetch("/admin/data")
      .then((r) => r.json())
      .then(setFiles);
  };

  useEffect(load, []);

  useEffect(() => {
    if (!files.some((f) => f.derived?.status === "running")) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [files]);

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

  const recompute = async (name, derived) => {
    if (derived && derived.status !== "none") {
      const ok = confirm(
        `Régénérer les suggestions de ${name} ?\nLes modifications manuelles seront perdues.`
      );
      if (!ok) return;
    }
    const res = await authFetch(`/admin/data/${encodeURIComponent(name)}/recompute`, {
      method: "POST",
    });
    const out = await res.json();
    if (out.error) {
      alert(out.error);
      return;
    }
    load();
  };

  const deleteFile = async (name) => {
    if (!confirm(`Supprimer ${name} ?`)) return;
    await authFetch(`/admin/data/${name}`, { method: "DELETE" });
    setSelected(null);
    load();
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    return (bytes / 1024).toFixed(1) + " KB";
  };

  if (selected) {
    const back = () => setSelected(null);
    return selected.mode === "derived" ? (
      <DerivedView name={selected.name} onBack={back} />
    ) : (
      <DataFileView name={selected.name} onBack={back} />
    );
  }

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
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{f.name}</p>
                <p className="text-xs text-muted">
                  {formatSize(f.size)} — {new Date(f.modified * 1000).toLocaleString("fr-FR")}
                </p>
                <div className="mt-1">
                  <DerivedBadge
                    derived={f.derived}
                    onRetry={() => recompute(f.name, f.derived)}
                  />
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => setSelected({ name: f.name, mode: "source" })}
                  className="cursor-pointer text-xs text-accent hover:underline"
                >
                  Voir
                </button>
                <button
                  onClick={() => setSelected({ name: f.name, mode: "derived" })}
                  className="cursor-pointer text-xs text-accent hover:underline"
                >
                  Généré
                </button>
                <button
                  onClick={() => deleteFile(f.name)}
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
