from github_api import Count_Total_Files, Count_File_Types, get_largest_files, download_files, Get_Repo_Languages
from code_analyzer import AnalyzeFiles
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary


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


