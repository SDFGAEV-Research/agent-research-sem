from __future__ import annotations

import re
from dataclasses import replace

from research_platform.governance.algorithm.api import (
    AlgorithmLanguage,
    AlgorithmMetrics,
    AlgorithmSymbol,
    FileAnalysis,
    SourceDocument,
)
from .scoring import estimated_complexity, score_metrics

_JS_FUNC = re.compile(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")
_SHELL_FUNC = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{")
_JS_NON_FUNCTION_KEYWORDS = {"if", "for", "while", "switch", "catch", "with", "else", "do", "try"}


def _balanced_block(lines: list[str], start: int, open_char: str = "{", close_char: str = "}") -> int:
    depth = 0
    seen = False
    for idx in range(start, len(lines)):
        line = lines[idx]
        depth += line.count(open_char)
        if line.count(open_char):
            seen = True
        depth -= line.count(close_char)
        if seen and depth <= 0:
            return idx
    return len(lines) - 1


def _build_symbol(document: SourceDocument, name: str, start: int, end: int, body: list[str], language: AlgorithmLanguage) -> AlgorithmSymbol:
    loop_tokens = ("for ", "for(", "while ", "while(", ".forEach(") if language == AlgorithmLanguage.JAVASCRIPT else ("for ", "while ", "until ", "select ")
    branch_tokens = ("if ", "if(", "case ", "?", "catch") if language == AlgorithmLanguage.JAVASCRIPT else ("if ", "case ", "&&", "||")
    loops = 0
    max_depth = 0
    depth = 0
    subprocess_in_loop = 0
    io_in_loop = 0
    sort_calls = 0
    calls = 0
    for raw in body:
        line = raw.strip()
        opens_loop = any(token in line for token in loop_tokens)
        if opens_loop:
            loops += 1
            depth += 1
            max_depth = max(max_depth, depth)
        calls += line.count("(")
        sort_calls += line.count(".sort(") + line.count(" sort ")
        if depth:
            if language == AlgorithmLanguage.SHELL and re.search(r"(^|[;&|]\s*)(curl|wget|python|node|java|docker|git|ssh|scp|rsync|find|tar|unzip)\b", line):
                subprocess_in_loop += 1
            if language == AlgorithmLanguage.JAVASCRIPT and re.search(r"\b(fs\.|fetch\(|axios\.|child_process\.)", line):
                io_in_loop += 1
        if language == AlgorithmLanguage.JAVASCRIPT:
            depth += line.count("{") - line.count("}")
            depth = max(0, depth)
        else:
            if re.match(r"^(done|fi|esac)\b", line):
                depth = max(0, depth - 1)
    branches = sum(sum(line.count(token) for token in branch_tokens) for line in body)
    base = AlgorithmMetrics(
        source_lines=max(1, end - start + 1),
        branches=branches,
        loops=loops,
        max_loop_depth=max_depth,
        sort_calls=sort_calls,
        io_calls_in_loops=io_in_loop,
        subprocess_calls_in_loops=subprocess_in_loop,
        call_count=calls,
        cyclomatic_estimate=1 + branches + loops,
        estimated_complexity=estimated_complexity(loops=loops, max_loop_depth=max_depth, sort_calls=sort_calls, recursive_calls=0),
    )
    score, findings = score_metrics(base)
    return AlgorithmSymbol(
        symbol_id=f"{document.relative_path}::{name}",
        relative_path=document.relative_path,
        language=language,
        qualified_name=name,
        line_start=start + 1,
        line_end=end + 1,
        metrics=replace(base, risk_score=score),
        findings=findings,
    )


class JavaScriptAlgorithmAnalyzer:
    language = AlgorithmLanguage.JAVASCRIPT
    revision = "javascript-structural-v2"

    def analyze(self, document: SourceDocument) -> FileAnalysis:
        lines = document.text.splitlines()
        symbols: list[AlgorithmSymbol] = []
        seen: set[tuple[str, int]] = set()
        for idx, line in enumerate(lines):
            match = _JS_FUNC.search(line)
            if not match:
                continue
            name = next((value for value in match.groups() if value), "anonymous")
            if name in _JS_NON_FUNCTION_KEYWORDS:
                continue
            key = (name, idx)
            if key in seen:
                continue
            seen.add(key)
            end = _balanced_block(lines, idx)
            symbols.append(_build_symbol(document, name, idx, end, lines[idx:end + 1], self.language))
        return FileAnalysis(document.relative_path, document.language, document.sha256, self.revision, tuple(symbols), 0)


class ShellAlgorithmAnalyzer:
    language = AlgorithmLanguage.SHELL
    revision = "shell-structural-v2"

    def analyze(self, document: SourceDocument) -> FileAnalysis:
        lines = document.text.splitlines()
        symbols: list[AlgorithmSymbol] = []
        for idx, line in enumerate(lines):
            match = _SHELL_FUNC.match(line)
            if not match:
                continue
            end = _balanced_block(lines, idx)
            symbols.append(_build_symbol(document, match.group(1), idx, end, lines[idx:end + 1], self.language))
        return FileAnalysis(document.relative_path, document.language, document.sha256, self.revision, tuple(symbols), 0)


__all__ = ["JavaScriptAlgorithmAnalyzer", "ShellAlgorithmAnalyzer"]
