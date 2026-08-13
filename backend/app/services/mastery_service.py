"""Mastery service for the student knowledge graph closed loop.

Flow:
  exercise submit -> knowledge-unit mastery -> section mastery
  -> chapter mastery -> course mastery.

The course graph uses Chapter nodes for chapters/sections. A leaf Chapter with
no knowledge point children is treated as a virtual knowledge point, matching
the product rule that "a section without knowledge points is itself the
knowledge point".
"""
import logging
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.course import Course
from app.models.kg_graph import KgGraph
from app.models.learning import StudentCourseMastery, StudentKnowledgeMastery

logger = logging.getLogger(__name__)

OBJECTIVE_TYPES = {"single_choice", "multiple_choice", "T_or_F", "choice", "true_false"}
CONTAINS_RELATION_NAMES = {"包含", "鍖呭惈"}
PASS_DEGREE = 3.0


class MasteryService:
    """Student knowledge graph mastery service."""

    async def update_knowledge_mastery(
        self,
        stu_id: int,
        course_id: int,
        kg_node_name: str | None,
        question_type: str,
        do_score: Optional[float],
        do_isTrue: Optional[bool],
        db: AsyncSession,
        kg_id: int | None = None,
    ) -> None:
        """Update one knowledge unit after an exercise submission.

        Knowledge unit names come from questions.kg_node_name. For ordinary
        sections this is a real knowledge point; for sections without children
        it can be the section name itself.
        """
        if not kg_node_name:
            return

        this_degree = self._calc_degree(question_type, do_score, do_isTrue)
        result = await db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.stu_id == stu_id,
                StudentKnowledgeMastery.course_id == course_id,
                StudentKnowledgeMastery.kg_node_name == kg_node_name,
            )
        )
        mastery = result.scalar_one_or_none()

        if mastery is None:
            mastery = StudentKnowledgeMastery(
                stu_id=stu_id,
                course_id=course_id,
                kg_id=kg_id,
                kg_node_name=kg_node_name,
                kg_degree=this_degree,
                answered_count=1,
                correct_count=1 if this_degree >= PASS_DEGREE else 0,
            )
            db.add(mastery)
        else:
            old_count = mastery.answered_count or 0
            new_count = old_count + 1
            mastery.kg_degree = round(
                (float(mastery.kg_degree or 0.0) * old_count + this_degree) / new_count,
                2,
            )
            mastery.answered_count = new_count
            mastery.kg_id = kg_id or mastery.kg_id
            if this_degree >= PASS_DEGREE:
                mastery.correct_count = (mastery.correct_count or 0) + 1

        await db.flush()

        try:
            await self.sync_course_mastery(stu_id, course_id, db)
        except Exception as exc:
            logger.error(
                "[MasteryService] failed to sync course mastery stu_id=%s course_id=%s: %s",
                stu_id,
                course_id,
                exc,
                exc_info=True,
            )

        await db.commit()

    @staticmethod
    def _calc_degree(
        question_type: str,
        do_score: Optional[float],
        do_isTrue: Optional[bool],
    ) -> float:
        """Convert one answer into a 0-5 mastery score."""
        if question_type in OBJECTIVE_TYPES:
            return 5.0 if do_isTrue else 0.0
        if do_score is None:
            return 0.0
        return round(max(0.0, min(5.0, do_score / 10 * 5)), 2)

    async def sync_course_mastery(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> dict[str, Any]:
        """Recompute and upsert student_course_mastery for teacher dashboards."""
        hierarchy = await self.get_mastery_hierarchy(stu_id, course_id, db)
        result = await db.execute(
            select(StudentCourseMastery).where(
                StudentCourseMastery.stu_id == stu_id,
                StudentCourseMastery.course_id == course_id,
            )
        )
        mastery = result.scalar_one_or_none()
        if mastery is None:
            mastery = StudentCourseMastery(
                stu_id=stu_id,
                course_id=course_id,
                course_degree=hierarchy["course_degree"],
                course_process=hierarchy["course_process"],
            )
            db.add(mastery)
        else:
            mastery.course_degree = hierarchy["course_degree"]
            mastery.course_process = hierarchy["course_process"]
        await db.flush()
        return hierarchy

    async def _get_graph_name(self, course_id: int, db: AsyncSession) -> Optional[str]:
        course_result = await db.execute(
            select(Course).where(Course.course_id == course_id)
        )
        course = course_result.scalar_one_or_none()
        if course is None or course.kg_id is None:
            return None

        graph_result = await db.execute(
            select(KgGraph).where(KgGraph.id == course.kg_id)
        )
        graph = graph_result.scalar_one_or_none()
        return graph.graph_name if graph else None

    async def _fetch_graph_data(self, graph_name: str) -> Optional[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{settings.AI_SERVICE_URL}/kg/graph/data",
                    params={"graph_name": graph_name},
                    headers={"X-Service-Token": settings.AI_SERVICE_TOKEN},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error(
                "[MasteryService] failed to fetch graph data graph_name=%s: %s",
                graph_name,
                exc,
            )
            return None

    @staticmethod
    def _parse_hierarchy(data: dict[str, Any]) -> dict[str, Any]:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        node_map = {n["id"]: n for n in nodes if "id" in n}

        chapter_contains_targets: set[str] = set()
        chapter_children: dict[str, list[dict[str, Any]]] = {}
        chapter_knowledge_points: dict[str, list[dict[str, Any]]] = {}

        for edge in edges:
            if edge.get("relationship_name") not in CONTAINS_RELATION_NAMES:
                continue
            source = node_map.get(edge.get("source"))
            target = node_map.get(edge.get("target"))
            if not source or not target:
                continue

            source_is_chapter = source.get("type") == "Chapter"
            target_is_chapter = target.get("type") == "Chapter"
            if source_is_chapter and target_is_chapter:
                chapter_contains_targets.add(edge["target"])
                chapter_children.setdefault(edge["source"], []).append(target)
            elif source_is_chapter and not target_is_chapter:
                chapter_knowledge_points.setdefault(edge["source"], []).append(target)

        top_level_chapters = [
            node
            for node in nodes
            if node.get("type") == "Chapter" and node.get("id") not in chapter_contains_targets
        ]
        top_level_chapters.sort(key=lambda node: node.get("name", ""))

        return {
            "top_level_chapters": top_level_chapters,
            "chapter_children": chapter_children,
            "chapter_knowledge_points": chapter_knowledge_points,
            "node_map": node_map,
        }

    async def get_mastery_hierarchy(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> dict[str, Any]:
        course_result = await db.execute(
            select(Course).where(Course.course_id == course_id)
        )
        course = course_result.scalar_one_or_none()
        course_name = course.course_name if course else f"course-{course_id}"

        mastery_result = await db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.stu_id == stu_id,
                StudentKnowledgeMastery.course_id == course_id,
            )
        )
        mastery_rows = mastery_result.scalars().all()
        degree_map = {m.kg_node_name: float(m.kg_degree or 0.0) for m in mastery_rows}
        answered_map = {m.kg_node_name: int(m.answered_count or 0) for m in mastery_rows}
        correct_map = {m.kg_node_name: int(m.correct_count or 0) for m in mastery_rows}

        graph_name = await self._get_graph_name(course_id, db)
        if graph_name is None:
            return self._empty_hierarchy(course_id, course_name)

        data = await self._fetch_graph_data(graph_name)
        if data is None:
            return self._empty_hierarchy(course_id, course_name)

        hierarchy = self._parse_hierarchy(data)
        chapters = [
            self._build_chapter_node(
                chapter,
                hierarchy["chapter_children"],
                hierarchy["chapter_knowledge_points"],
                degree_map,
                answered_map,
                correct_map,
            )
            for chapter in hierarchy["top_level_chapters"]
        ]

        course_degree = self._avg([chapter["degree"] for chapter in chapters])
        course_process = self._avg([chapter["process"] for chapter in chapters])

        return {
            "course_id": course_id,
            "course_name": course_name,
            "course_degree": course_degree,
            "course_process": course_process,
            "chapters": chapters,
        }

    def _build_chapter_node(
        self,
        chapter: dict[str, Any],
        chapter_children: dict[str, list[dict[str, Any]]],
        chapter_knowledge_points: dict[str, list[dict[str, Any]]],
        degree_map: dict[str, float],
        answered_map: dict[str, int],
        correct_map: dict[str, int],
    ) -> dict[str, Any]:
        chapter_id = chapter["id"]
        section_nodes = chapter_children.get(chapter_id, [])
        direct_kps = chapter_knowledge_points.get(chapter_id, [])

        sections = [
            self._build_chapter_node(
                section,
                chapter_children,
                chapter_knowledge_points,
                degree_map,
                answered_map,
                correct_map,
            )
            for section in section_nodes
        ]

        kp_nodes = [
            self._knowledge_point_node(kp.get("name", ""), degree_map, answered_map, correct_map)
            for kp in direct_kps
        ]

        if not sections and not kp_nodes:
            # Product rule: a section without knowledge points is itself a
            # practiceable knowledge unit.
            kp_nodes.append(
                self._knowledge_point_node(
                    chapter.get("name", ""),
                    degree_map,
                    answered_map,
                    correct_map,
                    is_virtual=True,
                )
            )

        child_degrees = [section["degree"] for section in sections] + [
            kp["degree"] for kp in kp_nodes
        ]
        child_processes = [section["process"] for section in sections] + [
            1.0 if kp["answered_count"] > 0 else 0.0 for kp in kp_nodes
        ]

        return {
            "name": chapter.get("name", ""),
            "degree": self._avg(child_degrees),
            "process": self._avg(child_processes),
            "sections": sections,
            "knowledge_points": kp_nodes,
        }

    @staticmethod
    def _knowledge_point_node(
        name: str,
        degree_map: dict[str, float],
        answered_map: dict[str, int],
        correct_map: dict[str, int],
        is_virtual: bool = False,
    ) -> dict[str, Any]:
        node = {
            "name": name,
            "degree": degree_map.get(name, 0.0),
            "answered_count": answered_map.get(name, 0),
            "correct_count": correct_map.get(name, 0),
        }
        if is_virtual:
            node["is_virtual"] = True
        return node

    @staticmethod
    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    @staticmethod
    def _empty_hierarchy(course_id: int, course_name: str) -> dict[str, Any]:
        return {
            "course_id": course_id,
            "course_name": course_name,
            "course_degree": 0.0,
            "course_process": 0.0,
            "chapters": [],
        }
