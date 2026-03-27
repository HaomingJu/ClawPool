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
            "name": "gitlab_rebase_merge_request",
            "description": (
                "对 GitLab MR 发起 rebase（将目标分支最新提交合入源分支）。"
                "异步操作，立即返回 rebase_in_progress 状态。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "mr_iid": {"type": "integer", "description": "MR 的项目内 IID"},
                    "skip_ci": {
                        "type": "boolean",
                        "description": "是否跳过 rebase 后触发的 CI Pipeline（默认 true）",
                    },
                },
                "required": ["project_id", "mr_iid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_get_merge_request",
            "description": "获取 GitLab 单个 MR 的详细信息（含 merge_status、pipeline 状态等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "mr_iid": {"type": "integer", "description": "MR 的项目内 IID"},
                },
                "required": ["project_id", "mr_iid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gitlab_check_mr_mergeable",
            "description": (
                "检查 GitLab MR 是否可以合并。"
                "返回 mergeable(bool)、merge_status、has_conflicts、pipeline_status、draft 等字段。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID 或路径"},
                    "mr_iid": {"type": "integer", "description": "MR 的项目内 IID"},
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

# ── Feishu Bitable Tools ──────────────────────────────────────────────────────

BITABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bitable_list_tables",
            "description": "列出飞书多维表格中的所有数据表",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_token": {
                        "type": "string",
                        "description": "多维表格的 app_token（URL 中 /base/ 后的部分）",
                    },
                },
                "required": ["app_token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bitable_list_views",
            "description": "列出飞书多维表格指定数据表的所有视图（网格视图、看板视图等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_token": {"type": "string", "description": "多维表格 app_token"},
                    "table_id": {"type": "string", "description": "数据表 ID"},
                },
                "required": ["app_token", "table_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bitable_list_fields",
            "description": "列出飞书多维表格指定数据表的所有字段（列名）",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_token": {"type": "string", "description": "多维表格 app_token"},
                    "table_id": {"type": "string", "description": "数据表 ID"},
                },
                "required": ["app_token", "table_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bitable_get_record",
            "description": "获取飞书多维表格中的单条记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_token": {"type": "string", "description": "多维表格 app_token"},
                    "table_id": {"type": "string", "description": "数据表 ID"},
                    "record_id": {"type": "string", "description": "记录 ID"},
                },
                "required": ["app_token", "table_id", "record_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bitable_search_records",
            "description": (
                "搜索飞书多维表格记录，支持条件过滤。"
                "filter_conditions 每项格式：{\"field_name\": \"状态\", \"operator\": \"is\", \"value\": [\"进行中\"]}。"
                "operator 可选：is / isNot / contains / doesNotContain / isEmpty / isNotEmpty / isGreater / isLess。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_token": {"type": "string", "description": "多维表格 app_token"},
                    "table_id": {"type": "string", "description": "数据表 ID"},
                    "filter_conditions": {
                        "type": "array",
                        "description": "过滤条件列表，为空则返回所有记录",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field_name": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "conjunction": {
                        "type": "string",
                        "description": "多条件关系：and 或 or（默认 and）",
                        "enum": ["and", "or"],
                    },
                    "field_names": {
                        "type": "array",
                        "description": "只返回指定字段，为空则返回全部",
                        "items": {"type": "string"},
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "返回记录数上限（默认 20，最大 500）",
                    },
                    "view_id": {
                        "type": "string",
                        "description": "按视图 ID 过滤，只返回该视图可见的记录（可通过 bitable_list_views 获取）",
                    },
                },
                "required": ["app_token", "table_id"],
            },
        },
    },
]

# ── 高层业务工具 ───────────────────────────────────────────────────────────────

BUSINESS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_pending_mrs",
            "description": (
                "查询指定项目的待合入 MR 列表（代码合入评审=评审通过待合入 且 CR评审=通过）。"
                "支持项目：北汽、上汽（上汽EP2）、广丰（GAC）、奇瑞T28。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "项目名称，如：北汽、上汽、广丰、奇瑞T28",
                    },
                },
                "required": ["project_name"],
            },
        },
    },
]

# ── 合并导出 ───────────────────────────────────────────────────────────────────

TOOLS = JENKINS_TOOLS + GITLAB_TOOLS + BITABLE_TOOLS + BUSINESS_TOOLS
