# Copyright (C) 2026 Quirino Scaramastra
# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.19)
project(c-manage-skill-qt VERSION 1.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

add_executable(c-manage-skill-qt
    src/main.cpp
    src/motore.h src/motore.cpp
    src/finestra.h src/finestra.cpp
    src/dialoghi.h src/dialoghi.cpp
    src/stile.h src/stile.cpp
    src/lingua.h src/lingua.cpp
    risorse/risorse.qrc
)

# Cartella del programma Python (quella con .venv e c_manage_skill/); si può cambiare con C_MANAGE_SKILL_DIR
get_filename_component(PROGETTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
target_compile_definitions(c-manage-skill-qt PRIVATE
    PROGETTO_DIR="${PROGETTO_DIR}"
    VERSIONE_GUI="${PROJECT_VERSION}")
target_compile_options(c-manage-skill-qt PRIVATE -Wall -Wextra)
target_link_libraries(c-manage-skill-qt PRIVATE Qt6::Widgets)
