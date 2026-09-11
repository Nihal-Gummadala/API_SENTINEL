def Code_Warnings(function_complexity_dict, TODO_locs, FIXME_locs):

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
            if metrics["max_nesting"] >= 2: 
                warnings.append( f"{file_name}: Function {function_name}() has a maximum nesting depth of {metrics['max_nesting']}" ) 
                types.append(('nesting', metrics["max_nesting"]))
            if metrics["cyclomatic_complexity"] >= 6: 
                if metrics["cyclomatic_complexity"] <= 10: 
                    warnings.append( f"{file_name}: Function {function_name}() has moderate cyclomatic complexity of {metrics['cyclomatic_complexity']}" ) 
                    types.append(('cyclomatic', 'moderate')) 
                else: 
                    warnings.append( f"{file_name}: Function {function_name}() has high cyclomatic complexity of {metrics['cyclomatic_complexity']}" ) 
                    types.append(('cyclomatic', 'high'))

    for name, lines in TODO_locs.items():
        if lines:
            line_str = ", ".join(str(l) for l in lines)
            warnings.append(f"{name}: TODO found on lines {line_str}")
            types.append('TODO')
    for name, lines in FIXME_locs.items():
        if lines:
            line_str = ", ".join(str(l) for l in lines)
            warnings.append(f"{name}: FIXME found on lines {line_str}")
            types.append('FIXME')
    return warnings, types

def Code_Quality_Score(function_complexity_dict, unused_imports, TODO_locs, FIXME_locs):
        repo_health = 100
        _, types = Code_Warnings(function_complexity_dict, TODO_locs, FIXME_locs)

        for warning_type in types:

                if warning_type == 'function_length':
                        repo_health -= 2

                if warning_type == 'function_complexity':
                        repo_health -= 5

                if warning_type == 'TODO':
                    repo_health -= 2

                if warning_type == 'FIXME':
                    repo_health -= 2
                
                if isinstance(warning_type, tuple) and warning_type[0] == 'nesting': 
                    nesting_depth = warning_type[1] 
                    if nesting_depth == 2: 
                        repo_health -= 2 
                    elif nesting_depth == 3: 
                        repo_health -= 4 
                    elif nesting_depth == 4:
                        repo_health -= 16 
                    elif nesting_depth > 4: 
                        repo_health -= 16 * (2 ** (nesting_depth - 4))

                if isinstance(warning_type, tuple) and warning_type[0] == 'cyclomatic': 
                    complexity_level = warning_type[1] 
                    if complexity_level == 'moderate': 
                        repo_health -= 3 
                    elif complexity_level == 'high': 
                        repo_health -= 5

        unused_import_penalty = min(len(unused_imports) * 2, 20)
        repo_health -= unused_import_penalty

        if repo_health < 0:
                repo_health = 0

        return repo_health

def Repository_Summary(file_lines_sizes, function_num_dict, classes_num_dict, imports_num_dict, function_complexity_dict, quality_score, unused_imports, TODO_locs, FIXME_locs):
    total_lines = sum(file_lines_sizes.values())
    total_functions = sum(function_num_dict.values())
    total_classes = sum(classes_num_dict.values())
    total_imports = sum(imports_num_dict.values())

    warnings, _ = Code_Warnings(function_complexity_dict, TODO_locs, FIXME_locs)

    summary = {"total_files": len(file_lines_sizes), "total_lines": total_lines, "total_functions": total_functions, "total_classes": total_classes, "total_imports": total_imports, "total_warnings": len(warnings), "total_unused_imports": len(unused_imports), "quality_score": quality_score}

    return summary