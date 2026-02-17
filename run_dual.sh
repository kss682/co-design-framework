#!/bin/bash
# echo "removing previous simulation results"
# rm -rf simulation_results/*

BUILD_DIR="inverted-pendulum/src/build"

if [ -d $BUILD_DIR ]; then
    mkdir -p $BUILD_DIR
fi
cd $BUILD_DIR

# make clean
make

if [ -f merged_to_csv.csv ]; then
    rm merged_to_csv.csv
fi

if [ -f states.csv ]; then
    rm states.csv
fi

cp -rf ~/myworks/thesis/co-design-framework/cpn-system-models/simulation_results/plant1_trace.csv .
cp -rf ~/myworks/thesis/co-design-framework/cpn-system-models/simulation_results/plant2_trace.csv .

if [ -x simulate-lqr-dual ]; then
    ./simulate-lqr-dual -1 plant1_trace.csv -2 plant2_trace.csv -o states_dual.csv
else 
    echo "Error: simulate-lqr-dual executable not found"
    exit 1
fi

if [ -x visualization_dual ]; then
    ./visualization_dual -f states_dual.csv
else
    echo "Error: visualization executable not found"
    exit 1
fi

