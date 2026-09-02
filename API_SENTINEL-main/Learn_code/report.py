from github_api import Count_Total_Files, Count_File_Types, get_largest_files, download_files, Get_Repo_Languages
from code_analyzer import AnalyzeFiles
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary
import json


def report_info(repo_url, content_url, repository):

    (file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict) = AnalyzeFiles(content_url)

    quality_score = Code_Quality_Score(function_complexity_dict)

    warnings, _ = Code_Warnings(function_complexity_dict)

    summary = Repository_Summary(file_lines_sizes, function_num_dict, classes_num_dict, imports_num_dict, function_complexity_dict, quality_score)

    languages = Get_Repo_Languages(repo_url)

    largest_files = get_largest_files(content_url)

    return {'repository': repository, 'languages': languages, 'summary': summary, 'warnings': warnings, 'largest_files': largest_files}

def print_report(report):
    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']

    print("\n========== GITHUB REPOSITORY ANALYZER ==========")
    print(f"Repository: {repository}")
    print(f"Languages: {', '.join(languages) if languages else 'none detected'}")

    print("\nSUMMARY")
    print(f"Files: {summary['total_files']}")
    print(f"Lines: {summary['total_lines']}")
    print(f"Functions: {summary['total_functions']}")
    print(f"Classes: {summary['total_classes']}")
    print(f"Imports: {summary['total_imports']}")

    print("\nLARGEST FILES")
    for path, size in reversed(largest_files):
        print(f"- {path} ({size:,} bytes)")

    print("\nCODE QUALITY")
    print(f"Score: {summary['quality_score']}/100")

    print("\nWARNINGS")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings!")

    print("\n===============================================")

def Get_HTML_Report(report):

    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub Repository Analyzer</title>
    </head>

    <body>
        <h1>GitHub Repository Analyzer</h1>

        <h2>Repository</h2>
        <p>{repository}</p>

        <h2>Languages</h2>
        <p>{', '.join(languages)}</p>

        <h2>Summary</h2>
        <p>Files: {summary['total_files']}</p>
        <p>Lines: {summary['total_lines']}</p>
        <p>Functions: {summary['total_functions']}</p>
        <p>Classes: {summary['total_classes']}</p>
        <p>Imports: {summary['total_imports']}</p>

        <h2>Code Quality</h2>
        <p>Score: {summary['quality_score']}/100</p>

    </body>
    </html>
    """
    with open("report.html", "w") as file:
        file.write(html_content)

def Get_Json_report(report):
    with open("report.json", 'w') as file:
        json_report = json.dump(report, file, indent=4)