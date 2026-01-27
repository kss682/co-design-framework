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

cp -rf ~/myworks/thesis/co-design-framework/cpn-system-models/simulation_results/100_sourc.csv .
cp -rf ~/myworks/thesis/co-design-framework/cpn-system-models/simulation_results/102_dest.csv .
cp -rf ~/myworks/thesis/co-design-framework/cpn-system-models/simulation_results/101_dest.csv .

if [ -x merge_to_csv ]; then
    ./merge_to_csv \
    -a 100_sourc.csv \
    -b 102_dest.csv \
    -c 101_dest.csv \
    -o merged_to_csv.csv
else
    echo "Error: merge_to_csv executable not found"
    exit 1
fi

if [ -x simulate-lqr ]; then
    ./simulate-lqr -f merged_to_csv.csv -o states.csv
else 
    echo "Error: simulate-lqr executable not found"
    exit 1
fi

if [ -x visualization ]; then
    ./visualization -f states.csv
else
    echo "Error: visualization executable not found"
    exit 1
fi

