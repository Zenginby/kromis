# Graph Report - .  (2026-07-23)

## Corpus Check
- Corpus is ~15,446 words - fits in a single context window. You may not need a graph.

## Summary
- 199 nodes · 293 edges · 16 communities (12 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.82)
- Token cost: 100,000 input · 11,000 output

## Community Hubs (Navigation)
- [[_COMMUNITY_FastAPI Routes & Endpoints|FastAPI Routes & Endpoints]]
- [[_COMMUNITY_Azure Client & Credentials|Azure Client & Credentials]]
- [[_COMMUNITY_Frontend UI Logic|Frontend UI Logic]]
- [[_COMMUNITY_Design Concepts & Guards|Design Concepts & Guards]]
- [[_COMMUNITY_Settings Credential Tests|Settings Credential Tests]]
- [[_COMMUNITY_Storage & History|Storage & History]]
- [[_COMMUNITY_Edit Route Tests|Edit Route Tests]]
- [[_COMMUNITY_Azure HTTP Client Tests|Azure HTTP Client Tests]]
- [[_COMMUNITY_Azure Edit Client Tests|Azure Edit Client Tests]]
- [[_COMMUNITY_Settings Route Tests|Settings Route Tests]]
- [[_COMMUNITY_GenerateApp Route Tests|Generate/App Route Tests]]
- [[_COMMUNITY_Storage Delete Tests|Storage Delete Tests]]
- [[_COMMUNITY_Launch Script|Launch Script]]
- [[_COMMUNITY_Subagent-Driven Dev Process|Subagent-Driven Dev Process]]

## God Nodes (most connected - your core abstractions)
1. `$()` - 25 edges
2. `_client()` - 11 edges
3. `AzureImageError` - 7 edges
4. `_client()` - 7 edges
5. `_first_complete_credentials()` - 6 edges
6. `generate()` - 6 edges
7. `run()` - 6 edges
8. `FakeMultipartClient` - 6 edges
9. `FakeClient` - 6 edges
10. `_png_bytes()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `GPT-Image Studio` --references--> `run.sh Launch Script`  [EXTRACTED]
  README.md → run.sh
- `run.sh Launch Script` --references--> `Python Dependencies (requirements.txt)`  [EXTRACTED]
  run.sh → requirements.txt
- `Pillow Dependency for Logo Compositing` --references--> `KURUM Logo Overlay`  [INFERRED]
  .superpowers/sdd/final-review-fixes.md → README.md
- `Pillow Dependency for Logo Compositing` --references--> `Python Dependencies (requirements.txt)`  [EXTRACTED]
  .superpowers/sdd/final-review-fixes.md → requirements.txt
- `POST /api/edit route` --references--> `Python Dependencies (requirements.txt)`  [EXTRACTED]
  .superpowers/sdd/task-3-brief.md → requirements.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Defense-in-Depth Input Validation Guards** — sdd_task_2_report_path_traversal_guard, sdd_task_3_report_content_length_guard, sdd_final_review_v11_fixes_decompression_bomb_guard, sdd_final_review_fixes_gallery_escaping [INFERRED 0.75]
- **Image Edit Feature Flow** — sdd_task_1_brief_azure_edit, sdd_task_3_brief_edit_route, sdd_task_3_brief_to_png, sdd_task_5_brief_edit_panel [EXTRACTED 1.00]
- **Image Delete Feature Flow** — sdd_task_2_brief_storage_delete, sdd_task_4_brief_delete_route, sdd_task_5_brief_edit_panel [EXTRACTED 1.00]

## Communities (16 total, 4 thin omitted)

### Community 0 - "FastAPI Routes & Endpoints"
Cohesion: 0.08
Nodes (26): add_logo(), edit(), generate(), GenerateRequest, get_settings(), index(), LogoRequest, _now() (+18 more)

### Community 1 - "Azure Client & Credentials"
Cohesion: 0.14
Nodes (20): AzureImageError, build_payload(), _candidate_paths(), decode_images(), edit(), _first_complete_credentials(), generate(), get_settings_status() (+12 more)

### Community 2 - "Frontend UI Logic"
Cohesion: 0.17
Nodes (21): $(), ACCEPTED_UPLOAD_TYPES, addLogo(), applyConfigured(), clearSource(), clearUploadPreviewUrl(), deleteImage(), loadHistory() (+13 more)

### Community 3 - "Design Concepts & Guards"
Cohesion: 0.13
Nodes (18): Azure gpt-image-2 Deployment, GPT-Image Studio, KURUM Logo Overlay, Python Dependencies (requirements.txt), run.sh Launch Script, XSS-Safe Gallery Card Rendering, Pillow Dependency for Logo Compositing, Decompression-Bomb Dimension Guard in _to_png (+10 more)

### Community 5 - "Storage & History"
Cohesion: 0.22
Nodes (7): delete(), _history_path(), list_history(), Üretilen görsellerin diske kaydı ve history.json yönetimi., _read_history(), save(), _write_history()

### Community 6 - "Edit Route Tests"
Cohesion: 0.35
Nodes (12): _client(), _png_bytes(), test_edit_from_source_id(), test_edit_from_upload(), test_edit_maps_azure_error(), test_edit_rejects_bad_size(), test_edit_rejects_both_file_and_source_id(), test_edit_rejects_huge_dimensions() (+4 more)

### Community 7 - "Azure HTTP Client Tests"
Cohesion: 0.25
Nodes (5): FakeClient, FakeResponse, httpx.Client yerine geçen minimal sahte istemci., test_generate_calls_correct_endpoint_and_decodes(), test_generate_raises_friendly_on_error()

### Community 8 - "Azure Edit Client Tests"
Cohesion: 0.29
Nodes (5): FakeMultipartClient, FakeResponse, httpx.Client yerine geçer; data+files ile POST'u yakalar., test_edit_calls_edits_endpoint_with_multipart_and_decodes(), test_edit_raises_friendly_on_error()

### Community 10 - "Generate/App Route Tests"
Cohesion: 0.46
Nodes (7): _client(), test_generate_happy_path(), test_generate_maps_azure_error(), test_generate_rejects_bad_size(), test_history_returns_saved(), test_output_directory_name_returns_404(), test_output_missing_file_returns_404()

### Community 11 - "Storage Delete Tests"
Cohesion: 0.43
Nodes (4): _save(), test_delete_keeps_other_records(), test_delete_removes_record_and_file(), test_delete_unknown_returns_false()

## Knowledge Gaps
- **10 isolated node(s):** `RequestValidationError`, `UploadFile`, `run.sh script`, `statusEl`, `ACCEPTED_UPLOAD_TYPES` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `RequestValidationError`, `UploadFile`, `GPT-Image Studio — yerel FastAPI arayüzü.` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Routes & Endpoints` be split into smaller, more focused modules?**
  _Cohesion score 0.08199643493761141 - nodes in this community are weakly interconnected._
- **Should `Azure Client & Credentials` be split into smaller, more focused modules?**
  _Cohesion score 0.13768115942028986 - nodes in this community are weakly interconnected._
- **Should `Design Concepts & Guards` be split into smaller, more focused modules?**
  _Cohesion score 0.13071895424836602 - nodes in this community are weakly interconnected._
- **Should `Settings Credential Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._