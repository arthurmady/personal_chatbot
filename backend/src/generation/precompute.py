import json
import logging
import time
from pathlib import Path

from json_repair import repair_json
from src.generation.context_builder import load_facts_from_file
from src.generation.json_blob import extract_json_blob
from src.generation.prompts import NAME
from src.llm_client import llm

logger = logging.getLogger(__name__)

DERIVED_DIR = Path("data/derived")
SCHEMA_VERSION = 2
_CHUNK_SIZE = 5

MAX_QUESTION_CHARS = 130
MAX_QUESTION_WORDS = 15
MAX_SUMMARY_KEYWORD_WORDS = 10

PRECOMPUTE_SYSTEM = """Tu prépares les données d'aide à la conversation d'un chat personnel qui présente {name} à la troisième personne.
On te donne une liste de TAGS et une liste de faits. Tu produis UNE question de suggestion PAR TAG, puis un résumé et une question PAR DÉTAIL pour chaque fait.

RÈGLES POUR TOUTE QUESTION :
- Français, 3e personne : "Qu'a-t-il fait ?", jamais "Qu'as-tu fait ?".
- COURTE : 14 mots maximum, 130 caractères maximum. Se termine par "?".
- ZÉRO SPOIL : la question n'apporte AUCUN élément de réponse. Elle n'utilise AUCUN mot qui n'existe que dans un contenu de détail non encore donné (personne, outil, lieu, chiffre, méthode, particulière, résultat).
- Elle est TOUJOURS ancrée sur le contexte du fait, tiré de l'Essentiel (entreprise, école, projet, sujet) : une question de détail ne doit jamais pouvoir se lire hors contexte.
  Mauvais : "Comment a-t-il surmonté les limitations d'accès aux logs ?" (de quel stage parle-t-on ?)
  Bon : "Comment a-t-il surmonté les limitations d'accès aux logs lors de son stage chez MBDA ?"
- Si l'Essentiel est un simple NOM/LABEL, utilise "Qu'est-ce que [nom] ?" ou "Quelle est [nom] ?".
- Jamais de guillemet autour de la question, jamais d'autre phrase que la question.

1. "tags" : pour CHAQUE tag fourni, EXACTEMENT UNE question de suggestion portant sur ce sujet COMPLET.
   - Elle invite à parler de tout le sujet : jamais un fait précis, jamais un détail.
   - Elle s'ancre sur le nom du tag et reste vague.
   - Exemple : tag "Expériences" -> "Quelles ont été ses principales expériences ?".

2. Pour CHAQUE fait, produis exactement :

   a. "summary_keywords" : 1 à 3 idées extraites UNIQUEMENT du champ "Essentiel".
      - Le plus COURT possible : le plus souvent le seul sujet, en 1 à 3 mots, jamais une phrase.
      - Ajoute une info ("Sujet : info") UNIQUEMENT si elle distingue le fait d'un autre du même tag (une année, une durée, un diplôme) ; jamais d'adjectif ou de précision décorative ("régulière", "principalement"...).
      - Jamais du "Plus", jamais de contenu de détail.
      - Exemples : "Pratique la musculation" -> ["Musculation"] ; "Anime des soirées en tant que DJ" -> ["DJ"] ; "Stage chez Acme Corp en 2024" -> ["Acme Corp : stage 2024"].

   b. "details" : un objet qui associe CHAQUE identifiant de détail fourni à UNE question vague.
      - Lis le détail UNIQUEMENT pour choisir le sujet de la question, jamais pour la rédiger.
      - La question reste GÉNÉRALE : elle amène l'interlocuteur à en parler sans rien révéler.
      - TEST : si AU MOINS DEUX mots de la question n'existent QUE dans le détail non donné, la question SPOILE -> réécris-la plus vague.
      - Rappelle toujours dans la question le contexte de l'Essentiel (ex. "lors de son stage chez MBDA", "dans le projet KOP", "à l'IIT Madras").
      - Si l'Essentiel est un label, ancre la question dessus : "Qu'est-ce que [label] ?" adapté au détail.

FORMAT DE SORTIE (strict, JSON seul, sans texte autour) :
{{"tags": {{"<tag>": "Question ?"}}, "facts": {{"<id_du_fait>": {{"summary_keywords": ["Mot-clé court"], "details": {{"<id_du_detail>": "Question ?"}}}}}}}}

Ne produis AUCUN tag ni AUCUN fait absent du contexte. Ne saute AUCUN tag, AUCUN fait ni AUCUN identifiant de détail.
"""

PRECOMPUTE_TEMPLATE = """TAGS À TRAITER : {tags}

CONTEXTE DES FAITS :
{context}
"""

TAGS_TEMPLATE = """TAGS À TRAITER : {tags}

Essentiels par tag (jamais de détail) :
{essentials}
"""

PRECOMPUTE_TEMPLATE = """CONTEXTE DES FAITS :
{context}
"""


def build_facts_context(facts: list[dict], tags: list[str]) -> str:
    blocks = []
    for fact in facts:
        lines = [f"[id: {fact['id']}] (tags: {', '.join(fact.get('tags', []))})"]
        lines.append(f"Essentiel : {fact['essential']}")
        if fact.get("plus"):
            lines.append(f"Plus : {fact['plus']}")
        for d in fact.get("details", []):
            lines.append(f"[$id: {d['id']}] {d['content']}")
        blocks.append("\n".join(lines))
    context = "\n\n---\n\n".join(blocks)
    return PRECOMPUTE_TEMPLATE.format(tags=", ".join(tags), context=context)


def build_tags_context(tags: list[str], facts: list[dict]) -> str:
    lines = []
    for tag in tags:
        essentials = [
            fact.get("essential", "")
            for fact in facts
            if tag in fact.get("tags", [])
        ]
        lines.append(f"- {tag} : {' | '.join(e for e in essentials if e)}")
    return TAGS_TEMPLATE.format(tags=", ".join(tags), essentials="\n".join(lines))


def _parse_json(raw: str) -> dict | None:
    blob = extract_json_blob(raw)
    try:
        parsed = json.loads(blob)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    try:
        parsed = json.loads(repair_json(blob))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_question(value) -> str:
    if not isinstance(value, str):
        return ""
    q = value.strip().splitlines()[0].strip().strip('"«»')
    if not q.endswith("?") or len(q) > MAX_QUESTION_CHARS:
        logger.debug("question rejetée (%d car): %r", len(q), q[:80])
        return ""
    if len(q.split()) > MAX_QUESTION_WORDS:
        logger.debug("question rejetée (%d mots): %r", len(q.split()), q[:80])
        return ""
    return q


def _clean_keywords(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        kw = item.strip().rstrip(",;.")
        if not kw or len(kw.split()) > MAX_SUMMARY_KEYWORD_WORDS:
            continue
        if kw not in out:
            out.append(kw)
    return out[:3]


def _merge_entry(target: dict, source: dict, fact: dict) -> None:
    entry = target.setdefault(fact["id"], {
        "tags": list(fact.get("tags", [])),
        "summary_keywords": [],
        "details": {},
    })

    entry["summary_keywords"] = _clean_keywords(source.get("summary_keywords"))

    details = source.get("details")
    if not isinstance(details, dict):
        details = {}
    for d in fact.get("details", []):
        q = _clean_question(details.get(d["id"]))
        if q:
            entry["details"][d["id"]] = q


def _fact_problems(target: dict, fact: dict) -> list[str]:
    entry = target.get(fact["id"], {})
    problems = []
    if not entry.get("summary_keywords"):
        problems.append(f"{fact['id']}: summary_keywords manquant")
    missing = [d["id"] for d in fact.get("details", []) if d["id"] not in entry.get("details", {})]
    if missing:
        problems.append(f"{fact['id']}: détails sans question {missing}")
    return problems


def _merge_facts(target: dict, source, facts: list[dict]) -> None:
    if not isinstance(source, dict):
        logger.warning("precompute: clé 'facts' illisible (%d faits)", len(facts))
        return
    for fact in facts:
        entry = source.get(fact["id"])
        if isinstance(entry, dict):
            _merge_entry(target, entry, fact)
        else:
            logger.warning("precompute: fait absent %s", fact["id"])


def _merge_tags(target: dict, source, all_tags: list[str]) -> list[str]:
    if not all_tags:
        return []
    if not isinstance(source, dict):
        return ["tags: réponse illisible"]
    problems = []
    for tag in all_tags:
        question = _clean_question(source.get(tag))
        if question:
            target[tag] = question
        else:
            problems.append(f"tag {tag}: question manquante")
    return problems


async def _invoke(context: str) -> dict | None:
    prompt = PRECOMPUTE_SYSTEM.format(name=NAME) + "\n\n" + context
    try:
        resp = await llm.ainvoke(prompt)
    except Exception:
        logger.exception("precompute LLM call failed")
        return None
    return _parse_json(resp.content)


async def generate_derived(facts: list[dict], all_tags: list[str]) -> tuple[dict, dict]:
    """Produit ({fact_id: entrée}, {tag: question de suggestion}) pour une source."""
    if not facts and not all_tags:
        return {}, {}

    target_facts: dict = {}
    target_tags: dict = {}

    parsed = await _invoke(build_facts_context(facts, all_tags))
    tag_problems = _merge_tags(target_tags, (parsed or {}).get("tags"), all_tags)
    _merge_facts(target_facts, (parsed or {}).get("facts"), facts)

    pending = [f for f in facts if _fact_problems(target_facts, f)]
    for attempt in range(2):
        if not pending:
            break
        logger.warning(
            "precompute pass %d: %d faits incomplets, nouvelle tentative",
            attempt + 2, len(pending),
        )
        for start in range(0, len(pending), _CHUNK_SIZE):
            chunk = pending[start:start + _CHUNK_SIZE]
            parsed = await _invoke(build_facts_context(chunk, all_tags))
            _merge_facts(target_facts, (parsed or {}).get("facts"), chunk)
        pending = [f for f in facts if _fact_problems(target_facts, f)]

    if tag_problems:
        logger.warning("precompute tags invalide (%d), nouvelle tentative", len(tag_problems))
        target_tags = {}
        parsed = await _invoke(build_tags_context(all_tags, facts))
        tag_problems = _merge_tags(target_tags, (parsed or {}).get("tags"), all_tags)

    problems = [p for f in pending for p in _fact_problems(target_facts, f)] + tag_problems
    if problems:
        raise ValueError("génération incomplète : " + "; ".join(problems[:5]))
    return target_facts, target_tags


def derived_path(source_name: str) -> Path:
    return DERIVED_DIR / f"{Path(source_name).stem}.json"


async def generate_for_source(source_path: Path) -> Path:
    facts = load_facts_from_file(source_path)
    all_tags = []
    for fact in facts:
        for tag in fact.get("tags", []):
            if tag not in all_tags:
                all_tags.append(tag)
    facts_map, tags_map = await generate_derived(facts, all_tags)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": source_path.name,
        "generated_at": time.time(),
        "fact_count": len(facts_map),
        "tag_count": len(tags_map),
        "tags": tags_map,
        "facts": facts_map,
    }
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    dest = derived_path(source_path.name)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("derived written: %s (%d facts, %d tags)", dest, len(facts_map), len(tags_map))
    return dest


def load_all_derived() -> dict:
    merged: dict = {}
    if not DERIVED_DIR.is_dir():
        return merged
    for path in sorted(DERIVED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("derived illisible: %s", path)
            continue
        facts = data.get("facts")
        if isinstance(facts, dict):
            merged.update(facts)
    return merged


def load_all_tag_suggestions() -> dict:
    """Fusionne les questions de suggestion par tag de toutes les sources (clé en minuscules)."""
    merged: dict = {}
    if not DERIVED_DIR.is_dir():
        return merged
    for path in sorted(DERIVED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("derived illisible: %s", path)
            continue
        tags = data.get("tags")
        if isinstance(tags, dict):
            for tag, question in tags.items():
                if isinstance(tag, str) and isinstance(question, str) and question.strip():
                    merged.setdefault(tag.strip().lower(), question.strip())
    return merged


def _manual_question(value) -> str:
    if not isinstance(value, str):
        return ""
    q = value.strip().splitlines()[0].strip().strip('"«»')
    if not q:
        return ""
    if not q.endswith("?"):
        q += "?"
    return q


def _manual_lines(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        line = " ".join(item.split()).rstrip(",;.")
        if line and line not in out:
            out.append(line)
    return out[:limit]


def sanitize_derived(payload: dict) -> dict:
    """Valide et normalise un contenu derived édité à la main."""
    if not isinstance(payload, dict):
        raise TypeError("payload invalide")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, dict):
        raise TypeError("champ 'facts' absent ou invalide")

    facts: dict = {}
    for fid, entry in raw_facts.items():
        if not isinstance(fid, str) or not fid.strip():
            raise TypeError("identifiant de fait invalide")
        if not isinstance(entry, dict):
            raise TypeError(f"entrée invalide pour '{fid}'")
        raw_tags = entry.get("tags")
        tags = (
            [t.strip() for t in raw_tags if isinstance(t, str) and t.strip()]
            if isinstance(raw_tags, list) else []
        )
        details: dict = {}
        raw_details = entry.get("details")
        if isinstance(raw_details, dict):
            for did, question in raw_details.items():
                if not isinstance(did, str) or not did.strip():
                    continue
                cleaned = _manual_question(question)
                if cleaned:
                    details[did.strip()] = cleaned
        facts[fid.strip()] = {
            "tags": tags,
            "summary_keywords": _manual_lines(entry.get("summary_keywords"), 5),
            "details": details,
        }

    raw_tags_map = payload.get("tags")
    tag_suggestions: dict = {}
    if isinstance(raw_tags_map, dict):
        for tag, question in raw_tags_map.items():
            if not isinstance(tag, str) or not tag.strip():
                continue
            cleaned = _manual_question(question)
            if cleaned:
                tag_suggestions[tag.strip()] = cleaned

    generated_at = payload.get("generated_at")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "",
        "generated_at": generated_at if isinstance(generated_at, (int, float)) else time.time(),
        "edited_at": time.time(),
        "fact_count": len(facts),
        "tag_count": len(tag_suggestions),
        "tags": tag_suggestions,
        "facts": facts,
    }


def save_derived(source_name: str, payload: dict) -> Path:
    clean = sanitize_derived(payload)
    clean["source"] = source_name
    dest = derived_path(source_name)
    if "tags" not in payload and dest.is_file():
        try:
            previous = json.loads(dest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        prev_tags = previous.get("tags")
        if isinstance(prev_tags, dict) and prev_tags:
            clean["tags"] = prev_tags
            clean["tag_count"] = len(prev_tags)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "derived saved by hand: %s (%d facts, %d tags)",
        dest, clean["fact_count"], clean["tag_count"],
    )
    return dest
