import os
import ast
from github_api import download_files
from doc_fetcher import Load_Registry
import tokenize
from io import StringIO
from urllib.parse import urlparse

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

HTTP_LIBRARIES = ("requests", "httpx")
HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")
SESSION_FACTORIES = ("Session", "Client", "AsyncClient") 
BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")

_PARAMETER = object()


class APICallVisitor(ast.NodeVisitor):
    """Finds HTTP calls made with requests/httpx and records what the call sends:
    the method, the URL (traced through simple variable assignments), and the
    query params / JSON body fields / headers when they can be read statically."""

    def __init__(self):
        self.api_calls = []
        self.http_libraries = {name: name for name in HTTP_LIBRARIES} 
        self.function_aliases = {}  
        self.session_factories = {}  
        self.sessions = {}           
        self.scopes = [{}]           


    def visit_Import(self, node):
        for name in node.names:
            if name.name in HTTP_LIBRARIES:
                self.http_libraries[name.asname or name.name] = name.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in HTTP_LIBRARIES:
            for name in node.names:
                local_name = name.asname or name.name
                if name.name in HTTP_METHODS or name.name == "request":
                    self.function_aliases[local_name] = (node.module, name.name)
                elif name.name in SESSION_FACTORIES:
                    self.session_factories[local_name] = node.module
        self.generic_visit(node)


    def visit_Module(self, node):
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        self.scopes[0][target.id] = statement.value
        self.generic_visit(node)

    def _visit_function(self, node):
        scope = {}
        arguments = node.args
        positional = arguments.posonlyargs + arguments.args
        defaults = [None] * (len(positional) - len(arguments.defaults)) + list(arguments.defaults)
        for argument, default in zip(positional, defaults):
            scope[argument.arg] = default if default is not None else _PARAMETER
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
            scope[argument.arg] = default if default is not None else _PARAMETER

        self.scopes.append(scope)
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def visit_FunctionDef(self, node):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)

    def visit_Assign(self, node):
        self.generic_visit(node) 
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.scopes[-1][target.id] = node.value
                self._remember_session(target.id, node.value)

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.value is not None:
            self.scopes[-1][node.target.id] = node.value
            self._remember_session(node.target.id, node.value)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and isinstance(node.op, ast.Add):
            previous = self._lookup(node.target.id)
            if previous is not None:
                self.scopes[-1][node.target.id] = ast.BinOp(left=previous, op=ast.Add(), right=node.value)

    def visit_With(self, node):
        for item in node.items:
            if isinstance(item.optional_vars, ast.Name):
                self._remember_session(item.optional_vars.id, item.context_expr)
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.visit_With(node)

    def _remember_session(self, name, value):
        if not isinstance(value, ast.Call):
            return
        library = None
        function = value.func
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            if function.value.id in self.http_libraries and function.attr in SESSION_FACTORIES:
                library = self.http_libraries[function.value.id]
        elif isinstance(function, ast.Name) and function.id in self.session_factories:
            library = self.session_factories[function.id]
        if library is None:
            return

        base_url = None
        for keyword in value.keywords:
            if keyword.arg == "base_url":
                base_url = self._resolve_string(keyword.value)
        self.sessions[name] = {"library": library, "base_url": base_url}

    def _lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                value = scope[name]
                return None if value is _PARAMETER else value
        return None

    def _resolve_string(self, node, depth=0):
        """Best-effort string value of an expression. Parts that can't be known
        become {expression} placeholders. Returns None if nothing is known."""
        if node is None or depth > 10:
            return None

        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None

        if isinstance(node, ast.Name):
            return self._resolve_string(self._lookup(node.id), depth + 1)

        if isinstance(node, ast.JoinedStr):
            text = ""
            for part in node.values:
                if isinstance(part, ast.Constant):
                    text += str(part.value)
                else:
                    inner = self._resolve_string(part.value, depth + 1)
                    text += inner if inner is not None else "{" + ast.unparse(part.value) + "}"
            return text

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._resolve_string(node.left, depth + 1)
            right = self._resolve_string(node.right, depth + 1)
            if left is None and right is None:
                return None
            if left is None:
                left = "{" + ast.unparse(node.left) + "}"
            if right is None:
                right = "{" + ast.unparse(node.right) + "}"
            return left + right

        return None

    def _resolve_dict(self, node, depth=0):
        if node is None or depth > 10:
            return None

        if isinstance(node, ast.Name):
            return self._resolve_dict(self._lookup(node.id), depth + 1)

        if isinstance(node, ast.Dict):
            values, complete = {}, True
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    values[key.value] = self._resolve_string(value, depth + 1)
                else:
                    complete = False 
            return values, complete

        if isinstance(node, ast.IfExp):
            first = self._resolve_dict(node.body, depth + 1)
            second = self._resolve_dict(node.orelse, depth + 1)
            if first is None or second is None:
                return None
            return {**second[0], **first[0]}, first[1] and second[1]

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
            values = {keyword.arg: self._resolve_string(keyword.value, depth + 1) for keyword in node.keywords if keyword.arg}
            return values, all(keyword.arg for keyword in node.keywords)

        return None


    def _match_call(self, node):
        function = node.func
        arguments = list(node.args)
        url_keyword = next((keyword.value for keyword in node.keywords if keyword.arg == "url"), None)
        method_keyword = next((keyword.value for keyword in node.keywords if keyword.arg == "method"), None)

        def unpack(library, name, session):
            if name in HTTP_METHODS:
                url = arguments[0] if arguments else url_keyword
                return library, name.upper(), url, session
            if name == "request":
                method_node = arguments[0] if arguments else method_keyword
                method = self._resolve_string(method_node)
                url = arguments[1] if len(arguments) > 1 else url_keyword
                return library, method.upper() if method else None, url, session
            return None

        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            owner = function.value.id
            if owner in self.http_libraries:
                return unpack(self.http_libraries[owner], function.attr, None)
            if owner in self.sessions:
                session = self.sessions[owner]
                return unpack(session["library"], function.attr, session)

        if isinstance(function, ast.Name) and function.id in self.function_aliases:
            library, name = self.function_aliases[function.id]
            return unpack(library, name, None)

        return None

    def _read_keyword(self, node, name):
        keyword = next((keyword for keyword in node.keywords if keyword.arg == name), None)
        if keyword is None:
            return {}, True
        resolved = self._resolve_dict(keyword.value)
        if resolved is None:
            return None, False
        return resolved

    def visit_Call(self, node):
        match = self._match_call(node)
        if match is not None:
            library, method, url_node, session = match

            url = self._resolve_string(url_node)
            if url is not None and session and session["base_url"] and not urlparse(url).scheme:
                url = session["base_url"].rstrip("/") + "/" + url.lstrip("/")

            params, params_complete = self._read_keyword(node, "params")
            json_body, json_complete = self._read_keyword(node, "json")
            data_body, data_complete = self._read_keyword(node, "data")
            headers, headers_complete = self._read_keyword(node, "headers")

            query_params = None if params is None else list(params)
            if url and "?" in url and query_params is not None:
                query_params += [pair.split("=")[0] for pair in url.split("?", 1)[1].split("&") if pair]

            if json_body is None or data_body is None:
                body_fields = None
            else:
                body_fields = list(json_body) + list(data_body)

            if session is not None:
                headers = None

            incomplete = [name for name, complete in (("params", params_complete), ("json", json_complete),
                          ("data", data_complete), ("headers", headers_complete)) if not complete]

            self.api_calls.append({
                "library": library,
                "method": method,
                "url": url,
                "url_expression": ast.unparse(url_node) if url_node is not None else None,
                "url_status": URL_Status(url),
                "line": node.lineno,
                "query_params": query_params,
                "body_fields": body_fields,
                "headers": headers,
                "incomplete": incomplete,
            })

        self.generic_visit(node)


def URL_Status(url):
    if url is None:
        return "unresolved"
    host = Normalize_URL(url)[0]
    return "resolved" if host else "partial"


def Normalize_URL(url):
    if not url:
        return None, []
    url = url.split("#", 1)[0].split("?", 1)[0]
    if "://" in url:
        url = url.split("://", 1)[1]
    elif not url.startswith("{"):
        return None, [segment for segment in url.split("/") if segment]

    host, _, path = url.partition("/")
    if "{" in host or not host:
        return None, []
    segments = []
    for segment in path.split("/"):
        if not segment:
            continue
        segments.append("{}" if "{" in segment else segment)
    return host.lower(), segments

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

def Identify_API(api_calls, registry=None):
    if registry is None:
        registry = Load_Registry()
    host_to_api = {host: name for name, info in registry.items() for host in info["hosts"]}

    identified_calls = []
    for api_call in api_calls:
        if api_call["url_status"] != "resolved":
            api_name = "Unidentified" 
        else:
            host, _ = Normalize_URL(api_call["url"])
            api_name = host_to_api.get(host, "Unknown API")
        identified_calls.append({**api_call, "api": api_name})

    return identified_calls

def Is_Fixture(file_name):

        return "fixtures" in file_name.replace(os.sep, "/").split("/")[:-1]

def Analyze_Sources(sources):

        analysis = {
                "file_lines_sizes": {},
                "functions_dict": {}, "function_num_dict": {},
                "classes_dict": {}, "classes_num_dict": {},
                "imports_dict": {}, "imports_num_dict": {},
                "function_complexity_dict": {},
                "unused_imports": [],
                "skipped_files": [],
                "TODO_locs": {}, "FIXME_locs": {},
                "api_calls": {},
        }
        registry = Load_Registry()

        for file_name, source in sources.items():
                if not ShouldAnalyzeFile(file_name) or Is_Fixture(file_name):
                        continue

                try:
                        ast.parse(source=source, filename=file_name)
                except SyntaxError:
                        analysis["skipped_files"].append(file_name)
                        continue

                analysis["file_lines_sizes"][file_name] = Count_Lines(source)

                function_num, functions = Count_Functions(file_name, source)
                analysis["functions_dict"][file_name] = functions
                analysis["function_num_dict"][file_name] = function_num

                classes_num, classes = Count_Classes(file_name, source)
                analysis["classes_dict"][file_name] = classes
                analysis["classes_num_dict"][file_name] = classes_num

                imports_num, imports = Count_Imports(file_name, source)
                analysis["imports_dict"][file_name] = imports
                analysis["imports_num_dict"][file_name] = imports_num

                analysis["function_complexity_dict"][file_name] = Count_Function_Complexity(file_name, source)

                for import_name in sorted(Get_Unused_Imports(file_name, source)):
                        analysis["unused_imports"].append(f"{file_name}: {import_name}")

                TODO, FIXME = find_TODO_and_FIXME(source)
                analysis["TODO_locs"][file_name] = TODO
                analysis["FIXME_locs"][file_name] = FIXME

                api_calls = Detect_API_Calls(file_name, source)
                analysis["api_calls"][file_name] = Identify_API(api_calls, registry)

        return analysis

def AnalyzeFiles(github_url_content):
        downloaded_files = download_files(github_url_content, only=ShouldAnalyzeFile)
        return Analyze_Sources(downloaded_files)

SKIP_DIRECTORIES = {".git", "__pycache__", "venv", ".venv", "env", "node_modules", "cache", "fixtures"}

def Read_Local_Folder(folder):
        sources, sizes = {}, {}
        for root, directories, files in os.walk(folder):
                directories[:] = [d for d in directories if d not in SKIP_DIRECTORIES]
                for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, folder).replace(os.sep, "/")
                        sizes[relative_path] = os.path.getsize(full_path)
                        if ShouldAnalyzeFile(file):
                                with open(full_path, encoding="utf-8", errors="replace") as handle:
                                        sources[relative_path] = handle.read()
        return sources, sizes
