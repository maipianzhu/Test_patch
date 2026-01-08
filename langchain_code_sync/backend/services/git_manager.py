import subprocess
import json
import os
import hashlib
from typing import Dict, List, Tuple, Optional


class DiscoveryManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir

    def _update_paths(self, local_a: str, local_b: str):
        """转换路径后更新变量"""
        self.repo_a_dir = local_a
        self.repo_b_dir = local_b
        self.metadata_path = os.path.join(local_b, ".sync_metadata.json")

    def run_git(self, args: List[str], cwd: str) -> str:
        """Discovery 专用的文本模式命令"""
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        return result.stdout if result.returncode == 0 else ""

    def ensure_local_repo(self, path_or_url: str, name_hint: str) -> str:
        """URL 转 Hash 路径并克隆/同步"""
        if path_or_url.startswith(("http", "git@")):
            url_hash = hashlib.sha256(path_or_url.encode("utf-8")).hexdigest()[:12]
            repo_name = path_or_url.split("/")[-1].replace(".git", "")
            home = os.path.expanduser("~")
            workspace = os.path.join(home, ".git_sync_agent_workspace")
            local_path = os.path.join(workspace, f"{repo_name}_{url_hash}")

            os.makedirs(workspace, exist_ok=True)
            if not os.path.exists(local_path):
                subprocess.run(["git", "clone", path_or_url, local_path], check=True)
            else:
                subprocess.run(["git", "fetch", "origin"], cwd=local_path, check=True)
                # 自动获取远程主分支名并重置
                res = subprocess.run(
                    ["git", "remote", "show", "origin"],
                    cwd=local_path,
                    capture_output=True,
                    text=True,
                )
                branch = "main" if "HEAD branch: main" in res.stdout else "master"
                subprocess.run(
                    ["git", "reset", "--hard", f"origin/{branch}"],
                    cwd=local_path,
                    check=True,
                )
            return local_path
        return os.path.abspath(path_or_url)

    def load_metadata(self) -> Optional[str]:
        if hasattr(self, "metadata_path") and os.path.exists(self.metadata_path):
            with open(self.metadata_path, "r") as f:
                return json.load(f).get("last_synced_commit_repo_a")
        return None

    def find_best_match(self, max_search_depth: int = 100) -> Tuple[str, float]:
        # 指纹识别逻辑... (保持你之前的逻辑，使用 self.run_git)
        target_fp = self._get_fingerprint(self.repo_b_dir)
        commits = self.run_git(
            ["rev-list", "HEAD", f"--max-count={max_search_depth}"], self.repo_a_dir
        ).splitlines()
        best_commit, max_score = "", -1.0
        for cid in commits:
            a_fp = self._get_fingerprint(self.repo_a_dir, cid)
            matches = sum(1 for p, h in target_fp.items() if a_fp.get(p) == h)
            score = matches / len(target_fp) if target_fp else 0
            if score >= 1.0:
                return cid, 1.0
            if score > max_score:
                max_score, best_commit = score, cid
        return best_commit, max_score

    def _get_fingerprint(self, cwd: str, commit_ish: str = "HEAD"):
        out = self.run_git(["ls-tree", "-r", commit_ish], cwd)
        return {
            line.split(maxsplit=3)[3]: line.split(maxsplit=3)[2]
            for line in out.splitlines()
            if len(line.split()) >= 4
        }

    def get_pending_commits(self, base_commit: str) -> List[str]:
        """
        强制从远程获取最新列表，确保不被本地过时的 HEAD 欺骗
        """
        # 1. 必须先 fetch，否则本地永远看不到 GitHub 上的 311eb8d
        subprocess.run(["git", "fetch", "origin"], cwd=self.repo_a_dir, check=True)

        # 2. 【核心修改】使用 origin/main 进行比对，而不是 HEAD
        # 这确保了你能发现 88c579 到 311eb8d 之间的那个增量
        output = self.run_git(
            ["rev-list", f"{base_commit}..origin/main", "--reverse"], self.repo_a_dir
        ).strip()

        commits = output.splitlines() if output else []
        print(f"DEBUG: 从 {base_commit[:8]} 到 origin/main 发现 {len(commits)} 个提交")
        return commits

    def save_metadata(self, commit_id: str):
        """
        保存已同步的 Commit ID 到元数据文件
        """
        # 确保 repo_b_dir 是物理路径且存在
        if not self.repo_b_dir or not os.path.exists(self.repo_b_dir):
            # 兜底逻辑：如果路径没初始化，尝试即时推导（虽然正常流程应该已经初始化了）
            print("DEBUG: save_metadata 路径异常，尝试自动定位...")

        path = os.path.join(self.repo_b_dir, ".sync_metadata.json")
        print(f"DEBUG: 正在保存元数据 -> {path}")

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"last_synced_commit_repo_a": commit_id}, f, indent=2)

    def get_remote_head(self) -> str:
        """获取 Repo A 远程仓库真实的最新 Commit ID"""
        # 再次执行 fetch 确保数据最新
        subprocess.run(["git", "fetch", "origin"], cwd=self.repo_a_dir, check=True)
        return self.run_git(["rev-parse", "origin/main"], self.repo_a_dir).strip()


class PatchManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir

    def _run_git_raw(self, args: List[str], cwd: str) -> bytes:
        """二进制模式运行，专门用于 Patch"""
        return subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=False
        ).stdout

    def _run_git_text(self, args: List[str], cwd: str) -> str:
        """文本模式运行，用于 log/commit"""
        res = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        return res.stdout

    def generate_patch(self, commit_id: str) -> bytes:
        """生成二进制补丁"""
        return self._run_git_raw(
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
                ":!checkpoints.db*",
            ],
            self.repo_a_dir,
        )

    def apply_patch_attempt(self, patch_bytes: bytes) -> Tuple[bool, str]:
        """关键修复：使用 wb 模式写入字节流"""
        if not patch_bytes or len(patch_bytes) < 10:
            return True, ""
        patch_path = os.path.join(self.repo_b_dir, "temp_sync.patch")

        # --- 核心修复：wb 代表 write binary ---
        with open(patch_path, "wb") as f:
            f.write(patch_bytes)

        errors = []
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
                return True, ""
            except subprocess.CalledProcessError as e:
                errors.append(e.stderr)
        return False, "\n".join(errors)

    def get_conflict_files(self) -> List[str]:
        out = self._run_git_text(
            ["diff", "--name-only", "--diff-filter=U"], self.repo_b_dir
        )
        return out.strip().splitlines()

    def get_three_way_content(self, file_path: str) -> Dict[str, str]:
        contents = {}
        for stage, label in [("1", "base"), ("2", "ours"), ("3", "theirs")]:
            raw = self._run_git_raw(["show", f":{stage}:{file_path}"], self.repo_b_dir)
            contents[label] = raw.decode("utf-8", errors="replace")
        return contents

    def get_commit_metadata(self, commit_id: str) -> Dict[str, str]:
        author = self._run_git_text(
            ["log", "-1", "--format=%an <%ae>", commit_id], self.repo_a_dir
        ).strip()
        msg = self._run_git_text(
            ["log", "-1", "--format=%B", commit_id], self.repo_a_dir
        ).strip()
        return {"author": author, "message": msg}

    def commit_with_metadata(self, metadata: Dict[str, str]):
        self._run_git_text(["add", "."], self.repo_b_dir)
        self._run_git_text(
            [
                "commit",
                f"--author={metadata['author']}",
                "-m",
                metadata["message"],
                "--no-verify",
            ],
            self.repo_b_dir,
        )

    def save_metadata(self, commit_id: str):
        path = os.path.join(self.repo_b_dir, ".sync_metadata.json")
        with open(path, "w") as f:
            json.dump({"last_synced_commit_repo_a": commit_id}, f, indent=2)

    def push_to_remote(self):
        subprocess.run(
            ["git", "push", "origin", "HEAD", "--force"],
            cwd=self.repo_b_dir,
            check=True,
        )

    def resolve_file_manually(self, file_path: str, final_content: str):
        """
        将用户在 UI 上修好的代码写入物理文件,并标记为已解决(git add)
        """
        # 1. 确定文件的绝对路径
        full_path = os.path.join(self.repo_b_dir, file_path)

        # 2. 写入用户修改后的内容（使用 utf-8 文本模式）
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        # 3. 执行 git add 将文件标记为已解决冲突状态
        # 确保你使用的是类中定义的运行 git 的方法（例如 _run_git_text 或 run_git）
        # 这里建议调用内部定义的命令执行函数
        self._run_git_text(["add", file_path], self.repo_b_dir)
        print(f"DEBUG: 已手动解决并 add 文件: {file_path}")

    def is_all_resolved(self) -> bool:
        """检查是否所有冲突都已经 git add 过了"""
        # 如果 get_conflict_files 返回空列表，说明没有处于 Unmerged 状态的文件了
        return len(self.get_conflict_files()) == 0
