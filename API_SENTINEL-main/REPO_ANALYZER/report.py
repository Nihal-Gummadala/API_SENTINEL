from github_api import get_largest_files, Get_Repo_Languages, Count_Languages, Largest_From_Sizes
from code_analyzer import AnalyzeFiles, Analyze_Sources, Read_Local_Folder
from quality import Code_Warnings, Code_Quality_Score, Repository_Summary, API_Warnings, API_Health_Score
from api_checks import Run_API_Checks
from html import escape
import json


def report_info(repo_url, content_url, repository, local_path=None, check_apis=True):
    """Analyze a GitHub repo (repo_url/content_url) or, with local_path, a folder on disk."""

    if local_path:
        sources, file_sizes = Read_Local_Folder(local_path)
        analysis = Analyze_Sources(sources)
        language_counts = Count_Languages(list(file_sizes))
        languages = [name for name, count in sorted(language_counts.items(), key=lambda item: -item[1])
                     if count and name != 'other']
        largest_files = Largest_From_Sizes(file_sizes)
    else:
        analysis = AnalyzeFiles(content_url)
        languages = Get_Repo_Languages(repo_url)
        largest_files = get_largest_files(content_url)

    function_complexity_dict = analysis["function_complexity_dict"]
    unused_imports = analysis["unused_imports"]
    TODO_locs, FIXME_locs = analysis["TODO_locs"], analysis["FIXME_locs"]

    quality_score = Code_Quality_Score(function_complexity_dict, unused_imports, TODO_locs, FIXME_locs)

    warnings, _ = Code_Warnings(function_complexity_dict, TODO_locs, FIXME_locs)

    summary = Repository_Summary(analysis["file_lines_sizes"], analysis["function_num_dict"], analysis["classes_num_dict"], analysis["imports_num_dict"], function_complexity_dict, quality_score, unused_imports, TODO_locs, FIXME_locs)

    if check_apis:
        api_report = Run_API_Checks(analysis["api_calls"], repository)
    else:
        api_report = {"findings": [], "summary": {"total_calls": 0, "checked_calls": 0, "untracked_hosts": {}, "unverified": [], "apis": {}}, "errors": ["API checks were turned off"]}

    api_health = API_Health_Score(api_report["findings"], api_report["summary"]["checked_calls"])

    return {'repository': repository, 'languages': languages, 'summary': summary, 'warnings': warnings, 'largest_files': largest_files, 'unused_imports': unused_imports, 'skipped_files': analysis["skipped_files"], 'function_complexity': function_complexity_dict, 'api_calls': analysis["api_calls"], 'api_findings': api_report["findings"], 'api_summary': api_report["summary"], 'api_errors': api_report["errors"], 'api_health': api_health}

def print_report(report):
    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']
    unused_imports = report['unused_imports']
    skipped_files = report['skipped_files']
    function_complexity = report['function_complexity']

    print("\n========== GITHUB REPOSITORY ANALYZER ==========")
    print(f"Repository: {repository}")
    print(f"Languages: {', '.join(languages) if languages else 'none detected'}")

    print("\nSUMMARY")
    print(f"Files: {summary['total_files']}")
    print(f"Lines: {summary['total_lines']}")
    print(f"Functions: {summary['total_functions']}")
    print(f"Classes: {summary['total_classes']}")
    print(f"Imports: {summary['total_imports']}")

    print("\nFUNCTION METRICS")
    for file_name, functions in function_complexity.items():
        print(f"\n{file_name}")

        for function_name, metrics in functions.items():
            print(f"  {function_name}()")
            print(f"    Lines: {metrics['lines']}")
            print(f"    If statements: {metrics['ifs']}")
            print(f"    Loops: {metrics['loops']}")
            print(f"    Max loop nesting: {metrics['max_nesting']}")
            print(f"    Cyclomatic complexity: {metrics['cyclomatic_complexity']}")

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

    print("\nAPI CALLS")
    found_api_call = False
    for file_name, calls in report['api_calls'].items():
        for call in calls:
            found_api_call = True
            print(f"- {file_name} (line {call['line']})")
            print(f"    API: {call['api']}")
            print(f"    Method: {call['method']}")
            print(f"    URL: {call['url'] if call['url'] else '(from ' + str(call['url_expression']) + ')'}")
    if not found_api_call:
        print("None found!")

    print_api_compatibility(report)

    print("\n===============================================")

def print_api_compatibility(report):
    api_summary = report['api_summary']
    findings = report['api_findings']

    print("\nAPI COMPATIBILITY")
    health = report['api_health']
    print(f"Score: {health}/100" if health is not None else "Score: n/a (no calls could be checked against docs)")
    print(f"Calls found: {api_summary['total_calls']}, checked against docs: {api_summary['checked_calls']}")

    for api, info in api_summary['apis'].items():
        versions = ", ".join(info['versions_checked'])
        line = f"- {api}: checked against " + (f"version {versions}" if versions else "its current docs")
        if info.get('latest_version'):
            line += f" (newest: {info['latest_version']})"
        if info.get('docs_fetched_at'):
            line += f", docs downloaded {info['docs_fetched_at'][:10]}"
        print(line)
        for version, upgrade in info.get('upgrades', {}).items():
            affected = upgrade['changes_affecting_calls']
            print(f"    {upgrade['calls']} call(s) on {version}. Upgrading to {upgrade['to']}: "
                  + (f"{affected} breaking change(s) affect your calls (listed below)" if affected
                     else "none of its breaking changes affect your calls"))

    if findings:
        print("\nAPI FINDINGS")
        for warning in API_Warnings(findings):
            print(f"- {warning}")
    elif api_summary['checked_calls']:
        print("No API problems found!")

    if api_summary['untracked_hosts']:
        print("\nAPIs WITHOUT DOCS (add them to api_registry.json to check them)")
        for host, count in api_summary['untracked_hosts'].items():
            print(f"- {host} ({count} call{'s' if count != 1 else ''})")

    if api_summary['unverified']:
        print("\nCALLS THAT COULDN'T BE CHECKED")
        for item in api_summary['unverified']:
            print(f"- {item['file']} line {item['line']}: {item['reason']}")

    for error in report['api_errors']:
        print(f"! {error}")

def Get_HTML_Report(report):

    repository = report['repository']
    languages = report['languages']
    summary = report['summary']
    warnings = report['warnings']
    largest_files = report['largest_files']
    unused_imports = report['unused_imports']
    skipped_files = report['skipped_files']
    api_summary = report['api_summary']

    largest_files_html = "".join(f"<li>{escape(path)} ({size:,} bytes)</li>" for path, size in reversed(largest_files))
    unused_imports_html = "".join(f"<li>{escape(unused_import)}</li>" for unused_import in unused_imports) or "<li>None found!</li>"
    warnings_html = "".join(f"<li>{escape(warning)}</li>" for warning in warnings) or "<li>No warnings!</li>"
    skipped_files_html = "".join(f"<li>{escape(skipped_file)}</li>" for skipped_file in skipped_files)

    skipped_section = f"<h2>Could Not Parse</h2><ul>{skipped_files_html}</ul>" if skipped_files else ""

    api_call_rows = "".join(
        f"<tr><td>{escape(file_name)}</td><td>{call['line']}</td><td>{escape(call['api'])}</td>"
        f"<td>{escape(str(call['method']))}</td><td>{escape(call['url'] or '(from ' + str(call['url_expression']) + ')')}</td></tr>"
        for file_name, calls in report['api_calls'].items() for call in calls)
    api_calls_html = (f"<table><tr><th>File</th><th>Line</th><th>API</th><th>Method</th><th>URL</th></tr>{api_call_rows}</table>"
                      if api_call_rows else "<p>None found!</p>")

    finding_rows = "".join(
        f"<tr class='{finding['severity']}'><td>{finding['severity']}</td><td>{escape(finding['file'])}:{finding['line']}</td>"
        f"<td>{escape(finding['message'])}{'' if finding['confidence'] == 'verified' else ' <em>(' + finding['confidence'] + ')</em>'}</td>"
        f"<td>{escape(finding['source'])}</td>"
        f"<td>{'<a href=' + chr(34) + escape(finding['docs_url']) + chr(34) + '>docs</a>' if finding.get('docs_url') else ''}</td></tr>"
        for finding in report['api_findings'])
    api_findings_html = (f"<table><tr><th>Severity</th><th>Where</th><th>Problem</th><th>Found by</th><th></th></tr>{finding_rows}</table>"
                         if finding_rows else "<p>No API problems found!</p>")

    api_versions_html = "".join(
        f"<li>{escape(api)}: checked against {('version ' + escape(', '.join(info['versions_checked']))) if info['versions_checked'] else 'its current docs'}"
        f"{' (newest: ' + escape(info['latest_version']) + ')' if info.get('latest_version') else ''}"
        + "".join(f"<br>{upgrade['calls']} call(s) on {escape(version)}; upgrading to {escape(upgrade['to'])}: "
                  f"{upgrade['changes_affecting_calls']} breaking change(s) affect them"
                  for version, upgrade in info.get('upgrades', {}).items())
        + "</li>"
        for api, info in api_summary['apis'].items())
    untracked_html = "".join(f"<li>{escape(host)} ({count})</li>" for host, count in api_summary['untracked_hosts'].items())
    unverified_html = "".join(f"<li>{escape(item['file'])} line {item['line']}: {escape(item['reason'])}</li>" for item in api_summary['unverified'])
    errors_html = "".join(f"<li>{escape(error)}</li>" for error in report['api_errors'])
    api_health = report['api_health']

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub Repository Analyzer</title>
        <style>
            table {{ border-collapse: collapse; }}
            td, th {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; vertical-align: top; }}
            tr.high td:first-child {{ color: #b00020; font-weight: bold; }}
            tr.medium td:first-child {{ color: #b26a00; font-weight: bold; }}
        </style>
    </head>

    <body>
        <h1>GitHub Repository Analyzer</h1>

        <h2>Repository</h2>
        <p>{escape(repository)}</p>

        <h2>Languages</h2>
        <p>{escape(', '.join(languages)) if languages else 'none detected'}</p>

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

        <h2>API Calls</h2>
        {api_calls_html}

        <h2>API Compatibility</h2>
        <p>Score: {str(api_health) + '/100' if api_health is not None else 'n/a (no calls could be checked against docs)'}</p>
        <p>Calls found: {api_summary['total_calls']}, checked against docs: {api_summary['checked_calls']}</p>
        <ul>{api_versions_html}</ul>
        {api_findings_html}
        {'<h3>APIs without docs</h3><ul>' + untracked_html + '</ul>' if untracked_html else ''}
        {"<h3>Calls that couldn't be checked</h3><ul>" + unverified_html + '</ul>' if unverified_html else ''}
        {'<h3>Errors</h3><ul>' + errors_html + '</ul>' if errors_html else ''}

    </body>
    </html>
    """
    with open("report.html", "w") as file:
        file.write(html_content)

def Get_Json_report(report):
    with open("report.json", 'w') as file:
        json.dump(report, file, indent=4)
