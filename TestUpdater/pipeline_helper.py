import os, json, re, difflib, subprocess
from utils.multilspy import SyncLanguageServer
from utils.multilspy.multilspy_utils import TextUtils
from utils.gitter import UpdateRepo, setup_repo
from utils.parser import extract_method_from_line, extract_class_from_line, extract_class_varibles
from utils.logger import logger
from utils.configs import REPO_BASE, mvn_dict, java_dict

MVN_SKIPS = [
    '-DfailIfNoTests=false', 
    '-Dsurefire.failIfNoSpecifiedTests=false', 
    '-Dcheckstyle.skip', 
    '-Dspotless.check.skip',
    '-Djacoco.skip',
    '-Dspotless.apply.skip',
    '-Drat.skip',
    '-Denforcer.skip',
    '-Danimal.sniffer.skip',
    '-Dmaven.javadoc.skip',
    '-Dmaven.gitcommitid.skip',
    '-Dfindbugs.skip',
    '-Dwarbucks.skip',
    '-Dmodernizer.skip',
    '-Dimpsort.skip',
    '-Dpmd.skip',
    '-Dxjc.skip',
    '-Dair.check.skip-all',
    '-Dlicense.skip',
    '-Dremoteresources.skip',
    '-Dspotbugs.skip=true'
]

def extract_json(input_str: str):
    """
    Parses the input string and extracts code blocks in Java, which is surrounded by ```java and ``` or ``` and ```.
    """
    code_blocks = re.findall(
        r"```json\n(.*?)\n```|```\n(.*?)\n```", input_str, re.DOTALL
    )
    if len(code_blocks) == 0:
        return ""
    else:
        return code_blocks[0][0] if code_blocks[0][0] != "" else code_blocks[0][1]

def extract_code(input_str: str):
    """
    Parses the input string and extracts code blocks in Java, which is surrounded by ```java and ``` or ``` and ```.
    """
    code_blocks = re.findall(
        r"```java\n(.*?)\n```|```\n(.*?)\n```", input_str, re.DOTALL
    )
    if len(code_blocks) == 0:
        return input_str
    else:
         # Extract all non-empty code blocks
        extracted_blocks = []
        for block in code_blocks:
            if block[0]:  # If the first element (```java``` block) is not empty
                extracted_blocks.append(block[0])
            elif block[1]:  # If the second element (`````` block) is not empty
                extracted_blocks.append(block[1])

        return "\n".join(extracted_blocks)
    
def get_diff(src_code: str, tgt_code: str, n: int = -1) -> str:
    """
    Get the unified diff between two code snippets.

    Args:
        src_code (str): The source code snippet.
        tgt_code (str): The target code snippet.
        n (int): The numbers of context lines. (-1: means no limit)

    Returns:
        str: The unified diff between the source and target code snippets (with prefix line: @@).
    """
    src_lines = src_code.splitlines()
    tgt_lines = tgt_code.splitlines()
    if n == -1:
        n = max(len(src_lines), len(tgt_lines))
    # generate unified_diff
    diff = difflib.unified_diff(
        src_lines, tgt_lines, n=n, fromfile="Previous", tofile="Current"
    )
    diff = list(diff)[2:]
    diff_str = "\n".join(diff)
    return diff_str

def substitute_code(repo: UpdateRepo, exp, pred):
    test_file_path = exp["changed_test"].split('#')[0]
    testfile_ori = repo.get_file_tgt(test_file_path)
    if testfile_ori.find(exp["test_code_tgt"]) == -1:
        return None
    testfile_new = testfile_ori.replace(exp["test_code_tgt"], pred)
    testpath = os.path.join(repo.working_tree_dir, test_file_path)
    with open(testpath, "w", encoding="utf-8") as f:
        f.write(testfile_new)

def add_imports(repo: UpdateRepo, exp, imports: str):
    test_file_path = exp["changed_test"].split('#')[0]
    testpath = os.path.join(repo.working_tree_dir, test_file_path)
    with open(testpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    package_index = None
    for i, line in enumerate(lines):
        if line.strip().startswith("package"):
            package_index = i
            break
    if package_index is None:
        insert_index = 0
    else:
        insert_index = package_index + 1

    lines.insert(insert_index, imports)

    with open(testpath, "w", encoding="utf-8") as f:
        f.writelines(lines)

def build_test(exp):

    logger.info("##" * 5 + " [" + str(exp["test_id"]) + "] " + "##" * 5)
    logger.info(f"Repo Name : {exp['repo_name']}")
    logger.info(f"Commit ID : {exp['commit_tgt']}")

    # checkout the repository to this given commit
    repo_root = os.path.join(REPO_BASE, exp["repo_name"])
    changed_test = exp['changed_test']
    classname, methodname = changed_test.split('#')
    classname = classname.split('src/test/java/')[-1].replace('.java', '').replace('/', '.')
    test_case = f"{classname}#{methodname}"

    module = changed_test.split('src/test/java/')[0]
    if module.endswith('/'):
        module = module[:-1]

    logger.info(f"Test case: {test_case}")
    logger.info(f"Repo Root Path : {repo_root}")

    repo: UpdateRepo = setup_repo(exp["repo_name"], exp["commit_tgt"], repo_base=REPO_BASE)

    #  substitute with prediction
    pred = exp["test_gen"]
    substitute_code(repo, exp, pred)
    # import new imports
    imports = exp.get("imports_gen")
    if imports:
        add_imports(repo, exp, imports)

    os.chdir(repo_root)
    original_path = os.environ.get('PATH')

    os.environ['JAVA_HOME'] = java_dict[exp["tgt_java_version"]]
    os.environ['PATH'] = os.environ['JAVA_HOME'] + '/bin:' + os.environ['PATH']
    os.environ['MAVEN_HOME'] = mvn_dict[exp["tgt_maven_version"]]
    os.environ['PATH'] = os.environ['MAVEN_HOME'] + '/bin:' + os.environ['PATH']

    cmd =  ['mvn', '-T2C', 'clean', 'test', f'-Dtest={test_case}']
    if module:
        cmd.extend(['-pl', f'{module}', '--also-make'])
    cmd.extend(MVN_SKIPS)
    print(' '.join(cmd))

    try:
        # mvn test
        completed_process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300  # 5 min
        )
        output = completed_process.stdout.decode()
        lines = output.splitlines()
        build_info = [line for line in lines if 'BUILD SUCCESS' in line]
        test_info = [line for line in lines if 'Tests run' in line]
        error_info = [line for line in lines if '[ERROR]' in line]
        logger.info(test_info)
        logger.info(build_info)
        logger.info('\n'.join(error_info))
        # reset
        os.environ['PATH'] = original_path
    except subprocess.TimeoutExpired:
        logger.info("Execute timeout.")
        raise

    return completed_process.returncode, error_info, test_info

def align_code(code):
    code_lines = code.split('\n')
    move = len(code_lines[0]) - len(code_lines[0].lstrip())
    for i in range(len(code_lines)):
        if len(code_lines[i].lstrip().rstrip()) == 0:
            continue
        if move > len(code_lines[i]) - len(code_lines[i].lstrip()):
            move = len(code_lines[i]) - len(code_lines[i].lstrip())
    aligned_code = [l[move:] if len(l.lstrip().rstrip()) != 0 else l for l in code_lines]
    return '\n'.join(aligned_code)

def read_json(json_file):
    if not os.path.isfile(json_file):
        return None
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(output_file, obj):
    output_folder = os.sep.join(output_file.split(os.sep)[:-1])
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)

def get_function(name: str, repo_path, proj, repo: UpdateRepo, lsp: SyncLanguageServer):
    focal_relpath = proj["changed_prod"].split('#')[0]
    focal_file = repo.get_file_tgt(focal_relpath)
    method_start = focal_file.find(proj["prod_code_tgt"])

    name_idx = -1
    name_idx_match = re.search(rf'\b{name}\b', proj["prod_code_tgt"])
    if name_idx_match is not None:
        name_idx = name_idx_match.start()
    # find in test file
    if name_idx == -1:
        focal_relpath = proj["changed_test"].split('#')[0]
        focal_file = repo.get_file_tgt(focal_relpath)
        method_start = focal_file.find(proj["test_code_tgt"])
        name_idx_match = re.search(rf'\b{name}\b', proj["test_code_tgt"])
        if name_idx_match is not None:
            name_idx = name_idx_match.start()

    # not found
    if name_idx == -1:
        return ""
    # ***.***
    split_idx = name.find(".")
    if split_idx != -1:
        name_idx += split_idx + 1
    
    ln, cn = TextUtils.get_line_col_from_index(focal_file, method_start + name_idx)
    definition_loc = lsp.request_definition(focal_relpath, ln, cn)
    res = ""
    if len(definition_loc) != 0:
        rel_path = definition_loc[0]["relativePath"]
        file_str = repo.get_file_tgt(definition_loc[0]["relativePath"])
        line = definition_loc[0]["range"]["start"]["line"]
        method_info = extract_method_from_line(file_str, line)
        if method_info:
            res = f"Function {name} in {rel_path}: \n```java\n{method_info}\n```\n"
        else:
            logger.error(f"Error: can not find function {name}")
    return res

def get_class(name: str, repo_path, proj, repo: UpdateRepo, lsp: SyncLanguageServer):
    focal_relpath = proj["changed_prod"].split('#')[0]
    focal_file = repo.get_file_tgt(focal_relpath)
    method_start = focal_file.find(proj["prod_code_tgt"])

    name_idx = -1
    name_idx_match = re.search(rf'\b{name}\b', proj["prod_code_tgt"])
    if name_idx_match is not None:
        name_idx = name_idx_match.start()
    # find in test file
    if name_idx == -1:
        focal_relpath = proj["changed_test"].split('#')[0]
        focal_file = repo.get_file_tgt(focal_relpath)
        method_start = focal_file.find(proj["test_code_tgt"])
        name_idx_match = re.search(rf'\b{name}\b', proj["test_code_tgt"])
        if name_idx_match is not None:
            name_idx = name_idx_match.start()

    # not found
    if name_idx == -1:
        return ""
    # ***.***
    split_idx = name.find(".")
    if split_idx != -1:
        name_idx += split_idx + 1
    
    ln, cn = TextUtils.get_line_col_from_index(focal_file, method_start + name_idx)
    loc = lsp.request_definition(focal_relpath, ln, cn)
    res = ""
    if len(loc) != 0:
        rel_path = loc[0]["relativePath"]
        file_str = repo.get_file_tgt(loc[0]["relativePath"])
        class_info = extract_class_from_line(file_str, loc[0]["range"]["start"]["line"])
        if class_info:
            res = f"Class {name} in {rel_path}: \n```java\n{class_info}\n```\n"
        else:
            logger.error(f"Error: can not find class {name}")
    return res

def get_varibles(proj, repo: UpdateRepo):
    test_relpath = proj["changed_test"].split('#')[0]
    test_file = repo.get_file_tgt(test_relpath)
    varibles = extract_class_varibles(test_file)
    return '\n'.join([x.strip() for x in varibles])

def get_error_location(error_line):
    line_number = -1
    column_number = -1
    match = re.search(r"\[(\d+),(\d+)\]", error_line)
    if match:
            line_number = match.group(1)
            line_number = int(line_number)
            column_number = match.group(2)
            column_number = int(column_number)
    return line_number, column_number
    

def parse_error(error_info: list[str], repo_path, proj, repo, lsp):
    test_relpath = proj["changed_test"].split('#')[0]
    test_file = os.path.join(repo_path, test_relpath)
    if not os.path.exists(test_file):
        return None
    
    for index, line in enumerate(error_info):
       if line.find("Compilation failure") != -1:
            error_info = error_info[index:]
            break  
    for index, line in enumerate(error_info):
       if line.find("[Help 1]") != -1:
            error_info = error_info[:index+1]
            break         
    logger.info('\n'.join(error_info))
    error_infos = []
    symbol_need_names = []
    for index, line in enumerate(error_info):
        # 1. cannot find symbol
        if test_file in line and "cannot find symbol" in line:
            ln, cn = get_error_location(line)
            info_line = error_info[index+1].split()
            symbol_type = info_line[2] # variable, method, class, static
            symbol_name = info_line[3]
            
            with open(test_file, "r", encoding='utf-8') as f:
                file_lines = f.readlines()
                error_line = file_lines[ln-1].strip()
            
            symbol_need_name = symbol_name

            symbol_start = error_line.find(symbol_name)
            logger.info(f"ERROR LINE: {error_line}")
            if symbol_start != -1:
                if error_line[symbol_start - 1] == '.':
                        match = re.search(rf"([\w()]+)\.{symbol_name}", error_line)
                        if match:
                                symbol_need_name = match.group(1)
                if symbol_need_name not in symbol_need_names:
                        symbol_need_names.append(symbol_need_name)
                
            error_prompt = f"// <ERROR> Can not find symbol: {symbol_name}\n{error_line}"
            error_infos.append(error_prompt)
        
        # 2. cannot be applied to given type
        elif test_file in line and "cannot be applied to given type" in line:
            ln, cn = get_error_location(line)

            symbol_need_name = line.split()[3]
            if line.split()[2] == "method":
                symbol_need_name += "()"
            if symbol_need_name not in symbol_need_names:
                symbol_need_names.append(symbol_need_name)
            
            with open(test_file, "r", encoding='utf-8') as f:
                file_lines = f.readlines()
                error_line = file_lines[ln-1].strip()

            reason = ""
            reason_line = error_info[index + 3]
            if reason_line.find("reason:") != -1:
                reason_start = reason_line.find(":") + 1
                reason = reason_line[reason_start:]
            error_prompt = f"// <ERROR> {reason}\n{error_line}"
            error_infos.append(error_prompt)

        elif test_file in line:
            ln, cn = get_error_location(line)
            with open(test_file, "r", encoding='utf-8') as f:
                file_lines = f.readlines()
                error_line = file_lines[ln-1].strip()
            reason = line.split()[:1] + line.split()[1:]
            reason = ' '.join(reason)
            print(reason)
            error_prompt = f"// <ERROR> {reason}\n{error_line}"
            error_infos.append(error_prompt)
    info_need = []
    logger.info(symbol_need_names)
    for name in symbol_need_names:
        isFunc = False
        if name.find('(') != -1:
            name = name[:name.find('(')]
            isFunc = True
        if isFunc:
            func_info = get_function(name, repo_path, proj, repo, lsp)
            info_need.append(func_info)
        else:
            clas_info = get_class(name, repo_path, proj, repo, lsp)
            info_need.append(clas_info)
    info_need = '\n'.join(info_need)
    error_infos = '\n'.join(error_infos)
    prompt = ""
    if error_infos:
        prompt = f"Error Lines in the test method:\n```java\n{error_infos}\n```\n"
        if info_need:
            prompt += f"Information you can reference to is:\n{info_need}"
    return prompt

def parse_testfail(error_info, repo_path, proj, repo, lsp):
    test_relpath = proj["changed_test"].split('#')[0]
    test_class = proj["changed_test"].split('#')[0].split('/')[-1].split('.')[0]

    # Find report directory: Please refer to {dir} for the individual test results.
    report_dir = ""
    for line in error_info:
        if line.find("Please refer to") != -1 and line.find("test results") != -1:
            report_dir = line.split()[4]
            break
    # Find test class report
    report_name = ""
    if report_dir and os.path.exists(report_dir):
        filenames = [entry.name for entry in os.scandir(report_dir) if entry.is_file() and entry.name.endswith(".txt")]
        for filename in filenames:
            if filename.find(test_class) != -1:
                report_name = filename
                break
    report_path = os.path.join(report_dir, report_name)
    if not os.path.exists(report_path):
        return None
    # Extract info from test report
    filtered_info = []
    with open(report_path, "r") as f:
        lines = f.readlines()
        # Find begin of error info
        for idx, line in enumerate(lines):
            if line.find("Error:") != -1:
                lines = lines[idx:]
                break
        # filter out other "at" lines
        for line in lines:
            trimmed = line.strip()
            if trimmed and not (trimmed.startswith("at") and test_class not in line):
                filtered_info.append(line)

    for idx, line in enumerate(filtered_info):
        if line.strip().startswith("at"):
            match = re.search(r'.java:(\d+)\)', line)
            if match:
                ln = int(match.group(1))
            with open(os.path.join(repo_path, test_relpath), "r") as f:
                file_lines = f.readlines()
                error_line = file_lines[ln-1].strip()
            filtered_info[idx] = error_line + "\n"
        else:
            filtered_info[idx] = "\\\\" + line
    return ''.join(filtered_info)