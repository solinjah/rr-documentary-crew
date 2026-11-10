# Riddles & Realms Documentary Crew

A family of AI agents, run on the Anthropic API, that plans videos and prepares a documentary package for one topic.
The strategy agents read `channel.md` (niche, audience, what performs, topics already covered), so keep it up to date.

| Agent | Produces |
| --- | --- |
| Idea Scout | `_ideas/ideas-<date>.md`: ten ranked video ideas with angles, sources and risk notes (`--ideas`) |
| Archive Researcher | `research.md`: timeline, facts and quotes with numbered sources, what the record cannot settle |
| Image Scout | `images/` with openly licensed images from Wikimedia Commons, `credits.csv` and `shot_list.md` |
| Script Drafter | `script_draft.md`: a 10-minute episode script and three 60 to 75 second Shorts scripts |
| Hook Writer | `hooks.md`: five episode cold opens and three hooks per Short, best ones starred |
| Retention Editor | `script_final.md`: where viewers would leave and why, then the tightened final scripts |
| Title Strategist | `titles.md`: ten episode titles, Shorts titles and the description |
| Thumbnail Designer | `thumbnails.md`: five thumbnail concepts with image-generator prompts |

Claude, the editor, then fact-checks the package and produces the narrated episode, the Shorts, captions and thumbnail.

It needs only Python packages that install ready-made on Intel and Apple Silicon Macs.

## One-time setup on the Mac

You already installed **uv**. In Terminal:

1. Get the project. With the free **GitHub Desktop** app: File → Clone Repository → `solinjah/rr-documentary-crew`.
   It lands in `~/Documents/GitHub/rr-documentary-crew`.

2. Create your settings file and open it:

   ```
   cd ~/Documents/GitHub/rr-documentary-crew
   cp .env.example .env
   open -e .env
   ```

   Paste your Anthropic API key after `ANTHROPIC_API_KEY=`, then save and close. The `.env` file stays on your Mac
   and is never uploaded.

## Run it for a topic

```
cd ~/Documents/GitHub/rr-documentary-crew
uv run rr-crew "Violet Jessop"
```

The first run takes a minute longer while uv sets things up. When it finishes, the package is in
`crew-output/violet-jessop/` inside your Book folder. Tell Claude the topic is ready.

To get ten new video ideas:

```
uv run rr-crew --ideas
```

If a run stops part-way, run the same command again: finished steps are reused, so you only pay for the rest.
Add `--fresh` to redo every step.

To get new versions of the crew later: open GitHub Desktop and press **Fetch origin**, then **Pull**.

## Rules the agents follow

- Every fact carries a numbered source; disagreements are listed side by side, never resolved by guessing.
- Images are public domain or openly licensed, logged with author and license; anything that might show the wrong
  person, place or event is flagged for removal.
- Scripts use only facts from the research file and mark anything uncertain with [CHECK].
- Titles, hooks and thumbnails must promise only what the video delivers; no invented quotes, numbers or twists.
- Thumbnail prompts keep each person's look consistent and ask for correct anatomy and period details.

## Costs

Each topic uses several API calls plus up to about 15 web searches. Check the usage page at console.anthropic.com
after your first run to see the real cost per topic.
