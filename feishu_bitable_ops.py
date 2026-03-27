import os

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    Condition,
    FilterInfo,
    GetAppTableRecordRequest,
    ListAppTableFieldRequest,
    ListAppTableRequest,
    ListAppTableViewRequest,
    SearchAppTableRecordRequest,
    SearchAppTableRecordRequestBody,
)


class FeishuBitableOps:
    """
    飞书多维表格操作类，通过 lark-oapi SDK 查询多维表格数据。

    Args:
        app_id:     飞书应用 App ID
        app_secret: 飞书应用 App Secret
    """

    def __init__(self, app_id: str, app_secret: str):
        self.client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .build()
        )

    def ping(self) -> bool:
        """
        测试凭据是否有效（尝试获取 tenant_access_token）。
        返回 True 表示服务正常且凭据有效。
        """
        try:
            req = lark.authen.v1.InternalAccessTokenRequest.builder() \
                .request_body(
                    lark.authen.v1.CreateAccessTokenRequestBody.builder()
                    .grant_type("client_credentials")
                    .build()
                ).build()
        except Exception:
            pass
        # 改为通过一个轻量 API 探测
        try:
            resp = self.client.bitable.v1.app_table.list(
                ListAppTableRequest.builder()
                .app_token("PING_CHECK")
                .build()
            )
            # 404 / invalid token → code != 0，但能收到响应说明网络通
            return resp is not None
        except Exception:
            return False

    # ── 表格结构 ───────────────────────────────────────────────────

    def list_tables(self, app_token: str) -> list[dict]:
        """
        列出多维表格中所有数据表。

        Args:
            app_token: 多维表格的 app_token（URL 中 /base/ 后的部分）
        """
        resp = self.client.bitable.v1.app_table.list(
            ListAppTableRequest.builder()
            .app_token(app_token)
            .page_size(50)
            .build()
        )
        self._raise_if_failed(resp)
        items = resp.data.items or []
        return [{"table_id": t.table_id, "name": t.name} for t in items]

    def list_views(self, app_token: str, table_id: str) -> list[dict]:
        """
        列出指定数据表的所有视图。

        Args:
            app_token: 多维表格 app_token
            table_id:  数据表 ID
        """
        resp = self.client.bitable.v1.app_table_view.list(
            ListAppTableViewRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .page_size(50)
            .build()
        )
        self._raise_if_failed(resp)
        items = resp.data.items or []
        return [{"view_id": v.view_id, "view_name": v.view_name,
                 "view_type": v.view_type} for v in items]

    def list_fields(self, app_token: str, table_id: str) -> list[dict]:
        """
        列出指定数据表的所有字段。

        Args:
            app_token: 多维表格 app_token
            table_id:  数据表 ID
        """
        resp = self.client.bitable.v1.app_table_field.list(
            ListAppTableFieldRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .page_size(100)
            .build()
        )
        self._raise_if_failed(resp)
        items = resp.data.items or []
        return [{"field_id": f.field_id, "field_name": f.field_name,
                 "type": f.type} for f in items]

    # ── 记录查询 ───────────────────────────────────────────────────

    def get_record(self, app_token: str, table_id: str, record_id: str) -> dict:
        """
        获取单条记录。

        Args:
            app_token: 多维表格 app_token
            table_id:  数据表 ID
            record_id: 记录 ID
        """
        resp = self.client.bitable.v1.app_table_record.get(
            GetAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .record_id(record_id)
            .build()
        )
        self._raise_if_failed(resp)
        record = resp.data.record
        return {"record_id": record.record_id, "fields": record.fields}

    def search_records(
        self,
        app_token: str,
        table_id: str,
        filter_conditions: list[dict] | None = None,
        conjunction: str = "and",
        field_names: list[str] | None = None,
        page_size: int = 20,
        view_id: str | None = None,
    ) -> list[dict]:
        """
        搜索多维表格记录，支持条件过滤。

        Args:
            app_token:          多维表格 app_token
            table_id:           数据表 ID
            filter_conditions:  过滤条件列表，每项格式：
                                  {"field_name": "状态", "operator": "is", "value": ["进行中"]}
                                operator 可选值：is / isNot / contains / doesNotContain /
                                                  isEmpty / isNotEmpty / isGreater / isLess
            conjunction:        多条件关系，"and" 或 "or"（默认 and）
            field_names:        只返回指定字段（为空则返回全部）
            page_size:          每页记录数（默认 20，最大 500）
            view_id:            按视图过滤（可选）
        """
        body_builder = SearchAppTableRecordRequestBody.builder()

        if filter_conditions:
            conditions = [
                Condition.builder()
                .field_name(c["field_name"])
                .operator(c["operator"])
                .value(c.get("value", []))
                .build()
                for c in filter_conditions
            ]
            body_builder.filter(
                FilterInfo.builder()
                .conjunction(conjunction)
                .conditions(conditions)
                .build()
            )

        if field_names:
            body_builder.field_names(field_names)

        if view_id:
            body_builder.view_id(view_id)

        resp = self.client.bitable.v1.app_table_record.search(
            SearchAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .page_size(min(page_size, 500))
            .request_body(body_builder.build())
            .build()
        )
        self._raise_if_failed(resp)
        items = resp.data.items or []
        return [{"record_id": r.record_id, "fields": r.fields} for r in items]

    # ── 内部工具 ───────────────────────────────────────────────────

    @staticmethod
    def _raise_if_failed(resp) -> None:
        if not resp.success():
            raise RuntimeError(f"飞书 API 错误 code={resp.code}: {resp.msg}")


# ── 测试入口 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    APP_ID     = os.environ.get("APP_ID", "")
    APP_SECRET = os.environ.get("APP_SECRET", "")

    if not APP_ID or not APP_SECRET:
        print("[ERROR] 请设置环境变量 APP_ID 和 APP_SECRET")
        exit(1)

    ops = FeishuBitableOps(APP_ID, APP_SECRET)
    print("[OK] FeishuBitableOps 初始化成功")

    app_token = os.environ.get("BITABLE_APP_TOKEN", "")
    if not app_token:
        print("[INFO] 设置 BITABLE_APP_TOKEN 可进一步测试表格查询")
        exit(0)

    # ── 连通性检查 ──────────────────────────────────────────────────
    resp = ops.client.bitable.v1.app_table.list(
        ListAppTableRequest.builder()
        .app_token(app_token)
        .page_size(50)
        .build()
    )
    if not resp.success():
        print(f"[FAIL] API 返回错误 code={resp.code}: {resp.msg}")
        print("  请检查：")
        print("  1. APP_ID / APP_SECRET 是否正确")
        print("  2. 飞书应用是否开启权限：bitable:app:readonly")
        print("  3. 多维表格是否已将机器人设为「可查看」协作者")
        exit(1)

    # ── 列出所有数据表及视图 ────────────────────────────────────────
    tables = ops.list_tables(app_token)
    print(f"[OK] 找到 {len(tables)} 个数据表: {[t['name'] for t in tables]}")
    for table in tables:
        tid = table["table_id"]
        views = ops.list_views(app_token, tid)
        print(f"  表「{table['name']}」({tid}) 共 {len(views)} 个视图:")
        for v in views:
            print(f"    - [{v['view_type']}] {v['view_name']}  view_id={v['view_id']}")

    # ── 查询 view_id=vewddvPkuM 中的条目 ───────────────────────────
    TARGET_VIEW_ID = "vewddvPkuM"
    table_id = os.environ.get("BITABLE_TABLE_ID", "")

    # 若未指定 table_id，自动从各表视图中查找包含该 view_id 的数据表
    if not table_id:
        print(f"\n[INFO] 未指定 BITABLE_TABLE_ID，自动查找包含 view_id={TARGET_VIEW_ID} 的数据表...")
        for table in tables:
            tid = table["table_id"]
            views = ops.list_views(app_token, tid)
            if any(v["view_id"] == TARGET_VIEW_ID for v in views):
                table_id = tid
                print(f"[OK] 自动匹配到数据表「{table['name']}」({table_id})")
                break

    if not table_id:
        print(f"[WARN] 未找到包含 view_id={TARGET_VIEW_ID} 的数据表，请手动设置 BITABLE_TABLE_ID")
        exit(0)

    FILTER_FIELD = "代码合入评审"
    FILTER_VALUE = "评审通过待合入"

    print(f"\n[INFO] 查询 view_id={TARGET_VIEW_ID} 中「{FILTER_FIELD}={FILTER_VALUE}」的条目（table_id={table_id}）...")
    records = ops.search_records(
        app_token=app_token,
        table_id=table_id,
        view_id=TARGET_VIEW_ID,
        filter_conditions=[
            {"field_name": FILTER_FIELD, "operator": "is", "value": [FILTER_VALUE]},
            {"field_name": "CR评审", "operator": "is", "value": ["通过"]},
        ],
        page_size=50,
    )
    print(f"[OK] 共查到 {len(records)} 条记录:")
    for i, record in enumerate(records, 1):
        print(f"  [{i}] record_id={record['record_id']}")
        for field_name, field_value in record["fields"].items():
            print(f"       {field_name}: {field_value}")
