#!/usr/bin/env bash
# =============================================================================
# check.sh — dev-goal A 阶段编码后快速自检（Go / Python 自动检测）
#
# 用法:
#   check.sh                    # 当前目录
#   check.sh <dir>              # 指定目录
#   check.sh --json             # JSON 输出（供 Agent 解析）
#
# 输出: 紧凑的检查结果表，替代 Agent 逐文件 grep
# =============================================================================

set -euo pipefail
TARGET="${1:-.}"
[[ "$TARGET" == "--json" ]] && { TARGET="."; JSON=true; } || JSON=false

# ---- 检测语言 ----
go_count=$(find "$TARGET" -name "*.go" -not -name "*_test.go" 2>/dev/null | head -20 | wc -l)
py_count=$(find "$TARGET" -name "*.py" -not -name "test_*.py" -not -name "*_test.py" 2>/dev/null | head -20 | wc -l)

echo "| 检查项 | 结果 | 详情 |"
echo "|--------|------|------|"

check() {
  local item="$1" severity="$2" pattern="$3" hint="$4"
  local matches
  matches=$(grep -rnE "$pattern" "$TARGET" --include="*.go" --include="*.py" 2>/dev/null | grep -v '_test.go\|test_.*\.py\|SKILL.md\|\.git/' || true)
  if [ -z "$matches" ]; then
    echo "| $item | ✅ | — |"
  else
    local count=$(echo "$matches" | wc -l)
    local sample=$(echo "$matches" | head -3 | sed 's/.*\///; s/:/:/')
    local emoji="⚠️"
    [ "$severity" = "block" ] && emoji="🚨"
    echo "| $item | $emoji x$count | \`$sample\` |"
  fi
}

# === 通用检查（Go + Python 都跑） ===
check "🔑 硬编码密钥"  "block" '(?i)(api_key|api_secret|password|passwd|token|secret_key)\s*[:=]\s*"[^"]{8,}' \
  "密钥必须走 env，不能硬编码在源码中"

check "🔗 硬编码 URL"   "warn"  'https?://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' \
  "环境相关 URL 应走配置，不应写死在代码中"

# === Go 专项 ===
if [ "$go_count" -gt 0 ]; then
  check "🐹 nil,nil 返回"    "block" 'return nil, nil' \
    "Go 禁止 return nil, nil，必须 return T{}, err"
  check "🐹 包级 var 可变"   "warn"  '^var [a-z]+\s+[a-z]' \
    "包级可变变量应改为 DI 或显式初始化"
  check "🐹 取 loop 变量地址" "warn" 'for\s+.*range.*\{[^}]*&[a-z]' \
    "for range 中的 &item 可能指向同一个地址"
fi

# === Python 专项 ===
if [ "$py_count" -gt 0 ]; then
  check "🐍 裸 except"       "block" 'except\s*:' \
    "裸 except 会吞掉 KeyboardInterrupt，必须指定异常类型"
  check "🐍 吞异常 pass"     "block" 'except.*:\s*$' \
    "except 后直接 pass 属于吞异常"
  check "🐍 可变默认参数"    "block" 'def\s+\w+\([^)]*=\s*\[\]' \
    "可变默认参数 def f(x=[]) 在所有调用间共享"
  check "🐍 模块级可变状态"  "warn"  '^_?\w+\s*[:=]\s*\{\}' \
    "模块级空字典可能是可变全局状态（常量字典除外）"
  check "🐍 模块级 Client"   "warn"  '^_?\w+\s*=\s*(httpx\.|requests\.|redis\.|aiomysql\.)' \
    "模块级外部连接应用 DI 替代"
  check "🐍 __init__ IO"     "warn"  'def __init__\(self[^)]*\):\s*\n\s*(self\.\w+\s*=\s*(httpx|requests|open|connect))' \
    "__init__ 不应做 IO，应延迟到 async factory"
  check "🐍 裸 Any 使用"     "info"  ': Any[^a-zA-Z]' \
    "Any 应替换为 Protocol 或 TypeVar"
fi

echo ""
echo "> 💡 🚨=阻断级 ⚠️=警告级。修复所有阻断项后方可提交。"
