import requests
import os
from dotenv import load_dotenv

load_dotenv()

"""
  Apollo Client
"""


class ApolloAuthManager:
    """
    Legacy Apollo Client using Username/Password (Simulates Browser Login)
    """

    def __init__(self, url, username, pwd):
        self.url = url
        self.username = username
        self.pwd = pwd
        self.session = requests.Session()
        # Add Browser Headers to mimic real user
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            }
        )
        self.last_login_time = 0
        self.token_validity_seconds = 3600 * 2

    def get_items(self, env, app_id, namespace="application"):
        self.get_session()
        url = f"{self.url}apps/{app_id}/envs/{env}/clusters/default/namespaces/{namespace}/items"
        try:
            resp = self.session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    if not data:
                        return {
                            "error": f"API 返回空对象。请检查 AppId({app_id}) 是否存在。"
                        }
                    return data
                return {"error": f"API 返回未知格式数据: {type(data)}"}
            else:
                return {
                    "error": f"API Request Failed: {resp.status_code} - {resp.text}"
                }
        except Exception as e:
            return {"error": f"Request Exception: {str(e)}"}


class ApolloOpenApiClient:
    """
    Official Apollo Open API Client (Token Based)
    """

    def __init__(self, portal_url, token, timeout=10):
        self.portal_url = portal_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": self.token,
                "Content-Type": "application/json;charset=UTF-8",
            }
        )

    def _request(self, method, path, **kwargs):
        url = f"{self.portal_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            # If response is empty (like 204 No Content), return empty dict
            if not resp.text:
                return {}
            return resp.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise Exception(
                    f"Apollo API Error: {e.response.status_code} - {error_data.get('message', str(e))}"
                )
            except ValueError:
                raise Exception(
                    f"Apollo API Error: {e.response.status_code} - {e.response.text}"
                )
        except Exception as e:
            raise Exception(f"Request Error: {str(e)}")

    def get_env_clusters(self, app_id):
        """3.2.1 获取App的环境，集群信息"""
        path = f"/openapi/v1/apps/{app_id}/envclusters"
        return self._request("GET", path)

    def get_apps(self, app_ids=None):
        """3.2.2 获取App信息"""
        path = "/openapi/v1/apps"
        params = {}
        if app_ids:
            params["appIds"] = ",".join(app_ids)
        return self._request("GET", path, params=params)

    def get_cluster(self, env, app_id, cluster_name="default"):
        """3.2.3 获取集群详细信息"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}"
        return self._request("GET", path)

    def get_namespaces(self, env, app_id, cluster_name="default"):
        """3.2.5 获取集群下所有Namespace信息"""
        path = (
            f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces"
        )
        return self._request("GET", path)

    def get_namespace(
        self, env, app_id, cluster_name="default", namespace_name="application"
    ):
        """3.2.6 获取某个Namespace信息"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}"
        return self._request("GET", path)

    def create_namespace(self, app_id, namespace_dto):
        """3.2.7 创建Namespace"""
        path = f"/openapi/v1/apps/{app_id}/appnamespaces"
        return self._request("POST", path, json=namespace_dto)

    def get_namespace_lock(
        self, env, app_id, cluster_name="default", namespace_name="application"
    ):
        """3.2.8 获取某个Namespace当前编辑人"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/lock"
        return self._request("GET", path)

    def get_item(
        self, env, app_id, cluster_name="default", namespace_name="application", key=""
    ):
        """3.2.9 读取配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/items/{key}"
        return self._request("GET", path)

    def create_item(
        self,
        env,
        app_id,
        cluster_name="default",
        namespace_name="application",
        item_dto=None,
    ):
        """3.2.10 新增配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/items"
        return self._request("POST", path, json=item_dto)

    def batch_create_item(
        self,
        env,
        app_ids,
        cluster_name="default",
        namespace_name="application",
        item_dto=None,
    ):
        """批量新增配置 (跨多个AppId)"""
        results = {}
        for app_id in app_ids:
            try:
                res = self.create_item(
                    env, app_id, cluster_name, namespace_name, item_dto
                )
                results[app_id] = {"status": "success", "data": res}
            except Exception as e:
                results[app_id] = {"status": "error", "message": str(e)}
        return results

    def update_item(
        self,
        env,
        app_id,
        cluster_name="default",
        namespace_name="application",
        key="",
        item_dto=None,
        create_if_not_exists=False,
    ):
        """3.2.11 修改配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/items/{key}"
        params = {"createIfNotExists": create_if_not_exists}
        return self._request("PUT", path, params=params, json=item_dto)

    def delete_item(
        self,
        env,
        app_id,
        cluster_name="default",
        namespace_name="application",
        key="",
        operator="",
    ):
        """3.2.12 删除配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/items/{key}"
        params = {"operator": operator}
        return self._request("DELETE", path, params=params)

    def publish_namespace(
        self,
        env,
        app_id,
        cluster_name="default",
        namespace_name="application",
        release_dto=None,
    ):
        """3.2.13 发布配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/releases"
        return self._request("POST", path, json=release_dto)

    def batch_publish_namespace(
        self,
        env,
        app_ids,
        title,
        comment="",
        cluster_name="default",
        namespace_name="application",
    ):
        """批量发布配置 (跨多个AppId)"""
        results = {}
        release_dto = {
            "releaseTitle": title,
            "releaseComment": comment,
            "releasedBy": self.session.headers.get("Authorization"),  # Simplified
        }
        # In actual usage we should use the operator, but for now we follow the existing pattern
        for app_id in app_ids:
            try:
                res = self.publish_namespace(
                    env, app_id, cluster_name, namespace_name, release_dto
                )
                results[app_id] = {"status": "success", "data": res}
            except Exception as e:
                results[app_id] = {"status": "error", "message": str(e)}
        return results

    def get_latest_release(
        self, env, app_id, cluster_name="default", namespace_name="application"
    ):
        """3.2.14 获取已发布配置"""
        path = f"/openapi/v1/envs/{env}/apps/{app_id}/clusters/{cluster_name}/namespaces/{namespace_name}/releases/latest"
        return self._request("GET", path)

    def rollback_release(self, env, release_id, operator=""):
        """3.2.15 回滚配置"""
        path = f"/openapi/v1/envs/{env}/releases/{release_id}/rollback"
        params = {"operator": operator}
        return self._request("PUT", path, params=params)


# Configuration
username = os.getenv("APOLLO_USERNAME")
pwd = os.getenv("APOLLO_PWD")
openapi_token = os.getenv("APOLLO_OPENAPI_TOKEN")
# Portal URL (e.g., http://portal.apollo.com)
portal_url = os.getenv("APOLLO_PORTAL_URL", "http://test-apollo.worklaile.cn/")

# 1. Legacy Managers (Browser Simulation)
apollo_managers = {
    "test": ApolloAuthManager("http://test-apollo.worklaile.cn/", username, pwd),
}

# 2. Open API Client (Optional, requires Token)
apollo_openapi_client = None
if openapi_token:
    apollo_openapi_client = ApolloOpenApiClient(portal_url, openapi_token)

if __name__ == "__main__":
    if apollo_openapi_client:
        print("✅ Open API Client Initialized")
    else:
        print("ℹ️ Open API Token not found, skipping Open API client init.")
