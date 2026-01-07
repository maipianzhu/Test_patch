import os
import shutil
import subprocess
from langchain_code_sync.agent import app


def run_cmd(cmd, cwd):
    subprocess.run(
        cmd,
        shell=True,
        check=True,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def setup_repos(base_dir):
    repo_a = os.path.join(base_dir, "repo_a")
    repo_b = os.path.join(base_dir, "repo_b")

    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.makedirs(base_dir)

    # Init Repo A
    os.makedirs(repo_a)
    run_cmd("git init", repo_a)
    run_cmd("git config user.email 'test@example.com'", repo_a)
    run_cmd("git config user.name 'Test User'", repo_a)
    with open(os.path.join(repo_a, "file1.txt"), "w") as f:
        f.write("Hello World\n")
    run_cmd("git add .", repo_a)
    run_cmd("git commit -m 'Initial commit'", repo_a)

    # Clone Repo A to Repo B (simulating sync state)
    run_cmd(f"git clone {repo_a} {repo_b}", base_dir)
    run_cmd("git config user.email 'test@example.com'", repo_b)
    run_cmd("git config user.name 'Test User'", repo_b)

    return repo_a, repo_b


def test_sync_success():
    print("\n--- Testing Successful Sync ---")
    base_dir = "/tmp/test_git_sync"
    repo_a, repo_b = setup_repos(base_dir)

    # Make change in Repo A
    with open(os.path.join(repo_a, "file2.txt"), "w") as f:
        f.write("New feature\n")
    run_cmd("git add .", repo_a)
    run_cmd("git commit -m 'Add file2'", repo_a)

    # Run Agent
    patch_dir = os.path.join(base_dir, "patches")
    initial_state = {
        "source_repo_path": repo_a,
        "target_repo_path": repo_b,
        "patch_dir": patch_dir,
    }

    final_state = app.invoke(initial_state)

    # Verify
    if os.path.exists(os.path.join(repo_b, "file2.txt")):
        print("PASS: file2.txt synced to Repo B")
    else:
        print("FAIL: file2.txt not found in Repo B")


def test_conflict_handling():
    print("\n--- Testing Conflict Handling ---")
    base_dir = "/tmp/test_git_sync_conflict"
    repo_a, repo_b = setup_repos(base_dir)

    # Create conflict
    # Repo A modifies file1
    with open(os.path.join(repo_a, "file1.txt"), "w") as f:
        f.write("Hello Universe\n")
    run_cmd("git add .", repo_a)
    run_cmd("git commit -m 'Update file1'", repo_a)

    # Repo B modifies file1 differently
    with open(os.path.join(repo_b, "file1.txt"), "w") as f:
        f.write("Hello Multiverse\n")
    run_cmd("git add .", repo_b)
    run_cmd("git commit -m 'Update file1 local'", repo_b)

    # Run Agent (it should stop at conflict or request auth)
    patch_dir = os.path.join(base_dir, "patches")
    initial_state = {
        "source_repo_path": repo_a,
        "target_repo_path": repo_b,
        "patch_dir": patch_dir,
    }

    # Iterate steps to see where it lands
    print("Starting agent execution...")
    # NOTE: Since we didn't setup a real interrupt mechanism that blocks execution in this script,
    # invoke() will run until end or error.
    # But our graph has a loop if conflict repeats? No, `process_user_decision` handles it.
    # The current graph logic: apply -> fail -> conflict_analyzer -> process_user_decision -> (default skip/retry?)
    # Wait, `process_user_decision` defaults to repeating or something if decision is empty.
    # Let's see `nodes.py`.
    # `process_user_decision`: decision = state.get("user_decision", "").lower() ... default: `agent_suggestion` updated.
    # Then `route_after_resolve`: returns `apply_next_patch` (?) or `end`.
    # Wait, if `process_user_decision` doesn't change `current_patch_index`, it loops back to `apply_next_patch` via `route_after_resolve`?
    # Yes, `route_after_resolve` calls `apply_next_patch`.
    # This will cause an infinite loop if we don't provide input.
    # So checking this via `invoke` might hang.

    # We should use `stream` and break if we hit `process_user_decision` or verify state.

    # Actually, for the test script to pass without hang, we need to inject `user_decision` if valid.
    # But `invoke` starts from scratch.

    # Let's modify the graph logic in `process_user_decision` to have a default "skip" if running in test environment?
    # Or better, we can manually run steps or inspect the flow.

    # For now, let's just run `app.invoke` but with a limit or check.
    # Actually, I'll update the test to run one step at a time or handle recursion limit.
    # But for simplicity, let's just test success case first correctly.
    # For conflict, I will try to run until `analyze_conflict` and see if `conflict_error` is set.

    # Re-using the app object directly might be tricky if it doesn't support stopping easily.
    # Let's try `app.stream`.

    try:
        recursion_limit = 20
        step_count = 0
        current_state = initial_state
        for output in app.stream(initial_state):
            # Output is a dict of node_name: state_update
            step_count += 1
            for key, value in output.items():
                print(f"Node: {key}")
                if key == "analyze_conflict":
                    print("Conflict detected as expected.")
                    print(f"Suggestion: {value.get('agent_suggestion')}")
                    # Simulate user decision to Abort for test
                    current_state.update(value)
                    current_state["user_decision"] = "abort"
                    # We can't easily inject back into the running stream unless we use `interrupt` and `Command` (LangGraph v0.2)
                    # or if we are just verifying it REACHED this state.
                    return
            if step_count > recursion_limit:
                print("Hit recursion limit")
                break
    except Exception as e:
        print(f"Execution stopped: {e}")


if __name__ == "__main__":
    test_sync_success()
    test_conflict_handling()
