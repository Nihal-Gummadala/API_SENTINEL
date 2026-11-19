
import os
import sys
from report import report_info, print_report, Get_Json_report, Get_HTML_Report


def main():
    arguments = sys.argv[1:]
    check_apis = "--no-api-check" not in arguments
    arguments = [argument for argument in arguments if argument != "--no-api-check"]

    if arguments and arguments[0] == "--local":
        folder = os.path.abspath(arguments[1] if len(arguments) > 1 else ".")
        if not os.path.isdir(folder):
            print(f"{folder} is not a folder.")
            return
        repository = os.path.basename(folder.rstrip(os.sep))
        report = report_info(None, None, repository, local_path=folder, check_apis=check_apis)
    else:
        url = arguments[0] if arguments else input("Please enter Github url: ")

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
            report = report_info(repo_url, content_url, repository, check_apis=check_apis)
        except RuntimeError as error:
            print(f"Could not analyze the repository: {error}")
            return

    print_report(report)

    Get_HTML_Report(report)
    Get_Json_report(report)

if __name__ == "__main__":
    main()
