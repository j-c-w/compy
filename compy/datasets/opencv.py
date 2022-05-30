import glob
import os
import json
import py
import random
import subprocess
import sys
import traceback
from enum import Enum


import pandas as pd
from tqdm import tqdm

from compy.datasets import dataset
from compy.representations.extractors import ClangDriver


class BuildSystem(Enum):
    CONFIGURE = 1
    MAKE = 2
    CMAKE = 3


class OpencvDataset(dataset.Dataset):
    def __init__(self):
        super().__init__()

        # uri = "https://github.com/opencv/opencv.git"
        uri = "https://github.com/libav/libav.git"
        self.clone_git(uri)

        self.programming_language = ClangDriver.ProgrammingLanguage.CPlusPlus
        self.additional_include_dirs = []
        self.compiler_flags = ['-Wno-return-type']

    def get_size(self):
        return 1

    def detect_build_system(self):
        if os.path.exists(os.path.join(self.content_dir, 'configure')):
            return BuildSystem.CONFIGURE
        elif os.path.exists(os.path.join(self.content_dir, 'Makefile')):
            return BuildSystem.MAKE
        elif os.path.exists(os.path.join(self.content_dir, 'CMakeLists.txt')):
            return BuildSystem.CMAKE

    def preprocess(self, builder, visitor, start_at=False, num_samples=None, randomly_select_samples=False):
        # Record compilation invocations
        build_system = self.detect_build_system()
        if build_system == BuildSystem.CONFIGURE:
            cmd = "make clean || ./configure && make CC='echo xxyyzz' CXX='echo xxyyzz' --ignore-errors --keep-going"
        elif build_system == BuildSystem.MAKE:
            cmd = "make clean || make CC='echo xxyyzz' CXX='echo xxyyzz' --ignore-errors --keep-going"
        elif build_system == BuildSystem.CMAKE:
            cmd = "mkdir -p build && cd build && cmake .. -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
        else:
            raise Exception()

        popen = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.content_dir,
            shell=True,
        )
        stdout, stderr = popen.communicate()
        stdout = py.builtin._totext(stdout, sys.getdefaultencoding())

        # Capture compilation invocations
        if build_system in [BuildSystem.CONFIGURE, BuildSystem.MAKE]:
            compilations = [x for x in stdout.splitlines() if x.startswith("xxyyzz")]
            compilations = [x for x in compilations if ".c" in x]
            compilations = [compilation.split(' ') for compilation in compilations]
        elif build_system == BuildSystem.CMAKE:
            with open(os.path.join(self.content_dir, 'build', 'compile_commands.json'), 'r') as f:
                compile_commands = json.load(f)
                compilations = [comp['command'].split(' ') for comp in compile_commands]
        else:
            raise Exception()

        invocations = []
        for compilation in tqdm(compilations):
            invocation = {"filename": None, "flags": [], "includes": []}

            for arg in compilation:
                if ".c" in arg:
                    invocation["filename"] = arg
                elif any([arg.startswith(x) for x in ["-std", "-f", "-W", "-D"]]):
                    invocation["flags"].append(arg)
                elif arg.startswith("-I"):
                    invocation["includes"].append(arg[len("-I") :])

            invocations.append(invocation)




        samples = []
        for invocation in tqdm(invocations, desc="Source Code -> IR+ -> Code rep in %s" % self.content_dir):
            # print(invocation)

            invocation['includes'] += [os.path.dirname(invocation['filename'])]
            includes = [(os.path.join(self.content_dir, x), ClangDriver.IncludeDirType.User) for x in invocation['includes']]
            includes += [('/usr/local/include', ClangDriver.IncludeDirType.System),
                         ('/usr/lib/llvm-10/lib/clang/10.0.0/include', ClangDriver.IncludeDirType.System),
                         ('/usr/include/x86_64-linux-gnu', ClangDriver.IncludeDirType.System),
                         ('/usr/include', ClangDriver.IncludeDirType.System)]
            flags = [flag for flag in invocation['flags'] if flag not in ['-fvisibility=hidden',
                                                                          '-fPIC',
                                                                          '-Wno-maybe-uninitialized',
                                                                          '-fomit-frame-pointer',
                                                                          '-fno-math-errno',
                                                                          '-fno-tree-vectorize',
                                                                          '-fdiagnostics-color=auto']]
            clang_driver = ClangDriver(
                ClangDriver.ProgrammingLanguage.C,
                ClangDriver.OptimizationLevel.O0,
                includes,
                flags,
            )

            try:
                builder.clang_driver = clang_driver

                filename_abs = os.path.join(self.content_dir, invocation['filename'])
                with open(filename_abs, "rb") as file:
                    source_code = file.read()
                extractionInfo = builder.string_to_info(source_code)

                for functionInfo in extractionInfo.functionInfos:
                    meta = {'filename': filename_abs}
                    sample = builder.info_to_representation(functionInfo, visitor, meta)
                    samples.append(sample)

            except (RuntimeError, FileNotFoundError) as e:
                print("Error", invocation)
                pass

        return {
            "samples": [
                {
                    "x": {"code_rep": sample},
                }
            ],
        }