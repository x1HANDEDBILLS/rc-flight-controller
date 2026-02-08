cmake_minimum_required(VERSION 3.10)
project(RC_Flight_Controller)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(SDL2 REQUIRED)

add_executable(rc-controller
    src/main.cpp
    # add any other .cpp files here
)

target_include_directories(rc-controller PRIVATE ${SDL2_INCLUDE_DIRS})
target_link_libraries(rc-controller PRIVATE ${SDL2_LIBRARIES} pthread)

# Optional: add more libraries if needed (e.g. for serial transmitter)
# target_link_libraries(rc-controller PRIVATE serial)  # if using serial lib
