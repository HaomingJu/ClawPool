"""
Ollama Function Calling 工具描述定义。

所有工具按服务分组：
  - Jenkins 工具（前缀 jenkins_）
  - GitLab 工具（前缀 gitlab_）

新增工具时在此文件追加即可，ai_chat.py 无需改动。
"""

# ── Jenkins Tools ──────────────────────────────────────────────────────────────

JENKINS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "jenkins_ping",
            "description": "测试 Jenkins 服务可用性",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_list_jobs",
            "description": "列出所有 Jenkins Job",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_get_job_info",
            "description": "获取指定 Jenkins Job 的详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job 名称"},
                },
                "required": ["job_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_trigger_build",
            "description": "触发 Jenkins Job 构建，可携带参数",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job 名称"},
                    "parameters": {
                        "type": "object",
                        "description": "构建参数键值对，无参数时留空",
                    },
                },
                "required": ["job_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_get_last_build",
            "description": "获取指定 Jenkins Job 的最近一次构建信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job 名称"},
                },
                "required": ["job_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_get_build_log",
            "description": "获取指定构建的控制台日志",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job 名称"},
                    "build_number": {"type": "integer", "description": "构建编号"},
                },
                "required": ["job_name", "build_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jenkins_get_queue",
            "description": "获取 Jenkins 当前构建队列",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ── GitLab Tools ───────────────────────────────────────────────────────────────

GITLAB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "gitlab_ping",
            "description": "测试 GitLab 服务可用性",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_list_projects",
            "description": "列出 GitLab 项目，可按名称搜索",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "项目名称关键字"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_list_branches",
            "description": "列出指定 GitLab 项目的所有分支",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或 'namespace/project'"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_create_branch",
            "description": "在 GitLab 项目中从指定 ref 创建新分支",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "branch": {"type": "string", "description": "新分支名称"},
                    "ref": {"type": "string", "description": "源分支/tag/commit"},
                },
                "required": ["project_id", "branch", "ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_list_merge_requests",
            "description": "列出 GitLab 项目的合并请求",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "state": {
                        "type": "string",
                        "description": "状态过滤：opened/closed/merged/all",
                        "enum": ["opened", "closed", "merged", "all"],
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_create_merge_request",
            "description": "在 GitLab 项目中创建合并请求（MR）",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "source_branch": {"type": "string", "description": "源分支"},
                    "target_branch": {"type": "string", "description": "目标分支"},
                    "title": {"type": "string", "description": "MR 标题"},
                    "description": {"type": "string", "description": "MR 描述（可选）"},
                },
                "required": ["project_id", "source_branch", "target_branch", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_accept_merge_request",
            "description": "合并指定的 GitLab MR",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "mr_iid": {"type": "integer", "description": "MR 的项目内 IID"},
                    "squash": {"type": "boolean", "description": "是否 squash 合并"},
                },
                "required": ["project_id", "mr_iid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_list_pipelines",
            "description": "列出 GitLab 项目的 Pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "ref": {"type": "string", "description": "分支/tag 过滤"},
                    "status": {"type": "string", "description": "状态过滤：running/success/failed 等"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_create_pipeline",
            "description": "手动触发 GitLab Pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "ref": {"type": "string", "description": "触发的分支或 tag"},
                    "variables": {
                        "type": "object",
                        "description": "Pipeline 变量键值对（可选）",
                    },
                },
                "required": ["project_id", "ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_retry_pipeline",
            "description": "重试 GitLab Pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "pipeline_id": {"type": "integer", "description": "Pipeline ID"},
                },
                "required": ["project_id", "pipeline_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_list_tags",
            "description": "列出 GitLab 项目的所有 Tag",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_create_tag",
            "description": "在 GitLab 项目中创建 Tag",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "tag_name": {"type": "string", "description": "Tag 名称"},
                    "ref": {"type": "string", "description": "打 Tag 的分支/commit"},
                    "message": {"type": "string", "description": "附注信息（可选，有则创建附注 Tag）"},
                },
                "required": ["project_id", "tag_name", "ref"],
            },
        },
    },
]

# ── 合并导出 ───────────────────────────────────────────────────────────────────

TOOLS = JENKINS_TOOLS + GITLAB_TOOLS
