#!/bin/bash
# DroneSync monitoring script

while true; do
    clear
    echo "=== DroneSync Monitor $(date) ==="
    echo ""
    
    echo "--- Containers ---"
    docker compose ps 2>/dev/null || echo "Docker not running"
    echo ""
    
    echo "--- Miner logs (last 5) ---"
    docker compose logs miner --tail=5 2>/dev/null || echo "No logs"
    echo ""
    
    echo "--- Validator logs (last 5) ---"
    docker compose logs validator --tail=5 2>/dev/null || echo "No logs"
    echo ""
    
    echo "--- TX Queue ---"
    python3 -c "
from dronesync.tx_queue import TxQueue
s = TxQueue().get_stats()
print('submitted:', s['submitted'], '| pending:', s['pending'], '| failed:', s['failed'])
" 2>/dev/null || echo "N/A"
    
    echo ""
    echo "Refreshing in 30s... (Ctrl+C to exit)"
    sleep 30
done
