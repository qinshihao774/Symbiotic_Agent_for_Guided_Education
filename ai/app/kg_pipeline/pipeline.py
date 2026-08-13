"""知识图谱构建 Pipeline — 端到端调度

7 步流程：
1. OCR（仅 PDF）
2. Chunking（携带 heading_path/heading_levels）
3. 章节节点生成（不用 LLM）
4. LLM 知识点抽取（注入章节上下文）
5. GraphBuilder（合并章节节点 + 知识点自动挂载）
6. 跨章节依赖抽取（LLM，可选）
7. AGE Storage + pgvector 切片入库

"""
import logging
import os
import tempfile
import datetime
from typing import Optional
from app.config import settings
from app.kg_pipeline.models import DocumentChunk, KnowledgeGraph3D, PipelineResult
from app.kg_pipeline.chunking import MarkdownChunker
from app.kg_pipeline.chapter_builder import ChapterBuilder
from app.kg_pipeline.extraction import KGExtractor, LlmExtractionError
from app.kg_pipeline.graph_builder import GraphBuilder
from app.kg_pipeline.cross_chapter import CrossChapterExtractor
from app.kg_pipeline.storage import AgeStorage, AgeConnectionError
from app.engines.rag.ingestion import DocIngestion
from app.ocr.service import (
    get_infer_result,
    get_output_parse_dir,
    run_ocr_parse as ocr_parse_files,
)
from app.ocr.schemas import OcrParseParams, StoredUpload
logger = logging.getLogger(__name__)
class OcrServiceError(Exception):
    """OCR 服务故障"""
    pass

class KGPipeline:
    """知识图谱构建 Pipeline"""
    def __init__(
        self,
        chunker: Optional[MarkdownChunker] = None,
        extractor: Optional[KGExtractor] = None,
        chapter_builder: Optional[ChapterBuilder] = None,
        graph_builder: Optional[GraphBuilder] = None,
        cross_chapter_extractor: Optional[CrossChapterExtractor] = None,
        storage: Optional[AgeStorage] = None,
        graph_name: Optional[str] = None,
        enable_cross_chapter: bool = True,
        ingestor: Optional[DocIngestion] = None,
    ):
        self.chunker = chunker or MarkdownChunker()
        self.extractor = extractor or KGExtractor()
        self.chapter_builder = chapter_builder or ChapterBuilder()
        self.graph_builder = graph_builder or GraphBuilder()
        self.cross_chapter_extractor = cross_chapter_extractor or CrossChapterExtractor(enable=enable_cross_chapter)
        self.storage = storage or AgeStorage(graph_name=graph_name)
        self.ingestor = ingestor or DocIngestion()
    async def _parse_document(self, file_path: str, output_dir: str) -> str:
        """调用 OCR 服务解析文档为 Markdown"""
        filename = os.path.basename(file_path)
        stem = os.path.splitext(filename)[0]
        suffix = os.path.splitext(filename)[1].lstrip(".").lower()
        if suffix not in ("pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"):
            raise OcrServiceError(f"Unsupported file type: .{suffix}")
        try:
            upload = StoredUpload(
                original_name=filename,
                stem=stem,
                path=file_path,
            )
            file_names = await ocr_parse_files(
                output_dir=output_dir,
                uploads=[upload],
                params=OcrParseParams(),
                server_url=settings.OCR_VLM_URL,
            )
        except Exception as e:
            raise OcrServiceError(f"OCR parsing failed: {e}") from e
        if not file_names:
            raise OcrServiceError("OCR returned no output files")
        pdf_name = file_names[0]
        parse_dir = get_output_parse_dir(output_dir, pdf_name)
        md_content = get_infer_result(".md", pdf_name, parse_dir)
        if md_content is None:
            raise OcrServiceError(f"Markdown result not found for {pdf_name}")
        return md_content
    async def _extract_all_chunks(
        self, chunks: list[DocumentChunk]
    ) -> tuple[list[KnowledgeGraph3D], int]:
        """逐块进行 LLM 抽取；单个 chunk 失败时跳过并计数，不中断整个构建

        Returns:
            (chunk_graphs, failed_chunks)：失败的 chunk 以空图占位
        """
        chunk_graphs: list[KnowledgeGraph3D] = []
        failed_chunks = 0
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            logger.info(f"[KG] Extracting chunk {i + 1}/{total}")
            try:
                kg = await self.extractor.extract_from_chunk(chunk)
            except LlmExtractionError as e:
                failed_chunks += 1
                logger.error(f"[KG] Chunk {i + 1}/{total} extraction failed, skipped: {e}")
                chunk_graphs.append(KnowledgeGraph3D())
                continue
            chunk_graphs.append(kg)
        return chunk_graphs, failed_chunks
    async def run_from_markdown(self, markdown_text: str, kg_graph_id: int | None = None) -> PipelineResult:
        """从 Markdown 文本直接构建知识图谱（跳过 OCR）

        7 步流程：

        1. Chunking — 生成携带 heading_path 的 chunks

        2. 章节节点生成 — 从 heading_path 生成 Chapter 节点 + contains 边

        3. LLM 知识点抽取 — 注入章节上下文

        4. GraphBuilder — 合并章节 + 知识点，自动挂载

        5. 跨章节依赖抽取 — LLM 按章节对判断依赖

        6. AGE Storage

        7. pgvector 切片入库 — 关联 kg_graph_id（失败不中断构建）

        Args:
            markdown_text: Markdown 格式的文档内容
            kg_graph_id: 关联的知识图谱 ID（用于向量切片入库）

        Returns:
            PipelineResult 执行统计

        """
        # Step 1: Chunking
        logger.info("[KG] Phase 1: Chunking")
        chunks = self.chunker.chunk(markdown_text)
        logger.info(f"[KG] Generated {len(chunks)} chunks")
        # Step 2: 章节节点生成（不用 LLM）
        logger.info("[KG] Phase 2: Chapter node generation")
        chapter_graph = self.chapter_builder.build(chunks)
        logger.info(f"[KG] Generated {len(chapter_graph.nodes)} chapter nodes, {len(chapter_graph.edges)} contains edges")
        # Step 3: LLM 知识点抽取
        logger.info("[KG] Phase 3: LLM Knowledge point extraction")
        chunk_graphs, failed_chunks = await self._extract_all_chunks(chunks)
        total_nodes = sum(len(kg.nodes) for kg in chunk_graphs)
        total_edges = sum(len(kg.edges) for kg in chunk_graphs)
        logger.info(f"[KG] Extracted {total_nodes} knowledge points, {total_edges} internal edges from LLM")
        if failed_chunks > 0:
            logger.warning(f"[KG] {failed_chunks}/{len(chunks)} chunks failed extraction, continuing with partial graph")
        # Step 4: GraphBuilder — 合并章节 + 知识点，自动挂载
        logger.info("[KG] Phase 4: Graph building (merge + auto-mount)")
        graph = self.graph_builder.build(
            chunk_graphs=chunk_graphs,
            chapter_graph=chapter_graph,
            chunks=chunks,
        )
        logger.info(f"[KG] Merged graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        # Step 5: 跨章节依赖抽取（可选）
        if self.cross_chapter_extractor.enable:
            logger.info("[KG] Phase 5: Cross-chapter dependency extraction")
            cross_edges = await self.cross_chapter_extractor.extract(graph)
            if cross_edges:
                for edge in cross_edges:
                    # 添加跨章节边到图
                    if edge.source_node_id in graph and edge.target_node_id in graph:
                        key = (edge.source_node_id, edge.target_node_id)
                        if not graph.has_edge(*key):
                            graph.add_edge(
                                edge.source_node_id,
                                edge.target_node_id,
                                relationship_name=edge.relationship_name,
                                description=edge.description,
                            )
                logger.info(f"[KG] Added {len(cross_edges)} cross-chapter dependency edges")
        else:
            logger.info("[KG] Phase 5: Cross-chapter extraction disabled, skipping")
        # Step 6: AGE Storage
        logger.info("[KG] Phase 6: AGE Storage")
        self.storage.initialize_graph()
        edge_count = self.storage.write_graph(graph)
        logger.info(f"[KG] Written {edge_count} edges to AGE")
        # Step 7: pgvector Ingestion（失败不中断构建）
        logger.info("[KG] Phase 7: pgvector ingestion")
        try:
            entities_per_chunk: dict[int, list[str]] = {}
            for i, kg in enumerate(chunk_graphs):
                ci = chunks[i].chunk_index if i < len(chunks) else i
                entities_per_chunk[ci] = [n.name for n in kg.nodes]

            sub_count = await self.ingestor.ingest(
                chunks=chunks,
                entities_per_chunk=entities_per_chunk,
                kg_graph_id=kg_graph_id,
                course_id=None,
                source="kg_pipeline",
            )
            logger.info(f"[KG] Ingested {sub_count} vector chunks to pgvector")
        except Exception as e:
            logger.warning(f"[KG] Step 7 (pgvector ingestion) failed: {e}")
            # Step 7 失败不影响整体 Pipeline 结果

        all_failed = failed_chunks > 0 and failed_chunks == len(chunks)
        return PipelineResult(
            chunks=len(chunks),
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
            status="failed" if all_failed else "completed",
            error=(
                f"All {len(chunks)} chunks failed extraction"
                if all_failed
                else None
            ),
            failed_chunks=failed_chunks,
        )
    async def run_from_file(self, file_path: str, kg_graph_id: int | None = None) -> PipelineResult:
        """从原始文档文件构建知识图谱（PDF → OCR → KG，或 Markdown → 直接处理）

        Args:
            file_path: 原始文档路径
            kg_graph_id: 关联的知识图谱 ID（用于向量切片入库）

        Returns:
            PipelineResult 执行统计

        """
        logger.info(f"[KG] Starting pipeline for: {file_path}")
        # 检查文件类型：Markdown 直接处理，跳过 OCR
        suffix = os.path.splitext(file_path)[1].lstrip(".").lower()
        logger.info(f"[KG] Filetype: {suffix}")
        if suffix == "md":
            logger.info("[KG] Markdown file detected, skipping OCR")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                logger.info(f"[KG] Loaded Markdown, length: {len(md_content)} chars")
                return await self.run_from_markdown(md_content, kg_graph_id=kg_graph_id)
            except Exception as e:
                logger.error(f"[KG] Failed to read Markdown file: {e}", exc_info=True)
                return PipelineResult(status="failed", error=str(e))
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                logger.info("[KG] Phase 0: OCR Parsing")
                md_content = await self._parse_document(file_path, tmpdir)
                logger.info(f"[KG] OCR completed, Markdown length: {len(md_content)} chars")
            except OcrServiceError as e:
                logger.error(f"[KG] OCR failed: {e}")
                return PipelineResult(status="failed", error=str(e))
            try:
                return await self.run_from_markdown(md_content, kg_graph_id=kg_graph_id)
            except Exception as e:
                logger.error(f"[KG] Pipeline failed after OCR: {e}", exc_info=True)
                return PipelineResult(status="failed", error=str(e))
