#!/usr/bin/env bash
# =============================================================================
# summarize.sh — compact git diff summary for dev-goal L 阶段复盘
#
# 用法:
#   summarize.sh                    # 工作区 vs HEAD
#   summarize.sh HEAD~3             # 最近 3 个提交
#   summarize.sh main..feature      # 分支对比
#   summarize.sh --since "2026-06-01"
#
# 输出: 表格化的变更摘要，替代 Agent 读完整 diff
# =============================================================================

set -euo pipefail

RANGE="${1:-HEAD}"

echo "## 变更概要"
echo ""

# ---- 人读统计 ----
echo "| 统计 | 数值 |"
echo "|------|------|"

# Files changed
files=$(git diff --name-only $RANGE 2>/dev/null | wc -l)
adds=$(git diff --shortstat $RANGE 2>/dev/null | awk '{print $4}' || echo "0")
dels=$(git diff --shortstat $RANGE 2>/dev/null | awk '{print $6}' || echo "0")

echo "| 文件数 | $files |"
echo "| +行 | +$adds |"
echo "| -行 | -$dels |"

# Commits in range
if [ "$RANGE" != "HEAD" ]; then
  commits=$(git log --oneline $RANGE 2>/dev/null | wc -l || echo "N/A")
  echo "| 提交数 | $commits |"
fi

echo ""

# ---- 按操作类型归类文件 ----
echo "### 按变更类型"
echo ""
echo "| 类型 | 文件 |"
echo "|------|------|"

git diff --name-status $RANGE 2>/dev/null | while read status file; do
  case "$status" in
    A) echo "| 🆕 新增 | $file |" ;;
    M) echo "| ✏️ 修改 | $file |" ;;
    D) echo "| 🗑️ 删除 | $file |" ;;
    R*) echo "| 🔄 重命名 | $file |" ;;
    *) echo "| ❓ $status | $file |" ;;
  esac
done

echo ""

# ---- 受影响函数/类（Python + Go + TypeScript 通用） ----
echo "### 受影响的符号"
echo ""
echo "| 文件 | 符号 | 类型 |"
echo "|------|------|------|"

git diff $RANGE 2>/dev/null | grep '^@@' | while read hunk; do
  # Extract the function/class context line that follows @@
  :
done

# Use a simpler approach: find added/removed function and class definitions
echo "_可用以下命令获取详细符号变更:_"
echo '```bash'
echo "# Go:"
echo "git diff $RANGE | grep -E '^[-+](func |type |var |const )' | sort -u"
echo "# Python:"
echo "git diff $RANGE | grep -E '^[-+](def |class |async def )' | sort -u"
echo '```'
echo ""

# ---- 新增/删除的公开 API ----
echo "### API 变更（公开符号）"
echo ""
echo "| 变更 | 符号 | 文件 |"
echo "|------|------|------|"

# Go: exported functions/types
if git diff $RANGE 2>/dev/null | grep -qE '\.go'; then
  git diff $RANGE 2>/dev/null | grep -E '^\+func [A-Z]|^\+type [A-Z]' | sed 's/^+//; s/^/| ➕ 新增 | /; s/$/ | —/' || true
  git diff $RANGE 2>/dev/null | grep -E '^\-func [A-Z]|^\-type [A-Z]' | sed 's/^-//; s/^/| ➖ 移除 | /; s/$/ | —/' || true
fi

# Python: exported (non-_) functions and classes
if git diff $RANGE 2>/dev/null | grep -qE '\.py'; then
  git diff $RANGE 2>/dev/null | grep -E '^\+def [a-z]|^\+class [A-Z]|^\+async def' | grep -v 'def _' | sed 's/^+//; s/^/| ➕ 新增 | /; s/$/ | —/' || true
  git diff $RANGE 2>/dev/null | grep -E '^\-def [a-z]|^\-class [A-Z]|^\-async def' | grep -v 'def _' | sed 's/^-//; s/^/| ➖ 移除 | /; s/$/ | —/' || true
fi

echo ""

# ---- 循环依赖风险提示 ----
echo "### 快速风险扫描"
echo ""

# Check if new imports cross module boundaries in a way that might create cycles
new_imports=$(git diff $RANGE 2>/dev/null | grep '^\+' | grep -E '(import |from .* import)' | wc -l || echo "0")
if [ "$new_imports" -gt 0 ]; then
  echo "- ⚠️ $new_imports 处新增 import，请在 finish-review 中检查循环依赖"
fi

# Check test file changes
test_changes=$(git diff --name-only $RANGE 2>/dev/null | grep -E '_test\.(go|py)|test_.*\.py|tests/' | wc -l || echo "0")
if [ "$test_changes" -eq 0 ]; then
  echo "- ⚠️ **无测试文件变更**，确认是否需要补充测试"
else
  echo "- ✅ $test_changes 个测试文件有变更"
fi

echo ""
echo "> 💡 此摘要为自动生成。详细审查请用 \`git diff $RANGE\`。"
