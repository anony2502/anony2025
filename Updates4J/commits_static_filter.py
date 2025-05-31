import os
import re
import json
import time
import shutil
import javalang
import traceback
import multiprocessing
import argparse
import subprocess as sp
from tqdm import tqdm
from git import Repo
from datetime import datetime
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

repo_list = "repos_topstars.txt"
enable_local_search = False
search_path = ""
repo_store_path = ""
compilation_unverified_commits_path = "unverified_commits_tops/"

data_leakage_date = "2021-01-01"
code_max_lines = 200

JAVA_LANGUAGE = Language(tsjava.language(), "java")
parser = Parser()
parser.set_language(JAVA_LANGUAGE)
# TAG
FILTERED = "filtered"
SUCCESS = "success"
EXCEPTION = "exception"

num_cores = 20
exps = []


def strim_commits(commits, appends=None):
    result = []
    for commit in tqdm(commits):
        strim_commit = {}
        strim_commit["commit_id"] = commit.hexsha
        strim_commit["date"] = commit.committed_datetime
        strim_commit["size"] = commit.size
        strim_commit["stats"] = commit.stats
        parent = {}
        if len(commit.parents) == 0:
            continue
        parent["commit_id"] = commit.parents[0].hexsha
        parent["date"] = commit.parents[0].committed_datetime
        parent["size"] = commit.parents[0].size
        strim_commit["parent"] = parent
        if appends is not None:
            for key, value in appends.items():
                strim_commit[key] = value
        result.append(strim_commit)
    return result


def clone_repo(repo_name):
    target_path = os.path.join(repo_store_path, repo_name)
    if os.path.exists(target_path):
        res = sp.run(
            "git checkout master",
            cwd=target_path,
            shell=True,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            res = sp.run(
                "git checkout main",
                cwd=target_path,
                shell=True,
                capture_output=True,
                text=True,
            )
        sp.run("git pull", cwd=target_path, shell=True, capture_output=True, text=True)
        return 0
    if enable_local_search:
        source_path = os.path.join(search_path, repo_name)
        if os.path.exists(source_path):
            # clone
            if not os.path.exists(target_path):
                os.makedirs(target_path)
            for item in os.listdir(source_path):
                src_item = os.path.join(source_path, item)
                tgt_item = os.path.join(target_path, item)
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, tgt_item)
                else:
                    shutil.copy2(src_item, tgt_item)
            # git pull
            while True:
                try:
                    result = sp.run(
                        "git fetch --all",
                        cwd=target_path,
                        shell=True,
                        capture_output=True,
                        text=True,
                    )
                    result = sp.run(
                        "git reset --hard",
                        cwd=target_path,
                        shell=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        break
                    else:
                        print("Git pull failed.")
                        print(result.stderr)
                        time.sleep(60)
                except Exception as e:
                    print("Exception occurred in pull.")
                    print(e)
    if os.path.exists(target_path):
        return 0
    else:
        # git clone
        os.makedirs(target_path)
        git_url = f"https://github.com/{repo_name}.git"
        while True:
            try:
                result = sp.run(
                    f"git clone {git_url} {target_path}",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    break
                else:
                    print("Git clone failed.")
                    print(result.stderr)
                    time.sleep(60)
            except Exception as e:
                print("Exception occurred in clone.")
                print(e)
    return 0


def get_changed_files_via_commit(commit):
    files = commit["stats"].files
    changed_files = files.keys()
    return list(changed_files)


def static_filter(commit):
    try:
        changed_files = get_changed_files_via_commit(commit)
        changed_prod_files = []
        changed_test_files = []
        for changed_file in changed_files:
            if not changed_file.endswith(".java"):
                continue
            file_name = changed_file.split("/")[-1].replace(".java", "")
            if file_name.startswith("Test") or file_name.endswith("Test"):
                changed_test_files.append(changed_file)
            else:
                changed_prod_files.append(changed_file)
        if len(changed_prod_files) == 0 or len(changed_test_files) == 0:
            return {"tag": FILTERED}

        # Class name matching
        class_name_matched = False
        matched_pairs = []
        for changed_prod_file in changed_prod_files:
            prod_class_name = changed_prod_file.split("/")[-1].replace(".java", "")
            for changed_test_file in changed_test_files:
                test_class_name = changed_test_file.split("/")[-1].replace(".java", "")
                if (
                    test_class_name == f"{prod_class_name}Test"
                    or test_class_name == f"Test{prod_class_name}"
                ):
                    class_name_matched = True
                    matched_pairs.append((changed_prod_file, changed_test_file))
        if not class_name_matched:
            return {"tag": FILTERED}

        test_dir = changed_test_files[0]
        test_dir = test_dir.split("/")
        if "test" in test_dir:
            index = test_dir.index("test")
            test_dir = "/".join(test_dir[: index + 2])
        else:
            test_dir = "src/test/java"

        samples = []
        for matched_pair in matched_pairs:
            prod_path = matched_pair[0]
            test_path = matched_pair[1]
            p = sp.run(
                f"git show {commit['parent']['commit_id']}:{prod_path}",
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                cwd=repo_path,
                shell=True,
            )
            src_prod_content = p.stdout.decode()
            p = sp.run(
                f"git show {commit['commit_id']}:{prod_path}",
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                cwd=repo_path,
                shell=True,
            )
            tgt_prod_content = p.stdout.decode()
            modified_methods, src_method_body, tgt_method_body = get_modified_methods(
                src_prod_content, tgt_prod_content
            )
            if modified_methods is None:
                continue
            p = sp.run(
                f"git show {commit['parent']['commit_id']}:{test_path}",
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                cwd=repo_path,
                shell=True,
            )
            src_test_content = p.stdout.decode()
            p = sp.run(
                f"git show {commit['commit_id']}:{test_path}",
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                cwd=repo_path,
                shell=True,
            )
            tgt_test_content = p.stdout.decode()
            modified_tests, src_test_body, tgt_test_body = get_modified_methods(
                src_test_content, tgt_test_content, test_code=True
            )
            if modified_tests is None:
                continue

            for idx, modified_test in enumerate(modified_tests):
                src_invoked_methods = get_invoked_methods(src_test_body[idx])
                tgt_invoked_methods = get_invoked_methods(tgt_test_body[idx])
                corresponding_prod = None
                max_diff = -100000
                for idx2, modified_method in enumerate(modified_methods):
                    if (
                        modified_method in src_invoked_methods
                        and modified_method in tgt_invoked_methods
                    ):
                        if (
                            len(tgt_method_body[idx2]) - len(src_method_body[idx2])
                            > max_diff
                        ):
                            max_diff = len(tgt_method_body[idx2]) - len(
                                src_method_body[idx2]
                            )
                            corresponding_prod = idx2
                if corresponding_prod is None:
                    continue
                sample = {}
                sample["commit_date"] = str(commit["date"])
                sample["commit_src"] = commit["parent"]["commit_id"]
                sample["commit_tgt"] = commit["commit_id"]
                sample["changed_test"] = f"{test_path}#{modified_test}"
                sample["changed_prod"] = f"{prod_path}#{modified_methods[idx2]}"
                sample["test_code_src"] = src_test_body[idx]
                sample["test_code_tgt"] = tgt_test_body[idx]
                sample["prod_code_src"] = src_method_body[idx2]
                sample["prod_code_tgt"] = tgt_method_body[idx2]
                if (
                    max(
                        len(sample["test_code_src"].split("\n")),
                        len(sample["test_code_tgt"].split("\n")),
                        len(sample["prod_code_src"].split("\n")),
                        len(sample["prod_code_tgt"].split("\n")),
                    )
                    > code_max_lines
                ):
                    continue
                samples.append(sample)

        if len(samples) == 0:
            return {"tag": FILTERED}
        # dup samples
        keys = set()
        result = []
        for sample in samples:
            key = f"{sample['prod_code_src']}::{sample['prod_code_tgt']}::{sample['test_code_src']}::{sample['test_code_tgt']}"
            if key in keys:
                continue
            keys.add(key)
            result.append(sample)
        return {"tag": SUCCESS, "samples": result}
    except Exception as e:
        exp = traceback.format_exc()
        return {"tag": EXCEPTION, "exp": exp}


def get_invoked_methods(method_content):
    try:
        tree = parser.parse(method_content.encode())
        root_node = tree.root_node

        invoked_methods = set()

        def traverse(node):
            if node.type == "method_invocation":
                method_name = node.child_by_field_name("name")
                if method_name:
                    method_text = method_name.text.decode()
                    if (
                        method_text not in {"fail", "verifyException"}
                        and "assert" not in method_text
                    ):
                        invoked_methods.add(method_text)
            for child in node.children:
                traverse(child)

        traverse(root_node)
        return invoked_methods

    except Exception as e:
        return None


def get_methods_from_tree(tree):
    methods = []

    def traverse(node):
        if node.type == "method_declaration":
            methods.append(node)
        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return methods


def get_modified_methods(src_content, tgt_content, test_code=False):
    try:
        src_tree = parser.parse(src_content.encode())
        tgt_tree = parser.parse(tgt_content.encode())
    except Exception:
        return None, None, None
    src_methods = get_methods_from_tree(src_tree)
    tgt_methods = get_methods_from_tree(tgt_tree)

    modified_methods = []
    src_method_body = []
    tgt_method_body = []

    for tgt_method in tgt_methods:
        tgt_method_name = tgt_method.child_by_field_name("name")
        if not tgt_method_name:
            continue
        tgt_method_name = tgt_method_name.text.decode()
        matched_src_method = None
        for src_method in src_methods:
            src_method_name = src_method.child_by_field_name("name")
            if src_method_name and src_method_name.text.decode() == tgt_method_name:
                matched_src_method = src_method
                break
        if matched_src_method and tgt_method.text == matched_src_method.text:
            continue

        if test_code:
            for child in tgt_method.children:
                if child.type == "modifiers" and not ("@Test" in child.text.decode()):
                    return None, None, None

        modified_methods.append(tgt_method_name)
        src_method_body.append(matched_src_method.text.decode())
        tgt_method_body.append(tgt_method.text.decode())
    return modified_methods, src_method_body, tgt_method_body


def extract_focal_code(java_code_content, method):
    method_name = method.name
    target_line_number = method.position.line
    java_code = java_code_content.split("\n")
    start = target_line_number
    while start >= 0:
        if java_code[start].find(method_name) != -1 and (
            java_code[start].find("public ") != -1
            or java_code[start].find("private ") != -1
            or java_code[start].find("protected ") != -1
        ):
            break
        if java_code[start].find("@Test") != -1:
            start = start + 1
            break
        start = start - 1
    define_line = start
    while start > 0:
        start = start - 1
        if java_code[start].find("@") == -1:
            break
    start = start + 1
    tmp = start
    while start >= 0:
        if java_code[start].find("/*") != -1:
            break
        elif (
            re.match("\s*(})\s*", java_code[start])
            or java_code[start].find(" class ") != -1
            or java_code[start].find(" interface ") != -1
            or java_code[start].startswith("class ")
            or java_code[start].startswith("import ")
        ):
            start = tmp
            break
        start = start - 1
    if start < 0:
        raise Exception("Error:" + method_name + " not found")
    end = define_line
    comment = False
    count = None
    end = end - 1
    while end + 1 < len(java_code) or count == None:
        end = end + 1
        if comment and java_code[end].find("*/") != -1:
            comment = False
            continue
        if (
            java_code[end].find("/*") != -1
            and java_code[end].find("*/") == -1
            and java_code[end][: java_code[end].find("/*")].find('"') == -1
            and java_code[end][: java_code[end].find("/*")].find("}") == -1
        ):
            comment = True
            continue
        if countSymbol(java_code[end], ";") != 0 and count == None:
            break
        left_count = countSymbol(java_code[end], "{")
        right_count = countSymbol(java_code[end], "}")
        diff = left_count - right_count
        if count == None and diff != 0:
            count = diff
        elif count != None:
            count = count + diff
        if count != None and count <= 0:
            break
    if (
        java_code[end].find("/*") != -1
        and java_code[end][: java_code[end].find("/*")].find('"') == -1
        and java_code[end][: java_code[end].find("/*")].find("}") == -1
    ):
        java_code[end] = java_code[end][: java_code[end].find("}") + 1]
    end = end + 1
    if end >= len(java_code):
        raise Exception("Error:Unexpected error in extract_focal_code()")
    if java_code[end].find("public ") != -1 or java_code[end].find("private ") != -1:
        end = end - 1
        while end > target_line_number and java_code[end].find("@") != -1:
            end = end - 1
        if java_code[end].find("*/") != -1:
            while end > target_line_number and java_code[end].find("/*") == -1:
                end = end - 1
    return "\n".join(java_code[start:end])


def countSymbol(line, symbol):
    count = 0
    string_flag = False
    char_flag = False
    for i in range(len(line)):
        if (
            line[i] == "/"
            and i + 1 < len(line)
            and line[i + 1] == "/"
            and not string_flag
            and not char_flag
        ):
            break
        if line[i] == '"' and (i == 0 or line[i - 1] != "\\"):
            string_flag = not string_flag
        if line[i] == "'" and (i == 0 or line[i - 1] != "\\") and not string_flag:
            char_flag = not char_flag
        if string_flag or char_flag:
            continue
        if line[i] == symbol:
            count = count + 1
    return count


def context_equal(node1, node2):
    if type(node1) != type(node2):
        return False
    if isinstance(node1, list):
        if len(node1) != len(node2):
            return False
        for i in range(len(node1)):
            if not context_equal(node1[i], node2[i]):
                return False
    elif isinstance(node1, javalang.tree.Node):
        for attr in node1.attrs:
            if attr == "documentation" or attr == "annotations":
                continue
            if not context_equal(getattr(node1, attr), getattr(node2, attr)):
                return False
    else:
        return node1 == node2
    return True


if __name__ == "__main__":

    if not os.path.exists(compilation_unverified_commits_path):
        os.makedirs(compilation_unverified_commits_path)

    repo_names = []
    with open(repo_list, "r", encoding="utf-8") as f:
        repo_names = [l.strip() for l in f.readlines()]

    for repo_name in repo_names:
        clone_repo(repo_name)
        print(f"Processing: {repo_name}")

        unverified_samples_json_path = os.path.join(
            compilation_unverified_commits_path,
            f"unverified_{repo_name.replace('/', '_')}.json",
        )
        repo_path = os.path.join(repo_store_path, repo_name)
        git_repo = Repo(repo_path)

        commits_date_filter = list(
            git_repo.iter_commits(
                since=datetime.strptime(data_leakage_date, "%Y-%m-%d")
            )
        )
        commits_date_filter = strim_commits(
            commits_date_filter, {"repo_path": repo_path}
        )
        samples_coevo_filter = []

        with multiprocessing.Pool(processes=num_cores) as process_pool:
            for r in tqdm(
                process_pool.imap(static_filter, commits_date_filter),
                total=len(commits_date_filter),
                desc="Performing static analysis",
            ):
                if r["tag"] == FILTERED:
                    continue
                elif r["tag"] == SUCCESS:
                    samples_coevo_filter += r["samples"]
                elif r["tag"] == EXCEPTION:
                    exps.append(r["exp"])
        for k, v in enumerate(samples_coevo_filter):
            v["test_id"] = k
            v["repo_name"] = repo_name
        if len(samples_coevo_filter) >= 30:
            with open(unverified_samples_json_path, "w") as f:
                json.dump(samples_coevo_filter, f, indent=2)
        with open("./exception.json", "w") as f:
            json.dump(exps, f, indent=2)
