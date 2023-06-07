#!/bin/bash

set -eu

# git clone git@github.com:llvm/llvm-project
mkdir -p llvm-build
cd llvm-build
#cmake ../llvm-project -DLLVM_BUILD_LLVM_DYLIB=On -DLLVM_LINK_LLVM_DYLIB=On
cmake ../llvm-project/llvm -DLLVM_ENABLE_PROJECTS=clang -DBUILD_SHARED_LIBS=ON -DCMAKE_BUILD_TYPE=MinSizeRel -DCMAKE_INSTALL_PREFIX=$PWD/../llvm-install
make -j5
make -j install


# obviously does nothing --- here as documentation
export CPLUS_INCLUDE_PATH=$PWD/llvm-project/clang/include:$PWD/llvm-project/llvm/include/:$PWD/llvm-build/include/:$PWD/llvm-build/tools/clang/include
export LIBRARY_PATH=$PWD/llvm-build/lib
