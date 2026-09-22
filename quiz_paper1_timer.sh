#!/bin/bash

# Quiz 1: Questions 1-250
# Single countdown timer: 250 questions × 20 seconds = 5000 seconds

TOTAL=250
SECONDS_PER_Q=30
TOTAL_SECONDS=$((TOTAL * SECONDS_PER_Q))
SCORE=0
CURRENT=0


clear
echo "======================================"
echo "   PAPER 1: QUESTIONS 1-250"
echo "   Total Time: $((TOTAL_SECONDS/60)) minutes"
echo "   (You can spend more or less time per question)"
echo "======================================"
echo ""
echo "Press ENTER to start..."
read start

START_TIME=$(date +%s)
END_TIME=$((START_TIME + TOTAL_SECONDS))

for i in $(seq 1 $TOTAL); do
  CURRENT=$i
  
  # Get question from JSON (id $i)
  q=$(jq -r ".[$i-1]" questions.json)
  
  # Calculate remaining time
  NOW=$(date +%s)
  REMAINING=$((END_TIME - NOW))
  
  if [[ $REMAINING -le 0 ]]; then
    echo ""
    echo "⏰ TIME'S UP!"
    break
  fi
  
  clear
  echo "======================================"
  echo "   PAPER 1 - Question $i of $TOTAL"
  echo "   ⏱️  Time remaining: $((REMAINING/60)) min $((REMAINING%60)) sec"
  echo "   📊 Score: $SCORE/$((i-1))"
  echo "======================================"
  echo ""
  echo "Q$i: $(echo "$q" | jq -r '.question')"
  echo ""
  
  for j in {0..3}; do
    echo "  $(echo "$q" | jq -r ".options[$j]")"
  done
  
  echo ""
  echo -n "Your answer (A/B/C/D): "
  
  # Read answer (no per-question timeout)
  read ans
  
  # Check answer
  correct_ans=$(echo "$q" | jq -r '.answer')
  if [[ "${ans^^}" == "$correct_ans" ]]; then
    echo "  ✅ Correct!"
    ((SCORE++))
  else
    echo "  ❌ Wrong. Answer: $correct_ans"
  fi
  
  # Check if time is up after answering
  NOW=$(date +%s)
  if [[ $NOW -ge $END_TIME ]]; then
    echo ""
    echo "⏰ TIME'S UP FOR THE ENTIRE PAPER!"
    break
  fi
  
  echo ""
  echo "Press ENTER for next question..."
  read next
done

ELAPSED=$(( $(date +%s) - START_TIME ))
ANSWERED=$CURRENT

clear
echo "======================================"
echo "   PAPER 1 COMPLETE!"
echo "======================================"
echo ""
echo "📊 Final Score: $SCORE/$ANSWERED"
echo "📈 Percentage: $((SCORE*100/ANSWERED))%"
echo "⏱️  Time Used: $((ELAPSED/60)) min $((ELAPSED%60)) sec"
echo "======================================"

# Save score
echo "$(date): Paper 1 - Score: $SCORE/$ANSWERED ($((SCORE*100/ANSWERED))%)" >> quiz_results.txt
