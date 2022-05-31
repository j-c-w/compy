#include "clang_graph_frontendaction.h"

#include <exception>
#include <iostream>
#include <utility>

#include "clang/AST/ASTConsumer.h"
#include "clang/AST/Decl.h"
#include "clang/Analysis/CFG.h"
#include "clang/Frontend/ASTConsumers.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/MultiplexConsumer.h"
#include "clang/StaticAnalyzer/Core/Checker.h"
#include "llvm/Support/raw_ostream.h"

using namespace ::clang;
using namespace ::llvm;

namespace compy {
namespace clang {
namespace graph {

bool ExtractorASTVisitor::VisitStmt(Stmt *s) {
  // Collect child stmts
  std::vector<OperandInfoPtr> ast_relations;
  for (auto it : s->children()) {
    if (it) {
      StmtInfoPtr childInfo = getInfo(*it);
      ast_relations.push_back(childInfo);
    }
  }

  if (auto *ds = dyn_cast<DeclStmt>(s)) {
    for (const Decl *decl : ds->decls()) {
      ast_relations.push_back(getInfo(*decl, false));
    }
  }

  StmtInfoPtr info = getInfo(*s);
  info->ast_relations.insert(info->ast_relations.end(), ast_relations.begin(),
                             ast_relations.end());

  return RecursiveASTVisitor<ExtractorASTVisitor>::VisitStmt(s);
}

bool ExtractorASTVisitor::VisitFunctionDecl(FunctionDecl *f) {
  // Only proceed on function definitions, not declarations. Otherwise, all
  // function declarations in headers are traversed also.
  if (!f->hasBody() || !f->getDeclName().isIdentifier()) {
    // throw away the tokens
    tokenQueue_.popTokensForRange(f->getSourceRange(), false);
    return true;
  }

  //  ::llvm::errs() << f->getNameAsString() << "\n";

  FunctionInfoPtr functionInfo = getInfo(*f);
  extractionInfo_->functionInfos.push_back(functionInfo);

  // Add entry stmt.
  functionInfo->entryStmt = getInfo(*f->getBody());

  // Add args.
  for (auto it : f->parameters()) {
    functionInfo->args.push_back(getInfo(*it, true));
  }

  // Dump CFG.
  std::unique_ptr<CFG> cfg =
      CFG::buildCFG(f, f->getBody(), &context_, CFG::BuildOptions());
  //  cfg->dump(LangOptions(), true);

//  // Create CFG Blocks.
//  for (CFG::iterator it = cfg->begin(), Eb = cfg->end(); it != Eb; ++it) {
//    CFGBlock *B = *it;
//    functionInfo->cfgBlocks.push_back(getInfo(*B));
//  }

  return RecursiveASTVisitor<ExtractorASTVisitor>::VisitFunctionDecl(f);
}

bool ExtractorASTVisitor::VisitRecordDecl(::clang::RecordDecl *r) {
//  if (const RecordDecl *rdef = r->getDefinition()) {
//    extractionInfo_->recordInfos.push_back(getInfo(*rdef, true));
//  } else {
//    extractionInfo_->recordInfos.push_back(getInfo(*r, true));
//  }

  return RecursiveASTVisitor<ExtractorASTVisitor>::VisitRecordDecl(r);
}

CFGBlockInfoPtr ExtractorASTVisitor::getInfo(const ::clang::CFGBlock &block) {
  auto it = cfgBlockInfos_.find(&block);
  if (it != cfgBlockInfos_.end()) return it->second;

  CFGBlockInfoPtr info(new CFGBlockInfo);
  cfgBlockInfos_[&block] = info;

  // Collect name.
  info->name = "cfg_" + std::to_string(block.getBlockID());

  // Collect statements.
  for (CFGBlock::const_iterator it = block.begin(), Es = block.end(); it != Es;
       ++it) {
    if (Optional<CFGStmt> CS = it->getAs<CFGStmt>()) {
      const Stmt *S = CS->getStmt();
      info->statements.push_back(getInfo(*S));
    }
  }
  if (block.getTerminatorStmt()) {
    const Stmt *S = block.getTerminatorStmt();
    info->statements.push_back(getInfo(*S));
  }

  // Collect successors.
  for (CFGBlock::const_succ_iterator it = block.succ_begin(),
                                     Es = block.succ_end();
       it != Es; ++it) {
    CFGBlock *B = *it;
    if (B) info->successors.push_back(getInfo(*B));
  }

  return info;
}

FunctionInfoPtr ExtractorASTVisitor::getInfo(const FunctionDecl &func) {
  FunctionInfoPtr info(new FunctionInfo());

  // Collect name.
  info->name = func.getNameAsString();

  // Collect type.
  info->type = func.getType().getAsString();

  // Collect tokens
  info->tokens = tokenQueue_.popTokensForRange(func.getSourceRange(), false);

  return info;
}

StmtInfoPtr ExtractorASTVisitor::getInfo(const Stmt &stmt) {
  auto it = stmtInfos_.find(&stmt);
  if (it != stmtInfos_.end()) return it->second;

  StmtInfoPtr info(new StmtInfo);
  stmtInfos_[&stmt] = info;

  // Collect name.
  info->name = stmt.getStmtClassName();

  // Collect referencing targets.
  if (const DeclRefExpr *de = dyn_cast<DeclRefExpr>(&stmt)) {
    info->ref_relations.push_back(getInfo(*de->getDecl(), false));
  }

  // Collect tokens
  info->tokens = tokenQueue_.popTokensForRange(stmt.getSourceRange(), false);

  return info;
}

DeclInfoPtr ExtractorASTVisitor::getInfo(const Decl &decl, bool consumeTokens) {
  auto it = declInfos_.find(&decl);
  if (it != declInfos_.end()) {
    if (consumeTokens) {
      auto tokens = tokenQueue_.popTokensForRange(decl.getSourceRange(), false);
      it->second->tokens.insert(it->second->tokens.end(), tokens.begin(),
                                tokens.end());
    }

    return it->second;
  }

  DeclInfoPtr info(new DeclInfo);
  declInfos_[&decl] = info;

//  // If enum type, skip the rest
//  if (EnumDecl *ed = cast<EnumDecl*>(decl))
//    return info;

  info->kind = decl.getDeclKindName();

  // Collect name.
  if (const TypedefNameDecl *vd = dyn_cast<TypedefNameDecl>(&decl)) {
    info->name = vd->getQualifiedNameAsString();
    info->type = vd->getUnderlyingType()->getTypeClassName();

    if (const auto nameTokenPtr = tokenQueue_.getTokenAt(vd->getLocation())) {
      info->nameToken = *nameTokenPtr;
    }
  }

  if (const ValueDecl *vd = dyn_cast<ValueDecl>(&decl)) {
    info->name = vd->getQualifiedNameAsString();

    if (const auto nameTokenPtr = tokenQueue_.getTokenAt(vd->getLocation())) {
      info->nameToken = *nameTokenPtr;
    }
  }

  // Collect type.
  if (const ValueDecl *vd = dyn_cast<ValueDecl>(&decl)) {
    // As string
    info->type = vd->getType().getAsString();

    // Maybe this is a pointer. In that case, iteratively dereference pointers
    QualType tyIt = vd->getType();
    while (tyIt->isAnyPointerType()) {
      tyIt = tyIt->getPointeeType();
    }

    // Collect record decls
    if (const RecordDecl *rd = tyIt->getAsRecordDecl()) {
      if (const RecordDecl *rdef = rd->getDefinition()) {
        info->recordType = getInfo(*rdef, true);
      } else {
        info->recordType = getInfo(*rd, true);
      }
    }
  }

  // Collect tokens
  if (consumeTokens) {
    info->tokens = tokenQueue_.popTokensForRange(decl.getSourceRange(), false);
  }

//  for (auto &token : info->tokens) {
//      std::cout << token.location.getRawEncoding() << " : " << token.name << std::endl;
//  }

  return info;
}

EnumDeclInfoPtr ExtractorASTVisitor::getInfo(const EnumDecl &decl, bool consumeTokens) {
  auto it = enumDeclInfos_.find(&decl);
  if (it != enumDeclInfos_.end()) {
    return it->second;
  }

  EnumDeclInfoPtr info(new EnumDeclInfo);
  enumDeclInfos_[&decl] = info;

  info->name = decl.getQualifiedNameAsString();

  // Collect tokens
  if (consumeTokens) {
    info->tokens = tokenQueue_.popTokensForRange(decl.getSourceRange(), true);
  }

  return info;
}

RecordInfoPtr ExtractorASTVisitor::getInfo(const RecordDecl &decl, bool consumeTokens) {
  auto it = recordInfos_.find(&decl);
  if (it != recordInfos_.end()) return it->second;

  RecordInfoPtr info(new RecordInfo());
  recordInfos_[&decl] = info;

  // Collect name.
  info->name = decl.getQualifiedNameAsString();

  // Collect tokens
  if (consumeTokens) {
    info->tokens = tokenQueue_.popTokensForRange(decl.getSourceRange(), true);
  }

  // Collect fields
  for (RecordDecl::field_iterator it = decl.field_begin(), Eb = decl.field_end(); it != Eb; ++it) {
    // Maybe this is a pointer. In that case, iteratively dereference pointers
    QualType tyIt = it->getType();
    while (tyIt->isAnyPointerType()) {
      tyIt = tyIt->getPointeeType();
    }

    // Collect record decls
    // - From fields
    if (const RecordDecl *rd = tyIt->getAsRecordDecl()) {
      if (const RecordDecl *rdef = rd->getDefinition()) {
        info->referencedRecords.push_back(getInfo(*rdef, true));
      } else {
        info->referencedRecords.push_back(getInfo(*rd, true));
      }
    }
    // - From function pointers in fields
    std::string str = tyIt->getTypeClassName();
    if (const TypedefType *tt = tyIt->getAs<TypedefType>()) {
      const TypedefNameDecl *tnd = tt->getDecl();
      info->referencedTypedefs.push_back(getInfo(*tnd, true));
    }


      // - From function prototypes in fields
    if (const auto *PT = it->getType()->getAs<::clang::PointerType>()) {
        auto ptr = PT->getPointeeType();
        if (const auto *paren = ptr->getAs<::clang::ParenType>()) {
            if (const auto *fn = paren->desugar()->getAs<::clang::FunctionProtoType>()) {
              // Return type
              if (const RecordDecl *rd = fn->getReturnType()->getAsRecordDecl()) {
                info->referencedRecords.push_back(getInfo(*rd, true));
              }
              // Function param types
              for (const auto &param : fn->param_types()) {
                // Maybe this is a pointer. In that case, iteratively dereference pointers
                QualType paramTyIt = param;
                while (paramTyIt->isAnyPointerType()) {
                  paramTyIt = paramTyIt->getPointeeType();
                }

                if (const RecordDecl *rd = paramTyIt->getAsRecordDecl()) {
                  info->referencedRecords.push_back(getInfo(*rd, true));
                }
              }
            }
        }
    }

    // Collect enum decls
    if (const auto *ElabT = it->getType()->getAs<ElaboratedType>()) {
      auto Ty = ElabT->getNamedType();

      if (const auto *ET = Ty->getAs<EnumType>()) {
        const EnumDecl *ED = ET->getDecl();
        info->referencedEnums.push_back(getInfo(*ED, true));
      }
    }
  }

  info->isTypedef = isa<TypedefDecl>(decl);

  return info;
}

ExtractorASTConsumer::ExtractorASTConsumer(CompilerInstance &CI,
                                           ExtractionInfoPtr extractionInfo)
    : visitor_(CI.getASTContext(), std::move(extractionInfo), tokenQueue_),
      tokenQueue_(CI.getPreprocessor()) {}

bool ExtractorASTConsumer::HandleTopLevelDecl(DeclGroupRef DR) {
  for (auto it = DR.begin(), e = DR.end(); it != e; ++it) {
    visitor_.TraverseDecl(*it);
  }

  return true;
}

std::unique_ptr<ASTConsumer> ExtractorFrontendAction::CreateASTConsumer(
    CompilerInstance &CI, StringRef file) {
  extractionInfo.reset(new ExtractionInfo());
  //  CI.getASTContext().getLangOpts().OpenCL
  return std::make_unique<ExtractorASTConsumer>(CI, extractionInfo);
}

std::vector<TokenInfo> TokenQueue::popTokensForRange(
    ::clang::SourceRange range,
    bool ignore_consumed) {
  std::vector<TokenInfo> result;
  auto startPos = token_index_[range.getBegin().getRawEncoding()];
  auto endPos = token_index_[range.getEnd().getRawEncoding()];
  for (std::size_t i = startPos; i <= endPos; ++i) {

    if (!ignore_consumed && token_consumed_[i]) continue;

    result.push_back(tokens_[i]);
    token_consumed_[i] = true;
  }

  return result;
}

void TokenQueue::addToken(::clang::Token token) {
  TokenInfo info;
  info.index = nextIndex++;
  info.kind = token.getName();
  if (token.isLiteral()) {
    const char *literal_data = token.getLiteralData();
    std::string token_str(literal_data, token.getLength());
    info.name = token_str;
  } else {
    info.name = pp_.getSpelling(token, nullptr);
  }

  info.location = token.getLocation();
  tokens_.push_back(info);
  token_consumed_.push_back(false);
  token_index_[info.location.getRawEncoding()] = tokens_.size() - 1;
}

TokenInfo *TokenQueue::getTokenAt(SourceLocation loc) {
  auto pos = token_index_.find(loc.getRawEncoding());
  if (pos == token_index_.end()) return nullptr;

  return &tokens_[pos->second];
}

}  // namespace graph
}  // namespace clang
}  // namespace compy
