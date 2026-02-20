#!/bin/bash

echo "=========================================="
echo "Scene 4: Cafeteria Scene (26:15)"
echo "=========================================="

echo -e "\nQ: 'who's that'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":1575,"query":"who'\''s that","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\nQ: 'what's happening'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":1575,"query":"what'\''s happening","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\n=========================================="
echo "Scene 5: Kat & Mandella (8:04)"
echo "=========================================="

echo -e "\nQ: 'who's that'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":484,"query":"who'\''s that","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene')); print('A:', d.get('answer','No answer'))"

echo -e "\nQ: 'what's happening'"
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"10_things_i_hate_about_you","t_now":484,"query":"what'\''s happening","spoiler_mode":"off"}' \
  | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene')); print('A:', d.get('answer','No answer'))"

