import subprocess
import json
import os
from typing import Dict, List, Tuple, Optional


class DiscoveryManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir
        self.metadata_path = os.path.join(repo_b_dir, ".sync_metadata.json")

    def run_git(self, args: List[str], cwd: str) -> str:
        """运行 Git 命令并返回输出"""
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            raise Exception(f"Git command failed: {result.stderr}")
        return result.stdout.strip()

    def get_fingerprint(self, cwd: str, commit_ish: str = "HEAD") -> Dict[str, str]:
        """
        获取指纹：返回 {文件路径: 内容Hash}
        使用 ls-tree 可以极快地获取所有受 Git 管理的文件的 Blob ID
        """
        output = self.run_git(["ls-tree", "-r", commit_ish], cwd)
        fingerprint = {}
        for line in output.splitlines():
            if not line:
                continue
            # ls-tree 输出格式: 100644 blob <hash>    <path>
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                blob_hash = parts[2]
                file_path = parts[3]
                fingerprint[file_path] = blob_hash
        return fingerprint

    def load_metadata(self) -> Optional[str]:
        """从 RepoB 读取上一次同步的 Commit ID"""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, "r") as f:
                    data = json.load(f)
                    return data.get("last_synced_commit_repo_a")
            except:
                return None
        return None

    def save_metadata(self, commit_id: str):
        """保存同步进度"""
        with open(self.metadata_path, "w") as f:
            json.dump({"last_synced_commit_repo_a": commit_id}, f, indent=2)

    def find_best_match(self, max_search_depth: int = 100) -> Tuple[str, float]:
        """
        核心算法：在 RepoA 中寻找最像 RepoB 当前状态的 Commit
        """
        # 1. 获取 RepoB 的当前指纹
        target_fingerprint = self.get_fingerprint(self.repo_b_dir)
        target_files_count = len(target_fingerprint)

        if target_files_count == 0:
            raise Exception("RepoB is empty or not a git repo.")

        # 2. 获取 RepoA 最近的提交列表
        commits = self.run_git(
            ["rev-list", "HEAD", f"--max-count={max_search_depth}"], self.repo_a_dir
        ).splitlines()

        best_commit = ""
        max_score = -1.0

        print(f"开始指纹比对，搜索深度: {len(commits)}...")

        for cid in commits:
            current_a_fingerprint = self.get_fingerprint(self.repo_a_dir, cid)

            # 计算匹配得分：路径一致且 Hash 一致的文件数
            matches = sum(
                1
                for path, h in target_fingerprint.items()
                if current_a_fingerprint.get(path) == h
            )

            score = matches / target_files_count

            # 只要达到 100% 匹配，立即停止搜索
            if score >= 1.0:
                return cid, 1.0

            if score > max_score:
                max_score = score
                best_commit = cid

        return best_commit, max_score


class PatchManager:
    def __init__(self, repo_a_dir: str, repo_b_dir: str):
        self.repo_a_dir = repo_a_dir
        self.repo_b_dir = repo_b_dir

    def _run_git(self, args: List[str], cwd: str) -> str:
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        return result.stdout.strip()

    def generate_patch(self, commit_id: str) -> str:
        """在 RepoA 中为特定 commit 生成补丁内容"""
        # 使用 -1 保证只生成这一个 commit 的补丁
        return self._run_git(["show", commit_id, "--patch"], self.repo_a_dir)

    def apply_patch_attempt(self, patch_content: str) -> bool:
        """尝试在 RepoB 应用补丁"""
        # 将补丁写入临时文件
        patch_path = os.path.join(self.repo_b_dir, "temp_sync.patch")
        with open(patch_path, "w") as f:
            f.write(patch_content)

        try:
            # 尝试使用 git am -3 (三路合并模式)
            # 如果没有共同历史，可以使用 git apply --3way
            subprocess.run(
                ["git", "apply", "--3way", "temp_sync.patch"],
                cwd=self.repo_b_dir,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
        finally:
            if os.path.exists(patch_path):
                os.remove(patch_path)

    def get_conflict_files(self) -> List[str]:
        """获取当前冲突的文件列表"""
        output = self._run_git(
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
                content = self._run_git(
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
        self._run_git(["add", file_path], self.repo_b_dir)

    def is_all_resolved(self) -> bool:
        """检查是否所有冲突都已 add"""
        conflicts = self.get_conflict_files()
        return len(conflicts) == 0
