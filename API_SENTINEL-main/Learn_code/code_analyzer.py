import os
import ast
from github_api import Count_Total_Files, download_files

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

    def visit_If(self, node):
        self.ifs += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.loops += 1
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
            "lines": node.end_lineno - node.lineno + 1
        }

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        visitor = FunctionBodyVisitor()
        for statement in node.body:
            visitor.visit(statement)

        self.functions[node.name] = {
            "ifs": visitor.ifs,
            "loops": visitor.loops,
            "lines": node.end_lineno - node.lineno + 1
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

def AnalyzeFiles(github_url_content):
        file_lines_sizes = {}
        functions_dict, function_num_dict = {}, {}
        classes_dict, classes_num_dict = {}, {}
        imports_dict, imports_num_dict = {}, {}
        function_complexity_dict = {}
        unused_imports = []
        skipped_files = []

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

        return file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict, unused_imports, skipped_files