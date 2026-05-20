#!/bin/bash
JSON_FILE="${1:-json/single_pendulum_cart_1/network.json}"
SIM_TIME=20
TRACE_FILE="simulation_results/plant1_trace.csv"
STATES_FILE="simulation_results/plant1_trace_states.csv"
DELTA="${2:-0.15}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULTS_DIR="benchmark"
mkdir -p "$RESULTS_DIR"

# --- Helpers ---

extract_max_theta() {
    local csv_file="$1"
    local start_time="${2:-0}"
    if [ -f "$csv_file" ]; then
        tail -n +2 "$csv_file" | \
            awk -F',' -v t_start="$start_time" '{
                if (NF >= 4 && $1 >= t_start && $4 ~ /^-?[0-9]/) {
                    val = ($4 < 0) ? -$4 : $4
                    if (val > max) max = val
                }
            } END {
                if (max != "") printf "%.10f", max
                else print "N/A"
            }'
    else
        echo "N/A"
    fi
}

extract_last_hit_time() {
    local output="$1"
    echo "$output" | grep -i "Last hit old mode:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

extract_first_hit_time() {
    local output="$1"
    echo "$output" | grep -i "First hit new mode:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

extract_measured_window() {
    local output="$1"
    echo "$output" | grep -i "Measured window:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

extract_transition_status() {
    local output="$1"
    local status=$(echo "$output" | grep -i "Transition status:" | awk -F':' '{print $2}' | tr -d ' ' | head -1)
    echo "${status:-unknown}"
}

run_single() {
    local delta="$1"
    local switch_time="$2"
    local x0="$3"
    local epsilon="$4"

    rm -rf simulation_results/*

    local sw_flag=""
    if [ -n "$switch_time" ]; then
        sw_flag="-sw $switch_time"
    fi

    main_output=$(python3 main.py -f "$JSON_FILE" -s Delay -t "$SIM_TIME" -d "$delta" $sw_flag 2>&1)

    local status=$(extract_transition_status "$main_output")
    local last_hit=$(extract_last_hit_time "$main_output")
    local first_hit=$(extract_first_hit_time "$main_output")
    local measured_window=$(extract_measured_window "$main_output")
    [ -z "$first_hit" ] && first_hit="N/A"
    [ -z "$measured_window" ] && measured_window="N/A"

    if [ -f "$TRACE_FILE" ]; then
        local x0_flag=""
        local eps_flag=""
        if [ -n "$x0" ]; then
            x0_flag="-x $x0"
        fi
        if [ -n "$epsilon" ]; then
            eps_flag="-e $epsilon"
        fi
        python3 pendulum_simulator.py -f "$TRACE_FILE" $eps_flag 2>&1
        max_theta=$(extract_max_theta "$STATES_FILE" "$last_hit")
    else
        max_theta="N/A"
    fi

    echo "$status,$last_hit,$first_hit,$measured_window,$max_theta"
}

WC_K1_FROZEN="-0.01505422,-0.08406382,0.17563262,0.98074453"


echo ""
echo "=============================================="
echo "6.4.3: Switch Time Sweep ($DELTA)"
echo "=============================================="

RESULTS_643="${RESULTS_DIR}/switch_time_sweep_${TIMESTAMP}.csv"
echo "switch_time,hit_index,delta,status,last_hit,first_hit,measured_window,max_theta" > "$RESULTS_643"

# Mode 1 period=20ms: hits at 0.019, 0.039, 0.059, ...
# Switch right after Nth hit: t_switch = N * 0.020
for hit_idx in 1 2 3 4 5 6 7 8 9 10; do
    sw_time=$(echo "$hit_idx * 0.010" | bc -l)
    echo "  Running: switch after hit #$hit_idx (t=$sw_time)"

    for delta in $(seq 0.010 0.010 0.250); do
        result=$(run_single "$delta" "$sw_time" "$WC_K1_FROZEN" "1")
        echo "$sw_time,$hit_idx,$delta,$result" >> "$RESULTS_643"
    done
done

echo "Results: $RESULTS_643"
echo ""
printf "%-12s %-10s %-10s %-12s %-14s %s\n" "Switch Time" "Hit #" "Delta" "Status" "Meas. Window" "Max |θ|"
printf "%-12s %-10s %-10s %-12s %-14s %s\n" "-----------" "-----" "-----" "------" "------------" "-------"
tail -n +2 "$RESULTS_643" | while IFS=',' read -r sw hit delta status last_hit first_hit mw theta; do
    printf "%-12s %-10s %-10s %-12s %-14s %s\n" "$sw" "$hit" "$delta" "$status" "$mw" "$theta"
done

echo ""
echo "=============================================="
echo "6.4 experiments complete!"
echo "=============================================="
