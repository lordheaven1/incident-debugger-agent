import asyncio
from pathlib import Path
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, engine, init_db
from app.core.embeddings import embed_query, embed_texts
from app.core.models import CodeChunk

ALLOWED_EXTENSIONS = {".py", ".md"}
IGNORED_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache"}


def chunk_file(file_path: Path, root_dir: Path, chunk_size: int = 25, overlap: int = 5) -> list[dict]:
    lines = file_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []

    chunks = []
    rel_path = file_path.relative_to(root_dir).as_posix()
    step = max(1, chunk_size - overlap)

    for start in range(0, len(lines), step):
        end = min(start + chunk_size, len(lines))
        snippet = "\n".join(lines[start:end]).strip()
        if snippet:
            chunks.append(
                {
                    "file_path": rel_path,
                    "start_line": start + 1,
                    "end_line": end,
                    "content": snippet,
                }
            )
        if end == len(lines):
            break

    return chunks


async def index_directory(target_dir: str = "sample_service") -> None:
    await init_db()
    root = Path(target_dir).resolve()
    files = [
        p for p in root.rglob("*")
        if p.is_file()
        and p.suffix in ALLOWED_EXTENSIONS
        and not any(part in IGNORED_DIRS for part in p.parts)
    ]

    all_chunks = []
    for file_path in files:
        all_chunks.extend(chunk_file(file_path, root.parent))

    if not all_chunks:
        print("No matching files found to index.")
        return

    texts = [f"{c['file_path']}\n{c['content']}" for c in all_chunks]
    embeddings = embed_texts(texts)

    async with AsyncSessionLocal() as session:
        await session.execute(delete(CodeChunk))
        for chunk, vector in zip(all_chunks, embeddings):
            session.add(
                CodeChunk(
                    file_path=chunk["file_path"],
                    start_line=chunk["start_line"],
                    end_line=chunk["end_line"],
                    content=chunk["content"],
                    embedding=vector,
                )
            )
        await session.commit()

    print(f"Indexed {len(all_chunks)} chunks from {len(files)} files into pgvector.")


async def verify_search(query: str) -> None:
    query_vec = embed_query(query)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(CodeChunk)
            .order_by(CodeChunk.embedding.cosine_distance(query_vec))
            .limit(2)
        )
        results = (await session.execute(stmt)).scalars().all()

    print(f"\nTop matches for: '{query}'")
    for match in results:
        print(f"- {match.file_path} (lines {match.start_line}-{match.end_line})")


async def main() -> None:
    try:
        await index_directory("sample_service")
        await verify_search("ZeroDivisionError: division by zero in calculate_token_quota")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())