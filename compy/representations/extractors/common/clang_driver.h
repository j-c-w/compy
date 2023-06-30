#pragma once

#include <memory>
#include <string>
#include <tuple>
#include <vector>

#include "clang/Frontend/FrontendAction.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"

namespace compy {

class ClangDriver {
 public:
  enum ProgrammingLanguage {
    C = 0,
    CPLUSPLUS = 1,
    OPENCL = 3,
    LLVM = 4,
  };

  enum OptimizationLevel { O0 = 0, O1 = 1, O2 = 2, O3 = 3, Unspecified = 4};

  enum IncludeDirType {
    SYSTEM = 0,
    USER = 1,
  };

 public:
  ClangDriver(ProgrammingLanguage programmingLanguage,
              OptimizationLevel optimizationLevel,
              std::vector<std::tuple<std::string, IncludeDirType>> includeDirs,
              std::vector<std::string> compilerFlags);
  ClangDriver(ProgrammingLanguage programmingLanguage,
              std::vector<std::string> compilerFlags);

  void addIncludeDir(std::string includeDir, IncludeDirType includeDirType);
  void removeIncludeDir(std::string includeDir, IncludeDirType includeDirType);
  void setOptimizationLevel(OptimizationLevel optimizationLevel);
  void setFileName(std::string fileName);
  std::string getFileName() const;
  void setCompilerBinary(std::string path);
  std::string getCompilerBinary() const;

  void Invoke(std::string src,
              std::vector<::clang::FrontendAction *> frontendActions,
              std::vector<::llvm::Pass *> passes);

 private:
  void InvokeClangAndLLVM(std::string *src,
                          std::vector<::clang::FrontendAction *>& frontendActions,
                          std::vector<::llvm::Pass *>& passes);
  void InvokeLLVM(std::string& src,
                  std::vector<::llvm::Pass *>& passes);
  void runLLVMPasses(std::unique_ptr<::llvm::Module> Module,
                     std::vector<::llvm::Pass *>& passes);

 private:
  std::shared_ptr<::llvm::legacy::PassManager> pm_;

  ProgrammingLanguage programmingLanguage_;
  OptimizationLevel optimizationLevel_;
  std::vector<std::tuple<std::string, IncludeDirType>> includeDirs_;
  std::vector<std::string> compilerFlags_;
  std::string fileName_;
  std::string compilerBinary_;
};
using ClangDriverPtr = std::shared_ptr<ClangDriver>;

class SimpleClangDriver : public ClangDriver {
    public:
        SimpleClangDriver(std::vector<std::string> compilerFlags);
};

}  // namespace compy
