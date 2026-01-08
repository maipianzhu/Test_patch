import subprocess
import json
import os
from typing import Dict, List, Tuple, Optional


class DiscoveryManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir
        # 元数据存放在 RepoB 的根目录下
        self.metadata_path = os.path.join(repo_b_dir, ".sync_metadata.json")

    def run_git(self, args: List[str], cwd: str) -> str:
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            return ""  # 或者抛出异常，视情况而定
        return result.stdout

    def ensure_local_repo(self, path_or_url: str, name: str) -> str:
        if path_or_url.startswith(("http", "git@")):
            home = os.path.expanduser("~")
            workspace = os.path.join(home, ".git_sync_agent_workspace")
            os.makedirs(workspace, exist_ok=True)
            local_path = os.path.join(workspace, name)

            if not os.path.exists(local_path):
                print(f"正在克隆 {name}...")
                subprocess.run(["git", "clone", path_or_url, local_path], check=True)
            else:
                print(f"正在深度同步 {name} 远程状态...")
                # 1. 获取远程最新数据
                subprocess.run(["git", "fetch", "origin"], cwd=local_path, check=True)

                # 2. 【核心修复】强制将本地分支重置为远程分支的状态
                # 假设分支名为 main（如果是 master 请修改）
                # 这步会确保本地代码和远程 GitHub 上的代码一模一样
                branch = "main"
                subprocess.run(
                    ["git", "reset", "--hard", f"origin/{branch}"],
                    cwd=local_path,
                    check=True,
                )

                # 3. 清理可能存在的未跟踪文件（防止干扰补丁）
                subprocess.run(["git", "clean", "-fd"], cwd=local_path, check=True)

            return local_path
        return os.path.abspath(path_or_url)

    def get_fingerprint(self, cwd: str, commit_ish: str = "HEAD") -> Dict[str, str]:
        output = self.run_git(["ls-tree", "-r", commit_ish], cwd)
        fingerprint = {}
        for line in output.splitlines():
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                fingerprint[parts[3]] = parts[2]
        return fingerprint

    def find_best_match(self, max_search_depth: int = 100) -> Tuple[str, float]:
        target_fp = self.get_fingerprint(self.repo_b_dir)
        if not target_fp:
            return "", 0.0

        commits = self.run_git(
            ["rev-list", "HEAD", f"--max-count={max_search_depth}"], self.repo_a_dir
        ).splitlines()
        best_commit, max_score = "", -1.0

        for cid in commits:
            a_fp = self.get_fingerprint(self.repo_a_dir, cid)
            matches = sum(1 for p, h in target_fp.items() if a_fp.get(p) == h)
            score = matches / len(target_fp)
            if score >= 1.0:
                return cid, 1.0
            if score > max_score:
                max_score, best_commit = score, cid
        return best_commit, max_score

    def load_metadata(self) -> Optional[str]:
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, "r") as f:
                return json.load(f).get("last_synced_commit_repo_a")
        return None

    def save_metadata(self, commit_id: str):
        with open(self.metadata_path, "w") as f:
            json.dump({"last_synced_commit_repo_a": commit_id}, f, indent=2)

    def get_pending_commits(self, base_commit: str) -> List[str]:
        """
        获取从 base 到 远程最新提交 之间的所有 commit id
        """
        # 1. 首先确保本地已经拿到了远程的最新的提交信息
        self.run_git(["fetch", "origin"], self.repo_a_dir)

        # 2. 对比时，使用 origin/main (或者你指定的远程分支名) 而不是 HEAD
        # 这样才能发现你在 GitHub 上新提交的代码
        remote_branch = "origin/main"  # 假设主分支是 main

        output = self.run_git(
            ["rev-list", f"{base_commit}..{remote_branch}", "--reverse"],
            self.repo_a_dir,
        )
        return output.splitlines() if output else []


class PatchManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir

    def run_git(self, args: List[str], cwd: str) -> str:
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        # 核心修改：移除 .strip()，原样返回输出以保护补丁格式
        return result.stdout

    def generate_patch(self, commit_id: str) -> str:
        """
        生成补丁，移除末尾多余的 strip
        """
        # 注意：这里也移除了末尾的 .strip()
        return self.run_git(
            [
                "show",
                commit_id,
                "--patch",
                "--binary",
                "--full-index",
                "--no-color",
                "--pretty=format:",
                "--",
                ".",
                ":!workspace",
                ":!**/workspace/**",
                ":!backend/workspace",
                ":!checkpoints.db*",
            ],
            self.repo_a_dir,
        )

    def apply_patch_attempt(self, patch_content: str) -> Tuple[bool, str]:
        # 增加校验，防止传入空字符串
        if not patch_content or not patch_content.strip():
            return True, "Empty patch"

        patch_path = os.path.join(self.repo_b_dir, "temp_sync.patch")
        # 使用 newline='' 确保换行符不被系统修改（跨平台兼容）
        with open(patch_path, "w", encoding="utf-8", newline="") as f:
            f.write(patch_content)

        all_errors = []
        # 增加 --recount 参数，这会让 Git 尝试自动修正小的格式错误
        for p_level in ["1", "2"]:
            try:
                subprocess.run(
                    [
                        "git",
                        "apply",
                        f"-p{p_level}",
                        "--3way",
                        "--recount",
                        "--whitespace=nowarn",
                        "temp_sync.patch",
                    ],
                    cwd=self.repo_b_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                print(f"DEBUG: 使用 -p{p_level} 成功应用补丁")
                return True, ""
            except subprocess.CalledProcessError as e:
                all_errors.append(f"[-p{p_level}] {e.stderr}")

        return False, "\n".join(all_errors)

    def get_commit_metadata(self, commit_id: str) -> Dict[str, str]:
        # 在这里手动 strip 结果，因为元数据需要清理空格
        author_name = self.run_git(
            ["log", "-1", "--format=%an", commit_id], self.repo_a_dir
        ).strip()
        author_email = self.run_git(
            ["log", "-1", "--format=%ae", commit_id], self.repo_a_dir
        ).strip()
        subject = self.run_git(
            ["log", "-1", "--format=%s", commit_id], self.repo_a_dir
        ).strip()
        body = self.run_git(["log", "-1", "--format=%b", commit_id], self.repo_a_dir)

        return {
            "author": f"{author_name} <{author_email}>",
            "message": f"{subject}\n\n{body}".strip(),
        }

    # ... 其余方法保持不变，但确保调用 run_git 后如果需要处理路径名，手动加上 .strip() ...

    def commit_with_metadata(self, metadata: Dict[str, str]):
        """
        在 RepoB 中使用指定的元数据提交代码
        """
        # 1. 先 git add
        self.run_git(["add", "."], self.repo_b_dir)

        # 2. 构造 commit 命令，指定作者
        # --author="Name <email>" 可以伪造/还原原作者
        cmd = [
            "commit",
            f"--author={metadata['author']}",
            "-m",
            metadata["message"],
            "--no-verify",  # 跳过可能的 pre-commit hook
        ]
        self.run_git(cmd, self.repo_b_dir)

    def push_to_remote(self):
        """
        将本地工作区的改动推送到远程仓库
        """
        # 这里的 origin 是 git clone 时默认建立的远程引用
        # HEAD 代表推送当前分支
        result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=self.repo_b_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Exception(f"推送远程仓库失败: {result.stderr}")
        return result.stdout
