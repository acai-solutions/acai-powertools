# acai.ai_tools

Utility module providing tool implementations for AI agents and search functionality.  
No hexagonal architecture — flat utility code.

---

## Components

```
acai/ai_tools/
├── __init__.py            # Public API: BM25Index, TextEditorTool
├── bm25_index.py          # Full BM25 ranking implementation
├── text_editor_tool.py    # File operations with sandbox and backup
└── tools_schemas.py       # Claude API tool definitions
```

---

## BM25Index

A full [BM25](https://en.wikipedia.org/wiki/Okapi_BM25) ranking implementation for keyword search over document collections.

```python
from acai.ai_tools import BM25Index

index = BM25Index(k1=1.5, b=0.75)

index.add_document({"content": "Swiss civil code article 1", "id": "art-1"})
index.add_document({"content": "Swiss contract law overview", "id": "art-2"})

results = index.search("civil code", top_k=5)
for doc, score in results:
    print(doc["id"], score)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `k1` | `float` | `1.5` | Term frequency saturation parameter. |
| `b` | `float` | `0.75` | Document length normalization (0 = no normalization, 1 = full). |
| `tokenizer` | `Callable \| None` | `None` | Custom tokenizer function. Default splits on non-word characters. |

### Methods

| Method | Description |
|--------|-------------|
| `add_document(doc)` | Add a document dict (must contain `"content"` key). |
| `search(query, top_k)` | Score and rank documents. Returns `[(doc, score), …]`. |

---

## TextEditorTool

A sandboxed file editor with backup/restore capabilities. Useful as a tool for AI agents.

```python
from acai.ai_tools import TextEditorTool

editor = TextEditorTool(base_dir="/workspace", backup_dir="/workspace/.backups")

# View file or directory
content = editor.view("src/main.py")
content = editor.view("src/main.py", view_range=[10, 20])

# Read/write
text = editor.read("config.json")
editor.write("output.txt", "Hello, world!")
editor.create("new_file.py", "print('hello')")

# String replacement
editor.str_replace("main.py", old_str="foo", new_str="bar")

# Backup & restore
editor.restore_backup("main.py")
```

### Methods

| Method | Description |
|--------|-------------|
| `view(path, view_range=None)` | View file contents or list directory. Line numbers are 1-based. |
| `read(path)` | Read entire file as string. |
| `write(path, content)` | Write content to file (creates backup first). |
| `create(path, content)` | Create a new file (fails if it exists). |
| `delete(path)` | Delete a file (creates backup first). |
| `str_replace(path, old_str, new_str)` | Replace exact string in file. Must match exactly once. |
| `restore_backup(path)` | Restore most recent backup. |

### Security

- All paths are validated against `base_dir` — traversal outside the sandbox is denied.
- Backups are timestamped and stored in `backup_dir`.

---

## tools_schemas

Claude API tool definitions using `ToolParam` schema format:

- `add_duration_to_datetime` — Add a duration to a datetime value
- `set_reminder` — Set a reminder for a future time

These are intended as reference implementations for defining Claude-compatible tool schemas.
