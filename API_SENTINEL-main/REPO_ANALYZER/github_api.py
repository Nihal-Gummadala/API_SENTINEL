import requests
import os


token = os.environ.get("GITHUB_TOKEN")

headers = {"Authorization": f"Bearer {token}"} if token else {}


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


def isDir(dict_to_check):
        if dict_to_check['type'] == 'dir':
                return True
        return False

def Count_Total_Files(github_url_content, count=0, HEADERS=headers):
        file_sizes={}
        files = ()

        contents = requests.get(github_url_content, headers=HEADERS).json()
        if isinstance(contents, dict):
                message = contents.get('message', 'unexpected response from GitHub')
                raise RuntimeError(f"GitHub error for {github_url_content}: {message}")

        if len(contents) == 0:
                return 0, (), {}

        for file in contents:
                if isDir(file):
                        file_url_content = f"{github_url_content}{file['name']}/"
                        new_count, new_files, new_size = Count_Total_Files(file_url_content, HEADERS=HEADERS)
                        count += new_count
                        files = files + new_files
                        file_sizes = file_sizes | new_size
                else:
                        count += 1
                        files = files + (file['path'],)
                        file_sizes[file['path']] = file['size']

        return count, files, file_sizes

def Count_File_Types(github_url_content, HEADERS=headers):
        _, file_names, _ = Count_Total_Files(github_url_content, HEADERS=HEADERS)

        language_count = {'other': 0}
        for key, name in langauge_dict.items():
                language_count[name] = 0

        for file_name in file_names:
                root, ext = os.path.splitext(file_name)
                ext = ext.lower()
                if ext in langauge_dict:
                        language_count[langauge_dict[ext]] += 1
                else:
                        language_count['other'] += 1

        return language_count

def get_largest_files(github_url_content, HEADERS=headers):
        _, _, file_sizes = Count_Total_Files(github_url_content, HEADERS=HEADERS)
        file_sizes_sorted = dict(sorted(file_sizes.items(), key=lambda item: item[1]))
        largest_files = list(file_sizes_sorted.items())[-3:]

        return largest_files

def download_files(github_url_content, HEADERS=headers):
        downloaded_files = {}
        parts = github_url_content.split("/repos/")[1].split("/")
        username, repository = parts[0], parts[1]

        _, files, _ = Count_Total_Files(github_url_content, HEADERS=HEADERS)
        for file in files:
                meta = requests.get(f"https://api.github.com/repos/{username}/{repository}/contents/{file}", headers=HEADERS).json()
                downloaded_files[file] = requests.get(meta['download_url'], headers=HEADERS).text

        return downloaded_files

def Get_Repo_Languages(repo_url, HEADERS=headers):
        url_languages = f"{repo_url}/languages"
        return list(requests.get(url_languages, headers=HEADERS).json().keys())