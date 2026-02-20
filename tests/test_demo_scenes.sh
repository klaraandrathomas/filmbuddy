#!/bin/bash

echo "=========================================="
echo "Scene 1: Bianca Introduction (3:00)"
echo "=========================================="

echo -e "\nQ: 'who's that'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":180,"query":"who'\''s that","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\nQ: 'what's happening'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":180,"query":"what'\''s happening","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\n=========================================="
echo "Scene 2: School Tour (4:00)"
echo "=========================================="

echo -e "\nQ: 'who's that'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":240,"query":"who'\''s that","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\nQ: 'what's happening'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":240,"query":"what'\''s happening","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\n=========================================="
echo "Scene 3: Kat vs Miss Perky (8:55)"
echo "=========================================="

echo -e "\nQ: 'who's that'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":535,"query":"who'\''s that","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\nQ: 'what's happening'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":535,"query":"what'\''s happening","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('Scene:', d.get('current_scene',{}).get('location','No scene')); print('A:', d.get('answer','No answer'))"

