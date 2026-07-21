# CMake generated Testfile for 
# Source directory: I:/workspace/hyper_spherical
# Build directory: I:/workspace/hyper_spherical/build_test
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
if(CTEST_CONFIGURATION_TYPE MATCHES "^([Dd][Ee][Bb][Uu][Gg])$")
  add_test([=[tesseract_core_tests]=] "I:/workspace/hyper_spherical/build_test/Debug/pirate_tests.exe")
  set_tests_properties([=[tesseract_core_tests]=] PROPERTIES  _BACKTRACE_TRIPLES "I:/workspace/hyper_spherical/CMakeLists.txt;197;add_test;I:/workspace/hyper_spherical/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
  add_test([=[tesseract_core_tests]=] "I:/workspace/hyper_spherical/build_test/Release/pirate_tests.exe")
  set_tests_properties([=[tesseract_core_tests]=] PROPERTIES  _BACKTRACE_TRIPLES "I:/workspace/hyper_spherical/CMakeLists.txt;197;add_test;I:/workspace/hyper_spherical/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Mm][Ii][Nn][Ss][Ii][Zz][Ee][Rr][Ee][Ll])$")
  add_test([=[tesseract_core_tests]=] "I:/workspace/hyper_spherical/build_test/MinSizeRel/pirate_tests.exe")
  set_tests_properties([=[tesseract_core_tests]=] PROPERTIES  _BACKTRACE_TRIPLES "I:/workspace/hyper_spherical/CMakeLists.txt;197;add_test;I:/workspace/hyper_spherical/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
  add_test([=[tesseract_core_tests]=] "I:/workspace/hyper_spherical/build_test/RelWithDebInfo/pirate_tests.exe")
  set_tests_properties([=[tesseract_core_tests]=] PROPERTIES  _BACKTRACE_TRIPLES "I:/workspace/hyper_spherical/CMakeLists.txt;197;add_test;I:/workspace/hyper_spherical/CMakeLists.txt;0;")
else()
  add_test([=[tesseract_core_tests]=] NOT_AVAILABLE)
endif()
