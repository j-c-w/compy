import pytest
import itertools
import subprocess
from typing import Mapping

import sqlite3

from compy.datasets import LivermorecDataset
from compy.datasets import OpenCLDevmapDataset
from compy.representations import RepresentationBuilder

from compy.representations.extractors import clang_driver_scoped_options
from compy.representations.extractors.extractors import Visitor
from compy.representations.extractors.extractors import clang
from compy.representations.ast_graphs import ASTGraphBuilder
from compy.representations.ast_graphs import ASTVisitor
from compy.representations.ast_graphs import ASTDataVisitor
from compy.representations.ast_graphs import ASTDataCFGVisitor
from compy.representations.ast_graphs import ASTDataCFGTokenVisitor
from compy.representations.extractors import ClangDriver
from compy.representations.extractors.extractors import ClangExtractor


def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, Mapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v).replace('\n', '').replace(' ', '')))
    return dict(items)


class objectview(object):
    def __init__(self, d):
        self.__dict__ = d


class TestBuilder(RepresentationBuilder):
    def string_to_info(self, src):
        functionInfo = objectview({"name": "xyz"})
        return objectview({"functionInfos": [functionInfo]})

    def info_to_representation(self, info, visitor):
        return "Repr"


def match_loops(root_stmt, depth_min=1):
    def collect_loop_sequences(stmt, current_chain = []):
        ret = []
        if stmt.name == 'ForStmt':
            new_chain = current_chain + [stmt]
            ret += [new_chain]
        else:
            new_chain = current_chain

        if hasattr(stmt, 'ast_relations') and len(stmt.ast_relations):
            ret += list(itertools.chain.from_iterable(
                [collect_loop_sequences(s, new_chain) for s in stmt.ast_relations]))

        return ret

    all_loop_seqs = collect_loop_sequences(root_stmt)
    filtered_loop_seqs = [l for l in all_loop_seqs if len(l) > depth_min]

    size_by_loop = {}
    for loop_seq in filtered_loop_seqs:
        s = loop_seq[0]
        if s not in size_by_loop:
            size_by_loop[s] = len(loop_seq)
        size_by_loop[s] = max(len(loop_seq), size_by_loop[s])

    return size_by_loop


def get_statement_counts(stmt):
    def stmt_count_fn(stmt, ret={}):
        if stmt not in ret:
            ret[stmt.name] = 1
        ret[stmt.name] += 1
        if hasattr(stmt, 'ast_relations'):
            for s in stmt.ast_relations:
                stmt_count_fn(s, ret)

    stmt_counts = {}
    stmt_count_fn(stmt, stmt_counts)

    return stmt_counts


def loops_to_infos(loops):
    def get_tokens(stmt):
        ret = stmt.tokens

        if hasattr(stmt, 'ast_relations'):
            for s in stmt.ast_relations:
                ret += get_tokens(s)

        return ret

    def indent(c_unindented):
        result = subprocess.run(['indent'], input=c_unindented, capture_output=True, text=True)
        return result.stdout

    loop_infos = []
    for loop, depth in loops.items():
        token_infos = get_tokens(loop)
        tokens_infos_sorted = [t.name for t in sorted(token_infos, key=lambda x: x.index) if 'pragma' not in t.kind]
        tokens = ' '.join(tokens_infos_sorted)

        loop_infos.append({
            'meta': {
                'max_loop_depth': depth,
                'num_tokens': len(token_infos),
                'stmt_counts': get_statement_counts(loop)
            },
            'src': indent(tokens),
        })

    return loop_infos


class ASTGraphBuilder(RepresentationBuilder):
    def __init__(self, clang_driver=None):
        RepresentationBuilder.__init__(self)

        self.__clang_driver = clang_driver
        self.__extractor = ClangExtractor(self.__clang_driver)

        self.loop_infos = []

    def string_to_info(self, src, additional_include_dir=None, filename=None):
        with clang_driver_scoped_options(self.__clang_driver, additional_include_dir=additional_include_dir, filename=filename):
            return self.__extractor.GraphFromString(src)

    def info_to_representation(self, info, visitor=ASTDataVisitor):
        vis = visitor()
        info.accept(vis)

#        for fi in info.functionInfos:
#            print(' '.join([t.name for t in fi.tokens]))

        # Extract loops
        loops = match_loops(info.entryStmt)
        self.loop_infos += loops_to_infos(loops)


datasets = [
    LivermorecDataset(),
    OpenCLDevmapDataset()
]

for ds in datasets:
    clang_driver = ClangDriver(
        ds.programming_language,
        ClangDriver.OptimizationLevel.O3,
        [(x, ClangDriver.IncludeDirType.User) for x in ds.additional_include_dirs],
        ds.compiler_flags
    )
    builder = ASTGraphBuilder(clang_driver)

    class CustomVisitor(Visitor):
        def __init__(self):
            Visitor.__init__(self)

            self.function_infos = []

        def visit(self, v):
            self.function_infos.append(v)

    sample = ds.preprocess(builder, CustomVisitor)

    # Print
    for loop_info in sorted(builder.loop_infos, key=lambda s: s['meta']['num_tokens']):
        print('-' * 80)
        print(loop_info['meta'])
        print()
        print(loop_info['src'])

    # Store in SQL DB
    loop_infos_flat = [flatten_dict(x) for x in builder.loop_infos]
    all_keys = set(itertools.chain.from_iterable([x.keys() for x in loop_infos_flat]))
    int_keys = {x for x in all_keys if x.startswith('meta')}

    # establish connection to sqlite database and save into db
    conn = sqlite3.connect('loops.db')
    c = conn.cursor()

    # create a sqlite3 database to store the dictionary values
    def create_table():
        cols = ', '.join([x + ' INT' for x in int_keys])
        c.execute('CREATE TABLE IF NOT EXISTS loops(src TEXT, ' + cols + ')')

    create_table()

    for loop_info in loop_infos_flat:
        columns = ', '.join(loop_info.keys())
        placeholders = ', '.join('?' * len(loop_info))
        sql = 'INSERT INTO loops ({}) VALUES ({})'.format(columns, placeholders)
        c.execute(sql, list(loop_info.values()))

    conn.commit()

print('done')