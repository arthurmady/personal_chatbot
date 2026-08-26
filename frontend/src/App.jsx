import { useState } from "react";

function App() {
  const [question, setQuestion] = useState("");       // ce que l'utilisateur tape
  const [messages, setMessages] = useState([]);        // historique de la conversation
  const [loading, setLoading] = useState(false);       // pour afficher "en cours..."

  const envoyerQuestion = async () => {
    if (!question.trim()) return; // évite d'envoyer une question vide

    // On ajoute tout de suite le message de l'utilisateur à l'affichage
    const nouveauMessageUser = { role: "user", content: question };
    setMessages((prev) => [...prev, nouveauMessageUser]);
    setQuestion(""); // on vide le champ de texte
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: nouveauMessageUser.content }),
      });

      const data = await response.json();

      // On ajoute la réponse du bot à l'affichage
      const messageBot = { role: "bot", content: data.reponse };
      setMessages((prev) => [...prev, messageBot]);
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

  // Permet d'envoyer en appuyant sur "Entrée"
  const gererTouche = (e) => {
    if (e.key === "Enter") {
      envoyerQuestion();
    }
  };

  return (
    <div>
      <h1>Mon Chatbot</h1>

      <div>
        {messages.map((msg, index) => (
          <p key={index}>
            <strong>{msg.role === "user" ? "Toi" : "Bot"} :</strong> {msg.content}
          </p>
        ))}
        {loading && <p><em>Le bot réfléchit...</em></p>}
      </div>

      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={gererTouche}
        placeholder="Pose ta question..."
      />
      <button onClick={envoyerQuestion}>Envoyer</button>
    </div>
  );
}

export default App;