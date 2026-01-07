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
        return result.stdout.strip()

    def ensure_local_repo(self, path_or_url: str, name: str) -> str:
        """确保仓库在本地，如果是 URL 则克隆"""
        if path_or_url.startswith(("http", "git@")):
            workspace = os.path.abspath("workspace")
            os.makedirs(workspace, exist_ok=True)
            local_path = os.path.join(workspace, name)

            if not os.path.exists(local_path):
                print(f"Cloning {name}...")
                subprocess.run(["git", "clone", path_or_url, local_path], check=True)
            else:
                print(f"Updating {name}...")
                subprocess.run(["git", "fetch", "--all"], cwd=local_path, check=True)
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
        """获取从 base 到最新的所有 commit id"""
        output = self.run_git(
            ["rev-list", f"{base_commit}..HEAD", "--reverse"], self.repo_a_dir
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
        return result.stdout.strip()

    def generate_patch(self, commit_id: str) -> str:
        """
        使用 format-patch 生成标准补丁，它包含完整的元数据和差异
        """
        # --stdout 将补丁输出到字符串
        # -1 表示针对这一个 commit
        return self.run_git(
            ["format-patch", "-1", "--stdout", commit_id], self.repo_a_dir
        )

    def apply_patch_attempt(self, patch_content: str) -> Tuple[bool, str]:
        patch_path = os.path.join(self.repo_b_dir, "temp_sync.patch")
        with open(patch_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(patch_content)

        try:
            # --- 关键修改：更宽容的参数 ---
            # --3way: 允许三路合并
            # --whitespace=nowarn: 忽略行尾空格报错（解决你的报错的关键）
            # --reject: 如果补丁应用失败，强制生成 .rej 文件（这能保证我们拿到冲突信息）
            subprocess.run(
                ["git", "apply", "--3way", "--whitespace=nowarn", "temp_sync.patch"],
                cwd=self.repo_b_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return True, ""
        except subprocess.CalledProcessError as e:
            # 即便报错，我们也检查一下是否有文件冲突（git 可能会部分应用）
            return False, e.stderr

    def get_conflict_files(self) -> List[str]:
        """获取当前冲突的文件列表"""
        output = self.run_git(
            ["diff", "--name-only", "--diff-filter=U"], self.repo_b_dir
        )
        return output.splitlines()

    def get_three_way_content(self, file_path: str) -> Dict[str, str]:
        """
        核心逻辑：从 Git 暂存区提取三个阶段的内容
        Stage 1: Base (共同祖先)
        Stage 2: Ours (RepoB 当前)
        Stage 3: Theirs (RepoA 补丁)
        """
        contents = {}
        for stage, label in [("1", "base"), ("2", "ours"), ("3", "theirs")]:
            try:
                # git show :stage:path 获取特定阶段的文件内容
                content = self.run_git(
                    ["show", f":{stage}:{file_path}"], self.repo_b_dir
                )
                contents[label] = content
            except:
                contents[label] = ""  # 如果该阶段不存在（例如新增文件）
        return contents

    def resolve_file_manually(self, file_path: str, final_content: str):
        """
        将用户在 UI 上修好的代码写入物理文件，并标记为已解决
        """
        full_path = os.path.join(self.repo_b_dir, file_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        # 必须执行 git add，告诉 git 冲突已解决
        self.run_git(["add", file_path], self.repo_b_dir)

    def is_all_resolved(self) -> bool:
        """检查是否所有冲突都已 add"""
        conflicts = self.get_conflict_files()
        return len(conflicts) == 0

    def get_commit_metadata(self, commit_id: str) -> Dict[str, str]:
        """
        从 RepoA 获取该提交的作者、邮箱和描述信息
        """
        # %an: 作者名, %ae: 邮箱, %s: 主题, %b: 正文
        author_name = self.run_git(
            ["log", "-1", "--format=%an", commit_id], self.repo_a_dir
        )
        author_email = self.run_git(
            ["log", "-1", "--format=%ae", commit_id], self.repo_a_dir
        )
        subject = self.run_git(["log", "-1", "--format=%s", commit_id], self.repo_a_dir)
        body = self.run_git(["log", "-1", "--format=%b", commit_id], self.repo_a_dir)

        return {
            "author": f"{author_name} <{author_email}>",
            "message": f"{subject}\n\n{body}".strip(),
        }

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
