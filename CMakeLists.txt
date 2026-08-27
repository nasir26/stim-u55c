cmake_minimum_required(VERSION 3.16)
project(stim_u55c LANGUAGES CXX)

# Phase 0: repo skeleton only, no kernel or host sources yet (see
# README.md "Phased plan"). host/ (XRT runtime, linked against Stim via
# FetchContent) and kernel/hls_testbench/ (C-sim testbenches, built with
# plain g++ so they run in CI without Vitis) get their CMake targets
# starting Phase 2, when there is C++ source to build.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
