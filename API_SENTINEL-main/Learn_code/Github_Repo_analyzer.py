from github_api import Count_Total_Files, Count_File_Types, get_largest_files, download_files
from code_analyzer import AnalyzeFiles
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary


def main():
    url = input("Please enter Github url: ")
    url_split = url.rstrip("/").split("/")
    username = url_split[-2]
    repository = url_split[-1]

    content_url = f"https://api.github.com/repos/{username}/{repository}/contents/"

    _, file_names, _ = Count_Total_Files(content_url)

    (file_lines_sizes, functions_dict, function_num_dict, classes_dict, classes_num_dict, imports_dict, imports_num_dict, function_complexity_dict) = AnalyzeFiles(content_url)

    quality_score = Code_Quality_Score(function_complexity_dict)

    warnings, _ = Code_Warnings(function_complexity_dict)

    summary = Repository_Summary(file_lines_sizes, function_num_dict, classes_num_dict, imports_num_dict, function_complexity_dict, quality_score)

    print("\n========== GITHUB REPOSITORY ANALYZER ==========")

    print("\nSUMMARY")
    print(f"Files: {summary['total_files']}")
    print(f"Lines: {summary['total_lines']}")
    print(f"Functions: {summary['total_functions']}")
    print(f"Classes: {summary['total_classes']}")
    print(f"Imports: {summary['total_imports']}")

    print("\nCODE QUALITY")
    print(f"Score: {summary['quality_score']}/100")

    print("\nWARNINGS")

    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings!")

    print("\n===============================================")


if __name__ == "__main__":
    main()