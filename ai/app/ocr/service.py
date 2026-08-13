"""OCR 解析服务 — 封装 mineru 的 aio_do_parse"""

import asyncio
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from loguru import logger

from mineru.cli.common import (
    aio_do_parse,
    normalize_upload_filename,
    normalize_task_stem,
    read_fn,
    uniquify_task_stems,
)

from app.ocr.schemas import StoredUpload, OcrParseParams


# 支持的文件后缀
PDF_SUFFIXES = {"pdf"}
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}
SUPPORTED_SUFFIXES = PDF_SUFFIXES | IMAGE_SUFFIXES


def build_upload_destination(upload_dir: str, filename: str) -> Path:
    """构建上传文件目标路径，自动处理重名"""
    destination = Path(upload_dir) / filename
    if not destination.exists():
        return destination

    base_name = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        candidate = Path(upload_dir) / f"{base_name}__upload_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


async def save_upload_files(
    upload_dir: str,
    files: list[UploadFile],
) -> list[StoredUpload]:
    """保存上传文件到磁盘，返回 StoredUpload 列表"""
    os.makedirs(upload_dir, exist_ok=True)
    uploads: list[StoredUpload] = []

    for upload in files:
        original_name = upload.filename or f"upload-{os.urandom(4).hex()}"
        filename = normalize_upload_filename(original_name)
        normalized_stem = normalize_task_stem(Path(filename).stem)
        destination = build_upload_destination(upload_dir, filename)
        try:
            with open(destination, "wb") as handle:
                while True:
                    chunk = await upload.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)

            file_suffix = Path(filename).suffix.lstrip(".").lower()
            if file_suffix not in SUPPORTED_SUFFIXES:
                cleanup_file(str(destination))
                raise ValueError(f"Unsupported file type: {file_suffix}")

            uploads.append(
                StoredUpload(
                    original_name=original_name,
                    stem=normalized_stem,
                    path=str(destination),
                )
            )
        except Exception:
            cleanup_file(str(destination))
            raise
        finally:
            await upload.close()

    # 去重文件名
    normalized_stems, renamed_stems = uniquify_task_stems(
        [upload.stem for upload in uploads]
    )
    if renamed_stems:
        uploads = [
            StoredUpload(
                original_name=upload.original_name,
                stem=effective_stem,
                path=upload.path,
            )
            for upload, effective_stem in zip(uploads, normalized_stems)
        ]
    return uploads


def load_file_bytes(uploads: list[StoredUpload]) -> tuple[list[str], list[bytes]]:
    """读取上传文件的字节数据"""
    file_names = []
    bytes_list = []
    for upload in uploads:
        try:
            file_bytes = read_fn(Path(upload.path))
        except Exception as exc:
            raise RuntimeError(f"Failed to load file {upload.original_name}: {exc}") from exc
        file_names.append(upload.stem)
        bytes_list.append(file_bytes)
    return file_names, bytes_list


async def run_ocr_parse(
    output_dir: str,
    uploads: list[StoredUpload],
    params: OcrParseParams,
    server_url: str,
) -> list[str]:
    """
    调用 mineru aio_do_parse 完成文档解析。
    固定使用 vlm-http-client 模式。
    返回解析成功的文件名列表。
    """
    file_names, bytes_list = await asyncio.to_thread(load_file_bytes, uploads)
    lang_list = [params.lang] * len(file_names)

    await aio_do_parse(
        output_dir=output_dir,
        pdf_file_names=file_names,
        pdf_bytes_list=bytes_list,
        p_lang_list=lang_list,
        backend="vlm-http-client",
        parse_method="auto",
        formula_enable=params.formula_enable,
        table_enable=params.table_enable,
        server_url=server_url,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=True,
        f_dump_orig_pdf=True,
        f_dump_content_list=True,
        start_page_id=params.start_page_id,
        end_page_id=params.end_page_id,
        image_analysis=True,
    )
    return file_names


def get_infer_result(
    file_suffix: str,
    pdf_name: str,
    parse_dir: str,
) -> Optional[str]:
    """从结果目录中读取推理结果文件"""
    result_path = os.path.join(parse_dir, f"{pdf_name}{file_suffix}")
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as fp:
            return fp.read()
    return None


def get_output_parse_dir(output_dir: str, pdf_name: str) -> str:
    """获取解析结果目录路径，自动探测 mineru 实际输出目录"""
    # mineru 不同 backend 的输出目录结构可能不同，自动探测
    candidates = [
        os.path.join(output_dir, pdf_name, "vlm-http-client", "auto"),
        os.path.join(output_dir, pdf_name, "vlm-http-client"),
        os.path.join(output_dir, pdf_name, "vlm"),
        os.path.join(output_dir, pdf_name, "pipeline"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    # fallback
    return os.path.join(output_dir, pdf_name)


def create_result_zip(
    output_dir: str,
    file_names: list[str],
) -> str:
    """将解析结果打包为 ZIP 文件，ZIP 内部扁平化（只保留文件名，去掉 vlm/ 层级）"""
    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix="ocr_result_")
    os.close(zip_fd)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for pdf_name in file_names:
            parse_dir = get_output_parse_dir(output_dir, pdf_name)
            if not os.path.exists(parse_dir):
                logger.warning(f"Parse dir not found: {parse_dir}")
                continue

            # 添加 .md 文件
            md_path = os.path.join(parse_dir, f"{pdf_name}.md")
            if os.path.exists(md_path):
                zf.write(md_path, arcname=f"{pdf_name}.md")

            # 添加 _middle.json
            middle_path = os.path.join(parse_dir, f"{pdf_name}_middle.json")
            if os.path.exists(middle_path):
                zf.write(middle_path, arcname=f"{pdf_name}_middle.json")

            # 添加 _content_list.json
            content_path = os.path.join(parse_dir, f"{pdf_name}_content_list.json")
            if os.path.exists(content_path):
                zf.write(content_path, arcname=f"{pdf_name}_content_list.json")

            # 添加 _content_list_v2.json
            content_v2_path = os.path.join(parse_dir, f"{pdf_name}_content_list_v2.json")
            if os.path.exists(content_v2_path):
                zf.write(content_v2_path, arcname=f"{pdf_name}_content_list_v2.json")

            # 添加 _model.json
            model_path = os.path.join(parse_dir, f"{pdf_name}_model.json")
            if os.path.exists(model_path):
                zf.write(model_path, arcname=f"{pdf_name}_model.json")

            # 添加 images 目录
            images_dir = os.path.join(parse_dir, "images")
            if os.path.isdir(images_dir):
                for img_file in sorted(Path(images_dir).iterdir()):
                    if img_file.is_file():
                        zf.write(
                            str(img_file),
                            arcname=f"images/{img_file.name}",
                        )

            # 添加原始文件
            for path in sorted(Path(parse_dir).iterdir()):
                if path.is_file() and path.name.startswith(f"{pdf_name}_origin."):
                    zf.write(str(path), arcname=path.name)

    return zip_path


def cleanup_file(file_path: str) -> None:
    """清理临时文件或目录"""
    try:
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
    except Exception as e:
        logger.warning(f"Failed to cleanup {file_path}: {e}")
