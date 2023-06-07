# Common compile options
set(compile_options_common
        -fno-rtti -fPIC
        -Wall -Wextra
        # LLVM warnings
        -Wno-unused-parameter -Wno-tautological-overlap-compare -Wno-deprecated-copy -Wno-class-memaccess -Wno-maybe-uninitialized
        # Clang warnings
        -Wno-comment -Wno-strict-aliasing)

find_package(LLVM 17 HINTS "llvm-install")

# if tools are linked against llvm shared object, we need to do the same
# otherwise, we end up with two versions (shared and static) of llvm libs
# if(LLVM_LINK_LLVM_DYLIB)
set(REQ_LLVM_LIBRARIES LLVMAArch64CodeGen LLVMAArch64AsmParser LLVMAArch64Desc LLVMAArch64Disassembler LLVMAArch64Info LLVMAArch64Utils LLVMAMDGPUCodeGen LLVMAMDGPUAsmParser LLVMAMDGPUDesc LLVMAMDGPUDisassembler LLVMAMDGPUInfo LLVMAMDGPUUtils LLVMARMCodeGen LLVMARMAsmParser LLVMARMDesc LLVMARMDisassembler LLVMARMInfo LLVMARMUtils LLVMAVRCodeGen LLVMAVRAsmParser LLVMAVRDesc LLVMAVRDisassembler LLVMAVRInfo LLVMBPFCodeGen LLVMBPFAsmParser LLVMBPFDesc LLVMBPFDisassembler LLVMBPFInfo  LLVMHexagonCodeGen LLVMHexagonAsmParser LLVMHexagonDesc LLVMHexagonDisassembler LLVMHexagonInfo LLVMLanaiCodeGen LLVMLanaiAsmParser LLVMLanaiDesc LLVMLanaiDisassembler LLVMLanaiInfo LLVMLoongArchCodeGen LLVMLoongArchAsmParser LLVMLoongArchDesc LLVMLoongArchDisassembler LLVMLoongArchInfo LLVMMipsCodeGen LLVMMipsAsmParser LLVMMipsDesc LLVMMipsDisassembler LLVMMipsInfo LLVMMSP430CodeGen LLVMMSP430AsmParser LLVMMSP430Desc LLVMMSP430Disassembler LLVMMSP430Info LLVMNVPTXCodeGen LLVMNVPTXDesc LLVMNVPTXInfo LLVMPowerPCCodeGen LLVMPowerPCAsmParser LLVMPowerPCDesc LLVMPowerPCDisassembler LLVMPowerPCInfo LLVMRISCVCodeGen LLVMRISCVAsmParser LLVMRISCVDesc LLVMRISCVDisassembler LLVMRISCVInfo LLVMSparcCodeGen LLVMSparcAsmParser LLVMSparcDesc LLVMSparcDisassembler LLVMSparcInfo LLVMSystemZCodeGen LLVMSystemZAsmParser LLVMSystemZDesc LLVMSystemZDisassembler LLVMSystemZInfo LLVMVECodeGen LLVMVEAsmParser LLVMVEDesc LLVMVEDisassembler LLVMVEInfo LLVMWebAssemblyCodeGen LLVMWebAssemblyAsmParser LLVMWebAssemblyDesc LLVMWebAssemblyDisassembler LLVMWebAssemblyInfo LLVMWebAssemblyUtils LLVMX86CodeGen LLVMX86AsmParser LLVMX86Desc LLVMX86Disassembler LLVMX86Info LLVMXCoreCodeGen LLVMXCoreDesc LLVMXCoreDisassembler LLVMXCoreInfo LLVMAsmParser LLVMLinker LLVMBitReader LLVMIRReader LLVMipo LLVMScalarOpts LLVMSupport LLVMFrontendOpenMP LLVMOption LLVMPasses LLVMCoroutines LLVMLTO LLVMCoverage LLVMAArch64CodeGen LLVMCodeGen LLVMObjCARCOpts LLVMTransformUtils LLVMAnalysis LLVMCore LLVMVectorize LLVMInstCombine)

# endif()

# if clang is built as a shared lib, use that, otherwise link to the static components
# if(DEFINED CLANG_LINK_CLANG_DYLIB AND CLANG_LINK_CLANG_DYLIB)
# set(REQ_CLANG_LIBRARIES clang-cpp)
    # else()
        set(REQ_CLANG_LIBRARIES clangBasic clangFrontendTool clang-cpp)
        # endif()
# Common library
add_library(extractors_common
        common/clang_driver.cc)
# llvm_map_components_to_libnames(REQ_LLVM_LIBRARIES ${LLVM_TARGETS_TO_BUILD}
#         asmparser
#         core
#         linker
#         bitreader
#         irreader
#         ipo
#         scalaropts
#         analysis
#         support
#         frontendopenmp
#         option
#         passes
#         objcarcopts
#         coroutines
#         lto
#         coverage
#         aarch64codegen
#         )
message(REQ_CLANG_LIBRARIES=${REQ_CLANG_LIBRARIES})
message(REQ_LLVM_LIBRARIES="${REQ_LLVM_LIBRARIES}")
list(LENGTH REQ_LLVM_LIBRARIES list_len)
message("Length is ${list_len}")
target_include_directories(extractors_common PUBLIC
        .
        ${LLVM_INCLUDE_DIRS}
        ${CLANG_INCLUDE_DIRS}
        )


link_directories(${REQ_LLVM_LIBRARIES} ${REQ_CLANG_LIBRARIES})
target_link_libraries(extractors_common
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(extractors_common PRIVATE
        ${compile_options_common}
        )

# Common tests
add_executable(extractors_common_tests
        common/clang_driver_test.cc
        )
target_link_libraries(extractors_common_tests
        extractors_common

        gmock
        gtest
        gtest_main
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(extractors_common_tests PRIVATE
        -fno-rtti -fPIC
        )

# # LLVM pybind11 module
pybind11_add_module(extractors
        extractors.cc
        )
target_link_libraries(extractors PRIVATE
        clang_extractor
        llvm_extractor
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(extractors PRIVATE
        -Wno-unused-value
        )

add_subdirectory(clang_ast)
add_subdirectory(llvm_ir)
