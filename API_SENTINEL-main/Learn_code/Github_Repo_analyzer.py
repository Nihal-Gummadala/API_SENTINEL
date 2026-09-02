from report import report_info, print_report, Get_Json_report, Get_HTML_Report


def main():
    url = input("Please enter Github url: ")

    url_split = url.strip().rstrip("/").split("/")
    if len(url_split) < 2:
        print("That does not look like a GitHub url.")
        return

    username = url_split[-2]
    repository = url_split[-1]
    if repository.endswith(".git"):
        repository = repository[:-len(".git")]

    repo_url = f"https://api.github.com/repos/{username}/{repository}"
    content_url = f"https://api.github.com/repos/{username}/{repository}/contents/"

    try:
        report = report_info(repo_url, content_url, repository)
    except RuntimeError as error:
        print(f"Could not analyze the repository: {error}")
        return

    print_report(report)

    Get_HTML_Report(report)
    Get_Json_report(report)

if __name__ == "__main__":
    main()