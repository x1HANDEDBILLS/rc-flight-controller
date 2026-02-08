cmake_minimum_required(VERSION 3.10)
project(PS5FlightController LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

find_package(SDL2 REQUIRED)
include_directories(${SDL2_INCLUDE_DIRS})

add_executable(flight src/main.cpp)
target_link_libraries(flight ${SDL2_LIBRARIES})
