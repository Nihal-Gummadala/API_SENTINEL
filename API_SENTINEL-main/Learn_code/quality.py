def Code_Warnings(function_complexity_dict):

    warnings = []
    types = []
    for file_name, functions in function_complexity_dict.items():
        for function_name, metrics in functions.items():
            if metrics["lines"] > 50:
                warnings.append(f"{file_name}: Function {function_name}() is {metrics['lines']} lines long")
                types.append('function_length')
            if metrics["ifs"] > 10:
                warnings.append(f"{file_name}: Function {function_name}() has {metrics['ifs']} if statements")
                types.append('function_complexity')
            if metrics["loops"] > 5:
                warnings.append(f"{file_name}: Function {function_name}() has {metrics['loops']} loops")
                types.append('function_complexity')
    return warnings, types

def Code_Quality_Score(function_complexity_dict, unused_imports):
        repo_health = 100
        _, types = Code_Warnings(function_complexity_dict)

        for warning_type in types:

                if warning_type == 'function_length':
                        repo_health -= 2

                if warning_type == 'function_complexity':
                        repo_health -= 5

        unused_import_penalty = min(len(unused_imports) * 2, 20)
        repo_health -= unused_import_penalty

        if repo_health < 0:
                repo_health = 0

        return repo_health

def Repository_Summary(file_lines_sizes, function_num_dict, classes_num_dict, imports_num_dict, function_complexity_dict, quality_score, unused_imports):
    total_lines = sum(file_lines_sizes.values())
    total_functions = sum(function_num_dict.values())
    total_classes = sum(classes_num_dict.values())
    total_imports = sum(imports_num_dict.values())

    warnings, _ = Code_Warnings(function_complexity_dict)

    summary = {"total_files": len(file_lines_sizes), "total_lines": total_lines, "total_functions": total_functions, "total_classes": total_classes, "total_imports": total_imports, "total_warnings": len(warnings), "total_unused_imports": len(unused_imports), "quality_score": quality_score}

    return summary