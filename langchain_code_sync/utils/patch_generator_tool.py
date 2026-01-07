"""
git操作工具
"""

import subprocess
import os
import shutil


import hashlib


class RepoSyncTool:
    def _run_git(self, repo_path, command):
        """执行Git命令的辅助函数"""
        try:
            result = subprocess.run(
                command,
                cwd=repo_path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(f"Git Error in {repo_path}: {e.stderr.strip()}")

    def _is_url(self, path):
        """Check if the path is a git URL (http, https, ssh, git)"""
        if not path:
            return False
        path = path.strip()
        return path.startswith(("http://", "https://", "git@", "ssh://"))

    def _ensure_local(self, path):
        """
        If path is a URL, clone it to a temp dir and return the local path.
        Otherwise return the path as is.
        """
        if not self._is_url(path):
            if not os.path.exists(path):
                raise Exception(f"Local path does not exist: {path}")
            return path

        # It's a URL, clone it
        repo_name = path.split("/")[-1].replace(".git", "")
        # Create a unique hash for the URL to avoid collisions if names are same
        url_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        temp_dir = f"/tmp/langchain_code_sync_repos/{repo_name}_{url_hash}"

        if not os.path.exists(temp_dir):
            print(f"Cloning remote repo {path} to {temp_dir}...")
            os.makedirs(os.path.dirname(temp_dir), exist_ok=True)
            subprocess.run(f"git clone {path} {temp_dir}", shell=True, check=True)
        else:
            # Optionally pull latest if it exists
            # For safety, we might want to check if it matches the remote,
            # here we assume simple caching and pull.
            print(f"Updating remote repo copy at {temp_dir}...")
            self._run_git(temp_dir, "git pull")

        return temp_dir

    def get_commit_hash(self, repo_path, revision="HEAD"):
        """获取指定引用的完成 commit Hash"""
        return self._run_git(repo_path, f"git rev-parse {revision}")

    def get_tree_hash(self, repo_path, revision="HEAD"):
        """Get the tree hash of a specific revision"""
        return self._run_git(repo_path, f"git rev-parse {revision}^{{tree}}")

    def _find_commit_with_tree(self, repo_path, tree_hash):
        """
        Search for a commit in repo_path that has the specified tree_hash.
        Returns the commit hash if found, else None.
        """
        # Get all commits with their tree hashes: "tree_hash commit_hash"
        # We limit to recent history for performance, e.g., last 500 commits?
        # Or search all if needed. Let's try --all but maybe limit if slow.
        try:
            cmd = f"git log --all --format='%T %H'"
            output = self._run_git(repo_path, cmd)
            for line in output.splitlines():
                parts = line.strip().split()
                if len(parts) == 2:
                    t_hash, c_hash = parts
                    if t_hash == tree_hash:
                        return c_hash
            return None
        except Exception:
            return None

    def generate_incremental_patches(
        self, source_repo, target_repo, output_dir, start_commit_id=None
    ):
        """
        对比两个仓库，生成增量 Patch
        :param source_repo: 代码较新的仓库路径 (Repo A) OR Remote URL
        :param target_repo: 代码较旧的仓库路径 (Repo B) OR Remote URL
        :param output_dir: 补丁存放目录
        :param start_commit_id: (Optional) Manually specified baseline commit from Source Repo
        """
        print(
            f"DEBUG: Generating patches. Source: '{source_repo}', Target: '{target_repo}', StartCommit: '{start_commit_id}'"
        )
        try:
            # Ensure we have local copies
            source_repo = self._ensure_local(source_repo)
            target_repo = self._ensure_local(target_repo)
            print(
                f"DEBUG: Local paths - Source: '{source_repo}', Target: '{target_repo}'"
            )
        except Exception as e:
            return f"Error accessing repositories: {e}"

        # 1、确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        else:
            # 清理旧patch，防止混淆
            for f in os.listdir(output_dir):
                if f.endswith(".patch"):
                    os.remove(os.path.join(output_dir, f))

        try:
            base_commit = None
            target_head = None  # Initialize to avoid UnboundLocalError

            # 0. Check for Manual Start Commit
            if start_commit_id:
                start_commit_id = start_commit_id.strip()
                if start_commit_id:
                    print(f"DEBUG: Using manual start commit: {start_commit_id}")
                    if self._commit_exists(source_repo, start_commit_id):
                        base_commit = start_commit_id
                    else:
                        return f"失败：指定的起始 Commit ID ({start_commit_id}) 在源仓库中不存在。"

            if not base_commit:
                # 2、获取目标仓库（repoB）的最新版本
                target_head = self.get_commit_hash(target_repo)

                # 3、检查源仓库（repoA）是否包含这个 commit
                if self._commit_exists(source_repo, target_head):
                    base_commit = target_head
            else:
                if target_head:
                    print(
                        f"Target head {target_head} not found in Source (Different Commit IDs)."
                    )
                print("Attempting to match via Tree Hash (Content Similarity)...")

                # Try to find a commit in Source that has the SAME Tree Hash as Target HEAD
                if not target_head:
                    target_head = self.get_commit_hash(target_repo)

                target_tree = self.get_tree_hash(target_repo, target_head)
                matching_commit = self._find_commit_with_tree(source_repo, target_tree)

                if matching_commit:
                    print(
                        f"Found content-identical commit in Source: {matching_commit}"
                    )
                    base_commit = matching_commit
                else:
                    print(
                        "Tree Hash match failed. Searching for common ancestor (graph)..."
                    )
                    common_commit = self._find_common_ancestor(source_repo, target_repo)
                    if common_commit:
                        print(f"Found common ancestor: {common_commit}")
                        base_commit = common_commit

            if not base_commit:
                return "失败：无法找到共同的基准 (Commit ID 或 Tree Hash 均不匹配)，无法增量同步。"

            # 4、在源仓库生成Patch
            cmd = f"git format-patch {base_commit}..HEAD -o {output_dir}"
            patch_list = self._run_git(source_repo, cmd)

            if not patch_list:
                return (
                    "没有检测到差异，两个仓库可能已经同步，或者源仓库没有更新的提交。"
                )

            # 统计生成了多少个文件
            count = len(patch_list.splitlines())
            return f"成功生成 {count} 个 Patch 文件，保存在: {output_dir}\n基准 Commit: {base_commit}"

        except Exception as e:
            if target_head and (
                "unknown revision" in str(e) or "bad revision" in str(e)
            ):
                return f"失败：源仓库中找不到目标仓库的 Commit ({target_head})。这意味着两个仓库的历史不相关，或者发生了 Rebase，无法自动增量同步。"
            return f"执行出错: {str(e)}"

    def apply_patch(self, repo_path, patch_path):
        """
        在指定仓库应用Patch
        :param repo_path: 目标仓库路径
        :param patch_path: patch文件绝对路径
        :return: (success: bool, message: str)
        """
        try:
            repo_path = self._ensure_local(repo_path)
            # 1. Check
            self._run_git(repo_path, f"git apply --check {patch_path}")
            # 2. Apply if check passed
            self._run_git(repo_path, f"git apply {patch_path}")
            return True, "Patch应用成功"
        except Exception as e:
            # git apply 失败，通常包含 conflict 信息
            return False, f"Patch应用失败: {str(e)}"

    def check_verify_conflict(self, repo_path):
        """
        辅助检查是否存在未解决的冲突文件 (.rej)
        """
        try:
            # For verifying conflicts, we need to look at the same path
            # where apply_patch was executed.
            # However, _ensure_local returns a temp path for URLs.
            # If the user passed a URL for target_repo, we must ensure
            # we are checking the SAME temp directory.
            # Since _ensure_local is deterministic (based on hash),
            # calling it again should return the same path.
            repo_path = self._ensure_local(repo_path)

            # git apply --reject 会生成 .rej 文件
            # 这里简单列出所有 .rej 文件
            result = self._run_git(repo_path, "find . -name '*.rej'")
            if result:
                files = [f.strip() for f in result.splitlines() if f.strip()]
                return True, files
            return False, []
        except Exception:
            return False, []

    def _commit_exists(self, repo_path, commit_hash):
        try:
            self._run_git(repo_path, f"git cat-file -e {commit_hash}")
            return True
        except Exception:
            return False

    def _find_common_ancestor(self, source_repo, target_repo):
        """
        Finds the most recent commit in target_repo that also exists in source_repo.
        """
        try:
            # Get log of target repo (first 100 commits to be safe)
            log_output = self._run_git(target_repo, "git log -n 100 --format='%H'")
            target_commits = log_output.splitlines()

            for commit in target_commits:
                commit = commit.strip("'").strip()  # clean up formatting
                if self._commit_exists(source_repo, commit):
                    return commit

            # Fallback: try git merge-base if they were related?
            # But they are unrelated repos on disk.
            return None
        except Exception as e:
            print(f"Error finding common ancestor: {e}")
            return None


# 实例化
sync_tool = RepoSyncTool()
