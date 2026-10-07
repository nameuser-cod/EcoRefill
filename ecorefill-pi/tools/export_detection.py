"""Export local custom weights to a NEW NCNN directory, preserving the source."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory ending in _ncnn_model")
    parser.add_argument("--imgsz", type=int, default=416)
    args = parser.parse_args()
    source, output = args.model.expanduser().resolve(), args.output.expanduser().resolve()
    if not source.is_file() or source.suffix != ".pt":
        parser.error("--model must be an existing local .pt checkpoint")
    if output.exists() or not output.name.endswith("_ncnn_model"):
        parser.error("--output must be a new directory ending in _ncnn_model")
    if args.imgsz < 32 or args.imgsz % 32:
        parser.error("--imgsz must be a positive multiple of 32")
    from ultralytics import YOLO, __version__

    # Ultralytics writes exports beside its input. Work on a temporary copy
    # so failed exports cannot leave files beside the deployed checkpoint.
    with tempfile.TemporaryDirectory(prefix="ecorefill-export-") as temporary:
        checkpoint = Path(temporary) / "candidate.pt"
        shutil.copy2(source, checkpoint)
        model = YOLO(str(checkpoint))
        if model.task != "detect" or set(model.names.values()) != {"plastic_bottle", "aluminum_can"}:
            parser.error("Export requires custom detection weights for plastic_bottle and aluminum_can")
        exported = Path(model.export(format="ncnn", imgsz=args.imgsz, batch=1,
                                     device="cpu", quantize=None))
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(exported, output)
    provenance = {
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "ultralytics": __version__, "format": "ncnn", "imgsz": args.imgsz,
        "quantize": None, "batch": 1,
        "status": "Candidate export; validate material decisions and benchmark on the Pi before activation.",
    }
    (output / "ecorefill-export.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"NCNN candidate: {output}")


if __name__ == "__main__":
    main()
