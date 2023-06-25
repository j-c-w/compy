import os
import sys

from compy.representations.extractors.extractors import SimpleClangDriver, ClangDriver
from compy.representations.extractors.extractors import ClangExtractor
from compy.representations.extractors.extractors import LLVMIRExtractor
from compy.representations.extractors.extractors import clang
from compy.representations.extractors.extractors import llvm

def main():
    clang_args = []
    run_extractor = False # Run the extractor on this compiler invocation?
    interactive_mode = False # Use interactive mode? (Pause after extraction for <CR> to allow file to be updated)

    # Don't use argparse becuase we want to leave the majority
    # of the args untouched --- just a few that are
    # going to control this tool rather than underlying
    # clang.
    for arg in sys.argv:
        if arg == "--extract":
            run_extractor = True
            # TODO --- that arg should probably be
            # a flag with an argument pointing to
            # a python class to run an extractor.
        elif arg == "--interactive":
            interactive_mode = True
        else:
            clang_args.append(arg)

    test = ClangDriver(
            ClangDriver.ProgrammingLanguage.C,
            ClangDriver.OptimizationLevel.O3,
            [],
            ["-Wall"]
            )
    
    if run_extractor:
        clang_driver = SimpleClangDriver(
                # SimpleClangDriver.ProgrammingLanguage.C,
                clang_args
        )
        extractor = ClangExtractor(clang_driver)

        print("Ran Extractor")

        # If interactive mode, then wait for update signal here
        # before running the clang compiler.
        if interactive_mode:
            input('Awaiting <CR> (avoid --interactive to skip)')

    # Regardless of if we ran the extractor, run the compiler
    # on the binary with the normal flags to produce the appropriate
    # object files and allow for integration within a wider
    # compilation system.
    run_clang(clang_args)

if __name__ == "__main__":
    main()
