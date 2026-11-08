import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool

from rr_documentary_crew.tools.wikimedia import CommonsImageTool, WikipediaArticleTool


def research_tools():
    tools = [WikipediaArticleTool(), ScrapeWebsiteTool()]
    if os.getenv("SERPER_API_KEY"):
        from crewai_tools import SerperDevTool
        tools.append(SerperDevTool())
    return tools


@CrewBase
class DocumentaryCrew:
    """Researcher -> Image Scout -> Script Drafter. The finished package goes to the editor (Claude) for fact-check and production."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"], tools=research_tools(), verbose=True)

    @agent
    def image_scout(self) -> Agent:
        return Agent(config=self.agents_config["image_scout"], tools=[CommonsImageTool()], verbose=True)

    @agent
    def script_drafter(self) -> Agent:
        return Agent(config=self.agents_config["script_drafter"], verbose=True)

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def image_task(self) -> Task:
        return Task(config=self.tasks_config["image_task"])

    @task
    def script_task(self) -> Task:
        return Task(config=self.tasks_config["script_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
