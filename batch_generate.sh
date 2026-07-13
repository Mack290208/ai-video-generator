#!/bin/bash
# 批量生成西瓜书视频 #3 ~ #10
# 用法: bash batch_generate.sh

cd "$(dirname "$0")"

TOPICS=(
  "03|经验风险与过拟合"
  "04|交叉验证与模型选择"
  "05|误差与过拟合与欠拟合"
  "06|评估方法"
  "07|性能度量"
  "08|偏差与方差"
  "09|线性回归"
  "10|对数几率回归"
)

TOTAL=${#TOPICS[@]}
SUCCESS=0
FAIL=0

echo "=========================================="
echo "  批量生成西瓜书视频 #3 ~ #10"
echo "  共 ${TOTAL} 个视频"
echo "=========================================="
echo ""

for item in "${TOPICS[@]}"; do
  NUM="${item%%|*}"
  TOPIC="${item#*|}"
  
  echo "[$((SUCCESS + FAIL + 1))/${TOTAL}] 生成: #${NUM} ${TOPIC}"
  echo "------------------------------------------"
  
  python approach1_storyboard.py "${TOPIC}"
  EXIT_CODE=$?
  
  if [ $EXIT_CODE -eq 0 ]; then
    # 重命名桌面文件，加上序号
    SAFE_TOPIC=$(echo "${TOPIC}" | sed 's/ /_/g; s/\//_/g' | cut -c1-20)
    SRC="$HOME/Desktop/西瓜书_${SAFE_TOPIC}.mp4"
    DST="$HOME/Desktop/${NUM}_西瓜书_${TOPIC}.mp4"
    
    if [ -f "$SRC" ]; then
      mv "$SRC" "$DST"
      echo "  ✓ 已保存: $(basename "$DST")"
    fi
    SUCCESS=$((SUCCESS + 1))
  else
    echo "  ✗ 生成失败!"
    FAIL=$((FAIL + 1))
  fi
  
  echo ""
done

echo "=========================================="
echo "  完成! 成功: ${SUCCESS}, 失败: ${FAIL}"
echo "=========================================="
