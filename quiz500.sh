#!/bin/bash
total=$(jq '. | length' questions.json)
random=$((RANDOM % total))
q=$(jq -r ".[$random]" questions.json)
echo "Q$(echo "$q" | jq -r '.id'): $(echo "$q" | jq -r '.question')"
echo ""
for i in {0..3}; do
  echo "  $(echo "$q" | jq -r ".options[$i]")"
done
echo ""
echo -n "Your answer: "; read ans
correct=$(echo "$q" | jq -r '.answer')
[[ "${ans^^}" == "$correct" ]] && echo "✅ Correct!" || echo "❌ Wrong. Answer: $correct"
