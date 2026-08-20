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
num_files = len(contents)

print(num_files)