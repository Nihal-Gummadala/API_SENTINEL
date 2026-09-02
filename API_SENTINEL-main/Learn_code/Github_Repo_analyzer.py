from github_api import Count_Total_Files, Count_File_Types, get_largest_files, download_files
from code_analyzer import AnalyzeFiles
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary
from report import report_info, print_report, Get_Json_report, Get_HTML_Report


def main():
    url = input("Please enter Github url: ")
    url_split = url.rstrip("/").split("/")
    username = url_split[-2]
    repository = url_split[-1]

    repo_url = f"https://api.github.com/repos/{username}/{repository}"
    content_url = f"https://api.github.com/repos/{username}/{repository}/contents/"

    report = report_info(repo_url, content_url, repository)
    print_report(report)

    Get_HTML_Report(report)
    Get_Json_report(report)

if __name__ == "__main__":
    main()