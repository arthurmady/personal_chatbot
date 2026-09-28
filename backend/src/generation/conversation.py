import json
import logging
import re
import time
import unicodedata
from langchain_core.messages import SystemMessage, HumanMessage
from json_repair import repair_json

from src.llm_client import llm
from src.generation.prompts import SYSTEM_PROMPT, FOLLOWUP_TEMPLATE
from src.generation.context_builder import load_facts, build_context, extract_topics

logger = logging.getLogger(__name__)

NAME = "Arthur"

_PARSE_FALLBACK = {
    "response": "",
    "summary": [],
    "fact_ids": [],
    "level": {},
    "suggestions": [],
}

_MAX_KEYWORD_WORDS = 10

_LETTER_STOPWORDS = frozenset(chr(c) for c in range(ord("a"), ord("z") + 1))

_STOPWORDS = frozenset("""
le la les de des du un une et en a au aux pour par sur dans avec que qui ne pas se sa son ses
est sont plus mais aussi ou d l s n c j m t qu on il elle ils elles nous vous tout tous tres
the and or if then else this that
""".split()) | _LETTER_STOPWORDS

_SUGG_EXTRA = frozenset("""
quel quelle quels quelles ce cet cette ces combien comment quand pourquoi peut peux peuvent
tu je lui leur tes toute toutes dont autres autre aussi chez pendant etait etaient etre avant
apres lors selon entre depuis plusieurs meme certains certaines telles tels ainsi donc alors cependant
toutefois
""".split())

_SUGG_STOPWORDS = _STOPWORDS | _SUGG_EXTRA

_CUT_MARKERS = re.compile(
    r"\s+(?:codé|créé|développé|utilisé|réalisé|conçu|fait|appliqué|entraîné|construit|"
    r"implémenté|écrit|permet|permettant|visant|destiné|destinée|destinés|pour|afin|avec|"
    r"sans|est|sont|qui|ainsi|offrant|incluant)\b",
    re.IGNORECASE,
)


class Conversation:

    def __init__(self):
        self.facts = load_facts()
        self.all_tags = extract_topics(self.facts)
        self.essentials_done: set[str] = set()
        self.details_done: set[str] = set()
        self.last_topic: str = ""

    def _get_fact_states(self) -> str:
        lines = []
        for fact in self.facts:
            fid = fact["id"]
            essential_done = fid in self.essentials_done
            details = fact.get("details", [])
            details_given = [d["id"] for d in details if d["id"] in self.details_done]
            details_remaining = [d["id"] for d in details if d["id"] not in self.details_done]

            if not essential_done:
                status = "not_discussed"
            elif details and not details_given:
                status = "essential_given"
            elif details_remaining:
                status = f"partial_details: [{', '.join(details_given)}]"
            else:
                status = "details_complete"
            lines.append(f"  {fid}: {status}")
        return "\n".join(lines)

    def _extract_json_blob(self, raw_content: str) -> str:
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if fence_match:
            return fence_match.group(1)
        first = raw_content.find("{")
        last = raw_content.rfind("}")
        if first != -1 and last > first:
            return raw_content[first:last + 1]
        return raw_content

    def _parse_response(self, raw_content: str) -> dict:
        blob = self._extract_json_blob(raw_content)
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            try:
                repaired = repair_json(blob)
                parsed = json.loads(repaired)
            except Exception:
                return {**_PARSE_FALLBACK, "response": raw_content}

        if not isinstance(parsed, dict):
            return {**_PARSE_FALLBACK, "response": raw_content}

        parsed.setdefault("response", raw_content)
        parsed.setdefault("summary", [])
        if not isinstance(parsed.get("fact_ids"), list):
            parsed["fact_ids"] = []
        if not isinstance(parsed.get("level"), dict):
            parsed["level"] = {}
        if not isinstance(parsed.get("suggestions"), list):
            parsed["suggestions"] = []

        return parsed

    @staticmethod
    def _target_display(target: dict | None) -> str:
        if not target:
            return "(aucune)"
        fact_id = target.get("fact_id", "")
        detail_id = target.get("detail_id", "")
        if detail_id:
            return f"[$id: {detail_id}]" + (f" du fait [id: {fact_id}]" if fact_id else "")
        return f"[id: {fact_id}]"

    def _build_messages(self, query: str, target: dict | None = None) -> list:
        context = build_context(self.facts, self.essentials_done, self.details_done)
        remaining_topics = self._remaining_topics()
        remaining_topics_display = "; ".join(remaining_topics) if remaining_topics else "(none)"
        all_topics = "; ".join(self.all_tags) if self.all_tags else "(none)"
        fact_states = self._get_fact_states()

        covered_display = self._covered_tags_display()

        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(
                name=NAME,
                context=context,
                remaining_topics=remaining_topics_display,
                all_topics=all_topics,
                fact_states=fact_states,
            )
        )
        human_message = HumanMessage(content=FOLLOWUP_TEMPLATE.format(
            already_covered=covered_display,
            query=query,
            last_topic=self.last_topic,
            suggestion_target=self._target_display(target),
        ))
        return [system_message, human_message]

    def _remaining_topics(self) -> list[str]:
        tag_to_fids: dict[str, list[str]] = {}
        for fact in self.facts:
            for tag in fact["tags"]:
                tag_to_fids.setdefault(tag.strip().lower(), []).append(fact["id"])

        covered_tags = set()
        for tag, fids in tag_to_fids.items():
            if all(fid in self.essentials_done for fid in fids):
                covered_tags.add(tag)

        return [t for t in self.all_tags if t.strip().lower() not in covered_tags]

    def _covered_tags_display(self) -> str:
        covered = []
        for fact in self.facts:
            if fact["id"] in self.essentials_done:
                for tag in fact["tags"]:
                    if tag not in covered:
                        covered.append(tag)
        return "; ".join(covered) if covered else "(none)"

    def _build_suggestions(self, llm_suggestions: list) -> list[dict]:
        result = []
        seen = set()
        for s in llm_suggestions:
            if isinstance(s, str):
                s = {"question": s}
            if not isinstance(s, dict):
                continue
            question = s.get("question")
            if not isinstance(question, str) or not question.strip():
                continue
            question = question.strip()
            if question in seen:
                continue
            seen.add(question)
            fact_id = s.get("fact_id")
            detail_id = s.get("detail_id")
            result.append({
                "question": question,
                "fact_id": fact_id if isinstance(fact_id, str) else "",
                "detail_id": detail_id if isinstance(detail_id, str) else "",
            })
        return result[:3]

    def _scope_tags(self, fact_ids: list) -> set:
        cited = {fid for fid in fact_ids if isinstance(fid, str)}
        tags = set()
        for fact in self.facts:
            if fact["id"] in cited:
                tags.update(t.strip().lower() for t in fact.get("tags", []))
        return tags

    def _fact_by_id(self, fact_id: str) -> dict | None:
        for fact in self.facts:
            if fact["id"] == fact_id:
                return fact
        return None

    def _fact_of_detail(self, detail_id: str) -> dict | None:
        for fact in self.facts:
            for d in fact.get("details", []):
                if d["id"] == detail_id:
                    return fact
        return None

    def resolve_suggestion_target(self, fact_id: str | None, detail_id: str | None) -> dict | None:
        fact = None
        resolved_detail = ""
        if detail_id:
            fact = self._fact_of_detail(detail_id)
            if fact is not None:
                resolved_detail = detail_id
        if fact is None and fact_id:
            fact = self._fact_by_id(fact_id)
        if fact is None:
            return None
        return {"fact_id": fact["id"], "detail_id": resolved_detail}

    def _detail_suggestion_target(self, fact_ids: list, suggestions: list) -> tuple | None:
        scope = self._scope_tags(fact_ids)
        if not scope:
            return None
        open_pairs = []
        for fact in self.facts:
            if fact["id"] not in self.essentials_done:
                continue
            if not any(t.strip().lower() in scope for t in fact.get("tags", [])):
                continue
            for d in fact.get("details", []):
                if d["id"] not in self.details_done:
                    open_pairs.append((fact, d))
        if not open_pairs:
            return None

        def is_detail_question(s: dict) -> bool:
            if s["detail_id"]:
                return any(s["detail_id"] == d["id"] for _fact, d in open_pairs)
            sw = {w for w in self._norm_words(s["question"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
            if not sw:
                return False
            for _fact, d in open_pairs:
                id_tokens = {t for t in d["id"].lower().split("_") if len(t) > 2}
                if sw & id_tokens:
                    return True
                cw = {w for w in self._norm_words(d["content"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
                if len(sw & cw) >= 2:
                    return True
            return False

        if any(is_detail_question(s) for s in suggestions):
            return None
        fact, detail = open_pairs[0]
        return fact, detail

    def _detail_suggestion_out_of_scope(self, s: dict, fact_ids: list) -> bool:
        scope = self._scope_tags(fact_ids)
        fact = None
        if s["detail_id"]:
            fact = self._fact_of_detail(s["detail_id"])
        if fact is None and s["fact_id"]:
            fact = self._fact_by_id(s["fact_id"])
        if fact is not None:
            return not any(t.strip().lower() in scope for t in fact.get("tags", []))
        sw = {w for w in self._norm_words(s["question"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
        if len(sw) < 2:
            return False
        matched_in = False
        matched_out = False
        for fact in self.facts:
            fact_scope = any(t.strip().lower() in scope for t in fact.get("tags", []))
            for d in fact.get("details", []):
                id_tokens = {t for t in d["id"].lower().split("_") if len(t) >= 4}
                cw = {w for w in self._norm_words(d["content"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
                if not (sw & id_tokens) and len(sw & cw) < 2:
                    continue
                if fact_scope:
                    matched_in = True
                else:
                    matched_out = True
        return matched_out and not matched_in

    @classmethod
    def _content_words(cls, text: str) -> set[str]:
        out = set()
        for w in cls._norm_words(text):
            if w in _SUGG_STOPWORDS or len(w) <= 2:
                continue
            if len(w) > 4 and w.endswith("s"):
                w = w[:-1]
            out.add(w)
        return out

    def _suggestion_lacks_detail_support(self, s: dict) -> bool:
        if not s["detail_id"]:
            return False
        fact = self._fact_of_detail(s["detail_id"])
        if fact is None:
            logger.info("suggestion dropped (unknown detail_id): %r", s)
            return True
        detail = next((d for d in fact.get("details", []) if d["id"] == s["detail_id"]), None)
        if detail is None:
            return True
        qw = self._content_words(s["question"])
        if not qw:
            return False
        known = (
            self._content_words(fact.get("essential") or "")
            | self._content_words(fact.get("plus") or "")
            | {t for t in s["detail_id"].lower().split("_") if len(t) > 2}
        )
        for f in self.facts:
            for d in f.get("details", []):
                if d["id"] in self.details_done:
                    known |= self._content_words(d["content"])
        if not (qw & known):
            logger.info("suggestion dropped (no anchor on known info): %r", s)
            return True
        spoiler = qw & (self._content_words(detail["content"]) - known)
        if len(spoiler) >= 2:
            logger.info("suggestion dropped (reveals detail): %r -> %s", s, sorted(spoiler))
            return True
        return False

    @classmethod
    def _short_subject(cls, raw: str) -> str:
        text = raw.replace("**", "").strip().lstrip("|-[]#*> ").rstrip(".")
        if " : " in text:
            text = text.split(" : ", 1)[1].strip()
        text = text.split(". ")[0].strip()
        m = _CUT_MARKERS.search(text)
        if m:
            cand = text[:m.start()].strip().strip(",;(")
            if len(cand.split()) >= 2:
                text = cand
        if len(text) > 70:
            text = text[:70].rsplit(" ", 1)[0] + "…"
        return text.strip()

    def _detail_question_fallback(self, fact: dict, detail: dict) -> str:
        subject = self._short_subject(detail["content"])
        if not subject:
            subject = self._short_subject(fact["essential"])
        if not subject:
            return ""
        first_word = subject.split(" ", 1)[0].strip(",;:()«».")
        if not re.fullmatch(r"[A-ZÀ-Þ/]+", first_word):
            subject = subject[0].lower() + subject[1:]
        return f"Peux-tu m'en dire plus sur le {subject} ?"

    async def _phrase_detail_question(self, fact: dict, detail: dict) -> str:
        fallback = self._detail_question_fallback(fact, detail)
        base = (
            "Formule UNE question de suggestion pour un chat personnel, en français, à la troisième personne.\n"
            f"Essentiel déjà donné : {fact['essential']}\n"
            f"Détail NON encore donné : {detail['content'][:400]}\n"
            "Règles : question COURTE (10 mots max), VAGUE, GÉNÉRALE. Ne répète et ne résume AUCUN fait "
            "du détail dans la question — elle doit seulement amener l'interlocuteur à en parler. "
            "Exemple : au lieu de « Comment a-t-il géré le projet seul avec un tuteur limité aux données ? », "
            "écris « Avec qui a-t-il travaillé sur le projet ? ». "
            "Commence par Qui/Quel/Quelle/Comment/Avec..., termine par '?', aucun guillemet, aucune autre "
            "phrase. Retourne UNIQUEMENT la question."
        )
        dw = {w for w in self._norm_words(detail["content"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
        for attempt in range(2):
            prompt = base if attempt == 0 else base + "\nENCORE PLUS COURT ET VAGUE : 6 mots maximum."
            try:
                resp = await llm.ainvoke(prompt)
                q = resp.content.strip().splitlines()[0].strip().strip('"«»')
                qw = {w for w in self._norm_words(q) if w not in _SUGG_STOPWORDS and len(w) > 2}
                if (
                    q.endswith("?")
                    and 3 <= len(q.split()) <= 10
                    and len(q) <= 110
                    and len(qw & dw) < 4
                ):
                    return q
            except Exception:
                logger.exception("detail question phrasing failed")
        return fallback

    @staticmethod
    def _strip_md(text: str) -> str:
        return text.replace("**", "").strip()

    def _parse_summary_markdown(self, text: str) -> list[dict]:
        entries: list[dict] = []
        tag = ""
        keywords: list[str] = []

        def flush():
            nonlocal tag, keywords
            if tag and keywords:
                entries.append({"tag": tag, "keywords": keywords})
            tag = ""
            keywords = []

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("**") and line.endswith("**") and line.count("**") == 2:
                flush()
                tag = line.strip("*").strip()
                continue
            if not tag:
                continue
            for part in line.split(","):
                part = part.strip()
                if part and len(part.split()) <= _MAX_KEYWORD_WORDS:
                    keywords.append(part)
        flush()
        return entries

    def _normalize_summary(self, raw) -> list[dict]:
        if isinstance(raw, str):
            raw = raw.replace("\\n", "\n")
            items = self._parse_summary_markdown(raw)
        elif isinstance(raw, list):
            items = raw
        else:
            return []

        entries: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tag = item.get("tag")
            if not isinstance(tag, str):
                continue
            tag = self._strip_md(tag)
            if not tag:
                continue
            raw_keywords = item.get("keywords")
            if not isinstance(raw_keywords, list):
                continue
            keywords: list[str] = []
            seen: set[str] = set()
            for kw in raw_keywords:
                if not isinstance(kw, str):
                    continue
                kw = self._strip_md(kw).strip().rstrip(",;.")
                if not kw or len(kw.split()) > _MAX_KEYWORD_WORDS:
                    continue
                key = kw.lower()
                if key in seen:
                    continue
                seen.add(key)
                keywords.append(kw)
            if not keywords:
                continue
            entries.append({"tag": tag, "keywords": keywords})
        return entries

    @staticmethod
    def _summary_to_markdown(entries: list[dict]) -> str:
        blocks = []
        for entry in entries:
            lines = entry["keywords"]
            blocks.append(f"**{entry['tag']}**\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    def _summary_suspicious_tokens(self) -> set[str]:
        if getattr(self, "_summary_guard_cache", None) is not None:
            return self._summary_guard_cache
        essential_tokens: set[str] = set()
        restricted_tokens: set[str] = set()
        for fact in self.facts:
            essential_tokens.update(self._norm_words(fact.get("essential", "")))
            plus = fact.get("plus")
            if plus:
                restricted_tokens.update(self._norm_words(plus))
            for detail in fact.get("details", []):
                restricted_tokens.update(self._norm_words(detail["content"]))
        self._summary_guard_cache = (restricted_tokens - essential_tokens) - _STOPWORDS
        return self._summary_guard_cache

    def _filter_non_essential_keywords(self, entries: list[dict]) -> list[dict]:
        suspicious = self._summary_suspicious_tokens()
        kept: list[dict] = []
        for entry in entries:
            tag_tokens = set(self._norm_words(entry["tag"]))
            keywords: list[str] = []
            for kw in entry["keywords"]:
                bad = sorted({w for w in self._norm_words(kw) if w in suspicious and w not in tag_tokens})
                if bad:
                    logger.info("summary keyword dropped (non-essential): %r -> %s", kw, bad)
                    continue
                keywords.append(kw)
            if keywords:
                kept.append({"tag": entry["tag"], "keywords": keywords})
            else:
                logger.info("summary tag dropped (all keywords non-essential): %r", entry["tag"])
        return kept

    @staticmethod
    def _fold(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")

    @classmethod
    def _norm_words(cls, text: str) -> list[str]:
        return [cls._fold(w) for w in re.sub(r"[^\w\s]", " ", text.lower()).split()]

    def _find_used_detail_ids(self, response_text: str) -> set[str]:
        resp_words = self._norm_words(response_text)
        if len(resp_words) < 4:
            return set()
        resp_grams = {tuple(resp_words[i:i + 4]) for i in range(len(resp_words) - 3)}
        resp_set = set(resp_words)
        used: set[str] = set()
        for fact in self.facts:
            for detail in fact.get("details", []):
                words = self._norm_words(detail["content"])
                if len(words) < 4:
                    continue
                if any(tuple(words[i:i + 4]) in resp_grams for i in range(len(words) - 3)):
                    used.add(detail["id"])
                    continue
                cw = {w for w in words if w not in _STOPWORDS and len(w) > 2}
                if len(cw) >= 2 and len(cw & resp_set) / len(cw) >= 0.6:
                    used.add(detail["id"])
        return used

    def _find_questioned_detail_ids(self, query: str, response_text: str, fact_ids: list) -> set[str]:
        qw = {w for w in self._norm_words(query) if w not in _SUGG_STOPWORDS and len(w) > 2}
        rw = set(self._norm_words(response_text))
        if len(qw) < 2:
            return set()
        cited = {fid for fid in fact_ids if isinstance(fid, str)}
        hit: set[str] = set()
        for fact in self.facts:
            if fact["id"] not in cited:
                continue
            for d in fact.get("details", []):
                if d["id"] in self.details_done:
                    continue
                id_tokens = {t for t in d["id"].lower().split("_") if len(t) > 2}
                cw = {w for w in self._norm_words(d["content"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
                if not cw:
                    continue
                targeted = len(qw & id_tokens) >= 2 or len(qw & cw) >= 2
                overlap = len(cw & rw)
                if targeted and overlap >= 2 and overlap / len(cw) >= 0.25:
                    hit.add(d["id"])
        return hit

    def _suggestion_targets_done(self, s: dict) -> bool:
        if s["detail_id"]:
            return s["detail_id"] in self.details_done
        sw = {w for w in self._norm_words(s["question"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
        if len(sw) < 2:
            return False
        for fact in self.facts:
            for d in fact.get("details", []):
                if d["id"] not in self.details_done:
                    continue
                id_tokens = {t for t in d["id"].lower().split("_") if len(t) > 2}
                if len(sw & id_tokens) >= 2:
                    return True
                cw = {w for w in self._norm_words(d["content"]) if w not in _SUGG_STOPWORDS and len(w) > 2}
                if len(sw & cw) >= 2:
                    return True
        return False

    def _has_open_subjects(self) -> bool:
        for fact in self.facts:
            if fact["id"] not in self.essentials_done:
                return True
            if any(d["id"] not in self.details_done for d in fact.get("details", [])):
                return True
        return False

    async def ask(self, query: str, target_fact_id: str | None = None,
                  target_detail_id: str | None = None) -> dict:
        target = self.resolve_suggestion_target(target_fact_id, target_detail_id)
        messages = self._build_messages(query, target)

        start = time.perf_counter()
        response = await llm.ainvoke(messages)
        elapsed = time.perf_counter() - start
        model_used = getattr(response, 'response_metadata', {}).get('model_name', llm.model_name)
        logger.info("Model: %s | Time: %.3fs", model_used, elapsed)

        parsed = self._parse_response(response.content)

        logger.debug("RAW RESPONSE: %s", response.content[:800])

        response_text = parsed.get("response", "")
        fact_ids = parsed.get("fact_ids", [])
        level_map = {
            fid: [s for s in level if isinstance(s, str)]
            for fid, level in parsed.get("level", {}).items()
            if isinstance(level, list)
        }
        llm_suggestions = parsed.get("suggestions", [])

        logger.info("fact_ids: %s | level: %s", fact_ids, level_map)

        used_detail_ids = self._find_used_detail_ids(response_text)
        if used_detail_ids:
            logger.info("detail ids detected in response: %s", sorted(used_detail_ids))
            facts_by_id = {f["id"]: f for f in self.facts}
            for fid in fact_ids:
                if not isinstance(fid, str) or fid not in facts_by_id:
                    continue
                own = {d["id"] for d in facts_by_id[fid].get("details", [])} & used_detail_ids
                if not own:
                    continue
                current = level_map.get(fid, [])
                level_map[fid] = sorted(set(current) | own)
            logger.info("level after detail check: %s", level_map)

        questioned_ids = self._find_questioned_detail_ids(query, response_text, fact_ids)
        if questioned_ids:
            logger.info("details marked done via question match: %s", sorted(questioned_ids))
            self.details_done.update(questioned_ids)

        logger.debug("PARSED RESPONSE: %s", response_text[:300])

        summary_entries = self._normalize_summary(parsed.get("summary", []))
        summary_entries = self._filter_non_essential_keywords(summary_entries)
        summary = self._summary_to_markdown(summary_entries)
        logger.debug("SUMMARY: %s", summary[:300])

        new_essential_ids = []
        has_new_essential = False
        for fid in fact_ids:
            if not isinstance(fid, str):
                continue
            level = level_map.get(fid, [])
            if fid not in self.essentials_done:
                new_essential_ids.append(fid)
                has_new_essential = True
            self.essentials_done.add(fid)
            for sub_id in level:
                self.details_done.add(sub_id)

        divers_fact_ids = {f["id"] for f in self.facts if "Divers" in f.get("tags", [])}
        has_non_divers_fact = any(fid not in divers_fact_ids for fid in new_essential_ids)

        turn_summary = summary if (has_new_essential and summary and has_non_divers_fact) else ""

        suggestions = self._build_suggestions(llm_suggestions)
        suggestions = [s for s in suggestions if not self._suggestion_targets_done(s)]
        suggestions = [s for s in suggestions if not self._detail_suggestion_out_of_scope(s, fact_ids)]
        suggestions = [s for s in suggestions if not self._suggestion_lacks_detail_support(s)]
        if not self._has_open_subjects():
            suggestions = []
        else:
            target = self._detail_suggestion_target(fact_ids, suggestions)
            if target:
                question = await self._phrase_detail_question(*target)
                if question:
                    backstop = {
                        "question": question,
                        "fact_id": target[0]["id"],
                        "detail_id": target[1]["id"],
                    }
                    suggestions = ([backstop] + suggestions)[:3]
        self.last_topic = "; ".join(
            f["tags"][0] for f in self.facts
            if f["id"] in new_essential_ids and f.get("tags")
        )
        logger.debug("essentials_done: %s", self.essentials_done)
        logger.debug("details_done: %s", self.details_done)
        logger.debug("turn_summary: %r", turn_summary)
        return {"response": response_text, "suggestions": suggestions, "turn_summary": turn_summary}
