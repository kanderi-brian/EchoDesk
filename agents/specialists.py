"""Domain agents that compose existing EchoDesk engines."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent
from .models import AgentContext, AgentResult, AgentTask


class PlannerAgent(BaseAgent):
    name = "planner"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        planner = self.services.get("planner")
        learning = self.services.get("learning_engine")
        recommendations = learning.recommend_plan(task.description) if learning else None
        if recommendations:
            context.set("learning_recommendations", recommendations)
        plan = planner.plan(task.description) if planner else None
        context.active_plan = plan
        assignments = self.assign_work(task.description, plan)
        context.set("assignments", assignments)
        return AgentResult(task.id, self.name, plan is not None, output={"plan": plan, "assignments": assignments, "recommendations": recommendations}, confidence=.85 if plan else .3, verification={"success": plan is not None})

    def assign_work(self, goal: str, plan: Any = None) -> list[str]:
        text = goal.casefold()
        agents = ["memory"]
        if any(word in text for word in ("research", "compare", "search", "internet")): agents.append("research")
        if any(word in text for word in ("code", "test", "bug", "repository", "implement")): agents.append("coding")
        if any(word in text for word in ("desktop", "click", "window", "application")): agents.extend(["vision", "desktop"])
        return list(dict.fromkeys(agents))

    def recommend_replan(self, results: list[AgentResult]) -> bool:
        return any(not result.success for result in results)

    def resolve_conflict(self, proposals: list[AgentResult], context: AgentContext) -> AgentResult | None:
        if not proposals: return None
        selected = max(proposals, key=lambda result: (bool(result.verification.get("success")), result.confidence))
        context.record("conflict_resolved", selected=selected.agent_name, task_id=selected.task_id)
        return selected


class CodingAgent(BaseAgent):
    name = "coding"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        root = Path(task.payload.get("root", "."))
        files = [str(path) for path in root.glob("*") if path.is_file()]
        executor = self.services.get("executor")
        output: Any = {"files": files, "recommendation": "Use TaskExecutor for approved code changes."}
        if task.payload.get("plan") is not None and executor:
            execution = executor.execute_plan(task.payload["plan"], task.description)
            output = execution.final_response
            success = execution.status == "SUCCESS"
        else:
            success = True
        return AgentResult(task.id, self.name, success, output=output, confidence=.75, verification={"success": success})


class ResearchAgent(BaseAgent):
    name = "research"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        internet, knowledge = self.services.get("internet_engine"), self.services.get("knowledge_engine")
        findings: list[Any] = []
        if knowledge and hasattr(knowledge, "search"):
            findings.append(knowledge.search(task.description))
        if internet and hasattr(internet, "search"):
            findings.append(internet.search(task.description))
        context.research_results.extend(findings)
        return AgentResult(task.id, self.name, True, output=findings, confidence=.7 if findings else .4, verification={"success": True})


class VisionAgent(BaseAgent):
    name = "vision"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        vision = self.services.get("vision_engine")
        if vision is None: return AgentResult(task.id, self.name, False, error="VisionEngine unavailable")
        scene = task.payload.get("scene") or vision.capture_scene(refresh=False)
        context.vision_state = scene
        query = task.payload.get("query")
        output = vision.find_element(query, scene) if query else scene
        return AgentResult(task.id, self.name, output is not None, output=output, confidence=getattr(output, "confidence", .8), verification={"success": output is not None})


class DesktopAgent(BaseAgent):
    name = "desktop"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        desktop, vision = self.services.get("desktop_controller"), self.services.get("vision_engine")
        if desktop is None: return AgentResult(task.id, self.name, False, error="Desktop controller unavailable")
        before = vision.capture_scene(refresh=False) if vision else None
        element = task.payload.get("element") or (vision.find_element(task.payload["query"], before) if vision and task.payload.get("query") else None)
        action = task.payload.get("action", "click")
        if element and hasattr(desktop, f"{action}_element"):
            output = getattr(desktop, f"{action}_element")(element)
        else:
            output = {"success": False, "message": "No semantic desktop target resolved."}
        verified = bool(output.get("success")) and (vision.verify_change(before) if vision and before else True)
        return AgentResult(task.id, self.name, verified, output=output, confidence=.8 if verified else .2, verification={"success": verified})


class MemoryAgent(BaseAgent):
    name = "memory"
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        memory = self.services.get("memory_engine")
        results: Any = []
        if memory and hasattr(memory, "search"):
            results = memory.search(task.description)
        context.retrieved_memories.append(results)
        return AgentResult(task.id, self.name, True, output=results, confidence=.65, verification={"success": True})
