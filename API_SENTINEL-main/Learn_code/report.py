from github_api import get_largest_files, Get_Repo_Languages
from code_analyzer import AnalyzeFiles
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary
import json


def report_info(repo_url, content_url, repository):

    (file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict, unused_imports, skipped_files, TODO_locs, FIXME_locs) = AnalyzeFiles(content_url)

    quality_score = Code_Quality_Score(function_complexity_dict, unused_imports, TODO_locs, FIXME_locs)

    warnings, _ = Code_Warnings(function_complexity_dict, TODO_locs, FIXME_locs)

    summary = Repository_Summary(file_lines_sizes, function_num_dict, classes_num_dict, imports_num_dict, function_complexity_dict, quality_score, unused_imports, TODO_locs, FIXME_locs)

    languages = Get_Repo_Languages(repo_url)

    largest_files = get_largest_files(content_url)

    return {'repository': repository, 'languages': languages, 'summary': summary, 'warnings': warnings, 'largest_files': largest_files, 'unused_imports': unused_imports, 'skipped_files': skipped_files}

def print_report(report):
    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']
    unused_imports = report['unused_imports']
    skipped_files = report['skipped_files']

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

    print("\nUNUSED IMPORTS")
    if unused_imports:
        for unused_import in unused_imports:
            print(f"- {unused_import}")
    else:
        print("None found!")

    print("\nWARNINGS")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings!")

    if skipped_files:
        print("\nCOULD NOT PARSE")
        for skipped_file in skipped_files:
            print(f"- {skipped_file}")

    print("\n===============================================")

def Get_HTML_Report(report):

    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']
    unused_imports = report['unused_imports']
    skipped_files = report['skipped_files']

    largest_files_html = "".join(f"<li>{path} ({size:,} bytes)</li>" for path, size in reversed(largest_files))
    unused_imports_html = "".join(f"<li>{unused_import}</li>" for unused_import in unused_imports) or "<li>None found!</li>"
    warnings_html = "".join(f"<li>{warning}</li>" for warning in warnings) or "<li>No warnings!</li>"
    skipped_files_html = "".join(f"<li>{skipped_file}</li>" for skipped_file in skipped_files)

    skipped_section = f"<h2>Could Not Parse</h2><ul>{skipped_files_html}</ul>" if skipped_files else ""

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
        <p>{', '.join(languages) if languages else 'none detected'}</p>

        <h2>Summary</h2>
        <p>Files: {summary['total_files']}</p>
        <p>Lines: {summary['total_lines']}</p>
        <p>Functions: {summary['total_functions']}</p>
        <p>Classes: {summary['total_classes']}</p>
        <p>Imports: {summary['total_imports']}</p>

        <h2>Largest Files</h2>
        <ul>{largest_files_html}</ul>

        <h2>Code Quality</h2>
        <p>Score: {summary['quality_score']}/100</p>

        <h2>Unused Imports</h2>
        <ul>{unused_imports_html}</ul>

        <h2>Warnings</h2>
        <ul>{warnings_html}</ul>

        {skipped_section}

    </body>
    </html>
    """
    with open("report.html", "w") as file:
        file.write(html_content)

def Get_Json_report(report):
    with open("report.json", 'w') as file:
        json.dump(report, file, indent=4)