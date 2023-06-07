set(REQ_LLVM_LIBRARIES LLVMAArch64CodeGen LLVMAArch64AsmParser LLVMAArch64Desc LLVMAArch64Disassembler LLVMAArch64Info LLVMAArch64Utils LLVMAMDGPUCodeGen LLVMAMDGPUAsmParser LLVMAMDGPUDesc LLVMAMDGPUDisassembler LLVMAMDGPUInfo LLVMAMDGPUUtils LLVMARMCodeGen LLVMARMAsmParser LLVMARMDesc LLVMARMDisassembler LLVMARMInfo LLVMARMUtils LLVMAVRCodeGen LLVMAVRAsmParser LLVMAVRDesc LLVMAVRDisassembler LLVMAVRInfo LLVMBPFCodeGen LLVMBPFAsmParser LLVMBPFDesc LLVMBPFDisassembler LLVMBPFInfo  LLVMHexagonCodeGen LLVMHexagonAsmParser LLVMHexagonDesc LLVMHexagonDisassembler LLVMHexagonInfo LLVMLanaiCodeGen LLVMLanaiAsmParser LLVMLanaiDesc LLVMLanaiDisassembler LLVMLanaiInfo LLVMLoongArchCodeGen LLVMLoongArchAsmParser LLVMLoongArchDesc LLVMLoongArchDisassembler LLVMLoongArchInfo LLVMMipsCodeGen LLVMMipsAsmParser LLVMMipsDesc LLVMMipsDisassembler LLVMMipsInfo LLVMMSP430CodeGen LLVMMSP430AsmParser LLVMMSP430Desc LLVMMSP430Disassembler LLVMMSP430Info LLVMNVPTXCodeGen LLVMNVPTXDesc LLVMNVPTXInfo LLVMPowerPCCodeGen LLVMPowerPCAsmParser LLVMPowerPCDesc LLVMPowerPCDisassembler LLVMPowerPCInfo LLVMRISCVCodeGen LLVMRISCVAsmParser LLVMRISCVDesc LLVMRISCVDisassembler LLVMRISCVInfo LLVMSparcCodeGen LLVMSparcAsmParser LLVMSparcDesc LLVMSparcDisassembler LLVMSparcInfo LLVMSystemZCodeGen LLVMSystemZAsmParser LLVMSystemZDesc LLVMSystemZDisassembler LLVMSystemZInfo LLVMVECodeGen LLVMVEAsmParser LLVMVEDesc LLVMVEDisassembler LLVMVEInfo LLVMWebAssemblyCodeGen LLVMWebAssemblyAsmParser LLVMWebAssemblyDesc LLVMWebAssemblyDisassembler LLVMWebAssemblyInfo LLVMWebAssemblyUtils LLVMX86CodeGen LLVMX86AsmParser LLVMX86Desc LLVMX86Disassembler LLVMX86Info LLVMXCoreCodeGen LLVMXCoreDesc LLVMXCoreDisassembler LLVMXCoreInfo LLVMAsmParser LLVMLinker LLVMBitReader LLVMIRReader LLVMipo LLVMScalarOpts LLVMSupport LLVMFrontendOpenMP LLVMOption LLVMPasses LLVMCoroutines LLVMLTO LLVMCoverage LLVMAArch64CodeGen LLVMCodeGen LLVMObjCARCOpts LLVMTransformUtils LLVMAnalysis LLVMCore LLVMVectorize LLVMInstCombine)

# endif()

# if clang is built as a shared lib, use that, otherwise link to the static components
# if(DEFINED CLANG_LINK_CLANG_DYLIB AND CLANG_LINK_CLANG_DYLIB)
# set(REQ_CLANG_LIBRARIES clang-cpp)
    # else()
        set(REQ_CLANG_LIBRARIES clangBasic clangFrontendTool clang-cpp)
# Extractor library
add_library(llvm_extractor
        llvm_extractor.cc
        llvm_graph_pass.cc
        llvm_graph_funcinfo.cc
        llvm_seq_pass.cc
        )
target_link_libraries(llvm_extractor
        extractors_common
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(llvm_extractor PRIVATE
        ${compile_options_common}
        )

# Extractor tests
add_executable(llvm_extractor_tests
        llvm_pass_test.cc
        llvm_extractor_test.cc
        )
target_link_libraries(llvm_extractor_tests
        llvm_extractor

        gmock
        gtest
        gtest_main
        -Wl,--start-group
        ${REQ_LLVM_LIBRARIES}
        ${REQ_CLANG_LIBRARIES}
        -Wl,--end-group
        )
target_compile_options(llvm_extractor_tests PRIVATE
        -fno-rtti -fPIC
        )
target_compile_definitions(llvm_extractor_tests PRIVATE
        CLANG_INSTALL_PREFIX=${CLANG_INSTALL_PREFIX}
        )
