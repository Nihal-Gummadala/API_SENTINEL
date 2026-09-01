import requests
import json
import os
import ast
from github_api import Count_Total_Files, download_files

def ShouldAnalyzeFile(file_name):
        langauge_dict = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".dart": "Dart",
    ".scala": "Scala",
    ".r": "R",
    ".lua": "Lua",
    ".pl": "Perl",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Fish",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".sql": "SQL",
    ".json": "JSON",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".txt": "Text",
    ".vue": "Vue",
    ".svelte": "Svelte",
        }

        root, ext = os.path.splitext(file_name)
        if ext==".py":
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
            self.imports.append(name.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for name in node.names:
            self.imports.append(f"{node.module}.{name.name}")
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

def AnalyzeFiles(github_url_content):
        file_lines_sizes = {}
        functions_dict, function_num_dict = {}, {}
        classes_dict, classes_num_dict = {}, {}
        imports_dict, imports_num_dict = {}, {}
        if_count, loops_count = 0, 0
        function_complexity_dict = {}

        _, file_names, _ = Count_Total_Files(github_url_content)
        downloaded_files = (download_files(github_url_content))
        for file_name in file_names:
                if ShouldAnalyzeFile(file_name):
                        downloaded_file = downloaded_files[file_name]

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

        return file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict