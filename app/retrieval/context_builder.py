def build_context(results: list[dict]) -> tuple[str, list[dict]]:
    if not results:
        return "No relevant document passages were found.", []
    blocks: list[str] = []
    citations: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for index, item in enumerate(results, start=1):
        filename = item["filename"]
        page = int(item["page_number"])
        key = (filename, page, item["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        source_id = f"S{len(citations) + 1}"
        blocks.append(
            f"[{source_id}] Source: {filename} | Page: {page} | "
            f"Chunk: {item['chunk_index']}\n{item['content']}"
        )
        citations.append({
            "source_id": source_id,
            "filename": filename,
            "page_number": page,
            "chunk_id": item["chunk_id"],
            "retrieval_score": item.get("rrf_score"),
            "retrieval_methods": item.get("retrieval_methods", []),
        })
    return "\n\n---\n\n".join(blocks), citations
