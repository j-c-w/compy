import itertools
import networkx as nx
import subprocess

from compy.representations import RepresentationBuilder
from compy.representations.extractors import clang_driver_scoped_options
from compy.representations.extractors.extractors import Visitor
from compy.representations.extractors.extractors import ClangDriver
from compy.representations.extractors.extractors import ClangExtractor
from compy.representations.extractors.extractors import clang
from compy.representations import common


def filter_type(type):
    if "[" in type or "]" in type:
        return "arrayType"
    elif "(" in type or ")" in type:
        return "fnType"
    elif "int" in type:
        return "intType"
    elif "float" in type:
        return "floatType"
    else:
        return "type"


def add_ast_edges(g: nx.MultiDiGraph, node):
    """Add edges with attr `ast` that represent the AST parent-child relationship"""

    if isinstance(node, clang.graph.FunctionInfo):
        g.add_node(node, attr="function")
        for arg in node.args:
            g.add_node(arg, attr=("argument", filter_type(arg.type)))
            g.add_edge(node, arg, attr="ast")

        g.add_node(node.entryStmt, attr=(node.entryStmt.name))
        g.add_edge(node, node.entryStmt, attr="ast")

    if isinstance(node, clang.graph.StmtInfo):
        for ast_rel in node.ast_relations:
            g.add_node(ast_rel, attr=(ast_rel.name))
            g.add_edge(node, ast_rel, attr="ast")


def add_ref_edges(g: nx.MultiDiGraph, node):
    """Add edges with attr `data` for data references of the given node"""

    if isinstance(node, clang.graph.StmtInfo):
        for ref_rel in node.ref_relations:
            g.add_node(ref_rel, attr=(filter_type(ref_rel.type)))
            g.add_edge(node, ref_rel, attr="data")


def add_cfg_edges(g: nx.MultiDiGraph, node):
    """Add edges with attr `cfg` or `in` for control flow for the given node"""

    if isinstance(node, clang.graph.FunctionInfo):
        for cfg_b in node.cfgBlocks:
            g.add_node(cfg_b, attr="cfg")
            for succ in cfg_b.successors:
                g.add_edge(cfg_b, succ, attr="cfg")
                g.add_node(succ, attr="cfg")
            for stmt in cfg_b.statements:
                g.add_edge(stmt, cfg_b, attr="in")
                g.add_node(stmt, attr=(stmt.name))


def add_token_ast_edges(g: nx.MultiDiGraph, node):
    """Add edges with attr `token` connecting tokens to the closest AST node covering them"""
    if hasattr(node, 'tokens'):
        for token in node.tokens:
            g.add_node(token, attr=token.name, seq_order=token.index)
            g.add_edge(node, token, attr="token")


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


def tokens_to_str(token_infos):
    return ' '.join([t.name for t in sorted(token_infos, key=lambda x: x.index) if 'pragma' not in t.kind])


def get_statement_counts(root_stmt):
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
    stmt_count_fn(root_stmt, stmt_counts)

    return stmt_counts


def max_depth(stmt, stmt_name):
    count = 1 if stmt.name in stmt_name else 0

    for sub_stmt in stmt.ast_relations:
        if isinstance(sub_stmt, clang.graph.StmtInfo):
            count += max_depth(sub_stmt, stmt_name)

    return count


class ASTVisitor(Visitor):
    def __init__(self):
        Visitor.__init__(self)
        self.edge_types = ["ast"]
        self.G = nx.MultiDiGraph()

    def visit(self, v):
        add_ast_edges(self.G, v)


class ASTDataVisitor(Visitor):
    def __init__(self):
        Visitor.__init__(self)
        self.edge_types = ["ast", "data"]
        self.G = nx.MultiDiGraph()

    def visit(self, v):
        add_ast_edges(self.G, v)
        add_ref_edges(self.G, v)


class ASTDataCFGVisitor(Visitor):
    def __init__(self):
        Visitor.__init__(self)
        self.edge_types = ["ast", "cfg", "in", "data"]
        self.G = nx.MultiDiGraph()

    def visit(self, v):
        add_ast_edges(self.G, v)
        add_ref_edges(self.G, v)
        add_cfg_edges(self.G, v)


class ASTDataCFGTokenVisitor(Visitor):
    def __init__(self):
        Visitor.__init__(self)
        self.edge_types = ["ast", "cfg", "in", "data", "token"]
        self.G = nx.MultiDiGraph()

    def visit(self, v):
        add_ast_edges(self.G, v)
        add_ref_edges(self.G, v)
        add_cfg_edges(self.G, v)
        add_token_ast_edges(self.G, v)


class ASTGraphBuilder(common.RepresentationBuilder):
    def __init__(self, clang_driver=None):
        common.RepresentationBuilder.__init__(self)

        if clang_driver:
            self.__clang_driver = clang_driver
        else:
            self.__clang_driver = ClangDriver(
                ClangDriver.ProgrammingLanguage.C,
                ClangDriver.OptimizationLevel.O3,
                [],
                ["-Wall"],
            )
        self.__extractor = ClangExtractor(self.__clang_driver)

        self.__graphs = []

    def string_to_info(self, src, additional_include_dir=None, filename=None):
        with clang_driver_scoped_options(self.__clang_driver, additional_include_dir=additional_include_dir, filename=filename):
            return self.__extractor.GraphFromString(src)

    def info_to_representation(self, info, visitor=ASTDataVisitor):
        vis = visitor()
        info.accept(vis)

        for (n, data) in vis.G.nodes(data=True):
            attr = data["attr"]
            if attr not in self._tokens:
                self._tokens[attr] = 1
            self._tokens[attr] += 1

        return common.Graph(vis.G, self.get_tokens(), vis.edge_types)


class ASTCodeVisitor(Visitor):
    def __init__(self):
        Visitor.__init__(self)
        self.function_infos = []

    def visit(self, v):
        self.function_infos.append(v)


class ASTCodeBuilder(RepresentationBuilder):
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

        # Extract loops
        loops = self.match_loops(functionInfo.entryStmt)
        self.loop_infos += self.loops_to_infos(loops, meta)

        return self.loop_infos

    def match_loops(self, root_stmt, depth_min=1):
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

        # Filter by loop depth
        filtered_loop_seqs = [l for l in all_loop_seqs if len(l) >= depth_min]

        # Filter by subscript expression. Look at the innermost nest
        def has_array_subscript(stmt):
            has = False
            if stmt.name == "ArraySubscriptExpr":
                has = True
            if hasattr(stmt, 'ast_relations'):
                for rel in stmt.ast_relations:
                    has = has | has_array_subscript(rel)
            return has
        filtered_loop_seqs = [l for l in filtered_loop_seqs if has_array_subscript(l[-1])]

        # # Filter so that we have only the most innermost for statements
        # mins_by_inner_fors = {}
        # for loop_seq in filtered_loop_seqs:
        #     inner_for = loop_seq[0]
        #
        #     if inner_for not in mins_by_inner_fors:
        #         mins_by_inner_fors[inner_for] = len(loop_seq)
        #
        #     if len(loop_seq) < mins_by_inner_fors[inner_for]:
        #         mins_by_inner_fors[inner_for] = len(loop_seq)
        # inner_fors = mins_by_inner_fors.keys()

        # List of loop nests -> Innermost/outermost loop
        size_by_loop = {}
        for loop_seq in filtered_loop_seqs:
            # Innermost loop
            s = loop_seq[-1]

            if s not in size_by_loop:
                size_by_loop[s] = len(loop_seq)
            size_by_loop[s] = max(len(loop_seq), size_by_loop[s])

        depth_by_loop = {}
        for loop_seq in filtered_loop_seqs:
            candidate = loop_seq[-1]
            depth = max_depth(candidate, 'ForStmt')
            if depth == 1:
                depth_by_loop[candidate] = depth

        return depth_by_loop

    def loops_to_infos(self, loops, meta):
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

            loop_info = {
                'meta': {
                    'max_loop_depth': depth,
                    'num_tokens': len(body_token_list),
                    'stmt_counts': get_statement_counts(loop),
                    'clang_returncode': compile_check(src)
                },
                'src': src,
                'body': indent(body)
            }
            loop_info.update(meta)
            loop_infos.append(loop_info)

        return loop_infos