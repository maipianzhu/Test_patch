from langchain_code_sync.utils import sync_tool
from langchain_core.tools import tool


@tool
def generate_incremental_patches(source_repo, target_repo, output_dir):
    """
    自动对比两个 Git 仓库的差异并生成 patch 文件。
    当需要把 source_repo 的新代码同步给 target_repo 时使用。
    输入必须有: source_repo,target_repo,output_dir。
    工具会自动找到 target_repo 的最新 commit,并在 source_repo 中导出后续所有的变更
    """
    return sync_tool.generate_incremental_patches(source_repo, target_repo, output_dir)
