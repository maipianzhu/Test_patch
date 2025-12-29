from langchain_core.tools import tool
import os

# Set env vars BEFORE importing apollo_client to ensure it picks them up
os.environ["APOLLO_USERNAME"] = ""
os.environ["APOLLO_PWD"] = ""

from langGraph_app.utils.apollo_client import apollo_managers, apollo_openapi_client

# Define the operator for write actions (must be a valid user in Apollo)
APOLLO_OPERATOR = os.getenv("APOLLO_OPERATOR", "apollo")


@tool
def get_apollo_config(env: str, app_id: str, namespace: str = "application") -> str:
    """
    获取指定环境 Apollo 的配置列表,如果没有指定默认为application

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_id: 应用ID (AppId)
        namespace: 命名空间名称。可以是任何有效的 Namespace，例如 'application' 或 'system'。
    """
    env_key = env.lower()

    # 1. 尝试使用 Open API Client (优先)
    if apollo_openapi_client:
        try:
            # 3.2.6 获取某个Namespace信息 (包含 items)
            ns_data = apollo_openapi_client.get_namespace(
                env, app_id, namespace_name=namespace
            )
            items_data = ns_data.get("items", [])

            return _format_items(items_data, env, app_id)
        except Exception as e:
            # 如果 Open API 失败，可以考虑降级或者直接报错
            # 这里简单返回失败信息，或者如果没配 Token 自然不会进这里
            return f"❌ Open API 调用失败: {e}"

    # 2. 降级到 Legacy Client
    client = apollo_managers.get(env_key)

    if not client:
        return f"❌ 错误: 未配置环境 '{env}' 的连接信息。"

    # 调用 Legacy Client 获取数据
    items_data = client.get_items(env, app_id, namespace)

    # 错误处理
    if isinstance(items_data, dict) and "error" in items_data:
        return f"❌ 获取失败: {items_data['error']}"

    if not items_data:
        return f"⚠️ 环境 {env} 中 {app_id} 的配置为空。"

    return _format_items(items_data, env, app_id)


def _format_items(items_data, env, app_id):
    """
    格式化输出 (Markdown 表格形式，利于 LLM 阅读)
    """
    if not items_data:
        return f"⚠️ 环境 {env} 中 {app_id} 的配置为空。"

    result_text = f"### 📋 环境: {env} | AppId: {app_id}\n\n"
    result_text += "| Key | Value | Modified By | Modified Time |\n"
    result_text += "|-----|-------|-------------|---------------|\n"

    for item in items_data:
        # 保护性获取字段，防止 Key 不存在
        k = item.get("key", "")
        # Filter out empty keys
        if not k or not str(k).strip():
            continue

        v = str(item.get("value", ""))
        user = item.get("dataChangeLastModifiedBy", "")
        time_str = item.get("dataChangeLastModifiedTime", "")

        # 截断过长的 Value
        display_v = (v[:20] + "..") if len(v) > 20 else v

        result_text += f"| {k} | {display_v} | {user} | {time_str} |\n"

    return result_text


# 辅助函数：供 Streamlit 使用返回原始数据
def get_apollo_config_raw(env, app_id, namespace="application"):
    env_key = env.lower()

    if apollo_openapi_client:
        try:
            ns_data = apollo_openapi_client.get_namespace(
                env, app_id, namespace_name=namespace
            )
            return ns_data.get("items", [])
        except Exception as e:
            print(f"Open API Fetch Error: {e}")
            pass

    client = apollo_managers.get(env_key)
    if client:
        return client.get_items(env, app_id, namespace)
    return {"error": "Env not found"}


@tool
def create_apollo_item(
    env: str,
    app_id: str,
    key: str,
    value: str,
    comment: str = "",
    namespace: str = "application",
) -> str:
    """
    在 Apollo 指定环境中创建配置项。

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_id: 应用ID
        key: 配置 Key
        value: 配置 Value
        comment: 备注/注释
        namespace: 命名空间名称。支持任意 Namespace，如 'application', 'system' 等。
    """
    if not apollo_openapi_client:
        return "❌ 错误: 未配置 Apollo Open API Token，无法执行写操作。"

    item_dto = {
        "key": key,
        "value": value,
        "comment": comment,
        "dataChangeCreatedBy": APOLLO_OPERATOR,
    }

    try:
        apollo_openapi_client.create_item(
            env=env, app_id=app_id, namespace_name=namespace, item_dto=item_dto
        )
        return f"✅ 成功创建配置项: {key} = {value}"
    except Exception as e:
        return f"❌ 创建失败: {str(e)}"


@tool
def update_apollo_item(
    env: str,
    app_id: str,
    key: str,
    value: str,
    comment: str = "",
    namespace: str = "application",
    create_if_not_exists: bool = False,
) -> str:
    """
    更新 Apollo 指定环境中的配置项。

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_id: 应用ID
        key: 配置 Key
        value: 新的配置 Value
        comment: 备注/注释
        namespace: 命名空间名称。支持任意 Namespace，如 'application', 'system' 等。
        create_if_not_exists: 如果不存在是否创建
    """
    if not apollo_openapi_client:
        return "❌ 错误: 未配置 Apollo Open API Token，无法执行写操作。"

    item_dto = {
        "key": key,
        "value": value,
        "comment": comment,
        "dataChangeLastModifiedBy": APOLLO_OPERATOR,
    }

    try:
        apollo_openapi_client.update_item(
            env=env,
            app_id=app_id,
            namespace_name=namespace,
            key=key,
            item_dto=item_dto,
            create_if_not_exists=create_if_not_exists,
        )
        return f"✅ 成功更新配置项: {key} = {value}"
    except Exception as e:
        return f"❌ 更新失败: {str(e)}"


@tool
def delete_apollo_item(
    env: str, app_id: str, key: str, namespace: str = "application"
) -> str:
    """
    删除 Apollo 指定环境中的配置项。

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_id: 应用ID
        key: 配置 Key
        namespace: 命名空间名称。支持任意 Namespace，如 'application', 'system' 等。
    """
    if not apollo_openapi_client:
        return "❌ 错误: 未配置 Apollo Open API Token，无法执行写操作。"

    try:
        apollo_openapi_client.delete_item(
            env=env,
            app_id=app_id,
            namespace_name=namespace,
            key=key,
            operator=APOLLO_OPERATOR,
        )
        return f"✅ 成功删除配置项: {key}"
    except Exception as e:
        return f"❌ 删除失败: {str(e)}"


@tool
def publish_apollo_release(
    env: str, app_id: str, title: str, comment: str = "", namespace: str = "application"
) -> str:
    """
    发布 Apollo 指定环境的 Namespace 配置。

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_id: 应用ID
        title: 发布标题 (Release Title)
        comment: 发布备注
        namespace: 命名空间名称。支持任意 Namespace，如 'application', 'system' 等。
    """
    if not apollo_openapi_client:
        return "❌ 错误: 未配置 Apollo Open API Token，无法执行写操作。"

    release_dto = {
        "releaseTitle": title,
        "releaseComment": comment,
        "releasedBy": APOLLO_OPERATOR,
    }

    try:
        # 这个操作会把当前 Namespace 下所有 Modified 的配置发布
        res = apollo_openapi_client.publish_namespace(
            env=env, app_id=app_id, namespace_name=namespace, release_dto=release_dto
        )
        return f"✅ 发布成功! Release Name: {res.get('name', 'Unknown')}"
    except Exception as e:
        return f"❌ 发布失败: {str(e)}"


@tool
def batch_add_apollo_config(
    env: str,
    app_ids: list[str],
    key: str,
    value: str,
    comment: str = "",
    namespace: str = "application",
    publish_now: bool = False,
) -> str:
    """
    批量在多个 AppID 中新增或更新 Apollo 配置项。

    Args:
        env: 环境名称 (test, qa, uat, prod)
        app_ids: 应用ID列表 (例如: ['app1', 'app2'])
        key: 配置 Key
        value: 配置 Value
        comment: 备注/注释
        namespace: 命名空间名称
        publish_now: 是否在新增后立即发布
    """
    if not apollo_openapi_client:
        return "❌ 错误: 未配置 Apollo Open API Token，无法执行写操作。"

    report = f"### 🚀 批量新增配置报告 ({env})\n\n"
    report += f"**Key:** `{key}` | **Value:** `{value}`\n\n"
    report += "| AppID | Status | Publish Status | Message |\n"
    report += "|-------|--------|----------------|---------|\n"

    for app_id in app_ids:
        app_id = app_id.strip()
        if not app_id:
            continue

        create_status = "Skipped"
        pub_status = "-"
        msg = "-"

        try:
            # 1. 检查配置是否已存在
            existing_item = None
            try:
                existing_item = apollo_openapi_client.get_item(
                    env=env, app_id=app_id, namespace_name=namespace, key=key
                )
            except Exception as e:
                # 如果是 404 则表示不存在，可以继续新增
                if "404" not in str(e):
                    raise e

            if existing_item:
                # 2. 如果已存在，检查值是否一致
                if str(existing_item.get("value")) == str(value):
                    create_status = "✅ No Change"
                else:
                    # 3. 值不一致，进行更新
                    update_dto = {
                        "key": key,
                        "value": value,
                        "comment": comment,
                        "dataChangeLastModifiedBy": APOLLO_OPERATOR,
                    }
                    apollo_openapi_client.update_item(
                        env=env,
                        app_id=app_id,
                        namespace_name=namespace,
                        key=key,
                        item_dto=update_dto,
                    )
                    create_status = "✅ Updated"
            else:
                # 4. 不存在，进行创建
                create_dto = {
                    "key": key,
                    "value": value,
                    "comment": comment,
                    "dataChangeCreatedBy": APOLLO_OPERATOR,
                }
                apollo_openapi_client.create_item(
                    env=env,
                    app_id=app_id,
                    namespace_name=namespace,
                    item_dto=create_dto,
                )
                create_status = "✅ Created"

        except Exception as e:
            create_status = "❌ Failed"
            msg = str(e)

        # 5. 如果操作成功且需要发布
        if "✅" in create_status and publish_now:
            try:
                release_dto = {
                    "releaseTitle": f"Batch Update: {key}",
                    "releaseComment": comment,
                    "releasedBy": APOLLO_OPERATOR,
                }
                apollo_openapi_client.publish_namespace(
                    env=env,
                    app_id=app_id,
                    namespace_name=namespace,
                    release_dto=release_dto,
                )
                pub_status = "✅ Published"
            except Exception as e:
                pub_status = "❌ Pub Failed"
                msg = f"Save OK, but: {str(e)}"

        report += f"| {app_id} | {create_status} | {pub_status} | {msg} |\n"

    return report


def run_test():
    target_env = "TEST"  # 修改为你配置的一个环境 Key
    target_app_id = "invoice-ws-priv"  # 修改为你真实的 AppId

    print(f"🚀 开始测试: 连接 {target_env} 环境...")

    # 方式一：直接调用 Client (模拟 Streamlit 获取数据)
    print("\n1️⃣  [Raw Mode] 正在获取原始 JSON 数据...")
    raw_data = get_apollo_config_raw(target_env, target_app_id)

    if isinstance(raw_data, dict) and "error" in raw_data:
        print(f"❌ 失败: {raw_data['error']}")
        # 提示：如果是 404，可能是 AppId 不对；如果是 401/403，可能是账号密码不对
    else:
        item_count = len(raw_data)
        print(f"✅ 成功! 获取到 {item_count} 条配置项。")
        if item_count > 0:
            print(
                f"   第一条配置: Key={raw_data[0].get('key')}, Value={raw_data[0].get('value')}"
            )

    # 方式二：通过 Tool 调用 (模拟 LLM 调用)
    print("\n2️⃣  [Tool Mode] 正在模拟 AI 调用工具...")
    try:
        # invoke 需要传入字典参数
        tool_output = get_apollo_config.invoke(
            {"env": target_env, "app_id": target_app_id, "namespace": "system"}
        )
        print("----- Tool 返回结果 (Markdown) -----")
        print(tool_output)
        print("------------------------------------")
    except Exception as e:
        print(f"❌ Tool 调用报错: {e}")


if __name__ == "__main__":
    run_test()
