#!/bin/bash

JSON_FILE="${1:-json/single_pendulum_cart_1/network.json}"
SIM_TIME=20
TRACE_FILE="simulation_results/plant1_trace.csv"
STATES_FILE="simulation_results/plant1_trace_states.csv"

# Results file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULTS_DIR="benchmark"
mkdir -p "$RESULTS_DIR"
RESULTS_FILE="${RESULTS_DIR}/delta_sweep_${TIMESTAMP}.csv"

# CSV header
echo "delta,status,measured_window_ms,max_theta" > "$RESULTS_FILE"

echo "=============================================="
echo "Delta Sweep"
echo "=============================================="
echo "JSON file:    $JSON_FILE"
echo "Delta range:  0.010 to 0.250 (step 0.005)"
echo "Results file: $RESULTS_FILE"
echo "=============================================="

# Function to extract max absolute theta from a given start time onward
# Usage: extract_max_theta <csv_file> [start_time]
# If start_time is provided, only considers rows where t >= start_time
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

# Function to extract measured window from main.py output
extract_measured_window() {
    local output="$1"
    # Extract the number before "ms" from "Measured window: X.XXXms"
    echo "$output" | grep -i "Measured window:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

extract_last_hit_time(){
    local output="$1"

    echo "$output" | grep -i "Last hit old mode:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

extract_first_hit_time(){
    local output="$1"

    echo "$output" | grep -i "First hit new mode:" | awk -F':' '{print $2}' | sed 's/ms//g' | tr -d ' ' | head -1
}

# 5ms steps from 10ms to 250ms
for delta in $(seq 0.010 0.005 0.250); do
    echo ""
    echo "Running with delta = $delta"
    echo "----------------------------------------------"
    
    # Clean up previous results
    rm -rf simulation_results/*
    
    # Run main.py with delta parameter and capture output
    main_output=$(python3 main.py -f "$JSON_FILE" -s Delay -t "$SIM_TIME" -d "$delta" 2>&1)
    main_exit_code=$?
    
    # Determine transition status (from the sufficient condition check)
    transition_status=$(echo "$main_output" | grep -i "Transition status:" | awk -F':' '{print $2}' | tr -d ' ' | head -1)
    if [ -z "$transition_status" ]; then
        # Fallback to old method
        if echo "$main_output" | grep -qi "violated"; then
            status="violated"
        elif echo "$main_output" | grep -qi "satisfied"; then
            status="satisfied"
        else
            status="unknown"
        fi
    else
        status=$(echo "$transition_status" | tr '[:upper:]' '[:lower:]')
    fi
    
    # Extract measured window
    measured_window=$(extract_measured_window "$main_output")
    if [ -z "$measured_window" ]; then
        measured_window="N/A"
    fi

    last_hit_time=$(extract_last_hit_time "$main_output")
    if [ -z "$last_hit_time" ]; then
        last_hit_time="N/A"
    fi

    first_hit_time=$(extract_first_hit_time "$main_output")
    if [ -z "$first_hit_time" ]; then
        first_hit_time="N/A"
    fi
    
    if [ $main_exit_code -eq 0 ]; then
        echo "main.py - Status: $status, Measured window: ${measured_window}ms"
    else
        echo "main.py failed (exit $main_exit_code)"
    fi
    
    # Run pendulum simulator
    if [ -f "$TRACE_FILE" ]; then
        python3 pendulum_simulator.py -f "$TRACE_FILE"
        sim_exit_code=$?
        
        max_theta=$(extract_max_theta "$STATES_FILE" "$last_hit_time")
        
        if [ $sim_exit_code -eq 0 ]; then
            echo "Pendulum sim - Max |θ|: $max_theta rad"
        else
            echo "Pendulum simulator failed"
            max_theta="N/A"
        fi
    else
        echo "Trace file not found"
        max_theta="N/A"
    fi
    
    # Append to CSV
    echo "$delta,$status,$last_hit_time,$first_hit_time,$measured_window,$max_theta" >> "$RESULTS_FILE"
done

# Summary
echo ""
echo "=============================================="
echo "Complete! Results: $RESULTS_FILE"
echo "=============================================="
echo ""
printf "%-10s %-12s %-20s %-20s %-20s %s\n" "Delta" "Status" "Last Hit (ms)" "First Hit (ms)" "Measured Window" "Max |θ|"
printf "%-10s %-12s %-20s %-20s %-20s %s\n" "-----" "------" "-------------" "--------------" "---------------" "-------"
tail -n +2 "$RESULTS_FILE" | while IFS=',' read -r delta status last_hit first_hit window theta; do
    printf "%-10s %-12s %-20s %-20s %-20s %s\n" "$delta" "$status" "$last_hit" "$first_hit" "${window}ms" "$theta"
done