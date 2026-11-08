# Riddles & Realms Documentary Crew

Three AI agents that prepare a documentary package for one topic:

| Agent | Produces |
| --- | --- |
| Archive Researcher | `research.md`: timeline, facts and quotes, each with a numbered source, plus what the record cannot settle |
| Image Scout | `images/` with 8 to 12 openly licensed images, `credits.csv` (author, license, source page) and `shot_list.md` |
| Script Drafter | `script_draft.md`: a 10-minute episode script, three 60 to 75 second Shorts scripts, a title and a description |

Claude, the editor, then fact-checks the package and produces the narrated episode, the Shorts, captions and thumbnail.

## One-time setup on the Mac

Open **Terminal** and run these one at a time.

1. Install uv, the tool that installs Python and crewAI for you:

   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Close Terminal and open it again.

2. Install crewAI:

   ```
   uv tool install crewai
   ```

3. Get this project onto the Mac. The easiest way for a private repository is the free **GitHub Desktop** app:
   File → Clone Repository → `solinjah/rr-documentary-crew` → save it in your Documents folder.

4. Go into the project folder and install its parts:

   ```
   cd ~/Documents/GitHub/rr-documentary-crew
   crewai install
   ```

5. Create your settings file and open it:

   ```
   cp .env.example .env
   open -e .env
   ```

   Paste your API key after `ANTHROPIC_API_KEY=` (or switch to the OpenAI lines), and set `OUTPUT_DIR` to the folder
   Claude can read, for example:

   ```
   OUTPUT_DIR=/Users/ronaljoseph/Desktop/1 milly/untitled folder/TTRR/Book/crew-output
   ```

   Save and close. The `.env` file stays on your Mac and is never uploaded to GitHub.

## Run it for a topic

```
cd ~/Documents/GitHub/rr-documentary-crew
TOPIC="Violet Jessop" crewai run
```

When it finishes, the package is in `OUTPUT_DIR/violet-jessop/`. Tell Claude the topic is ready.

## Rules the agents follow

- Every fact carries a numbered source; disagreements are listed side by side, never resolved by guessing.
- Images are public domain or openly licensed, logged with author and license, and never show a different
  person, place or event as if it were this one.
- Scripts use only facts from the research file and mark anything uncertain with [CHECK].

## Costs

Each run calls your AI provider several times. Expect roughly a few cents to under a dollar per topic with a
Sonnet-class model; check your provider's usage page after the first run.
