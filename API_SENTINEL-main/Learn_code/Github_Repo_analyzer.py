"""User enters GitHub URL
        ↓
Parse the URL
        ↓
Find username + repository
        ↓
Call GitHub API
        ↓
GitHub sends JSON
        ↓
Python converts JSON → Python data
        ↓
Analyze the data
        ↓
Print results"""
import requests
import json
import os

token = os.environ.get("GITHUB_TOKEN")

headers = {"Authorization": f"Bearer {token}"}

url = input("Please enter Github url:")
url_split = url.split("/")
username = url_split[-2]
repository = url_split[-1]
print(username + "  " + repository)

response = requests.get(f"https://api.github.com/repos/{username}/{repository}", headers=headers)
print(response.status_code)
print(response.text)
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
        files = ()
        if len(requests.get(github_url_content, HEADERS).json()) == 0:
                return 0, ()

        for file in requests.get(github_url_content, headers=HEADERS).json():
                if isDir(file):
                        file_url_content = f"{github_url_content}{file['name']}/"
                        new_count, new_files = Count_Total_Files(file_url_content, HEADERS=headers)
                        count += new_count
                        files = files + new_files
                else:
                        count += 1
                        files = files + (file['name'],)

        return count, files

def Count_File_Types(github_url_content, HEADERS=headers):
        file_count, file_names = Count_Total_Files(github_url_content)
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


print(Count_Total_Files(content_url))
print(Count_File_Types(content_url))
