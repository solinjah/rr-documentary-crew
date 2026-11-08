"""Run the crew for one topic.

    crewai run                         asks for a topic
    TOPIC="Violet Jessop" crewai run   uses the TOPIC setting
"""
import os
import re
import sys

from rr_documentary_crew.crew import DocumentaryCrew


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def run():
    topic = os.getenv("TOPIC") or (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "") or input("Topic: ").strip()
    if not topic:
        sys.exit("No topic given.")
    output_dir = os.getenv("OUTPUT_DIR", "output")
    inputs = {"topic": topic, "topic_slug": slugify(topic), "output_dir": output_dir}
    os.makedirs(os.path.join(output_dir, inputs["topic_slug"], "images"), exist_ok=True)
    DocumentaryCrew().crew().kickoff(inputs=inputs)
    print(f"\nDone. Package saved in {output_dir}/{inputs['topic_slug']}/")


if __name__ == "__main__":
    run()
