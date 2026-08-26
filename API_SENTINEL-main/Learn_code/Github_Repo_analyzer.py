import requests
import json
import os
import ast


token = os.environ.get("GITHUB_TOKEN")

headers = {"Authorization": f"Bearer {token}"}

url = input("Please enter Github url:")
url_split = url.split("/")
username = url_split[-2]
repository = url_split[-1]
print(username + "  " + repository)

response = requests.get(f"https://api.github.com/repos/{username}/{repository}", headers=headers)
print(response.status_code)
data = None
if response.status_code == 200:
    data = response.json()

with open("data.json", "w") as json_file:
    json.dump(data, json_file, indent=4)



language_url = data['languages_url']

languages = list(requests.get(language_url, headers=headers).json().keys())
repo = data['name']
stars = data['stargazers_count']
print(f"{languages}, {repo}, {stars}")

content_url = (f"https://api.github.com/repos/{username}/{repository}/contents/")
contents = requests.get(f"https://api.github.com/repos/{username}/{repository}/contents/", headers=headers).json()

def countfiles(folder_url):
        count = 0
        for file in requests.get(folder_url).json():
                count += 1
        return count


def isDir(dict_to_check):
        if dict_to_check['type'] == 'dir':
                return True
        return False

def Count_Total_Files(github_url_content, count=0, HEADERS=headers):
        file_sizes={}
        files = ()
        if len(requests.get(github_url_content, HEADERS).json()) == 0:
                return 0, (), {}

        for file in requests.get(github_url_content, headers=HEADERS).json():
                if isDir(file):
                        file_url_content = f"{github_url_content}{file['name']}/"
                        new_count, new_files, new_size = Count_Total_Files(file_url_content, HEADERS=headers)
                        count += new_count
                        files = files + new_files
                        file_sizes = file_sizes | new_size
                else:
                        count += 1
                        files = files + (file['path'],)
                        file_sizes[file['path']] = file['size']

        return count, files, file_sizes

def Count_File_Types(github_url_content, HEADERS=headers):
        file_count, file_names, _ = Count_Total_Files(github_url_content)
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

        language_count = {'other': 0}
        for key, name in langauge_dict.items():
                language_count[name] = 0
        
        for file_name in file_names:
                root, ext = os.path.splitext(github_url_content + file_name)
                if ext in langauge_dict:
                        language_count[langauge_dict[ext]] += 1 
                else:
                        language_count['other'] += 1
        
        return language_count

def get_largest_files(github_url_content, HEADERS=headers):
        _, _, file_sizes = Count_Total_Files(github_url_content)
        file_sizes_sorted = dict(sorted(file_sizes.items(), key=lambda item: item[1]))
        largest_files = list(file_sizes_sorted.items())[-3:]

        return largest_files

def download_files(github_url_content, HEADERS=headers, username=username, repository=repository):
        downloaded_files = {}
        _, files, _ = Count_Total_Files(github_url_content)
        for file in files:
                download_url = ((requests.get(f"https://api.github.com/repos/{username}/{repository}/contents/{file}", HEADERS))).json()['download_url']
                download_content_raw = requests.get(download_url, HEADERS).text
                downloaded_files[file] = download_content_raw
        
        return downloaded_files

def ShouldAnalyzeFile(file_name, HEADERS=headers):
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
        if ext in langauge_dict:
                return True
        
        return False

def Count_Lines(file_contents, HEADERS=headers):
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


def AnalyzeFiles(github_url_content, HEADERS=headers):
        file_lines_sizes = {}
        functions_dict, function_num_dict = {}, {}
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

        return file_lines_sizes, functions_dict, function_num_dict


print(AnalyzeFiles(content_url))