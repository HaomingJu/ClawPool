import os
import requests
from requests.auth import HTTPBasicAuth


class JenkinsOps:
    """
    Jenkins 操作类，通过 Jenkins REST API 进行常见 CI/CD 操作。

    Args:
        base_url:   Jenkins 服务地址，如 http://jenkins.example.com:8080
        username:   Jenkins 用户名
        api_token:  Jenkins API Token（在用户配置页面生成）
    """

    def __init__(self, base_url: str, username: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Content-Type": "application/json"})

    def _get(self, path: str, params: dict = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp

    def _post(self, path: str, data=None, params: dict = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, data=data, params=params)
        resp.raise_for_status()
        return resp

    # ──────────────────────────────────────────────
    # Job 管理
    # ──────────────────────────────────────────────

    def list_jobs(self) -> list[dict]:
        """获取所有顶层 Job 列表"""
        data = self._get("/api/json").json()
        return data.get("jobs", [])

    def get_job_info(self, job_name: str) -> dict:
        """获取指定 Job 的详细信息"""
        return self._get(f"/job/{job_name}/api/json").json()

    def create_job(self, job_name: str, config_xml: str) -> None:
        """用 XML 配置创建新 Job"""
        self.session.headers.update({"Content-Type": "application/xml"})
        try:
            self._post(f"/createItem", data=config_xml, params={"name": job_name})
        finally:
            self.session.headers.update({"Content-Type": "application/json"})

    def enable_job(self, job_name: str) -> None:
        """启用 Job"""
        self._post(f"/job/{job_name}/enable")

    def disable_job(self, job_name: str) -> None:
        """禁用 Job"""
        self._post(f"/job/{job_name}/disable")

    # ──────────────────────────────────────────────
    # 构建触发与查询
    # ──────────────────────────────────────────────

    def trigger_build(self, job_name: str, parameters: dict = None) -> None:
        """
        触发构建。
        parameters: 若 Job 有参数，传入 {"KEY": "VALUE"} 字典
        """
        if parameters:
            params_list = [{"name": k, "value": v} for k, v in parameters.items()]
            self._post(
                f"/job/{job_name}/buildWithParameters",
                params={k: v for k, v in parameters.items()},
            )
        else:
            self._post(f"/job/{job_name}/build")

    def get_build_info(self, job_name: str, build_number: int) -> dict:
        """获取指定构建的信息"""
        return self._get(f"/job/{job_name}/{build_number}/api/json").json()

    def get_last_build(self, job_name: str) -> dict:
        """获取最近一次构建信息"""
        return self._get(f"/job/{job_name}/lastBuild/api/json").json()

    def get_build_log(self, job_name: str, build_number: int) -> str:
        """获取构建日志"""
        return self._get(f"/job/{job_name}/{build_number}/consoleText").text

    def get_queue(self) -> list[dict]:
        """获取当前构建队列"""
        data = self._get("/queue/api/json").json()
        return data.get("items", [])

    # ──────────────────────────────────────────────
    # 节点（Agent）管理
    # ──────────────────────────────────────────────

    def list_nodes(self) -> list[dict]:
        """获取所有节点（含 master）"""
        data = self._get("/computer/api/json").json()
        return data.get("computer", [])

    def get_node_info(self, node_name: str) -> dict:
        """获取指定节点信息（master 使用 '(built-in)'）"""
        return self._get(f"/computer/{node_name}/api/json").json()

    # ──────────────────────────────────────────────
    # 系统
    # ──────────────────────────────────────────────

    def get_jenkins_version(self) -> str:
        """返回 Jenkins 版本号"""
        resp = self.session.get(f"{self.base_url}/api/json")
        return resp.headers.get("X-Jenkins", "unknown")

    def ping(self) -> bool:
        """
        测试 Jenkins 服务可用性及 Token 有效性。
        返回 True 表示服务正常且认证通过，否则返回 False。
        """
        try:
            resp = self.session.get(f"{self.base_url}/api/json", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False


if __name__ == "__main__":
    JENKINS_URL   = os.environ.get("JENKINS_URL",   "http://jenkins.example.com:8080")
    JENKINS_USER  = os.environ.get("JENKINS_USER",  "admin")
    JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")

    if not JENKINS_TOKEN:
        print("[ERROR] 环境变量 JENKINS_TOKEN 未设置，请先执行：")
        print("  export JENKINS_TOKEN=your_api_token")
        exit(1)

    client = JenkinsOps(JENKINS_URL, JENKINS_USER, JENKINS_TOKEN)
    ok = client.ping()
    if ok:
        version = client.get_jenkins_version()
        print(f"[OK] Jenkins 服务可用，版本：{version}")
    else:
        print("[FAIL] Jenkins 服务不可用或 Token 无效，请检查地址与凭据。")
