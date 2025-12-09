#!/bin/bash

test_scene() {
    local name=$1
    local time=$2
    
    echo "=========================================="
    echo "$name"
    echo "=========================================="
    
    echo -e "\nQ: 'who's that'"
    curl -s -X POST http://localhost:8000/ask \
      -H "Content-Type: application/json" \
      -d "{\"film_id\":\"10_things_i_hate_about_you\",\"t_now\":$time,\"query\":\"who's that\",\"spoiler_mode\":\"off\"}" \
      | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene'), '(conf:', str(s.get('alignment_confidence',0)) + ')'); print('A:', d.get('answer','No answer')[:300] + '...')"
    
    echo -e "\nQ: 'what's happening'"
    curl -s -X POST http://localhost:8000/ask \
      -H "Content-Type: application/json" \
      -d "{\"film_id\":\"10_things_i_hate_about_you\",\"t_now\":$time,\"query\":\"what's happening\",\"spoiler_mode\":\"off\"}" \
      | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('current_scene',{}); print('Scene: [' + ('SYNTHETIC' if s.get('synthetic') else 'SCRIPT') + ']', s.get('location','No scene'), '(conf:', str(s.get('alignment_confidence',0)) + ')'); print('A:', d.get('answer','No answer')[:300] + '...')"
    
    echo ""
}

test_scene "Scene 1: Mandella/Michael Hallway (19:30)" 1170
test_scene "Scene 2: School Tour (4:00)" 240
test_scene "Scene 3: Cafeteria Mocking (21:50)" 1310
test_scene "Scene 4: Boys' Room (45:30)" 2730
test_scene "Scene 5: Kat's Room (18:30)" 1110

