#!/usr/bin/env bash
# =============================================================================
# search-knowledge.sh — dev-goal O0 历史经验检索辅助脚本
#
# 用法（自动检测路径）:
#   search-knowledge.sh <keyword1> [keyword2...]
#
# 用法（手动指定项目根目录）:
#   search-knowledge.sh --project-root <path> <keyword1> [keyword2...]
#
# 示例:
#   search-knowledge.sh Strategy 解耦 支付
#   search-knowledge.sh --project-root "g:/Program/go/Seele" Strategy 解耦
#
# 输出: Markdown 格式的检索结果表，可直接粘贴到 workflow log 的 O0 章节
# =============================================================================

set -euo pipefail

# ---- Parse optional --project-root ----
PROJECT_ROOT=""
if [ "${1:-}" = "--project-root" ]; then
  PROJECT_ROOT="${2:?--project-root requires a path}"
  shift 2
fi

# ---- Auto-detect project root if not specified ----
if [ -z "$PROJECT_ROOT" ]; then
  PROJECT_ROOT="$PWD"
fi

# ---- Derive paths ----
DOCS_DIR="$PROJECT_ROOT/docs"

# Derive memory directory from Claude Code convention:
# Project path -> slug: replace \ : / with -, strip leading -
# e.g. g:\Program\go\Seele -> g--Program-go-Seele
PROJECT_SLUG=$(echo "$PROJECT_ROOT" | sed 's|\\\\|/|g; s|:||g; s|^/||; s|/$||; s|/|-|g; s|\\|-|g')
MEMORY_DIR="$HOME/.claude/projects/${PROJECT_SLUG}/memory"

# Fallback: search for any matching project directory
if [ ! -d "$MEMORY_DIR" ]; then
  # Try to find by matching the last component of project path
  PROJECT_NAME=$(basename "$PROJECT_ROOT")
  for d in "$HOME"/.claude/projects/*/; do
    dirname=$(basename "$d")
    if echo "$dirname" | grep -qi "$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]')"; then
      MEMORY_DIR="${d}memory"
      break
    fi
  done
fi

KEYWORDS=("$@")

if [ ${#KEYWORDS[@]} -eq 0 ]; then
  echo "| 来源 | 相关经验 | 对本次的启示 |"
  echo "|------|---------|------------|"
  echo "| — | 未提供搜索关键词 | — |"
  exit 0
fi

# Build grep pattern: keyword1|keyword2|...
PATTERN=$(IFS='|'; echo "${KEYWORDS[*]}")

# ---- Output header ----
echo "### 历史经验检索"
echo ""
echo "> 🔍 关键词: \`${PATTERN}\`"
echo "> 📁 项目: \`${PROJECT_ROOT}\`"
echo "> 🧠 memory: \`${MEMORY_DIR}\`"
echo "> 📄 docs: \`${DOCS_DIR}\`"
echo ""

# ---- Search memory/ ----
FOUND_ANY=false

search_memory() {
  [ -d "$MEMORY_DIR" ] || return

  # Read MEMORY.md index first for fast lookup
  if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
    while IFS= read -r line; do
      if echo "$line" | grep -qE '^-\s*\[.+\]\(.+\.md\)'; then
        for kw in "${KEYWORDS[@]}"; do
          if echo "$line" | grep -qi "$kw"; then
            local fname=$(echo "$line" | sed 's/.*(\(.*\.md\)).*/\1/')
            local desc=$(echo "$line" | sed 's/.*—\s*//')
            echo "| 📝 memory/${fname} | ${desc} | 索引匹配: \`${kw}\` |"
            FOUND_ANY=true
            break
          fi
        done
      fi
    done < "$MEMORY_DIR/MEMORY.md"
  fi

  # Deep search: grep inside memory files
  for f in "$MEMORY_DIR"/*.md; do
    [ -f "$f" ] || continue
    local fname=$(basename "$f")
    [ "$fname" = "MEMORY.md" ] && continue
    if grep -qiE "$PATTERN" "$f" 2>/dev/null; then
      local desc=$(grep -m1 "^description:" "$f" 2>/dev/null | sed 's/^description:\s*//' || echo "内容匹配")
      echo "| 📝 memory/${fname} | ${desc} | 文件内容命中 |"
      FOUND_ANY=true
    fi
  done
}

# ---- Search docs/ workflow 目录 ----
search_docs() {
  [ -d "$DOCS_DIR" ] || return

  for f in "$DOCS_DIR"/*/devgoal流程.md; do
    [ -f "$f" ] || continue
    local dirname=$(basename "$(dirname "$f")")
    if grep -qiE "$PATTERN" "$f" 2>/dev/null; then
      local desc=$(head -10 "$f" | grep -m1 "^# Workflow:" | sed 's/^# Workflow:\s*//' || echo "内容匹配")
      echo "| 📄 docs/${dirname}/devgoal流程.md (L-Phase) | ${desc} | 历史 devgoal流程 匹配 |"
      FOUND_ANY=true
    fi
  done
}

search_memory
search_docs

# ---- No results ----
if [ "$FOUND_ANY" = false ]; then
  echo "| — | 🆕 未找到相关历史经验 | 首次探索 — 本次 L 阶段将为此场景沉淀第一份经验 |"
fi

echo ""
echo "> 💡 以上匹配项需进一步 **Read** 文件内容以提取具体经验细节。"
