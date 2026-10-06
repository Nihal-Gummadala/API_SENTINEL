import os
import ast
from github_api import Count_Total_Files, download_files
import tokenize
from io import StringIO
from urllib.parse import urlparse

KNOWN_APIS = {
    "api.github.com": "GitHub",
    "api.openai.com": "OpenAI"
}

def ShouldAnalyzeFile(file_name):
        root, ext = os.path.splitext(file_name)
        if ext.lower() == ".py":
                return True

        return False

def Count_Lines(file_contents):
        lines = file_contents.splitlines()
        return len(lines)

class FunctionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = []

    def visit_FunctionDef(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)

class ClassVisitor(ast.NodeVisitor):
        def __init__(self):
                self.classes = []

        def visit_ClassDef(self, node):
                self.classes.append(node.name)
                self.generic_visit(node)

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = []

    def visit_Import(self, node):
        for name in node.names:
            if name.asname:
                self.imports.append(name.asname)
            else:
                self.imports.append(name.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == "__future__":
            self.generic_visit(node)
            return

        for name in node.names:
            if name.name == "*":
                continue
            if name.asname:
                self.imports.append(name.asname)
            else:
                self.imports.append(name.name)
        self.generic_visit(node)

class FunctionBodyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.ifs = 0
        self.loops = 0
        self.current_depth = 0
        self.max_depth = 0
        self.cyclomatic = 1

    def visit_If(self, node):
        self.ifs += 1
        self.cyclomatic += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.loops += 1
        self.current_depth += 1
        self.max_depth = max(self.max_depth, self.current_depth)
        self.cyclomatic += 1
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_While(self, node):
        self.loops += 1
        self.current_depth += 1
        self.max_depth = max(self.max_depth, self.current_depth)
        self.cyclomatic += 1
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_BoolOp(self, node):
        if isinstance(node.op, (ast.And, ast.Or)):
            self.cyclomatic += len(node.values) - 1
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):

        return

    def visit_AsyncFunctionDef(self, node):

        return

class FunctionComplexityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}

    def visit_FunctionDef(self, node):
        visitor = FunctionBodyVisitor()
        for statement in node.body:
            visitor.visit(statement)

        self.functions[node.name] = {
            "ifs": visitor.ifs,
            "loops": visitor.loops,
            "lines": node.end_lineno - node.lineno + 1,
            "max_nesting": visitor.max_depth,
            "cyclomatic_complexity": visitor.cyclomatic
        }

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        visitor = FunctionBodyVisitor()
        for statement in node.body:
            visitor.visit(statement)

        self.functions[node.name] = {
            "ifs": visitor.ifs,
            "loops": visitor.loops,
            "lines": node.end_lineno - node.lineno + 1,
            "max_nesting": visitor.max_depth,
            "cyclomatic_complexity": visitor.cyclomatic
        }

        self.generic_visit(node)

class UnusedImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.used_names = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            word = node.value.strip().split("[")[0].split(".")[0]
            if word.isidentifier():
                self.used_names.add(word)
        self.generic_visit(node)

class APICallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.api_calls = []
        self.http_libraries = {"requests": "requests", "httpx": "httpx"}

    def visit_Import(self, node):
        for name in node.names:
            if name.name in ("requests", "httpx") and name.asname:
                self.http_libraries[name.asname] = name.name
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):

            library = node.func.value
            method = node.func.attr

            if isinstance(library, ast.Name) and library.id in self.http_libraries:
                library_name = self.http_libraries[library.id]

                if method in ("get", "post", "put", "delete", "patch"):

                    url = None

                    if node.args:
                        first_argument = node.args[0]

                        if isinstance(first_argument, ast.Constant):
                            if isinstance(first_argument.value, str):
                                url = first_argument.value

                        elif isinstance(first_argument, ast.JoinedStr):
                            url = ""
                            for part in first_argument.values:
                                if isinstance(part, ast.Constant):
                                    url += part.value
                                else:
                                    url += "{" + ast.unparse(part.value) + "}"

                    self.api_calls.append({"library": library_name,"method": method.upper(),"url": url,"line": node.lineno})

        self.generic_visit(node)

def Count_Imports(file_name, file_contents):
    ast_tree = ast.parse(source=file_contents, filename=file_name)

    import_counter = ImportVisitor()
    import_counter.visit(ast_tree)

    return len(import_counter.imports), import_counter.imports

def Count_Functions(file_name, file_contents):
        ast_tree = ast.parse(source = file_contents, filename = file_name)
        function_counter = FunctionVisitor()
        function_counter.visit(ast_tree)

        return len(function_counter.functions), function_counter.functions

def Count_Classes(file_name, file_contents):
        ast_tree = ast.parse(source = file_contents, filename = file_name)
        class_counter = ClassVisitor()
        class_counter.visit(ast_tree)

        return len(class_counter.classes), class_counter.classes

def Count_Function_Complexity(file_name, file_contents):
    ast_tree = ast.parse(
        source=file_contents,
        filename=file_name
    )

    visitor = FunctionComplexityVisitor()
    visitor.visit(ast_tree)

    return visitor.functions

def Get_Unused_Imports(file_name, file_contents):
    unused_imports = set()

    ast_tree = ast.parse(source=file_contents, filename=file_name)
    unused_import_visitor = UnusedImportVisitor()
    unused_import_visitor.visit(ast_tree)

    used_names = unused_import_visitor.used_names
    _, imports = Count_Imports(file_name, file_contents)
    for import_in_code in imports:
        if import_in_code not in used_names:
            unused_imports.add(import_in_code)

    return unused_imports

def find_TODO_and_FIXME(file_contents):
    TODO_loc = []
    FIXME_loc = []

    tokens = tokenize.generate_tokens(StringIO(file_contents).readline)

    for token in tokens:
        if token.type == tokenize.COMMENT:
            comment = token.string.upper()
            line_number = token.start[0]

            if "TODO" in comment:
                TODO_loc.append(line_number)

            if "FIXME" in comment:
                FIXME_loc.append(line_number)

    return TODO_loc, FIXME_loc

def Detect_API_Calls(file_name, source_code):
    tree = ast.parse(source=source_code, filename=file_name)

    api_visitor = APICallVisitor()
    api_visitor.visit(tree)

    return api_visitor.api_calls

def Identify_API(api_calls):
    identified_calls = []

    for api_call in api_calls:
        api_name = "Unknown API"
        url = api_call["url"]

        if url:
            host = urlparse(url).hostname
            if host in KNOWN_APIS:
                api_name = KNOWN_APIS[host]

        identified_calls.append({**api_call, "api": api_name})

    return identified_calls

def AnalyzeFiles(github_url_content):
        file_lines_sizes = {}
        functions_dict, function_num_dict = {}, {}
        classes_dict, classes_num_dict = {}, {}
        imports_dict, imports_num_dict = {}, {}
        function_complexity_dict = {}
        unused_imports = []
        skipped_files = []
        TODO_locs = {}
        FIXME_locs = {}
        api_calls_dict = {}

        _, file_names, _ = Count_Total_Files(github_url_content)
        downloaded_files = download_files(github_url_content)
        for file_name in file_names:
                if ShouldAnalyzeFile(file_name):
                        downloaded_file = downloaded_files[file_name]

                        try:
                                ast.parse(source=downloaded_file, filename=file_name)
                        except SyntaxError:
                                skipped_files.append(file_name)
                                continue

                        num_lines = Count_Lines(downloaded_file)
                        file_lines_sizes[file_name] = num_lines

                        function_num, functions = Count_Functions(file_name, downloaded_file)
                        functions_dict[file_name] = functions
                        function_num_dict[file_name] = function_num

                        classes_num, classes = Count_Classes(file_name, downloaded_file)
                        classes_dict[file_name] = classes
                        classes_num_dict[file_name] = classes_num

                        imports_num, imports = Count_Imports(file_name, downloaded_file)
                        imports_dict[file_name] = imports
                        imports_num_dict[file_name] = imports_num

                        function_complexity = Count_Function_Complexity(file_name, downloaded_file)
                        function_complexity_dict[file_name] = function_complexity

                        for import_name in sorted(Get_Unused_Imports(file_name, downloaded_file)):
                                unused_imports.append(f"{file_name}: {import_name}")

                        TODO, FIXME = find_TODO_and_FIXME(downloaded_file)
                        TODO_locs[file_name] = TODO
                        FIXME_locs[file_name] = FIXME
                        
                        api_calls = Detect_API_Calls(file_name, downloaded_file)
                        api_calls_dict[file_name] = Identify_API(api_calls)


        return file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict, unused_imports, skipped_files, TODO_locs, FIXME_locs, api_calls_dict