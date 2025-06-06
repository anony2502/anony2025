"""
Manage git repositories by GitPython
"""

import os, git, json, re
from git import Repo, Diff, Commit
from .configs import REPO_BASE
from .multilspy.multilspy_types import Position
from .formatter import formatted_java_code, formatted_java_code_with_pos
from .helper import get_diff, line_range_from_diff
from .logger import logger


class Progress(git.remote.RemoteProgress):
    def __init__(self):
        super().__init__()

    def update(self, op_code, cur_count, max_count=None, message=""):
        if len(message) != 0:
            if cur_count == max_count:
                print(self._cur_line)
            else:
                print(self._cur_line, end="\r")

    def finalize(self):
        print(self._cur_line)


class UpdateRepo(Repo):

    def __init__(self, path: str, commit_id: str):
        self.commit_id = commit_id
        super().__init__(path)
        self.git.checkout(commit_id, f=True)
        logger.info(f"-> Repo head commit at: {commit_id[:6]}.")

    def checkout_src(self):
        # not suggest: checkout to the commit before commit_id
        logger.info(f"-> Repo checkouts to the src commit.")
        self.git.checkout(self.commit_id + "^")

    def checkout_tgt(self):
        # not suggest: checkout to the commit before commit_id
        logger.info(f"-> Repo checkouts to the tgt commit.")
        self.git.checkout(self.commit_id)

    def get_file_src(self, rel_path: str) -> str:
        if self.head.commit.hexsha != self.commit_id:
            self.checkout_tgt()
        commit = self.head.commit.parents[0]
        # check whether the file exists in the src commit
        try:
            blob = commit.tree[rel_path]
            return blob.data_stream.read().decode()
        except:
            return ""

    def get_file_tgt(self, rel_path: str) -> str:
        if self.head.commit.hexsha != self.commit_id:
            self.checkout_tgt()
        # check whether the file exists in the src commit
        commit = self.head.commit
        try:
            blob = commit.tree[rel_path]
            return blob.data_stream.read().decode()
        except:
            return ""

    # Return the diff of the given file path between the src and tgt commit
    def get_file_diff(self, rel_path: str, unified=0) -> str:
        if self.head.commit.hexsha != self.commit_id:
            self.checkout_tgt()
        diffs: list[Diff] = self.head.commit.diff(
            "HEAD~1",
            paths=rel_path,
            create_patch=True,
            R=True,
            unified=unified,
        )
        if not diffs:
            return ""
        return diffs[0].diff.decode()

    # return the diff item of the given target position
    # format to transform method_inovation into one line
    # This is used for constructing UsageCtx
    def get_diff_from_pos(
        self,
        rel_path: str,
        pos: Position,
        collect_before: bool = False,
        collect_after: bool = False,
    ) -> str:
        """
        Get the differences between the source code and target code at the given target position.

            Args:
                rel_path (str): The relative path of the file.
                pos (Position): The position in the target file.
                collect_before (bool): Whether to include the context before the target position.
                collect_after (bool): Whether to include the context after the target position.

            Returns:
                str: The differences between the source code and target code at the given position.
        """
        file_src = self.get_file_src(rel_path)
        file_src_fmt = formatted_java_code(file_src)

        file_tgt = self.get_file_tgt(rel_path)
        file_tgt_fmt, pos_fmt = formatted_java_code_with_pos(file_tgt, cursor_pos=pos)
        # print(f"Formatted position: {pos_fmt}")

        # we consider that the number of context for target position is 4
        diff_list = get_diff(file_src_fmt, file_tgt_fmt, n=3).splitlines()
        add_pattern = re.compile(r"@@.*\+(\d+)(,\d+)? @@")
        # the target diff item without comments
        clean_diff: list[str] = []
        # the target position index in the target diff item
        target_idx = -1
        flag = False
        for line in diff_list:
            if flag:
                if line.startswith("@@"):
                    break
                clean_line = line.lstrip("-").lstrip("+").lstrip()
                if not clean_line:
                    continue
                # add clean line to the diff item
                if line[0] == "-" or line[0] == "+":
                    if clean_line[0] not in {"*", "/"}:
                        clean_diff.append(line)
                # check target line
                if line[0] != "-":
                    if add_cur == pos_fmt["line"]:
                        # If the target line is a comment line, return empty string
                        if clean_line[0] not in {"*", "/"}:
                            # add the invocation line if unchanged(contexts changed)
                            if line[0] != "-" and line[0] != "+":
                                clean_diff.append(line)
                            target_idx = len(clean_diff) - 1
                    add_cur += 1

            if line.startswith(f"@@") and "+" in line:
                match = add_pattern.match(line)
                # diff line index from 1
                add_start = eval(match.group(1)) - 1
                add_numstr = match.group(2)
                add_num = eval(add_numstr[1:]) if add_numstr else 1
                if add_start <= pos_fmt["line"] < add_start + add_num:
                    # print(line)
                    add_cur = add_start
                    flag = True
        if not clean_diff and target_idx == -1:
            return ""

        # filter before(after) by context_type
        if collect_before and not collect_after:
            max_lines = 5
            filter_diff = clean_diff[: target_idx + 1]
        elif collect_after and not collect_before:
            max_lines = 5
            filter_diff = clean_diff[target_idx:]
            target_idx = 0
        elif collect_before and collect_after:
            max_lines = 10
            filter_diff = clean_diff
        else:
            max_lines = 5
            start_ln, end_ln = line_range_from_diff(clean_diff, target_idx)
            # the last statement should be the invokement line
            end_ln = target_idx
            target_idx = target_idx - start_ln
            filter_diff = clean_diff[start_ln : end_ln + 1]

        # filter the context lines by contexts limit
        if len(filter_diff) > max_lines:
            half_lines = max_lines // 2
            lower_bound = max(0, target_idx - half_lines)
            upper_bound = min(len(filter_diff), target_idx + half_lines)
            # adjust to the max_lines
            if upper_bound - lower_bound < max_lines:
                if lower_bound > 0:
                    lower_bound = max(0, upper_bound - max_lines)
                elif upper_bound < len(filter_diff):
                    upper_bound = min(len(filter_diff), lower_bound + max_lines)
            filter_diff = filter_diff[lower_bound:upper_bound]

        return "\n".join(filter_diff)


def setup_repo(
    repo_name: str, commit_id: str, repo_base=REPO_BASE, do_clone=False
) -> UpdateRepo:
    repo_root = os.path.join(repo_base, repo_name)
    if os.path.exists(repo_root):
        logger.info(f"Load Repo existing at {repo_root}")
        repo = UpdateRepo(repo_root, commit_id)
        return repo
    else:
        if do_clone:
            repo_url = f"https://github.com/{repo_name}.git"
            logger.info(f"Cloning Repo from {repo_url}")
            Repo.clone_from(repo_url, repo_root, progress=Progress())
            logger.info(f"Repo is cloned at {repo_root}")
            repo = UpdateRepo(repo_root, commit_id)
            return repo
        else:
            assert (
                False
            ), f"Repo not found at {repo_root}, set do_clone=True to clone the repo."

def setup_repos_from_names(repo_names: list[str], repo_base=REPO_BASE):
    error_list = []
    total_count = len(repo_names)
    logger.info(f"Repos total counts: {total_count}.")
    for i, repo_name in enumerate(repo_names):
        logger.info(f"Setup Repo-{i}/{total_count}: {repo_name}")
        try:
            repo_root = os.path.join(repo_base, repo_name)
            if os.path.exists(repo_root):
                logger.info(f"Repo exists at {repo_root}")
                continue
            else:
                repo_url = f"https://github.com/{repo_name}.git"
                logger.info(f"Cloning Repo from {repo_url}")
                Repo.clone_from(repo_url, repo_root, progress=Progress())
                logger.info(f"Repo is cloned at {repo_root}")
        except Exception as e:
            error_list.append(repo_name)
    logger.info(
        f"Setup {len(repo_names)} repos, {len(error_list)} failed.\nFailed Repos: {', '.join(error_list)}"
    )