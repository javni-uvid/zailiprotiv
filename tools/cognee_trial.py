"""A trial of cognee on one bill, with no LLM key: the graph is extracted by the local GLiNER model and embedded by
a local multilingual fastembed model. Writes the graph cognee draws (graf.html), its nodes and edges (graf.json)
and what took how long (proba.txt) into the folder given. Run by the cognee-trial workflow; nothing goes to the site."""
import asyncio
import json
import sys
import time
from pathlib import Path


async def main(pdf: str, out: str):
    import cognee
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    log = []
    t = time.time()
    await cognee.remember(pdf, dataset_name="zakon", extractor="gliner_demo", self_improvement=False)
    log.append(f"remember (dodavanje + graf + embedding): {time.time() - t:.0f} s")
    t = time.time()
    await cognee.visualize_graph(str(folder / "graf.html"), dataset="zakon", full=True, include_session_events=False)
    graph = await cognee.visualize_graph_json(dataset="zakon", full=True) if hasattr(cognee, "visualize_graph_json") else None
    log.append(f"vizualizacija: {time.time() - t:.0f} s")
    if graph is not None:
        (folder / "graf.json").write_text(graph if isinstance(graph, str) else json.dumps(graph, ensure_ascii=False, default=str), encoding="utf-8")
    t = time.time()
    for q in ("Ko je investitor projekta?", "Koje institucije učestvuju?", "Генералштаб"):
        try:
            hits = await cognee.search(q, query_type=cognee.SearchType.CHUNKS, datasets=["zakon"], top_k=3)
            log.append(f"\npretraga: {q}\n" + "\n".join("  - " + str(h)[:300].replace("\n", " ") for h in hits))
        except Exception as e:  # a search type may need an LLM; say so and go on
            log.append(f"\npretraga: {q}: {type(e).__name__}: {e}"[:400])
    log.append(f"pretrage: {time.time() - t:.0f} s")
    (folder / "proba.txt").write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
