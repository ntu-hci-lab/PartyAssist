# De-identified Test Data

This folder is a de-identified export generated from simple-tasks result data.

- Source root: original extracted study data directory
- Source layout: `data/results/<user_id>/*.json` and `data/images/...`
- Output keeps the same JSON-based layout.
- Participant folders are renamed to random pseudonyms like `participant_a1b2c3d4`.
- JSON `timestamp` fields are removed.
- JSON filenames replace timestamp suffixes with per-test run labels such as `button_accuracy_001.json`.
- Referenced image folders are copied with anonymized path segments.
- No reverse lookup table is included in this export.

Summary:

- JSON files anonymized: 483
- Image directories copied: 158
- Image files copied: 3860
- Unique participants pseudonymized: 80
