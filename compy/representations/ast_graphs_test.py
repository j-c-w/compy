import os

import networkx as nx
import pytest

from compy.representations.extractors.extractors import Visitor
from compy.representations.extractors.extractors import clang
from compy.representations.extractors.extractors import ClangDriver
from compy.representations.ast_graphs import ASTGraphBuilder
from compy.representations.ast_graphs import ASTCodeBuilder
from compy.representations.ast_graphs import ASTCodeVisitor
from compy.representations.ast_graphs import ASTVisitor
from compy.representations.ast_graphs import ASTDataVisitor
from compy.representations.ast_graphs import ASTDataCFGVisitor
from compy.representations.ast_graphs import ASTDataCFGTokenVisitor


program_1fn_2 = """
int bar(int a) {
  if (a > 10)
    return a;
  return -1;
}
"""


# Construction
def test_construct_with_custom_visitor():
    class CustomVisitor(Visitor):
        def __init__(self):
            Visitor.__init__(self)
            self.edge_types = []
            self.G = nx.DiGraph()

        def visit(self, v):
            if not isinstance(v, clang.graph.ExtractionInfo):
                self.G.add_node(v, attr=type(v))

    builder = ASTGraphBuilder()
    info = builder.string_to_info(program_1fn_2)
    ast = builder.info_to_representation(info, CustomVisitor)

    assert len(ast.G) == 35


# Attributes
def test_get_node_list():
    builder = ASTGraphBuilder()
    info = builder.string_to_info(program_1fn_2)
    ast = builder.info_to_representation(info, ASTDataVisitor)
    nodes = ast.get_node_list()

    assert len(nodes) == 14


def test_get_edge_list():
    builder = ASTGraphBuilder()
    info = builder.string_to_info(program_1fn_2)
    ast = builder.info_to_representation(info, ASTDataVisitor)
    edges = ast.get_edge_list()

    assert len(edges) > 0

    assert type(edges[0][0]) is int
    assert type(edges[0][1]) is int
    assert type(edges[0][2]) is int


# Plot
def test_plot(tmpdir):
    for visitor in [ASTDataVisitor]:
        builder = ASTGraphBuilder()
        info = builder.string_to_info(program_fib)
        graph = builder.info_to_representation(info, ASTDataVisitor)

        outfile = os.path.join(tmpdir, str(visitor.__name__) + ".png")
        graph.draw(path=outfile, with_legend=True)

        assert os.path.isfile(outfile)

    # os.system('xdg-open ' + str(tmpdir))


# All visitors
def test_all_visitors():
    for visitor in [ASTVisitor, ASTDataVisitor, ASTDataCFGVisitor]:
        builder = ASTGraphBuilder()
        info = builder.string_to_info(program_1fn_2)
        ast = builder.info_to_representation(info, visitor)

        assert ast


def test_token_visitor():
    builder = ASTGraphBuilder()
    info = builder.string_to_info(program_1fn_2)
    ast = builder.info_to_representation(info, ASTDataCFGTokenVisitor)

    assert ast
    token_data = sorted([data for t, data in ast.G.nodes(data=True) if 'seq_order' in data], key=lambda x: x['seq_order'])
    tokens = [t['attr'] for t in token_data]
    assert tokens == [
        'int', 'bar', '(', 'int', 'a', ')',
        '{',
        'if', '(', 'a', '>', '10', ')', 'return', 'a', ';',
        'return', '-', '1', ';',
        '}'
    ]

    leaves = ast.get_leaf_node_list()
    labels = ast.get_node_str_list()
    assert [labels[n] for n in leaves] == tokens


#
def build_compilable_code(src_in):
    driver = ClangDriver(
        ClangDriver.ProgrammingLanguage.C,
        ClangDriver.OptimizationLevel.O3,
        [],
        []
    )
    builder = ASTCodeBuilder(driver)
    info = builder.string_to_info(src_in)
    reps = builder.info_to_representation(info.functionInfos[0], ASTCodeVisitor, {})

    return reps


def test_code_builder_innermost_2_nested():
    src = """
    int* foo (int x, int* y) {
      for (int i=0; i<x; i++) {
        y[x] += 1;
      }
      return y;
    }
    """

    reps = build_compilable_code(src)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True
    assert len(reps) is 1
    assert reps[0]['body'].count('for') is 1


def test_code_builder_extract_innermost():
    src = """
    int* foo (int x, int* y) {
      for (int i=0; i<x; i++) {
        y[x] += 1;
      }
      return y;
    }
    """
    reps = build_compilable_code(src)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True
    assert len(reps) is 1
    assert reps[0]['body'].count('for') is 1


def test_code_builder_extract_innermost_2_nested():
    src = """
    int* foo (int x, int* y) {
      for (int i=0; i<x; i++) {
        for (int j=0; j<i; j++) {
          y[x] += 1;
        }
      }
      return y;
    }
    """
    reps = build_compilable_code(src)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True
    assert len(reps) is 1
    assert reps[0]['body'].count('for') is 1


def test_code_builder_extract_innermost_3_nested():
    src = """
    int* foo (int x, int* y) {
      for (int i=0; i<x; i++) {
        for (int j=0; j<i; j++) {
          for (int z=0; z<j; z++) {
            y[x] += 1;
          }
        }
      }
      return y;
    }
    """
    reps = build_compilable_code(src)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True
    assert len(reps) is 1
    assert reps[0]['body'].count('for') is 1


def test_code_builder_compile_anonymous_extern_struct():
    src = """
    extern struct {
        int x;
    } bar;
    int foo () {
      return bar.x;
    }
    """
    reps = build_compilable_code(src)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True


def test_code_builder_constants():
    src = """
    int* foo (int x, int* y) {
      int bar = 1337;
    
      for (int i=0; i<x; i++) {
        y[x] += bar;
      }
      return y;
    }
    """
    reps = build_compilable_code(src)
    print(reps)

    assert all([r['meta']['clang_returncode'] is 0 for r in reps]) is True
    assert len(reps) is 1
    assert "int bar = 1337;" in reps[0]['body']