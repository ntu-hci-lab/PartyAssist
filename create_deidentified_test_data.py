#!/usr/bin/env python3
"""Create a de-identified JSON bundle from simple-tasks result data."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import secrets
import shutil


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_ROOT = ROOT
DEFAULT_OUTPUT_ROOT = ROOT / "deidentified_test_data"
TIMESTAMP_STEM_RE = re.compile(r"^(?P<test_name>.+?)_(?P<stamp>\d{8}_\d{6})$")
TIMESTAMP_DIR_RE = re.compile(r"^\d{8}_\d{6}$")


@dataclass
class ExportSummary:
    json_files_anonymized: int = 0
    image_dirs_copied: int = 0
    image_files_copied: int = 0


@dataclass(frozen=True)
class SourceLayout:
    input_root: Path
    data_root: Path
    results_dir: Path
    images_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="De-identify simple-tasks JSON results into the same JSON-based layout."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Project root, exported root, or data directory containing results/ and images/.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory for the de-identified export.",
    )
    return parser.parse_args()


def resolve_source_layout(source_root: Path) -> SourceLayout:
    if (source_root / "data" / "results").is_dir():
        data_root = source_root / "data"
    elif (source_root / "results").is_dir():
        data_root = source_root
    else:
        raise ValueError(
            f"Could not find results under {source_root}. Expected either "
            f"{source_root / 'data' / 'results'} or {source_root / 'results'}."
        )

    return SourceLayout(
        input_root=source_root,
        data_root=data_root,
        results_dir=data_root / "results",
        images_dir=data_root / "images",
    )


def iter_json_files(results_dir: Path) -> list[Path]:
    return sorted(path for path in results_dir.rglob("*.json") if path.is_file())


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a top-level JSON object")
    return data


def infer_user_id(source_path: Path, results_dir: Path, data: dict) -> str:
    user_id = str(data.get("user_id") or "").strip()
    if user_id:
        return user_id
    return source_path.relative_to(results_dir).parts[0]


def infer_test_name(source_path: Path, data: dict) -> str:
    test_name = str(data.get("test_name") or "").strip()
    if test_name:
        return test_name

    match = TIMESTAMP_STEM_RE.match(source_path.stem)
    if match:
        return match.group("test_name")

    return source_path.stem


def discover_user_map(json_files: list[Path], results_dir: Path) -> dict[str, str]:
    user_ids: set[str] = set()
    for path in json_files:
        data = load_json(path)
        user_ids.add(infer_user_id(path, results_dir, data))

    user_map: dict[str, str] = {}
    used_codes: set[str] = set()
    for user_id in sorted(user_ids):
        while True:
            code = f"participant_{secrets.token_hex(4)}"
            if code not in used_codes:
                used_codes.add(code)
                user_map[user_id] = code
                break
    return user_map


def sanitize_string_value(value: str, user_map: dict[str, str]) -> str:
    stripped = value.strip()
    if stripped in user_map:
        return user_map[stripped]
    return value


def transform_json_value(value, user_map: dict[str, str]):
    if isinstance(value, dict):
        transformed: dict = {}
        for key, nested_value in value.items():
            if key == "timestamp":
                continue
            if key == "user_id" and isinstance(nested_value, str):
                transformed[key] = sanitize_string_value(nested_value, user_map)
                continue
            transformed[key] = transform_json_value(nested_value, user_map)
        return transformed

    if isinstance(value, list):
        return [transform_json_value(item, user_map) for item in value]

    if isinstance(value, str):
        return sanitize_string_value(value, user_map)

    return value


def resolve_image_source(path_text: str, input_root: Path, data_root: Path) -> Path | None:
    candidate_text = path_text.strip().replace("\\", "/")
    if not candidate_text:
        return None

    candidate = Path(candidate_text)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    roots_to_try = [input_root, data_root]
    data_parent = data_root.parent
    if data_parent not in roots_to_try:
        roots_to_try.append(data_parent)

    for root in roots_to_try:
        joined = (root / candidate).resolve()
        if joined.exists():
            return joined

    if candidate.parts and candidate.parts[0] in {"images", "results"}:
        joined = (data_root / candidate).resolve()
        if joined.exists():
            return joined

    return None


def resolve_expected_image_dir(
    *,
    images_root: Path,
    source_user_folder: str,
    original_user_id: str,
    raw_path_text: str,
    test_name: str,
    run_index: int,
) -> Path | None:
    image_group = {
        "analog_move": "analog_move",
        "analog_path_follow": "analog_path_trace",
    }.get(test_name)
    if image_group is None:
        return None

    image_root = images_root / image_group
    user_dir = resolve_image_user_dir(
        image_root=image_root,
        source_user_folder=source_user_folder,
        original_user_id=original_user_id,
        raw_path_text=raw_path_text,
    )
    if user_dir is None:
        return None

    run_dirs = sorted(path for path in user_dir.iterdir() if path.is_dir())
    if not run_dirs:
        return user_dir
    index = max(0, run_index - 1)
    if index >= len(run_dirs):
        index = len(run_dirs) - 1
    return run_dirs[index]


def resolve_image_user_dir(
    *,
    image_root: Path,
    source_user_folder: str,
    original_user_id: str,
    raw_path_text: str,
) -> Path | None:
    if not image_root.exists():
        return None

    candidates = [source_user_folder, original_user_id]

    raw_candidate = Path(raw_path_text.strip().replace("\\", "/"))
    if len(raw_candidate.parts) >= 4:
        candidates.append(raw_candidate.parts[3])

    for candidate in candidates:
        if not candidate:
            continue
        exact = image_root / candidate
        if exact.exists():
            return exact

    dirs = [path for path in image_root.iterdir() if path.is_dir()]
    suffix_candidates = []
    for candidate in candidates:
        if not candidate:
            continue
        parts = re.split(r"[_-]+", candidate)
        if len(parts) >= 2:
            suffix_candidates.append(parts[-1])

    for suffix in suffix_candidates:
        matches = [path for path in dirs if re.split(r"[_-]+", path.name)[-1] == suffix]
        if len(matches) == 1:
            return matches[0]

    return None


def anonymize_path_parts(
    parts: tuple[str, ...],
    *,
    pseudonym: str,
    run_label: str,
    user_map: dict[str, str],
) -> tuple[str, ...]:
    rewritten = []
    for part in parts:
        if part in user_map:
            rewritten.append(pseudonym)
        elif TIMESTAMP_DIR_RE.fullmatch(part):
            rewritten.append(run_label)
        else:
            rewritten.append(part)
    return tuple(rewritten)


def copy_image_artifact(
    *,
    source_image_path: Path,
    data_root: Path,
    output_root: Path,
    pseudonym: str,
    run_label: str,
    user_map: dict[str, str],
    copied_image_dirs: dict[Path, Path],
    summary: ExportSummary,
) -> Path | None:
    try:
        relative_path = Path("data") / source_image_path.relative_to(data_root)
    except ValueError:
        return None

    parts = list(relative_path.parts)
    if len(parts) >= 4 and parts[0] == "data" and parts[1] == "images":
        parts[3] = pseudonym
    if len(parts) >= 5 and parts[0] == "data" and parts[1] == "images" and TIMESTAMP_DIR_RE.fullmatch(parts[4]):
        parts[4] = run_label
    relative_path = Path(*parts)

    anonymized_relative = Path(
        *anonymize_path_parts(
            relative_path.parts,
            pseudonym=pseudonym,
            run_label=run_label,
            user_map=user_map,
        )
    )
    destination = output_root / anonymized_relative

    if source_image_path.is_dir():
        if source_image_path not in copied_image_dirs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_image_path, destination, dirs_exist_ok=True)
            copied_image_dirs[source_image_path] = destination
            summary.image_dirs_copied += 1
            summary.image_files_copied += sum(1 for p in source_image_path.rglob("*") if p.is_file())
        return anonymized_relative

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_image_path, destination)
    summary.image_files_copied += 1
    return anonymized_relative


def maybe_rewrite_image_entry(
    entry: str,
    *,
    input_root: Path,
    data_root: Path,
    images_root: Path,
    output_root: Path,
    source_user_folder: str,
    original_user_id: str,
    test_name: str,
    run_index: int,
    pseudonym: str,
    run_label: str,
    user_map: dict[str, str],
    copied_image_dirs: dict[Path, Path],
    summary: ExportSummary,
) -> str:
    prefix = entry.partition(": ")[0] if ": " in entry else entry
    source_image_path = resolve_expected_image_dir(
        images_root=images_root,
        source_user_folder=source_user_folder,
        original_user_id=original_user_id,
        raw_path_text=entry.partition(": ")[2] if ": " in entry else "",
        test_name=test_name,
        run_index=run_index,
    )
    if source_image_path is None and ": " in entry:
        _, _, raw_path = entry.partition(": ")
        source_image_path = resolve_image_source(raw_path, input_root, data_root)
    if source_image_path is None:
        return entry

    output_image_path = copy_image_artifact(
        source_image_path=source_image_path,
        data_root=data_root,
        output_root=output_root,
        pseudonym=pseudonym,
        run_label=run_label,
        user_map=user_map,
        copied_image_dirs=copied_image_dirs,
        summary=summary,
    )
    if output_image_path is None:
        return entry

    return f"{prefix}: {output_image_path.as_posix()}"


def transform_result_json(
    data: dict,
    *,
    input_root: Path,
    data_root: Path,
    images_root: Path,
    output_root: Path,
    source_user_folder: str,
    original_user_id: str,
    test_name: str,
    run_index: int,
    pseudonym: str,
    run_label: str,
    user_map: dict[str, str],
    copied_image_dirs: dict[Path, Path],
    summary: ExportSummary,
) -> dict:
    transformed = transform_json_value(data, user_map)

    if "image_files" in transformed and isinstance(transformed["image_files"], list):
        transformed["image_files"] = [
            maybe_rewrite_image_entry(
                entry=item,
                input_root=input_root,
                data_root=data_root,
                images_root=images_root,
                output_root=output_root,
                source_user_folder=source_user_folder,
                original_user_id=original_user_id,
                test_name=test_name,
                run_index=run_index,
                pseudonym=pseudonym,
                run_label=run_label,
                user_map=user_map,
                copied_image_dirs=copied_image_dirs,
                summary=summary,
            )
            if isinstance(item, str)
            else item
            for item in transformed["image_files"]
        ]

    return transformed


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def reset_output_root(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)


def write_readme(
    *,
    output_root: Path,
    summary: ExportSummary,
    user_map: dict[str, str],
) -> None:
    readme = output_root / "README.md"
    content = f"""# De-identified Test Data

This folder is a de-identified export generated from simple-tasks result data.

- Source root: user-provided simple-tasks result directory
- Source layout: `data/results/<user_id>/*.json` and `data/images/...`
- Output keeps the same JSON-based layout.
- Participant folders are renamed to random pseudonyms like `participant_a1b2c3d4`.
- JSON `timestamp` fields are removed.
- JSON filenames replace timestamp suffixes with per-test run labels such as `button_accuracy_001.json`.
- Referenced image folders are copied with anonymized path segments.
- No reverse lookup table is included in this export.

Summary:

- JSON files anonymized: {summary.json_files_anonymized}
- Image directories copied: {summary.image_dirs_copied}
- Image files copied: {summary.image_files_copied}
- Unique participants pseudonymized: {len(user_map)}
"""
    readme.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_root = args.source_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    try:
        layout = resolve_source_layout(source_root)
    except ValueError as exc:
        print(str(exc))
        print(
            "Provide --source-root pointing to either the repository root, an exported root "
            "that contains data/results, or the data directory itself."
        )
        return 1

    results_dir = layout.results_dir
    output_results_dir = output_root / "data" / "results"

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        print(
            "Run main.py or the individual tests first, or provide --source-root pointing "
            "to an existing results directory."
        )
        return 1

    json_files = iter_json_files(results_dir)
    if not json_files:
        print(f"No JSON files found under: {results_dir}")
        return 1

    user_map = discover_user_map(json_files, results_dir)
    summary = ExportSummary()
    copied_image_dirs: dict[Path, Path] = {}
    sequence_counters: dict[tuple[str, str], int] = defaultdict(int)

    reset_output_root(output_root)

    for source_path in json_files:
        data = load_json(source_path)
        source_user_folder = source_path.relative_to(results_dir).parts[0]
        original_user_id = infer_user_id(source_path, results_dir, data)
        pseudonym = user_map[original_user_id]
        test_name = infer_test_name(source_path, data)

        sequence_key = (pseudonym, test_name)
        sequence_counters[sequence_key] += 1
        run_label = f"{sequence_counters[sequence_key]:03d}"

        transformed = transform_result_json(
            data,
            input_root=layout.input_root,
            data_root=layout.data_root,
            images_root=layout.images_dir,
            output_root=output_root,
            source_user_folder=source_user_folder,
            original_user_id=original_user_id,
            test_name=test_name,
            run_index=sequence_counters[sequence_key],
            pseudonym=pseudonym,
            run_label=f"run_{run_label}",
            user_map=user_map,
            copied_image_dirs=copied_image_dirs,
            summary=summary,
        )

        output_path = output_results_dir / pseudonym / f"{test_name}_{run_label}.json"
        write_json(output_path, transformed)
        summary.json_files_anonymized += 1

    write_readme(
        output_root=output_root,
        summary=summary,
        user_map=user_map,
    )

    print(f"Created {output_root}")
    print(f"Source root: {source_root}")
    print(f"JSON anonymized: {summary.json_files_anonymized}")
    print(f"Image directories copied: {summary.image_dirs_copied}")
    print(f"Image files copied: {summary.image_files_copied}")
    print(f"Participants pseudonymized: {len(user_map)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
