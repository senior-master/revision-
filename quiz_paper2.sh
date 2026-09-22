#!/bin/bash

# Quiz 2: Questions 251-500
# 20 seconds per question = 5000 seconds total

TOTAL=250
TIME_PER_Q=20
TOTAL_TIME=$((TOTAL * TIME_PER_Q))
SCORE=0
CURRENT=0
START_ID=251

clear
echo "======================================"
echo "   PAPER 2: QUESTIONS 251-500"
echo "   Total Time: $((TOTAL_TIME/60)) minutes"
echo "   Time per question: ${TIME_PER_Q} seconds"
echo "======================================"
echo ""
echo "Press ENTER to start..."
read start

START_TIME=$(date +%s)
END_TIME=$((START_TIME + TOTAL_TIME))

for i in $(seq $START_ID 500); do
  CURRENT=$((i - START_ID + 1))
  q_index=$((i - 1))
  
  # Get question from JSON
  q=$(jq -r ".[$q_index]" questions.json)
  
  clear
  echo "======================================"
  echo "   PAPER 2 - Question $CURRENT of $TOTAL"
  echo "   Time remaining: $((($END_TIME - $(date +%s))/60)) min $((($END_TIME - $(date +%s))%60)) sec"
  echo "   Score: $SCORE/$((CURRENT-1))"
  echo "======================================"
  echo ""
  echo "Q$i: $(echo "$q" | jq -r '.question')"
  echo ""
  
  for j in {0..3}; do
    echo "  $(echo "$q" | jq -r ".options[$j]")"
  done
  
  echo ""
  echo -n "Your answer (A/B/C/D): "
  
  # Timer countdown
  if read -t $TIME_PER_Q ans; then
    # Answer was given
    correct_ans=$(echo "$q" | jq -r '.answer')
    if [[ "${ans^^}" == "$correct_ans" ]]; then
      echo "  ✅ Correct!"
      ((SCORE++))
    else
      echo "  ❌ Wrong. Answer: $correct_ans"
    fi
  else
    # Time ran out
    correct_ans=$(echo "$q" | jq -r '.answer')
    echo "  ⏰ Time's up! Answer: $correct_ans"
  fi
  
  # Check if time is up for entire exam
  if [[ $(date +%s) -ge $END_TIME ]]; then
    echo ""
    echo "⏰ TIME'S UP FOR THE ENTIRE PAPER!"
    break
  fi
  
  echo ""
  echo "Press ENTER for next question..."
  read next
done

ELAPSED=$(( $(date +%s) - START_TIME ))

clear
echo "======================================"
echo "   PAPER 2 COMPLETE!"
echo "======================================"
echo ""
echo "Final Score: $SCORE/$CURRENT"
echo "Percentage: $((SCORE*100/CURRENT))%"
echo "Time Used: $((ELAPSED/60)) min $((ELAPSED%60)) sec"
echo "======================================"

# Save score
echo "$(date): Paper 2 - Score: $SCORE/$CURRENT ($((SCORE*100/CURRENT))%)" >> quiz_results.txt
