import os
import sys
import subprocess

from compy.representations.extractors.extractors import SimpleClangDriver, ClangDriver
from compy.representations.extractors.extractors import ClangExtractor
from compy.representations.extractors.extractors import LLVMIRExtractor
from compy.representations.extractors.extractors import clang
from compy.representations.extractors.extractors import llvm

from compy.representations.ast_graphs import ASTCodeBuilder
from compy.representations.ast_graphs import ASTCodeVisitor

COMPILER='clang'

def run_clang(clang_args):
    subprocess.Popen([COMPILER] + clang_args)

# Process the output of clang -### into a list.
def get_extra_includes(hash_output):
    output_lines = []
    while True:
        line = hash_output.stderr.readline()
        if not line:
            break
        output_lines.append(line)

    includes = []

    output_ind = output_lines[4]
    as_flags = str(output_ind).split(" ")
    index = 0

    while index < len(as_flags):
        flag = as_flags[index]
        if flag == '"-internal-externc-isystem"':
            includes.append(as_flags[index + 1][1:-1])
        elif flag == '"-internal-isystem"':
            includes.append(as_flags[index + 1][1:-1])

        index += 1
    return [(include, ClangDriver.IncludeDirType.User) for include in includes]

def is_file(f):
    # TODO -- this check needs to say whether the file is a C file that we
    # should extract on.
    # NOT what it currently does.
    return os.path.exists(f)

def main():
    clang_args = []

    includes = []
    opt_level = ClangDriver.OptimizationLevel.O2

    run_extractor = False # Run the extractor on this compiler invocation?
    interactive_mode = False # Use interactive mode? (Pause after extraction for <CR> to allow file to be updated)

    # Don't use argparse becuase we want to leave the majority
    # of the args untouched --- just a few that are
    # going to control this tool rather than underlying
    # clang.
    ind = 1 # start at 1 because 0 is toolname
    while ind < len(sys.argv):
        arg = sys.argv[ind]
        # Check for, and delete, tool-specific args.
        if arg == "--extract":
            run_extractor = True
            # TODO --- that arg should probably be
            # a flag with an argument pointing to
            # a python class to run an extractor.
        elif arg == "--interactive":
            interactive_mode = True
        elif arg == "--compiler":
            global COMPILER
            COMPILER = sys.argv[ind + 1]
            ind += 1
        else:
            clang_args.append(arg)

        if arg == '-I':
            # Next arg is the include
            includes.append(sys.argv[ind + 1])
        elif arg.startswith('-I'):
            # This arg is the include:
            includes.append(arg[2:])

        # TODO -- need to properly process this so we
        # don't pick up other args by accident.
        if is_file(arg):
            src = arg

        if arg == '-O0':
            opt_level = ClangDriver.OptimizationLevel.O0
        if arg == '-O1':
            opt_level = ClangDriver.OptimizationLevel.O1
        if arg == '-O2':
            opt_level = ClangDriver.OptimizationLevel.O2
        if arg == '-O3':
            opt_level = ClangDriver.OptimizationLevel.O3
        # TODO -- what about Os and Omax?

        ind += 1

    test = ClangDriver(
            ClangDriver.ProgrammingLanguage.C,
            ClangDriver.OptimizationLevel.O3,
            [],
            ["-Wall"]
            )

    # Get the include directories that we need --- for some reason
    # the compy driver doesn't ge tthe normal include directories.
    outputs = subprocess.Popen([COMPILER, '-###'] + clang_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    extra_includes = get_extra_includes(outputs)
    
    if run_extractor:
        clang_driver = ClangDriver(
                ClangDriver.ProgrammingLanguage.C,
                opt_level,
                includes + extra_includes,
                clang_args,
            )
        builder = ASTCodeBuilder(clang_driver)
        visitor = lambda: ASTCodeVisitor()
        samples = []
        with open(src) as f:
            src_contents = f.read()
            extractionInfo = builder.string_to_info(src_contents)

            for functionInfo in extractionInfo.functionInfos:
                metadata = {}
                sample = builder.info_to_representation(functionInfo, visitor, metadata)
                samples.append(sample)

        print("Ran Extractor (found " + str(len(samples)) + " samples)")
        # print(samples) # TODO -- save these in a file

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
