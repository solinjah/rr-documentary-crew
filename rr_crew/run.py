"""Run the documentary crew for one topic.

    uv run rr-crew "Violet Jessop"

Writes research.md, images/ (with credits.csv), shot_list.md and script_draft.md into OUTPUT_DIR/<topic-slug>/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
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
SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 15}
FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 15}
FETCH_BETA = "web-fetch-2025-09-10"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def text_of(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", "") == "text").strip()


class Agent:
    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client, self.model, self.fetch_ok = client, model, True

    def _call(self, system, messages, tools):
        kwargs = dict(model=self.model, max_tokens=16000, system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        if self.fetch_ok and any(t.get("name") == "web_fetch" for t in tools or []):
            try:
                return self.client.beta.messages.create(betas=[FETCH_BETA], **kwargs)
            except anthropic.BadRequestError as e:
                print(f"  (page fetching unavailable, continuing with web search only: {e.message[:120]})")
                self.fetch_ok = False
                kwargs["tools"] = [t for t in tools if t.get("name") != "web_fetch"]
        return self.client.messages.create(**kwargs)

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
            return text_of(r.content)
        raise RuntimeError("The agent did not finish within the round limit.")


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Riddles & Realms documentary crew")
    ap.add_argument("topic", nargs="*", help='Topic, e.g. "Violet Jessop"')
    ap.add_argument("--skip-images", action="store_true")
    a = ap.parse_args()
    topic = " ".join(a.topic) or os.getenv("TOPIC") or input("Topic: ").strip()
    if not topic:
        sys.exit("No topic given.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is missing. Put it in the .env file (see .env.example).")
    model = os.getenv("MODEL", "claude-sonnet-5-5").removeprefix("anthropic/")
    out = Path(os.getenv("OUTPUT_DIR", "output")).expanduser() / slugify(topic)
    out.mkdir(parents=True, exist_ok=True)
    agent = Agent(anthropic.Anthropic(), model)

    print(f"[1/4] Researching {topic} ...")
    research = agent.ask(prompts.RESEARCHER, f"Topic: {topic}", tools=[SEARCH_TOOL, FETCH_TOOL, WIKI_TOOL])
    (out / "research.md").write_text(research)
    print(f"      saved research.md ({len(research.split())} words)")

    if not a.skip_images:
        print("[2/4] Finding images ...")
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
        print("[3/4] Writing the shot list ...")
        shots = agent.ask(prompts.SHOT_LIST, f"RESEARCH FILE:\n{research}\n\nCREDITS:\n{credits}")
        (out / "shot_list.md").write_text(shots)

    print("[4/4] Drafting the scripts ...")
    script = agent.ask(prompts.SCRIPT, f"RESEARCH FILE:\n{research}")
    (out / "script_draft.md").write_text(script)
    print(f"\nDone. Package saved in {out}")


if __name__ == "__main__":
    main()
