## 🛠️ 1. Execution & Interaction Rules
- **No Invisible Commands**: Do NOT run terminal commands or use browser subagents to verify visuals unless explicitly asked by the USER for a specific task.
- **Manual Handoff**: Instead of executing commands, provide the exact CLI strings in the chat for the USER to run manually.
- **Clean Files**: Do NOT place conversational messages, explanations, or filler text inside code files. Keep files focused purely on logic and documentation.

## 🏗️ 2. Engineering Standards
- **Modularity**: Always favor modular design. Break large scripts into logical segments or separate modules.
- **Clean Code**: Follow strict coding practices:
    - Comprehensive docstrings and inline comments for complex logic.
    - Logical repository structure (e.g., `src/`, `data/`, `tests/`).
    - Proper segmentation of concerns.

## 📥 3. Data & Resource Management
- **Local-First Data**: Prioritize local data over external API calls.
- **Idempotent Downloads**: If a task requires online data (e.g., yfinance, CSVs):
    1.  Check for the existence of a local cache/file first.
    2.  Only download if the local data is missing or explicitly requested to be refreshed.
    3.  Ensure downloaded data is saved locally for future runs.

---

## 📝 4. Documentation
- **CLI ↔ README Sync**: Whenever a CLI command is **introduced or modified** (new flags, changed defaults, removed parameters), the corresponding entry in `README.md` **must** be updated in the same change. Include:
    1.  The full command with example usage.
    2.  A table or list of all current parameters with defaults and descriptions.
    3.  A brief explanation of what the command does.
- **No Stale Docs**: If a command is removed, its README entry must also be removed.

---

## 🧠 5. Cognitive Handoff
- **Source of Truth**: Refer to this file at the start of every session to ensure compliance with the USER's preferred workflow.
