"""f09_read: 数据读取 Filter — TC4 处理逻辑。

职责: 格式检测（csv/xlsx/json/parquet）、编码推断、别名映射。
将异构数据源统一读取为 pandas DataFrame。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".parquet": "parquet",
}


class ReaderFilter:
    """数据读取 Filter — 自动检测格式并读取为 DataFrame。

    支持:
    - CSV（自动检测编码）
    - Excel (.xlsx/.xls)
    - JSON / JSONL
    - Parquet
    - 原始文本（存入 ctx.raw_text）

    读取结果写入 ctx.data。
    """

    name = "read"

    def __init__(self, encoding: str | None = None):
        self._encoding = encoding

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        source = ctx.meta.get("input_source", "")
        if not source:
            logger.warning(f"[{self.name}] No input_source specified")
            return ctx

        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {source}")

        ext = path.suffix.lower()
        fmt = SUPPORTED_EXTENSIONS.get(ext)

        if fmt is None:
            # 尝试作为原始文本读取
            logger.info(f"[{self.name}] Unknown format, reading as raw text: {ext}")
            raw = path.read_text(encoding=self._encoding or "utf-8")
            return object.__replace__(ctx, raw_text=raw)

        logger.info(f"[{self.name}] Reading {fmt}: {path}")

        if fmt == "csv":
            df = self._read_csv(path)
        elif fmt == "excel":
            df = pd.read_excel(path)
        elif fmt == "json":
            df = self._read_json(path)
        elif fmt == "parquet":
            df = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        logger.info(
            f"[{self.name}] Read {len(df)} rows x {len(df.columns)} columns"
        )

        return ctx.with_data(df).with_metric("raw_row_count", len(df))

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """读取 CSV，自动检测编码。"""
        if self._encoding:
            return pd.read_csv(path, encoding=self._encoding)

        # 尝试常见编码
        for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]:
            try:
                return pd.read_csv(path, encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue

        raise ValueError(f"Unable to detect encoding for: {path}")

    def _read_json(self, path: Path) -> pd.DataFrame:
        """读取 JSON 或 JSONL。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict):
            return pd.DataFrame([data])

        raise ValueError(f"Unexpected JSON structure in: {path}")

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_data(None)
