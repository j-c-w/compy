import os.path

import pytest
import itertools
import subprocess
from typing import Mapping

import sqlite3

from compy.datasets import LivermorecDataset
from compy.datasets import OpenCLDevmapDataset
from compy.datasets import GeneralDataset
from compy.datasets import PolybenchDataset
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
            items.append((new_key, str(v)))
    return dict(items)


class objectview(object):
    def __init__(self, d):
        self.__dict__ = d


def tokens_to_str(token_infos):
    return ' '.join([t.name for t in sorted(token_infos, key=lambda x: x.index) if 'pragma' not in t.kind])

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
        if any([allowed in stmt.name for allowed in ['Stmt', 'Expr', 'Operator', 'Literal']]):
            name = stmt.name
            if name not in ret:
                ret[name] = 1
            ret[name] += 1

            if stmt.name in ['BinaryOperator', 'UnaryOperator']:
                name = stmt.name + '_' + '_'.join([t.kind for t in stmt.tokens])
                if name not in ret:
                    ret[name] = 1
                ret[name] += 1

        if hasattr(stmt, 'ast_relations'):
            for s in stmt.ast_relations:
                stmt_count_fn(s, ret)

    stmt_counts = {}
    stmt_count_fn(stmt, stmt_counts)

    return stmt_counts


def loops_to_infos(loops, meta):
    def get_tokens(stmt):
        ret = stmt.tokens

        if hasattr(stmt, 'ast_relations'):
            for s in stmt.ast_relations:
                ret += get_tokens(s)

        return ret

    def get_all_stmts(stmt):
        ret = []
        ret.append(stmt)

        if hasattr(stmt, 'ast_relations'):
            for s in stmt.ast_relations:
                ret += get_all_stmts(s)
        return ret

    def get_referenced_records(root_record):
        visited = [root_record]
        todo = [root_record]

        while todo:
            current = todo.pop(0)

            for rec in current.referencedRecords:
                if rec not in visited:
                    visited.append(rec)
                    todo.append(rec)

        return reversed(visited)

    def get_referenced_records_rpo(root_record):
        all_nodes = get_referenced_records(root_record)

        # Standard colouring for DFS
        WHITE = 0  # Not seen yet
        GRAY = 1   # Seen but not completed
        BLACK = 2  # Seen and completed

        # Colours for each node
        colours = {n: WHITE for n in all_nodes}
        # Order of nodes. We calculate a post order then reverse it.
        # Nodes will be appended as they are marked black
        order = []

        # The actual DFS
        def dfs(n):
            colours[n] = GRAY
            for rec in n.referencedRecords:
                if colours[rec] == WHITE:
                    dfs(rec)
            colours[n] = BLACK
            order.append(n)

        # Do it from the root node first
        dfs(root_record)
        # Then keep doing it while there are white nodes
        for n in colours:
            if colours[n] == WHITE:
                dfs(n)

        # Now reverse
        # order.reverse()
        return order


    def get_undef_record_decls(stmt):
        # Record decls
        stmts = get_all_stmts(stmt)
        undef_recs = []
        for src_stmt in stmts:
            if hasattr(src_stmt, 'ref_relations'):
                for ref_stmt in src_stmt.ref_relations:
                    if ref_stmt not in stmts:
                        if ref_stmt.recordType:
                            recs = get_referenced_records_rpo(ref_stmt.recordType)
                            for rec in recs:
                                if rec not in undef_recs:
                                    undef_recs.append(rec)

        return undef_recs


    def declare_functions_used_in_records(undef_recs):
        undef_typedefed_fns = []
        for rec in undef_recs:
            for td in rec.referencedTypedefs:
                if td.type == 'Paren':
                    undef_typedefed_fns.append(td.name)
        return undef_typedefed_fns

    def declare_types_used_in_vars(stmt):
        used_typedefs = {}

        # Typedefs used by vars in the body
        stmts = get_undef_vars(stmt)
        for stmt in stmts:
            if hasattr(stmt, 'referencedTypedef') and stmt.referencedTypedef:
                if stmt.referencedTypedef.name not in used_typedefs:
                    used_typedefs[stmt.referencedTypedef.name] = []
                used_typedefs[stmt.referencedTypedef.name].append(tokens_to_str(stmt.referencedTypedef.tokens) + ';')

        return used_typedefs


    def declare_enums_used_in_records(undef_recs):
        enum_decls = []
        for rec in undef_recs:
            for en in rec.referencedEnums:
                enum_decls.append(tokens_to_str(en.tokens) + ';')
        return enum_decls


    def declare_types_used_in_records(undef_recs):
        used_typedefs = {}

        # Referenced builtin typedefs
        for rec in undef_recs:
            for td in rec.referencedTypedefs:
                if td.type == 'Builtin':
                    if td.name not in used_typedefs:
                        used_typedefs[td.name] = []
                    used_typedefs[td.name].append(tokens_to_str(td.tokens) + ';')

        # Forward decls
        for rec in undef_recs:
            if '(anonymous)' in rec.name:
                continue

            if rec.name not in used_typedefs:
                used_typedefs[rec.name] = []
            used_typedefs[rec.name].append('typedef struct %s %s;' % (rec.name, rec.name))


        # Actual decls
        for rec in undef_recs:
            if '(anonymous)' in rec.name:
                continue

            if rec.name not in used_typedefs:
                used_typedefs[rec.name] = []
            used_typedefs[rec.name].append('typedef ' + tokens_to_str(rec.tokens) + ' ' + rec.name + ';')

        return used_typedefs


    def get_undef_vars(stmt):
        stmts = get_all_stmts(stmt)
        undef_vars = []

        for src_stmt in stmts:
            if hasattr(src_stmt, 'ref_relations'):
                for ref_stmt in src_stmt.ref_relations:
                    if ref_stmt not in stmts:
                        undef_vars.append(ref_stmt)

        return list(set(undef_vars))

    def define_undef_vars(stmt, enum_decls):
        stmts = get_undef_vars(stmt)
        undef_vars = []

        for ref_stmt in stmts:
            if ref_stmt.kind == 'Function':
                args_start_idx = ref_stmt.type.index('(')
                undef_var_str = '%s %s %s' % (ref_stmt.type[0:args_start_idx], ref_stmt.name, ref_stmt.type[args_start_idx:])

            else:
                if '(*)' in ref_stmt.type:
                    undef_var_str = ref_stmt.type.replace('(*)', '(*' + ref_stmt.name + ')')
                elif '[' in ref_stmt.type:
                    undef_var_str = ref_stmt.type.replace('[', ' ' + ref_stmt.name + '[', 1)
                else:
                    undef_var_str = '%s %s' % (ref_stmt.type, ref_stmt.name)

                if ref_stmt.name in ''.join(enum_decls) and ref_stmt.name.isupper():
                    continue

            undef_vars.append(undef_var_str)

        return list(set(undef_vars))

    def indent(c_unindented):
        result = subprocess.run(['indent'], input=c_unindented, capture_output=True, text=True)
        return result.stdout

    def compile_check(src):
        p1 = subprocess.Popen(['clang', '-x', 'c', '-c', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p1_out = p1.communicate(input=src.encode())[0]
        return p1.returncode

    loop_infos = []
    for loop, depth in loops.items():
        # Headers
        includes = '#include <stdint.h>\n'
        includes += '#include <stdio.h>\n'

        # Define undefined types
        undef_recs = get_undef_record_decls(loop)

        types_in_record = declare_types_used_in_records(undef_recs)
        types_in_vars = declare_types_used_in_vars(loop)

        # For all recorded typedefs, get the ones with the largest sizes (is the definition)
        types = []
        for name, defs in {**types_in_record, **types_in_vars}.items():
            types.append(max(list(set(defs)), key=len))

        # Define undefined variables
        enums = declare_enums_used_in_records(undef_recs)
        vars = define_undef_vars(loop, enums)

        # fns = declare_functions_used_in_records(undef_recs)
        # for ut in fns:
        #     vars = vars.replace(ut, 'int')
        #     types_in_record = types_in_record.replace(ut, 'int')

        # Function
        body_token_list = get_tokens(loop)
        body = tokens_to_str(body_token_list)
        function = 'int fn(' + ', '.join(vars) + ') { ' + body + ' }'

        src = indent(includes + '\n\n'
                     + '\n'.join(types) + '\n\n'
                     + function)

#        print(meta['filename'])
#         print(src)
        loop_infos.append({
            'meta': {
                'max_loop_depth': depth,
                'num_tokens': len(body_token_list),
                'stmt_counts': get_statement_counts(loop),
                'filename': meta['filename'],
                'dataset_name': meta['dataset_name'],
                'clang_returncode': compile_check(src)
            },
            'src': src,
            'body': indent(body)
        })

    return loop_infos


class ASTGraphBuilder(RepresentationBuilder):
    def __init__(self, clang_driver=None):
        RepresentationBuilder.__init__(self)

        self.clang_driver = clang_driver
        self.__extractor = ClangExtractor(self.clang_driver)

        self.loop_infos = []

    def string_to_info(self, src, additional_include_dir=None, filename=None):
        with clang_driver_scoped_options(self.clang_driver, additional_include_dir=additional_include_dir, filename=filename):
            extractor = ClangExtractor(self.clang_driver)
            return extractor.GraphFromString(src)

    def info_to_representation(self, functionInfo, visitor, meta):
        vis = visitor()
        functionInfo.accept(vis)

#        for fi in info.functionInfos:
#            print(' '.join([t.name for t in fi.tokens]))

        # Extract loops
        loops = match_loops(functionInfo.entryStmt)
        self.loop_infos += loops_to_infos(loops, meta)


datasets = [
  LivermorecDataset(),
  GeneralDataset('https://github.com/libav/libav.git', 'libav'),
  GeneralDataset('https://github.com/mirror/x264.git', 'x264'),
  GeneralDataset('https://github.com/ImageMagick/ImageMagick.git', 'ImageMagick'),
  GeneralDataset('https://github.com/WinMerge/freeimage.git', 'freeimage'),
  GeneralDataset('https://github.com/DentonW/DevIL.git', 'DevIL', 'DevIL'),
  GeneralDataset('https://github.com/FFmpeg/FFmpeg.git', 'ffmpeg'),
  # GeneralDataset('https://github.com/opencv/opencv.git', 'opencv'),
]

loop_infos_flat = []

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

    loop_infos_flat += [flatten_dict(x) for x in builder.loop_infos]


    # Store in SQL DB
    all_keys = set(itertools.chain.from_iterable([x.keys() for x in loop_infos_flat]))
    int_keys = {x for x in all_keys if x.startswith('meta')}

    filename = 'loops.db'
    is_new_table = not os.path.isfile(filename)

    conn = sqlite3.connect(filename)
    c = conn.cursor()


    if is_new_table:
        int_cols = ', '.join([x + ' INT' for x in int_keys])
        cmd = 'CREATE TABLE IF NOT EXISTS loops(src TEXT, body TEXT, ' + int_cols + ')'
        print(cmd)
        c.execute(cmd)
    else:
        existing_cols = [col[1] for col in c.execute('pragma table_info(loops)').fetchall()]
        new_cols = list(set(int_keys) - set(existing_cols))
        for int_col in [x + ' INT' for x in new_cols]:
            cmd = 'ALTER TABLE loops ADD COLUMN ' + int_col + ';'
            print(cmd)
            c.execute(cmd)

    for loop_info in loop_infos_flat:
        columns = ', '.join(loop_info.keys())
        placeholders = ', '.join('?' * len(loop_info))
        sql = 'INSERT INTO loops ({}) VALUES ({})'.format(columns, placeholders)
        c.execute(sql, list(loop_info.values()))

    conn.commit()

print('done')