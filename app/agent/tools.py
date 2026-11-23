from pathlib import Path
import subprocess

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.embeddings import embed_query
from app.core.models import CodeChunk

PROJECT_ROOT = Path.cwd().resolve()


async def search_codebase(query: str, limit: int = 3) -> list[dict]:
    query_vec = embed_query(query)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(CodeChunk)
            .order_by(CodeChunk.embedding.cosine_distance(query_vec))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "file_path": row.file_path,
            "start_line": row.start_line,
            "end_line": row.end_line,
            "content": row.content,
        }
        for row in rows
    ]


def read_file_snippet(file_path: str, start_line: int = 1, end_line: int = 60) -> str:
    target = (PROJECT_ROOT / file_path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)) or not target.is_file():
        return f"File unavailable: {file_path}"

    lines = target.read_text(encoding="utf-8").splitlines()
    safe_start = max(1, start_line)
    safe_end = min(len(lines), end_line)
    numbered = [
        f"{idx}: {lines[idx - 1]}"
        for idx in range(safe_start, safe_end + 1)
    ]
    return "\n".join(numbered) if numbered else "Empty file."


def get_recent_git_commits(file_path: str, limit: int = 3) -> str:
    target = (PROJECT_ROOT / file_path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)) or not target.exists():
        return "No git history available for target path."

    try:
        result = subprocess.run(
            ["git", "log", f"-n{limit}", "--oneline", "--", file_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = result.stdout.strip()
        return output if output else "No commits recorded for this file yet."
    except Exception as exc:
        return f"Git lookup skipped: {exc}"