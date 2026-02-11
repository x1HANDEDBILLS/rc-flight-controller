cmake_minimum_required(VERSION 3.10)
project(RC_Flight_Controller)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(SDL2 REQUIRED)

# UPDATE THIS LINE: Add the 'cpp' subfolder
add_executable(rc-controller src/cpp/main.cpp)

target_include_directories(rc-controller PRIVATE 
    ${SDL2_INCLUDE_DIRS}
    ${PROJECT_SOURCE_DIR}/src/cpp  # Also update include path if headers are there
)

target_link_libraries(rc-controller PRIVATE 
    ${SDL2_LIBRARIES} 
    pthread
)