#github_api.py

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


_listing_cache = {}


def isDir(dict_to_check):
        if dict_to_check['type'] == 'dir':
                return True
        return False

def List_Repo_Files(github_url_content, HEADERS=headers):
        """Walk the repo once and return [{'path', 'size', 'download_url'}, ...]."""
        if github_url_content in _listing_cache:
                return _listing_cache[github_url_content]

        response = requests.get(github_url_content, headers=HEADERS)
        contents = response.json()
        if isinstance(contents, dict):
                message = contents.get('message', 'unexpected response from GitHub')
                raise RuntimeError(f"GitHub error for {github_url_content}: {message}")

        entries = []
        for file in contents:
                if isDir(file):
                        file_url_content = f"{github_url_content}{file['name']}/"
                        entries.extend(List_Repo_Files(file_url_content, HEADERS=HEADERS))
                else:
                        entries.append({'path': file['path'], 'size': file['size'], 'download_url': file.get('download_url')})

        _listing_cache[github_url_content] = entries
        return entries

def Count_Total_Files(github_url_content, count=0, HEADERS=headers):
        entries = List_Repo_Files(github_url_content, HEADERS=HEADERS)

        files = tuple(entry['path'] for entry in entries)
        file_sizes = {entry['path']: entry['size'] for entry in entries}

        return count + len(files), files, file_sizes

def Count_File_Types(github_url_content, HEADERS=headers):
        _, file_names, _ = Count_Total_Files(github_url_content, HEADERS=HEADERS)
        return Count_Languages(file_names)

def Count_Languages(file_names):
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

def Largest_From_Sizes(file_sizes):
        file_sizes_sorted = dict(sorted(file_sizes.items(), key=lambda item: item[1]))
        return list(file_sizes_sorted.items())[-3:]

def get_largest_files(github_url_content, HEADERS=headers):
        _, _, file_sizes = Count_Total_Files(github_url_content, HEADERS=HEADERS)
        return Largest_From_Sizes(file_sizes)

def download_files(github_url_content, HEADERS=headers, only=None):
        """Download file contents. The directory listing already includes each
        file's download_url, so no extra metadata request per file is needed.
        `only` is an optional function(path) -> bool to skip files we won't analyze."""
        downloaded_files = {}

        for entry in List_Repo_Files(github_url_content, HEADERS=HEADERS):
                if only is not None and not only(entry['path']):
                        continue
                if not entry['download_url']:
                        continue
                response = requests.get(entry['download_url'], headers=HEADERS)
                if response.status_code != 200:
                        raise RuntimeError(f"Could not download {entry['path']} (HTTP {response.status_code})")
                downloaded_files[entry['path']] = response.text

        return downloaded_files

def Get_Repo_Languages(repo_url, HEADERS=headers):
        url_languages = f"{repo_url}/languages"
        return list(requests.get(url_languages, headers=HEADERS).json().keys())
