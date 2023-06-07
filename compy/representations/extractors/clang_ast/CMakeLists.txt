set(REQ_LLVM_LIBRARIES LLVMAArch64CodeGen LLVMAArch64AsmParser LLVMAArch64Desc LLVMAArch64Disassembler LLVMAArch64Info LLVMAArch64Utils LLVMAMDGPUCodeGen LLVMAMDGPUAsmParser LLVMAMDGPUDesc LLVMAMDGPUDisassembler LLVMAMDGPUInfo LLVMAMDGPUUtils LLVMARMCodeGen LLVMARMAsmParser LLVMARMDesc LLVMARMDisassembler LLVMARMInfo LLVMARMUtils LLVMAVRCodeGen LLVMAVRAsmParser LLVMAVRDesc LLVMAVRDisassembler LLVMAVRInfo LLVMBPFCodeGen LLVMBPFAsmParser LLVMBPFDesc LLVMBPFDisassembler LLVMBPFInfo  LLVMHexagonCodeGen LLVMHexagonAsmParser LLVMHexagonDesc LLVMHexagonDisassembler LLVMHexagonInfo LLVMLanaiCodeGen LLVMLanaiAsmParser LLVMLanaiDesc LLVMLanaiDisassembler LLVMLanaiInfo LLVMLoongArchCodeGen LLVMLoongArchAsmParser LLVMLoongArchDesc LLVMLoongArchDisassembler LLVMLoongArchInfo LLVMMipsCodeGen LLVMMipsAsmParser LLVMMipsDesc LLVMMipsDisassembler LLVMMipsInfo LLVMMSP430CodeGen LLVMMSP430AsmParser LLVMMSP430Desc LLVMMSP430Disassembler LLVMMSP430Info LLVMNVPTXCodeGen LLVMNVPTXDesc LLVMNVPTXInfo LLVMPowerPCCodeGen LLVMPowerPCAsmParser LLVMPowerPCDesc LLVMPowerPCDisassembler LLVMPowerPCInfo LLVMRISCVCodeGen LLVMRISCVAsmParser LLVMRISCVDesc LLVMRISCVDisassembler LLVMRISCVInfo LLVMSparcCodeGen LLVMSparcAsmParser LLVMSparcDesc LLVMSparcDisassembler LLVMSparcInfo LLVMSystemZCodeGen LLVMSystemZAsmParser LLVMSystemZDesc LLVMSystemZDisassembler LLVMSystemZInfo LLVMVECodeGen LLVMVEAsmParser LLVMVEDesc LLVMVEDisassembler LLVMVEInfo LLVMWebAssemblyCodeGen LLVMWebAssemblyAsmParser LLVMWebAssemblyDesc LLVMWebAssemblyDisassembler LLVMWebAssemblyInfo LLVMWebAssemblyUtils LLVMX86CodeGen LLVMX86AsmParser LLVMX86Desc LLVMX86Disassembler LLVMX86Info LLVMXCoreCodeGen LLVMXCoreDesc LLVMXCoreDisassembler LLVMXCoreInfo LLVMAsmParser LLVMLinker LLVMBitReader LLVMIRReader LLVMipo LLVMScalarOpts LLVMSupport LLVMFrontendOpenMP LLVMOption LLVMPasses LLVMCoroutines LLVMLTO LLVMCoverage LLVMAArch64CodeGen LLVMCodeGen LLVMObjCARCOpts LLVMTransformUtils LLVMAnalysis LLVMCore LLVMVectorize LLVMInstCombine)

# endif()

# if clang is built as a shared lib, use that, otherwise link to the static components
# if(DEFINED CLANG_LINK_CLANG_DYLIB AND CLANG_LINK_CLANG_DYLIB)
# set(REQ_CLANG_LIBRARIES clang-cpp)
    # else()
        set(REQ_CLANG_LIBRARIES clangBasic clangFrontendTool clang-cpp)
# Extractor library
add_library(clang_extractor
        clang_extractor.cc
        clang_graph_frontendaction.cc
        clang_seq_frontendaction.cc
        )
target_link_libraries(clang_extractor
        extractors_common
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(clang_extractor PRIVATE
        ${compile_options_common}
        )

# Extractor tests
add_executable(clang_extractor_tests
        clang_extractor_test.cc
        )
target_link_libraries(clang_extractor_tests
        clang_extractor

        gmock
        gtest
        gtest_main
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(clang_extractor_tests PRIVATE
        -fno-rtti -fPIC
        )
