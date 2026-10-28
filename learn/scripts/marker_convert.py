"""Convert PDFs with Marker, loading the models once for the whole batch.

Called by learnctl.py with the learning-skills venv:
    .venv/Scripts/python.exe -I marker_convert.py jobs.json
jobs.json: [{"pdf": ..., "outdir": ..., "rel": ...}, ...]

Each outdir gets content.md (page anchors `<!-- page N -->`, 1-based, matching
the PDF viewer) plus the extracted images. Exit 1 if any job failed.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

PAGE_SEP = re.compile(r"^\{(\d+)\}-{20,}\s*$", re.M)


def main():
    jobs = json.load(open(sys.argv[1], encoding="utf-8"))
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    t0 = time.time()
    FORCE_OCR = os.environ.get("LEARN_MARKER_FORCE_OCR", "1") != "0"  # OCR gives LaTeX for inline math
    # Surya's GPU defaults (recognition batch 256) assume ~24 GB; on an 8 GB card Windows pages
    # VRAM to system RAM and a 29-page PDF made no progress in 30 min. Scale batches to the card.
    b = int(os.environ.get("LEARN_MARKER_BATCH", "16"))
    cfg = ConfigParser({"output_format": "markdown", "paginate_output": True, "force_ocr": FORCE_OCR,
                        "recognition_batch_size": b * 2, "equation_batch_size": b, "detection_batch_size": b // 2,
                        "layout_batch_size": b // 2, "table_rec_batch_size": b // 2, "ocr_error_batch_size": b})
    converter = PdfConverter(
        config=cfg.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=cfg.get_processors(),
        renderer=cfg.get_renderer(),
        llm_service=cfg.get_llm_service(),
    )
    print(f"marker models loaded in {time.time() - t0:.1f}s", flush=True)

    failed = 0
    for j in jobs:
        t = time.time()
        done_tag = Path(j["outdir"]) / ".done"
        if j.get("sha") and (Path(j["outdir"]) / "content.md").exists() and done_tag.exists() \
                and done_tag.read_text().strip() == j["sha"]:
            print(f"skip {j['rel']} (already converted)", flush=True)  # resume after an interrupted batch
            continue
        try:
            text, _, images = text_from_rendered(converter(j["pdf"]))
            out = Path(j["outdir"])
            out.mkdir(parents=True, exist_ok=True)
            for name, img in (images or {}).items():
                img.save(out / name)
            text = PAGE_SEP.sub(lambda m: f"<!-- page {int(m.group(1)) + 1} -->", text)
            (out / "content.md").write_text(f"<!-- source: {j['rel']} -->\n\n{text}\n", encoding="utf-8")
            if j.get("sha"):
                done_tag.write_text(j["sha"])
            print(f"ok   {j['rel']}  {time.time() - t:.1f}s", flush=True)
        except Exception as e:
            failed += 1
            print(f"FAIL {j['rel']}: {type(e).__name__}: {e}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
