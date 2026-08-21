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

url = input("Please enter Github url:")
url_split = url.split("/")
username = url_split[-2]
repository = url_split[-1]
print(username + "  " + repository)

response = requests.get(f"https://api.github.com/repos/{username}/{repository}")
print(response.status_code)
print(response.text)
data = None
if response.status_code == 200:
    data = response.json()

with open("data.json", "w") as json_file:
    json.dump(data, json_file, indent=4)



language_url = data['languages_url']

languages = list(requests.get(language_url).json().keys())
repo = data['name']
stars = data['stargazers_count']
print(f"{languages}, {repo}, {stars}")

contents = requests.get(f"https://api.github.com/repos/{username}/{repository}/contents/").json()

def countfiles(folder_url):
        count = 0
        for file in requests.get(folder_url).json():
                count += 1
        return count


def isDir(dict_to_check):
        if dict_to_check['type'] == 'dir':
                return True
        return False

def Count_Total_Files(github_url_content, count=0):
        if len(requests.get(github_url_content).json()) == 0:
                return 0

        for file in requests.get(github_url_content).json():
                print(file['name'])
                if isDir(file):
                        file_url_content = f"{github_url_content}{file['name']}/"
                        print(file_url_content)
                        Count_Total_Files(file_url_content, count)
                        count += Count_Total_Files(file_url_content)
                else:
                        count += 1

        return count



print(Count_Total_Files(f"https://api.github.com/repos/{username}/{repository}/contents/"))
