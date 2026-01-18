cmake_minimum_required(VERSION 3.25)
project(InvertedPendulumSimulator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

FetchContent_Declare(
    sfml
    GIT_REPOSITORY https://github.com/SFML/SFML.git
    GIT_TAG 2.6.1
)

FetchContent_MakeAvailable(sfml)

add_executable(simulate-lqr
    inverted_pendulum.cc
    inverted_pendulum.h
    simulate-lqr.cc
    lqr.cc
    lqr.h
    event.cc
    event.h
)

add_executable(merge_to_csv
    merge_to_csv.cc
    event.cc
    event.h
)

add_executable(visualization
    visualization.cc
    inverted_pendulum.h
)

target_link_libraries(visualization
    PRIVATE
        sfml-graphics
        sfml-window
        sfml-system
)

target_include_directories(simulate-lqr
    PRIVATE
        /opt/homebrew/include
)


target_include_directories(visualization
    PRIVATE
        /opt/homebrew/include
)