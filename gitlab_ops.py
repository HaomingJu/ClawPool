import os
import requests


class GitlabOps:
    """
    GitLab 操作类，通过 GitLab REST API v4 进行常见操作。

    Args:
        base_url:    GitLab 服务地址，如 https://gitlab.example.com
        access_token: GitLab Personal Access Token 或 Project Access Token
                      （需要相应 scope：api / read_api / read_repository 等）
    """

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip("/") + "/api/v4"
        self.session = requests.Session()
        self.session.headers.update({
            "PRIVATE-TOKEN": access_token,
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> requests.Response:
        resp = self.session.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp

    def _post(self, path: str, json: dict = None) -> requests.Response:
        resp = self.session.post(f"{self.base_url}{path}", json=json)
        resp.raise_for_status()
        return resp

    def _put(self, path: str, json: dict = None) -> requests.Response:
        resp = self.session.put(f"{self.base_url}{path}", json=json)
        resp.raise_for_status()
        return resp

    def _delete(self, path: str) -> requests.Response:
        resp = self.session.delete(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp

    # ──────────────────────────────────────────────
    # 项目（Project）
    # ──────────────────────────────────────────────

    def list_projects(self, search: str = None, owned: bool = False) -> list[dict]:
        """列出可访问的项目"""
        params = {"owned": owned, "per_page": 100}
        if search:
            params["search"] = search
        return self._get("/projects", params=params).json()

    def get_project(self, project_id: int | str) -> dict:
        """获取项目详情（project_id 可为数字 ID 或 'namespace/project' 路径）"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}").json()

    def create_project(self, name: str, namespace_id: int = None, **kwargs) -> dict:
        """创建项目，kwargs 可传入 GitLab 支持的其他字段（visibility, description 等）"""
        payload = {"name": name, **kwargs}
        if namespace_id:
            payload["namespace_id"] = namespace_id
        return self._post("/projects", json=payload).json()

    # ──────────────────────────────────────────────
    # 分支（Branch）
    # ──────────────────────────────────────────────

    def list_branches(self, project_id: int | str) -> list[dict]:
        """列出项目所有分支"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/repository/branches").json()

    def create_branch(self, project_id: int | str, branch: str, ref: str) -> dict:
        """从 ref（分支/tag/commit）创建新分支"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._post(f"/projects/{pid}/repository/branches",
                          json={"branch": branch, "ref": ref}).json()

    def protect_branch(self, project_id: int | str, branch: str,
                       push_access_level: int = 40,
                       merge_access_level: int = 40) -> dict:
        """
        保护分支。access_level: 0=No access, 30=Developer, 40=Maintainer
        """
        pid = requests.utils.quote(str(project_id), safe="")
        return self._post(f"/projects/{pid}/protected_branches", json={
            "name": branch,
            "push_access_level": push_access_level,
            "merge_access_level": merge_access_level,
        }).json()

    # ──────────────────────────────────────────────
    # 合并请求（Merge Request）
    # ──────────────────────────────────────────────

    def list_merge_requests(self, project_id: int | str, state: str = "opened") -> list[dict]:
        """
        列出 MR。state: opened / closed / merged / all
        """
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/merge_requests",
                         params={"state": state, "per_page": 100}).json()

    def create_merge_request(self, project_id: int | str, source_branch: str,
                             target_branch: str, title: str, **kwargs) -> dict:
        """创建 MR，kwargs 可传 description、assignee_id 等"""
        pid = requests.utils.quote(str(project_id), safe="")
        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            **kwargs,
        }
        return self._post(f"/projects/{pid}/merge_requests", json=payload).json()

    def accept_merge_request(self, project_id: int | str, mr_iid: int,
                              squash: bool = False) -> dict:
        """合并 MR"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._put(f"/projects/{pid}/merge_requests/{mr_iid}/merge",
                         json={"squash": squash}).json()

    def get_merge_request(self, project_id: int | str, mr_iid: int) -> dict:
        """
        获取单个 MR 详情，包含 merge_status / detailed_merge_status / pipeline 等字段。

        重要字段：
            merge_status          : can_be_merged / cannot_be_merged / checking / unchecked
            detailed_merge_status : mergeable / has_conflicts / ci_must_pass /
                                    ci_still_running / discussions_not_resolved /
                                    draft_status / not_open 等（GitLab 15.3+）
            blocking_discussions_resolved: bool
            has_conflicts         : bool
            pipeline              : 最新关联 Pipeline 信息（含 status）
        """
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/merge_requests/{mr_iid}").json()

    def check_mr_mergeable(self, project_id: int | str, mr_iid: int) -> dict:
        """
        检查 MR 是否可以合并，返回结构化结果。

        Returns:
            {
                "mergeable": bool,
                "merge_status": str,
                "detailed_merge_status": str,
                "has_conflicts": bool,
                "blocking_discussions_resolved": bool,
                "pipeline_status": str | None,   # 最新 Pipeline 状态
                "draft": bool,
                "state": str,                    # opened / closed / merged
                "web_url": str,
                "title": str,
            }
        """
        mr = self.get_merge_request(project_id, mr_iid)
        pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}
        detailed = mr.get("detailed_merge_status", "")
        return {
            "mergeable": detailed == "mergeable" or mr.get("merge_status") == "can_be_merged",
            "merge_status": mr.get("merge_status", ""),
            "detailed_merge_status": detailed,
            "has_conflicts": mr.get("has_conflicts", False),
            "blocking_discussions_resolved": mr.get("blocking_discussions_resolved", True),
            "pipeline_status": pipeline.get("status"),
            "draft": mr.get("draft", False),
            "state": mr.get("state", ""),
            "web_url": mr.get("web_url", ""),
            "title": mr.get("title", ""),
        }

    def close_merge_request(self, project_id: int | str, mr_iid: int) -> dict:
        """关闭 MR"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._put(f"/projects/{pid}/merge_requests/{mr_iid}",
                         json={"state_event": "close"}).json()

    # ──────────────────────────────────────────────
    # Pipeline / CI
    # ──────────────────────────────────────────────

    def list_pipelines(self, project_id: int | str, ref: str = None,
                       status: str = None) -> list[dict]:
        """
        列出 Pipeline。status: created/waiting_for_resource/preparing/pending/
                               running/success/failed/canceled/skipped/manual
        """
        pid = requests.utils.quote(str(project_id), safe="")
        params = {"per_page": 100}
        if ref:
            params["ref"] = ref
        if status:
            params["status"] = status
        return self._get(f"/projects/{pid}/pipelines", params=params).json()

    def create_pipeline(self, project_id: int | str, ref: str,
                        variables: dict = None) -> dict:
        """手动触发 Pipeline"""
        pid = requests.utils.quote(str(project_id), safe="")
        payload: dict = {"ref": ref}
        if variables:
            payload["variables"] = [{"key": k, "value": v} for k, v in variables.items()]
        return self._post(f"/projects/{pid}/pipeline", json=payload).json()

    def retry_pipeline(self, project_id: int | str, pipeline_id: int) -> dict:
        """重试失败的 Pipeline"""
        pid = requests.utils.quote(str(project_id), safe="")
        resp = self.session.post(
            f"{self.base_url}/projects/{pid}/pipelines/{pipeline_id}/retry"
        )
        resp.raise_for_status()
        return resp.json()

    def get_pipeline_jobs(self, project_id: int | str, pipeline_id: int) -> list[dict]:
        """获取 Pipeline 下所有 Job"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/pipelines/{pipeline_id}/jobs").json()

    # ──────────────────────────────────────────────
    # 标签（Tag）
    # ──────────────────────────────────────────────

    def list_tags(self, project_id: int | str) -> list[dict]:
        """列出所有 Tag"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/repository/tags").json()

    def create_tag(self, project_id: int | str, tag_name: str, ref: str,
                   message: str = None) -> dict:
        """创建 Tag（message 不为空则创建附注 Tag）"""
        pid = requests.utils.quote(str(project_id), safe="")
        payload = {"tag_name": tag_name, "ref": ref}
        if message:
            payload["message"] = message
        return self._post(f"/projects/{pid}/repository/tags", json=payload).json()

    def delete_tag(self, tag_name: str) -> None:
        """删除 Tag（已禁用危险操作）"""
        raise NotImplementedError("删除 Tag 属于危险操作，已被禁用。")

    # ──────────────────────────────────────────────
    # 用户 / 成员
    # ──────────────────────────────────────────────

    def get_current_user(self) -> dict:
        """获取当前 Token 对应的用户信息"""
        return self._get("/user").json()

    def ping(self) -> bool:
        """
        测试 GitLab 服务可用性及 Token 有效性。
        返回 True 表示服务正常且认证通过，否则返回 False。
        """
        try:
            resp = self.session.get(f"{self.base_url}/user", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_project_members(self, project_id: int | str) -> list[dict]:
        """列出项目成员"""
        pid = requests.utils.quote(str(project_id), safe="")
        return self._get(f"/projects/{pid}/members").json()

    def add_project_member(self, project_id: int | str, user_id: int,
                           access_level: int = 30) -> dict:
        """
        添加项目成员。access_level: 10=Guest,20=Reporter,30=Developer,
                                    40=Maintainer,50=Owner
        """
        pid = requests.utils.quote(str(project_id), safe="")
        return self._post(f"/projects/{pid}/members",
                          json={"user_id": user_id, "access_level": access_level}).json()

    def remove_project_member(self, project_id: int | str, user_id: int) -> None:
        """移除项目成员（已禁用危险操作）"""
        raise NotImplementedError("移除成员属于危险操作，已被禁用。")


if __name__ == "__main__":
    GITLAB_URL   = os.environ.get("GITLAB_URL",   "https://gitlab.example.com")
    GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")

    if not GITLAB_TOKEN:
        print("[ERROR] 环境变量 GITLAB_TOKEN 未设置，请先执行：")
        print("  export GITLAB_TOKEN=your_access_token")
        exit(1)

    client = GitlabOps(GITLAB_URL, GITLAB_TOKEN)
    ok = client.ping()
    if ok:
        user = client.get_current_user()
        print(f"[OK] GitLab 服务可用，当前用户：{user.get('username')}（{user.get('name')}）")
    else:
        print("[FAIL] GitLab 服务不可用或 Token 无效，请检查地址与凭据。")
