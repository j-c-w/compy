// C samples
constexpr char kProgram1[] =
    "int foo() {\n"
    "  return 1;\n"
    "}";
constexpr char kProgram2[] =
    "int max(int a, int b) {\n"
    "  if(a > b) {\n"
    "    return a;\n"
    "  } else {\n"
    "    return b;\n"
    "  }\n"
    "}";
constexpr char kProgram3[] =
    "#include <stdio.h>\n"
    "\n"
    "void foo() {\n"
    "  printf(\"Hello\");\n"
    "}";
constexpr char kProgram4[] =
    "#include \"tempHdr.h\"\n"
    "\n"
    "void foo() {\n"
    "  barbara(1.2, 3.4);\n"
    "}";
constexpr char kProgram5[] =
    "int max(int a, int b) {\n"
    "  if (a > b) {\n"
    "    return a;\n"
    "  } else {\n"
    "    return b;\n"
    "  }\n"
    "}\n"
    "int foo(int x) {\n"
    "  return max(1, x);\n"
    "}";
constexpr char kProgram6[] =
    "struct st {\n"
        "  int x[1337];\n"
        "  int y;\n"
        "};\n"
        "struct {\n"
        "  int x;\n"
        "  int y[1112];\n"
        "} st2;\n"
        "\n"
        "int foo(struct st s) {\n"
    "  return st2.x;\n"
    "  return st2.x;\n"
        "}";
constexpr char kProgram7[] =
    "enum suit {\n"
    "    club = 0,\n"
    "    diamonds = 10,\n"
    "    hearts = 20,\n"
    "    spades = 3,\n"
    "};"
    "struct {\n"
    "  int x;\n"
    "  enum suit s;\n"
    "} st2;\n"
    "\n"
    "int foo() {\n"
    "  return st2.x;\n"
    "}";
constexpr char kProgram8[] =
    "typedef struct st {\n"
    "  int x[1337];\n"
    "  int y;\n"
    "} st;\n"
    "struct {\n"
    "  int x;\n"
    "  int *(*foobar)(st* w, int h);\n"
    "} st2;\n"
    "\n"
    "int foo() {\n"
    "  return st2.x;\n"
    "}";
constexpr char kProgram9[] =
    "typedef int foobar;\n"
    "struct {\n"
    "  int x;\n"
    "  foobar* z;\n"
    "} st2;\n"
    "\n"
    "int foo() {\n"
    "  return st2.x;\n"
    "}";
constexpr char kProgram10[] =
    "typedef int foobar;\n"
    "int foo() {\n"
    "  foobar x = 4;"
    "  return x;\n"
    "}";
constexpr char kProgram11[] =
    "typedef int foobar;\n"
    "foobar foo() {\n"
    "  foobar x[10];"
    "  return x[1];\n"
    "}";
constexpr char kProgram12[] =
    "struct st2 {\n"
    "  int x;\n"
    "};\n"
    "int foo() {\n"
    "  struct st2 mys[10];"
    "  return mys[1].x;\n"
    "}";
constexpr char kProgram13[] =
    "int* foo (int x, int* y) {\n"
    "  int bar = 1337;\n"
    "  return 0;\n"
//    "\n"
//    "  for (int i=0; i<x; i++) {\n"
//    "    y[x] += bar;\n"
//    "  }\n"
//    "  return y;\n"
    "}";

// LLVM samples
constexpr char kLLVM1[] =
    "define dso_local void @A(i32*) #0 {\n"
    "  %2 = alloca i32*, align 8\n"
    "  %3 = alloca i32, align 4\n"
    "  store i32* %0, i32** %2, align 8\n"
    "  store i32 2, i32* %3, align 4\n"
    "  %4 = load i32, i32* %3, align 4\n"
    "  %5 = load i32*, i32** %2, align 8\n"
    "  %6 = getelementptr inbounds i32, i32* %5, i64 0\n"
    "  store i32 %4, i32* %6, align 4\n"
    "  ret void\n"
    "}\n";
constexpr char kLLVM2[] =
    "define dso_local void @A(i32*) #0 {\n"
    "  %2 = alloca i32*, align 8\n"
    "  %3 = alloca i32, align 4\n"
    "  store i32* %0, i32** %2, align 8\n"
    "}\n";