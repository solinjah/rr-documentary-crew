"""Run the documentary crew for one topic.

    uv run rr-crew "Violet Jessop"

    uv run rr-crew --ideas

Writes research.md, images/ (with credits.csv), shot_list.md, script_draft.md, hooks.md, script_final.md, titles.md
and thumbnails.md into OUTPUT_DIR/<topic-slug>/. Finished steps are reused on a re-run (use --fresh to redo them).
--ideas writes ten ranked video ideas to OUTPUT_DIR/_ideas/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from rr_crew import prompts
from rr_crew.commons import download_images, wikipedia_article

WIKI_TOOL = {
    "name": "wikipedia_article",
    "description": "Read an English Wikipedia article as plain text plus the external reference links it cites. "
                   "Use it to map a topic and find better sources to cite.",
    "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
}
SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5, "max_content_tokens": 8000}
FETCH_BETA = "web-fetch-2025-09-10"
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "64000"))
CUT = "[OUTPUT CUT OFF: this file is incomplete]"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def text_of(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", "") == "text").strip()


class Agent:
    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client, self.model, self.fetch_ok = client, model, True

    def _call(self, system, messages, tools):
        # Streaming lets long answers finish; a high token ceiling leaves room for the model's thinking plus the file.
        kwargs = dict(model=self.model, max_tokens=MAX_TOKENS, system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        if self.fetch_ok and any(t.get("name") == "web_fetch" for t in tools or []):
            try:
                with self.client.beta.messages.stream(betas=[FETCH_BETA], **kwargs) as s:
                    return s.get_final_message()
            except anthropic.BadRequestError as e:
                print(f"  (page fetching unavailable, continuing with web search only: {e.message[:120]})")
                self.fetch_ok = False
                kwargs["tools"] = [t for t in tools if t.get("name") != "web_fetch"]
        with self.client.messages.stream(**kwargs) as s:
            return s.get_final_message()

    def ask(self, system: str, prompt: str, tools=None, max_rounds: int = 40) -> str:
        messages = [{"role": "user", "content": prompt}]
        for _ in range(max_rounds):
            r = self._call(system, messages, tools)
            messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
            if r.stop_reason == "pause_turn":
                continue
            if r.stop_reason == "tool_use":
                results = []
                for b in r.content:
                    if b.type == "tool_use" and b.name == "wikipedia_article":
                        title = b.input.get("title", "")
                        print(f"  reading Wikipedia: {title}")
                        try:
                            out = wikipedia_article(title)
                        except Exception as e:
                            out = f"Error: {e}"
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
                if results:
                    messages.append({"role": "user", "content": results})
                    continue
            text = text_of(r.content)
            if r.stop_reason == "max_tokens":
                print("  WARNING: the answer hit the length limit and is incomplete.")
                text = (text + "\n\n" + CUT).strip()
            if not text:
                raise RuntimeError(f"The agent returned no text (stop reason: {r.stop_reason}). Nothing was saved; run again.")
            return text
        raise RuntimeError("The agent did not finish within the round limit.")


def channel_profile() -> str:
    for p in (Path.cwd() / "channel.md", Path(__file__).resolve().parent.parent / "channel.md"):
        if p.exists():
            return p.read_text()
    return "(no channel profile found)"


def step(out: Path, name: str, label: str, fresh: bool, make) -> str:
    """Run one bot, or reuse its file from an earlier run so a re-run costs nothing for finished steps."""
    f = out / name
    if f.exists() and not fresh and f.read_text().strip() and CUT not in f.read_text():
        print(f"{label} reusing {name}")
        return f.read_text()
    print(f"{label} ...")
    text = make()
    f.write_text(text)
    print(f"      saved {name} ({len(text.split())} words)")
    if CUT in text:
        sys.exit(f"\nStopped: {name} came back incomplete, so the next bots were not run. Run the same command again; "
                 "finished steps are kept.")
    return text


def run_ideas(agent: Agent, root: Path):
    profile = channel_profile()
    done = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")) if root.exists() else []
    print("Scouting 10 new video ideas ...")
    search = dict(SEARCH_TOOL, max_uses=8)
    ideas = agent.ask(prompts.IDEA_SCOUT,
                      f"CHANNEL PROFILE:\n{profile}\n\nTopics already researched by the crew: {', '.join(done) or 'none'}",
                      tools=[search, WIKI_TOOL])
    folder = root / "_ideas"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"ideas-{date.today().isoformat()}.md"
    f.write_text(ideas)
    print(f"\nDone. Ideas saved in {f}")


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Riddles & Realms documentary crew")
    ap.add_argument("topic", nargs="*", help='Topic, e.g. "Violet Jessop"')
    ap.add_argument("--ideas", action="store_true", help="Suggest 10 new video ideas instead of building a topic")
    ap.add_argument("--full", action="store_true",
                    help="Also run images, scripts, hooks, retention, titles and thumbnails (costs more)")
    ap.add_argument("--fresh", action="store_true", help="Redo every step instead of reusing finished ones")
    a = ap.parse_args()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is missing. Put it in the .env file (see .env.example).")
    model = os.getenv("MODEL", "claude-sonnet-5-5").removeprefix("anthropic/")
    root = Path(os.getenv("OUTPUT_DIR", "output")).expanduser()
    agent = Agent(anthropic.Anthropic(), model)
    if a.ideas:
        return run_ideas(agent, root)

    topic = " ".join(a.topic) or os.getenv("TOPIC") or input("Topic: ").strip()
    if not topic:
        sys.exit("No topic given.")
    out = root / slugify(topic)
    out.mkdir(parents=True, exist_ok=True)
    profile = f"CHANNEL PROFILE:\n{channel_profile()}\n\n"

    research = step(out, "research.md", f"[1/7] Researching {topic}", a.fresh,
                    lambda: agent.ask(prompts.RESEARCHER, f"Topic: {topic}", tools=[SEARCH_TOOL, FETCH_TOOL, WIKI_TOOL]))

    if not a.full:
        print(f"\nDone. Research saved in {out / 'research.md'}\n"
              "Claude writes the scripts, hooks and picture prompts from it. Add --full to have the bots do them too.")
        return

    if True:
        def images():
            raw = agent.ask(prompts.HOUSE, prompts.IMAGE_QUERIES + "\n\n" + research)
            try:
                queries = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
            except ValueError:
                queries = [topic]
            seen, folder = set(), out / "images"
            for q in queries[:10]:
                for line in download_images(q, folder, per_query=2, seen=seen):
                    print(f"      {line}")
            credits = (folder / "credits.csv").read_text() if (folder / "credits.csv").exists() else "(no images found)"
            return agent.ask(prompts.SHOT_LIST, f"RESEARCH FILE:\n{research}\n\nCREDITS:\n{credits}")
        step(out, "shot_list.md", "[2/7] Finding images and writing the shot list", a.fresh, images)

    draft = step(out, "script_draft.md", "[3/7] Drafting the scripts", a.fresh,
                 lambda: agent.ask(prompts.SCRIPT, f"RESEARCH FILE:\n{research}"))
    hooks = step(out, "hooks.md", "[4/7] Writing opening hooks", a.fresh,
                 lambda: agent.ask(prompts.HOOKS, f"{profile}RESEARCH FILE:\n{research}\n\nDRAFT SCRIPTS:\n{draft}"))
    final = step(out, "script_final.md", "[5/7] Retention edit", a.fresh,
                 lambda: agent.ask(prompts.RETENTION, f"{profile}RESEARCH FILE:\n{research}\n\nDRAFT SCRIPTS:\n{draft}\n\nHOOKS:\n{hooks}"))
    titles = step(out, "titles.md", "[6/7] Writing titles and description", a.fresh,
                  lambda: agent.ask(prompts.TITLES, f"{profile}FINAL SCRIPTS:\n{final}"))
    step(out, "thumbnails.md", "[7/7] Designing thumbnails", a.fresh,
         lambda: agent.ask(prompts.THUMBNAILS, f"{profile}TITLES:\n{titles}\n\nFINAL SCRIPTS:\n{final}"))
    print(f"\nDone. Package saved in {out}")

if __name__ == "__main__":
    main()
