"""Ask Pólya and the learn chat: request handlers (docs/specs/explain, docs/specs/learn-chat).

Every explanation is grounded in the idea, its premises' reasoning chains, the session's sources (notes first, then
fetched open sources) or notes, and the paper passage. Without an AI engine the reply is assembled from the content
bank and labelled with engine "deterministic". Evidence gathered in the chats (learn-chat replies, say-it-back) is
recorded with the hint rung capped at R2 (an explanation was just on screen) and kept out of the difficulty controller.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .. import db, llm, sources, tools
from . import explain, prompts, subagents, topic_map
from . import orchestrator as orch

THREAD_TAIL = 6
REQUEST_LINES = {
    "EXPLAIN": "Explain this card's idea.",
    "DIFFERENT": "Explain it differently from the earlier explanations in this chat.",
    "SIMPLER": "Explain it more simply: plain words, as little notation as possible.",
}
LEARNER_LINES = {"EXPLAIN": "Explain this", "DIFFERENT": "Explain it differently", "SIMPLER": "Simpler, please",
                 "OFFER": "Yes, show me"}
OFFER_LINES = {
    "CONFIDENT_WRONG": "The learner answered confidently and was wrong. Refute their belief, then explain.",
    "WHEEL_SPINNING": "The learner has missed this idea twice. Give a worked example.",
    "WRONG": "The learner got this card wrong. Explain why the right answer is right and where theirs went off.",
    "WEAK_REASONING": "The learner got it right but their reasoning was thin. Explain why the answer is right.",
    "STUCK": "The learner has been on this card a while and typed little.",
}


class _Explained(BaseModel):
    reply_markdown: str
    say_back_prompt: str = ""
    say_back_concepts: list[list[str]] = Field(default_factory=list)


class _Turn(BaseModel):
    reply_markdown: str
    question: str = ""
    concepts: list[list[str]] = Field(default_factory=list)


class _TurnAfterReply(BaseModel):
    verdict: str = "partial"
    quality: float = 0.5
    feedback_markdown: str = ""
    continue_: Optional[_Turn] = Field(default=None, alias="continue")
    next: Optional[_Turn] = None


class _Grade(BaseModel):
    verdict: str = "partial"
    quality: float = 0.5
    feedback_markdown: str = ""


# ------------------------------------------------------------------ shared context
def _premise_chains(conn, node: dict[str, Any]) -> str:
    lines = []
    for e in db.all_edges(conn):
        if e["edge_type"] == "DEDUCTION" and e["conclusion_node_id"] == node["id"]:
            titles = [n["title"] for n in (db.get_node(conn, p) for p in e["premise_node_ids"]) if n]
            lines.append(f"- From {', '.join(titles)}: {e['reasoning_chain_latex'][:400]}")
    return ("\nPremises of this idea and how they combine:\n" + "\n".join(lines[:4])) if lines else ""


def _grounding(session: dict[str, Any], node: dict[str, Any], query: str = "") -> tuple[str, set[int]]:
    passages = sources.passages_for(session["id"], node, query)
    if passages:
        ctx = sources.context(passages)
    else:
        ctx = topic_map.notes_context(session.get("_controller", {}).get("notes", []))
    return ctx + orch.paper_context(node), {p["n"] for p in passages}


def _tail(thread: list[dict[str, Any]], step_index: Optional[int] = None) -> str:
    msgs = [m for m in thread if step_index is None or m["step_index"] == step_index][-THREAD_TAIL:]
    if not msgs:
        return ""
    who = {"learner": "Learner", "polya": "Pólya", "say_back": "Learner (say it back)"}
    return "\n\nRecent chat:\n" + "\n".join(f"{who[m['role']]}: {m['text'][:400]}" for m in msgs)


def _bank_groups(content: dict[str, Any], node: dict[str, Any]) -> list[list[str]]:
    practice = content.get("practice") or {}
    groups = (practice.get(1) or {}).get("concept_groups") or []
    return groups or explain.key_term_groups(node)


def _msg_out(m: dict[str, Any]) -> dict[str, Any]:
    return {k: m[k] for k in ("id", "step_index", "node_id", "role", "kind", "text", "trigger", "style", "engine",
                              "before_answer", "meta", "created_at")}


def thread_out(session_id: str) -> list[dict[str, Any]]:
    with db.ro() as conn:
        return [_msg_out(m) for m in db.session_thread(conn, session_id)]


def _card(session: dict[str, Any], step_index: Optional[int], attempt: str, conn) -> dict[str, Any]:
    """The card the learner is looking at: the active step, or an earlier one they already answered."""
    active = session["active_step"]
    if step_index is None or step_index == active["step_index"]:
        meta = active.get("_meta", {})
        kind = active["kind"]
        nid = (active.get("target_node_ids") or [""])[0]
        if kind == "LEARN":
            learn = meta["learn"]
            nid = learn["ideas"][min(learn["current"], len(learn["ideas"]) - 1)]
        elif kind == "COMPLETE" or not nid:
            nid = session["dependency_plan"][-1]["node_id"]
        return {"step_index": active["step_index"], "kind": kind, "node_id": nid,
                "prompt": active.get("prompt_latex") or active.get("body_markdown") or "",
                "options": active.get("options", []), "answer": str(meta.get("correct") or meta.get("answer_summary") or ""),
                "explanation": str(meta.get("explanation") or meta.get("insight") or ""), "attempt": attempt,
                "result": "", "answered": False}
    hist = next((h for h in session["history_steps"] if h.get("step_index") == step_index), None)
    if not hist:
        raise HTTPException(404, f"no step {step_index} in this session")
    traces = [t for t in db.session_traces(conn, session["id"]) if t["step_index"] == step_index
              and not t["prompt_shown_latex"].startswith(("Learn chat:", "Say it back:"))]
    t = traces[-1] if traces else None
    tried = " ".join(x for x in ((t or {}).get("raw_prediction_locked", ""), (t or {}).get("verification_thinking", ""),
                                 f"(chose {t['selected_answer']})" if t and t.get("selected_answer") else "") if x)
    result = ""
    if t and t["outcome"] != "EXPLORATION_LOGGED":
        result = f"{'correct' if t['is_correct'] else 'incorrect'} ({t['outcome'].lower().replace('_', ' ')}, " \
                 f"confidence {t['confidence_slider']:.0%}, miss class {t['miss_class']})"
    return {"step_index": step_index, "kind": hist.get("kind", ""), "node_id": hist.get("node_id") or "",
            "prompt": (t or {}).get("prompt_shown_latex", ""), "options": (t or {}).get("options", []),
            "answer": hist.get("answer", ""), "explanation": hist.get("explanation", ""), "attempt": attempt or tried,
            "result": result, "answered": True}


def _card_text(card: dict[str, Any], reveal: bool) -> str:
    opts = "; ".join(f"{o.get('id', '')}) {o.get('label_latex') or o.get('label') or o.get('text_latex', '')}"[:200]
                     for o in card["options"][:5])
    lines = [f"\n\nCard the learner is looking at ({card['kind']}, {'answered' if card['answered'] else 'not answered yet'}):",
             card["prompt"][:1500]]
    if opts:
        lines.append(f"Options: {opts}")
    if reveal and card["answer"]:
        lines.append(f"Correct answer: {card['answer']}" + (f" — {card['explanation'][:800]}" if card["explanation"] else ""))
    if card["attempt"].strip():
        lines.append(f"Learner's attempt: {card['attempt'][:1200]}")
    if card["result"]:
        lines.append(f"Result: {card['result']}")
    return "\n".join(lines)


# ------------------------------------------------------------------ deterministic explanations (FR5)
def _fallback_explain(style: str, rep: str, node: dict[str, Any], content: dict[str, Any], card: dict[str, Any],
                      message: str, chains: str, passages: list[dict[str, Any]]) -> str:
    statement = f"$$ {node['statement_latex'][:500]} $$"
    hints = ((content.get("practice") or {}).get(1) or {}).get("hints", {})
    if style == "NUDGE":
        return (f"**What's being asked:** {card['prompt'][:300]}\n\n"
                + (f"**An earlier idea that helps:** {chains.splitlines()[-1][2:300]}\n\n" if chains else "")
                + "**Try:** the smallest case first: one dimension, or two elements. What does the claim say there?")
    if message and passages:
        p = passages[0]
        return f"From [{p['n']}] *{p['title']}*:\n\n> {p['text'][:600]}\n\n**{node['title']}.** {node['intuition_summary']}"
    if message:
        hits = tools.corpus_search(" ".join(sorted(topic_map.goal_terms(message))) or node["title"], max_blocks=1)
        if hits:
            b = hits[0]
            return f"From your notes (`{b['path']}:{b['line']}`), *{b['title']}*:\n\n> {b['body'][:600]}\n\n" \
                   f"**{node['title']}.** {node['intuition_summary']}"
    if rep:
        part = {"concrete": hints.get("R3") or node["intuition_summary"],
                "geometric": node["intuition_summary"],
                "symbolic": f"{statement}\n\n{node['formal_proof_sketch_latex'][:600]}",
                "computational": hints.get("R4") or content.get("reading", "")}[rep]
        return f"**Another way in ({rep}).** {part}"
    if style == "WORKED_EXAMPLE":
        return "\n\n".join(x for x in (hints.get("R3", ""), hints.get("R4", ""), f"**The idea.** {node['intuition_summary']}") if x)
    if style in ("CONTRAST", "REFUTATION"):
        bug = next(iter(content.get("misconceptions") or []), None)
        parts = []
        if style == "REFUTATION" and bug:
            parts.append(f"**The tempting belief:** ${bug['buggy_statement_latex']}$ ({bug['buggy_title']}). It is false.")
        if card["answer"]:
            parts.append(f"**The answer:** {card['answer']}" + (f". {card['explanation'][:600]}" if card["explanation"] else ""))
        parts.append(f"**The idea.** {node['intuition_summary']}\n\n{statement}")
        return "\n\n".join(parts)
    if style == "TERSE":
        return f"{node['intuition_summary']}\n\n{statement}"
    return content.get("reading") or f"{node['intuition_summary']}\n\n{statement}"


# ------------------------------------------------------------------ Ask Pólya (docs/specs/explain)
async def ask(session_id: str, action: str, message: str = "", trigger: str = "", step_index: Optional[int] = None,
              attempt: str = "") -> dict[str, Any]:
    if action == "ASK" and not message.strip():
        raise HTTPException(422, "empty question")
    with db.ro() as conn:
        session = orch._load(conn, session_id)
        card = _card(session, step_index, attempt, conn)
        thread = db.session_thread(conn, session_id)
        plan_nodes = [n for n in (db.get_node(conn, p["node_id"]) for p in session["dependency_plan"]) if n]
        node = (explain.mentioned_idea(message, plan_nodes) if message else None) or orch._node(conn, card["node_id"])
        chains = _premise_chains(conn, node)
        content, _ = orch.content_for(node, conn)
    if trigger == "STUCK" and card["answered"]:
        trigger = ""
    if action == "OFFER" and trigger:
        dup = next((m for m in thread if m["role"] == "polya" and m["step_index"] == card["step_index"]
                    and m["trigger"] == trigger), None)
        if dup:   # duplicate offer clicks are idempotent
            return {"reply_markdown": dup["text"], "style": dup["style"], "engine": dup["engine"], "node_id": dup["node_id"],
                    "say_back_prompt": dup["meta"].get("say_back_prompt"), "thread": [_msg_out(m) for m in thread]}
    style = explain.style_for(node["bkt_p_mastery"], action, trigger, bool(card["attempt"].strip()))
    used = [m["meta"].get("representation") for m in thread if m["role"] == "polya" and m["node_id"] == node["id"]]
    rep = explain.next_representation([u for u in used if u]) if action == "DIFFERENT" else ""
    grounding, allowed = _grounding(session, node, message)
    request = (f"The learner asks: {message}" if message else
               OFFER_LINES.get(trigger, "Explain this card's idea.") if action == "OFFER" or trigger else REQUEST_LINES[action])
    user = (prompts.node_context(node) + chains + f"\nSession goal: {session['target_goal']}"
            + _card_text(card, reveal=style != "NUDGE") + "\n\nStyle: " + prompts.EXPLAIN_STYLES[style]
            + (f"\nRepresentation: {prompts.REPRESENTATION_HINTS[rep]}." if rep else "")
            + _tail(thread) + f"\n\nRequest: {request}" + grounding)
    res = await llm.complete_json(prompts.EXPLAINER, user, max_tokens=1600)
    out: Optional[_Explained] = None
    if res.data:
        try:
            out = _Explained.model_validate(res.data)
        except Exception:
            out = None
    if out and out.reply_markdown.strip():
        reply, engine = out.reply_markdown, res.engine
        say_back = out.say_back_prompt or f"Why does *{node['title']}* hold?"
        concepts = out.say_back_concepts or _bank_groups(content, node)
    else:
        passages = sources.passages_for(session_id, node, message) if message else []
        reply = _fallback_explain(style, rep, node, content, card, message, chains, passages)
        engine = "deterministic"
        say_back = f"What does *{node['title']}* say, and why does it hold?"
        concepts = _bank_groups(content, node)
    reply, cited = sources.strip_unknown_citations(reply, allowed)
    if style == "NUDGE":
        say_back = ""
    before = card["kind"] in explain.GRADED_KINDS and not card["answered"]
    with db.tx() as conn:
        db.insert_explanation(conn, {"session_id": session_id, "step_index": card["step_index"], "node_id": node["id"],
                                     "role": "learner", "kind": action, "text": message.strip() or LEARNER_LINES.get(action, action),
                                     "trigger": trigger, "before_answer": before})
        db.insert_explanation(conn, {"session_id": session_id, "step_index": card["step_index"], "node_id": node["id"],
                                     "role": "polya", "kind": action, "text": reply, "trigger": trigger, "style": style,
                                     "engine": engine, "before_answer": before,
                                     "meta": {"say_back_prompt": say_back, "say_back_concepts": concepts,
                                              "representation": rep, "cited": cited}})
    return {"reply_markdown": reply, "style": style, "engine": engine, "node_id": node["id"],
            "say_back_prompt": say_back or None, "thread": thread_out(session_id)}


def get_thread(session_id: str) -> dict[str, Any]:
    with db.ro() as conn:
        session = orch._load(conn, session_id)
        thread = db.session_thread(conn, session_id)
    offer = session["_controller"].get("offer")
    if offer and any(m["role"] == "polya" and m["step_index"] == offer["step_index"] for m in thread):
        offer = None
    return {"thread": [_msg_out(m) for m in thread], "offer": offer, "sources": sources.listing(session_id)}


# ------------------------------------------------------------------ evidence from chats (FR6 / learn-chat FR4)
def _record_evidence(session: dict[str, Any], node_id: str, y: int, q: float, miss: str, partial: bool, confidence: float,
                     prompt_text: str, answer_text: str, tag: str) -> tuple[dict[str, Any], dict[str, Any]]:
    trace_id = db.new_id("tr")
    with db.tx() as conn:
        upd, tf = orch.apply_assessment(conn, session, node_id, y, q, miss, confidence, "R2", partial, None, {},
                                        trace_id, tag)
        db.insert_trace(conn, {"id": trace_id, "session_id": session["id"], "step_index": session["active_step"]["step_index"],
                               "phase": "READING", "target_node_ids": [node_id], "cue_level": 1,
                               "prompt_shown_latex": prompt_text[:4000], "verification_thinking": answer_text[:4000],
                               "confidence_slider": confidence, **tf})
        node = db.get_node(conn, node_id)
    return upd, node


async def _deterministic_quality(session_id: str, node: dict[str, Any], text: str, y: int, groups: list[list[str]],
                                 answer: str) -> tuple[float, str]:
    diag = await subagents.diagnose(session_id, {"raw_prediction_locked": "", "thinking_while_reading": [],
                                                 "verification_thinking": text, "prosody": {}, "confidence": 0.5,
                                                 "selected_answer": "", "is_correct": y, "correct_answer": answer,
                                                 "concept_groups": groups, "extra_text": text, "allow_llm": False}, node)
    return diag["trace_quality_score"], diag["miss_class"]


def _grade(res: llm.LLMResult) -> Optional[_Grade]:
    if not res.data:
        return None
    try:
        return _Grade.model_validate(res.data)
    except Exception:
        return None


async def say_back(session_id: str, text: str, confidence: float = 0.5, message_id: Optional[str] = None) -> dict[str, Any]:
    if len(text.strip()) < 8:
        raise HTTPException(422, "Say it in a few more words (one line is plenty).")
    with db.ro() as conn:
        session = orch._load(conn, session_id)
        thread = db.session_thread(conn, session_id)
    asked = [m for m in thread if m["role"] == "polya" and m["meta"].get("say_back_prompt")]
    target = next((m for m in asked if m["id"] == message_id), None) if message_id else (asked[-1] if asked else None)
    if not target:
        raise HTTPException(400, "nothing to say back yet: ask for an explanation first")
    with db.ro() as conn:
        node = orch._node(conn, target["node_id"])
        content, _ = orch.content_for(node, conn)
    groups = target["meta"].get("say_back_concepts") or _bank_groups(content, node)
    cov = explain.coverage(text, groups)
    g = _grade(await llm.complete_json(
        prompts.SAY_BACK_GRADER, prompts.node_context(node) + f"\n\nExplanation shown:\n{target['text'][:1500]}"
        f"\n\nSay-it-back prompt: {target['meta']['say_back_prompt']}\nLearner's line: {text}", max_tokens=400))
    y = int(g.verdict == "correct") if g else int(cov >= 0.5)
    partial = (g.verdict == "partial") if g else (0 < cov < 0.5)
    q0, miss = await _deterministic_quality(session_id, node, text, y, groups, node["statement_latex"])
    q = 0.5 * q0 + 0.5 * max(0.0, min(1.0, g.quality)) if g else q0
    if g and g.feedback_markdown.strip():
        verdict = g.feedback_markdown.strip()
    elif y:
        verdict = "Got it: that's the idea."
    else:
        missing = [grp[0] for grp in groups if grp and not any(s.lower() in text.lower() for s in grp)]
        verdict = "Close: you left out " + ", ".join(f"*{m}*" for m in missing[:2]) + "." if missing else "Not quite yet."
    upd, _ = _record_evidence(session, node["id"], y, q, miss, partial, confidence,
                              f"Say it back: {target['meta']['say_back_prompt']}", text, "SAY_BACK")
    with db.tx() as conn:
        db.insert_explanation(conn, {"session_id": session_id, "step_index": target["step_index"], "node_id": node["id"],
                                     "role": "say_back", "kind": "SAY_BACK", "text": text.strip(),
                                     "meta": {"answering": target["id"], "verdict": verdict, "is_correct": bool(y),
                                              "q": round(q, 3)}})
    return {"verdict_markdown": verdict, "is_correct": bool(y), "trace_quality_score": q, "node_update": upd,
            "thread": thread_out(session_id)}


# ------------------------------------------------------------------ learn chat (docs/specs/learn-chat)
def _det_turn(node: dict[str, Any], content: dict[str, Any], k: int, chains: str) -> _Turn:
    """The k-th deterministic chunk of an idea: intuition → reading → derivation → worked analog."""
    hints = ((content.get("practice") or {}).get(1) or {}).get("hints", {})
    chunks = [f"{node['intuition_summary']}\n\n$$ {node['statement_latex'][:500]} $$",
              content.get("reading") or node["intuition_summary"],
              node["formal_proof_sketch_latex"][:700] or chains.strip() or content.get("reading", ""),
              hints.get("R4") or hints.get("R3") or node["intuition_summary"]]
    questions = [f"In one sentence, in your own words: what does *{node['title']}* say?",
                 (content.get("predict") or {}).get("prompt") or f"Pick the simplest case of *{node['title']}*: what happens there?",
                 f"Why does *{node['title']}* hold? Which hypothesis does the argument need?",
                 f"Where would *{node['title']}* fail if you dropped one assumption?"]
    i = min(k, 3)
    return _Turn(reply_markdown=chunks[i], question=questions[i], concepts=_bank_groups(content, node))


def _learn_user(session: dict[str, Any], learn: dict[str, Any], node: dict[str, Any], chains: str, grounding: str,
                thread: list[dict[str, Any]], step_index: int, conn) -> str:
    titles = [orch._node(conn, i)["title"] for i in learn["ideas"]]
    idx = learn["ideas"].index(node["id"])
    style = explain.style_for(node["bkt_p_mastery"], "EXPLAIN", "", False)
    return (prompts.node_context(node) + chains + f"\nSession goal: {session['target_goal']}"
            + (f"\nWhat the learner said they already know: {learn['prior']}" if learn.get("prior") else "")
            + f"\nIdeas in this conversation, in order: {'; '.join(titles)}"
            + f"\nNow teaching idea {idx + 1} of {len(titles)}: {node['title']}"
            + "\nStyle: " + prompts.EXPLAIN_STYLES[style] + _tail(thread, step_index) + grounding)


async def _turn(session: dict[str, Any], learn: dict[str, Any], node: dict[str, Any], mode: str, thread: list[dict[str, Any]],
                question: str = "") -> tuple[_Turn, str, set[int]]:
    with db.ro() as conn:
        chains = _premise_chains(conn, node)
        content, _ = orch.content_for(node, conn)
        grounding, allowed = _grounding(session, node, question)
        user = _learn_user(session, learn, node, chains, grounding, thread, session["active_step"]["step_index"], conn)
    task = {"first": "Start this idea.", "continue": "The learner pressed Go on: teach the next step of this idea.",
            "ask": f"The learner asks: {question}\nAnswer it (grounded in the sources when they cover it), then ask one "
                   f"small question about the idea again."}[mode]
    res = await llm.complete_json(prompts.LEARN_TUTOR_TURN, user + f"\n\nTask: {task}", max_tokens=1400)
    if res.data:
        try:
            t = _Turn.model_validate(res.data)
            if t.reply_markdown.strip():
                return t, res.engine, allowed
        except Exception:
            pass
    k = learn["exchanges"].get(node["id"], 0)
    t = _det_turn(node, content, k, chains)
    if mode == "ask":
        passages = sources.passages_for(session["id"], node, question)
        t.reply_markdown = _fallback_explain("EXPLAIN", "", node, content, {"prompt": "", "answer": "", "explanation": ""},
                                             question, chains, passages)
    return t, "deterministic", allowed


def _render(t: _Turn, feedback: str = "") -> str:
    parts = [feedback.strip(), t.reply_markdown.strip(), f"**{t.question.strip()}**" if t.question.strip() else ""]
    return "\n\n".join(p for p in parts if p)


def _ready_text(learn: dict[str, Any], conn) -> str:
    first_id = (learn["covered_order"] or learn["ideas"])[0]
    first = orch._node(conn, first_id)["title"]
    moved = [orch._node(conn, i)["title"] for i in learn["ideas"] if learn["status"].get(i) == "moved_on" and i != first_id]
    also = ""
    if len(moved) > 2:
        also = f" The {len(moved)} ideas we didn't finish come after, so you can see where they stand."
    elif moved:
        also = f" We'll also check {' and '.join(f'*{m}*' for m in moved)} there."
    return ("You're ready to try recalling these. Press **Start recall**: it begins with *" + first + "*, the idea "
            "you learned first." + also)


async def learn_turn(session_id: str, action: str, message: str = "") -> dict[str, Any]:
    with db.ro() as conn:
        session = orch._load(conn, session_id)
        thread = db.session_thread(conn, session_id)
    active = session["active_step"]
    if active.get("kind") != "LEARN":
        raise HTTPException(400, "this session is not in a learning chat")
    if action in ("OPEN_REPLY", "REPLY", "ASK") and not message.strip():
        raise HTTPException(422, "empty message")
    learn = active["_meta"]["learn"]
    si = active["step_index"]
    if not learn["opened"] and action in ("REPLY", "GO_ON"):
        action = "OPEN_REPLY" if action == "REPLY" else "SKIP"
    if learn["opened"] and action in ("OPEN_REPLY", "SKIP"):
        action = "REPLY" if action == "OPEN_REPLY" else "GO_ON"
    if learn["ready"] and action not in ("ASK",):
        return _learn_out(session_id, learn, "deterministic")
    ideas = learn["ideas"]
    cur_id = ideas[min(learn["current"], len(ideas) - 1)]
    with db.ro() as conn:
        cur = orch._node(conn, cur_id)
    new_msgs: list[dict[str, Any]] = []
    engine = "deterministic"

    def learner(text: str, **meta: Any) -> None:
        new_msgs.append({"role": "learner", "kind": "LEARN", "text": text, "node_id": cur_id, "meta": meta})

    def polya(t: _Turn, eng: str, node_id: str, feedback: str = "", allowed: Optional[set[int]] = None) -> None:
        text, cited = sources.strip_unknown_citations(_render(t, feedback), allowed or set())
        meta = {"question": t.question, "concepts": t.concepts, "cited": cited}
        if eng != "deterministic" and not allowed:
            meta["engine_note"] = "from the AI's own knowledge"
        new_msgs.append({"role": "polya", "kind": "LEARN_Q" if t.question else "LEARN", "text": text, "node_id": node_id,
                         "engine": eng, "meta": meta})
        if t.question:
            learn["question"] = {"text": t.question, "concepts": t.concepts, "node_id": node_id}

    def advance(covered: bool) -> Optional[str]:
        """Close the current idea; returns the next idea id or None when the run is done."""
        learn["status"][cur_id] = "covered" if covered else "moved_on"
        if covered and cur_id not in learn["covered_order"]:
            learn["covered_order"].append(cur_id)
        learn["current"] += 1
        if learn["current"] >= len(ideas):
            learn["ready"] = True
            learn["question"] = None
            return None
        nxt = ideas[learn["current"]]
        learn["status"][nxt] = "current"
        return nxt

    def bump() -> int:
        learn["exchanges"][cur_id] = learn["exchanges"].get(cur_id, 0) + 1
        return learn["exchanges"][cur_id]

    if action in ("OPEN_REPLY", "SKIP"):
        if message.strip():
            learner(message.strip(), opening=True)
            learn["prior"] = message.strip()[:1000]
        learn["opened"] = True
        t, engine, allowed = await _turn(session, learn, cur, "first", thread)
        polya(t, engine, cur_id, allowed=allowed)
    elif action == "QUIZ_ME":
        learner("Quiz me")
        for i in ideas:
            if learn["status"].get(i) in ("todo", "current"):
                learn["status"][i] = "moved_on"
        learn["ready"] = True
        learn["question"] = None
        with db.ro() as conn:
            new_msgs.append({"role": "polya", "kind": "LEARN", "text": _ready_text(learn, conn), "node_id": cur_id})
    elif action == "ASK":
        bump()
        learner(message.strip(), asked=True)
        t, engine, allowed = await _turn(session, learn, cur, "ask", thread + [{"role": "learner", "text": message,
                                                                                    "step_index": si}], question=message)
        polya(t, engine, cur_id, allowed=allowed)
    elif action == "GO_ON":
        n = bump()
        learner("Go on")
        if n >= explain.MAX_EXCHANGES:
            nxt = advance(False)
            if nxt is None:
                with db.ro() as conn:
                    new_msgs.append({"role": "polya", "kind": "LEARN", "node_id": cur_id,
                                     "text": "Let's move on; we'll come back to this one in recall.\n\n" + _ready_text(learn, conn)})
            else:
                with db.ro() as conn:
                    nn = orch._node(conn, nxt)
                t, engine, allowed = await _turn(session, learn, nn, "first", thread)
                polya(t, engine, nxt, feedback="Let's move on; we'll come back to this one in recall.", allowed=allowed)
        else:
            t, engine, allowed = await _turn(session, learn, cur, "continue", thread)
            polya(t, engine, cur_id, allowed=allowed)
    else:   # REPLY to the pending question
        q = learn.get("question") or {"text": "", "concepts": [], "node_id": cur_id}
        n = bump()
        learner(message.strip(), answering=q["text"])
        engine, eng_used = "deterministic", None
        nxt_id = ideas[learn["current"] + 1] if learn["current"] + 1 < len(ideas) else None
        with db.ro() as conn:
            chains = _premise_chains(conn, cur)
            content, _ = orch.content_for(cur, conn)
            nxt = orch._node(conn, nxt_id) if nxt_id else None
            grounding, allowed = _grounding(session, cur, message)
            nxt_ground, nxt_allowed = _grounding(session, nxt, "") if nxt else ("", set())
            user = _learn_user(session, learn, cur, chains, grounding, thread, si, conn)
        user += (f"\n\nYour last question: {q['text']}\nLearner's answer: {message}"
                 + (f"\n\nNEXT idea (for the \"next\" turn):\n{prompts.node_context(nxt)}{nxt_ground}" if nxt else
                    "\n\nThere is no next idea: set \"next\" to null."))
        res = await llm.complete_json(prompts.LEARN_TUTOR_REPLY, user, max_tokens=2600)
        parsed: Optional[_TurnAfterReply] = None
        if res.data:
            try:
                parsed = _TurnAfterReply.model_validate(res.data)
                eng_used = res.engine
            except Exception:
                parsed = None
        groups = q.get("concepts") or _bank_groups(content, cur)
        cov = explain.coverage(message, groups)
        if parsed:
            y, partial = int(parsed.verdict == "correct"), parsed.verdict == "partial"
        else:
            y, partial = int(cov >= 0.5), 0 < cov < 0.5
        q0, miss = await _deterministic_quality(session_id, cur, message, y, groups, cur["statement_latex"])
        quality = 0.5 * q0 + 0.5 * max(0.0, min(1.0, parsed.quality)) if parsed else q0
        _, updated = _record_evidence(session, cur_id, y, quality, miss, partial, 0.5, f"Learn chat: {q['text']}",
                                      message, "LEARN_CHAT")
        ready_now = explain.p_recall(updated) >= explain.READY_RECALL
        feedback = (parsed.feedback_markdown if parsed and parsed.feedback_markdown.strip() else
                    "That's it." if y else "Partly there." if partial else "Not quite.")
        engine = eng_used or "deterministic"
        if ready_now or n >= explain.MAX_EXCHANGES:
            note = "You've got this one." if ready_now else "Let's move on; we'll come back to this one in recall."
            nxt_after = advance(ready_now)
            if nxt_after is None:
                with db.ro() as conn:
                    new_msgs.append({"role": "polya", "kind": "LEARN", "node_id": cur_id, "engine": engine,
                                     "text": f"{feedback}\n\n{note} {_ready_text(learn, conn)}"})
            elif parsed and parsed.next and parsed.next.reply_markdown.strip():
                polya(parsed.next, engine, nxt_after, feedback=f"{feedback} {note} Next: *{nxt['title']}*.",
                      allowed=nxt_allowed)
            else:
                t, eng2, al2 = await _turn(session, learn, nxt, "first", thread)
                polya(t, eng2, nxt_after, feedback=f"{feedback} {note} Next: *{nxt['title']}*.", allowed=al2)
        elif parsed and parsed.continue_ and parsed.continue_.reply_markdown.strip():
            polya(parsed.continue_, engine, cur_id, feedback=feedback, allowed=allowed)
        else:
            t = _det_turn(cur, content, n, chains)
            polya(t, "deterministic", cur_id, feedback=feedback, allowed=allowed)
    # persist the thread and the chat state
    with db.tx() as conn:
        for m in new_msgs:
            db.insert_explanation(conn, {"session_id": session_id, "step_index": si, "engine": m.get("engine", ""), **m})
        fresh = orch._load(conn, session_id)
        fresh["active_step"]["_meta"]["learn"] = learn
        fresh["active_step"]["learn_ideas"] = orch.learn_ideas_out(learn, conn)
        orch._persist(conn, fresh)
    return _learn_out(session_id, learn, engine)


def _learn_out(session_id: str, learn: dict[str, Any], engine: str) -> dict[str, Any]:
    with db.ro() as conn:
        ideas = orch.learn_ideas_out(learn, conn)
    return {"thread": thread_out(session_id), "learn_ideas": ideas, "ready": bool(learn["ready"]),
            "sources": sources.listing(session_id), "engine": engine}
