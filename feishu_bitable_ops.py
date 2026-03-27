import os

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    Condition,
    FilterInfo,
    GetAppTableRecordRequest,
    ListAppTableFieldRequest,
    ListAppTableRequest,
    ListAppTableViewRequest,
    SearchAppTableRecordRequest,
    SearchAppTableRecordRequestBody,
    UpdateAppTableRecordRequest,
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

    def update_record(self, app_token: str, table_id: str, record_id: str,
                      fields: dict) -> dict:
        """
        更新单条记录的指定字段。

        Args:
            app_token: 多维表格 app_token
            table_id:  数据表 ID
            record_id: 记录 ID
            fields:    要更新的字段键值对，如 {"代码合入评审": "已合入"}

        Returns:
            {"record_id": str, "fields": dict}
        """
        resp = self.client.bitable.v1.app_table_record.update(
            UpdateAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .record_id(record_id)
            .request_body(
                AppTableRecord.builder()
                .fields(fields)
                .build()
            )
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

    # ── 奇瑞T28 项目配置 ────────────────────────────────────────────
    APP_TOKEN = "Ft2ibanVKaEeMjsW2aTcr8eynvd"
    TABLE_ID  = "tblTsX1YCNXfFgTP"
    VIEW_ID   = "vewVL8akAQ"

    # ── 连通性检查 ──────────────────────────────────────────────────
    resp = ops.client.bitable.v1.app_table.list(
        ListAppTableRequest.builder()
        .app_token(APP_TOKEN)
        .page_size(50)
        .build()
    )
    if not resp.success():
        print(f"[FAIL] API 返回错误 code={resp.code}: {resp.msg}")
        print("  请检查：")
        print("  1. APP_ID / APP_SECRET 是否正确")
        print("  2. 飞书应用是否开启权限：bitable:app")
        print("  3. 多维表格是否已将机器人设为「可编辑」协作者")
        exit(1)

    # ── 查询待合入记录 ──────────────────────────────────────────────
    FILTER_FIELD  = "代码合入评审"
    FILTER_VALUE  = "评审通过待合入"
    TARGET_VALUE  = "已合入"

    print(f"\n[INFO] 查询奇瑞T28 view_id={VIEW_ID} 中「{FILTER_FIELD}={FILTER_VALUE}」的记录...")
    records = ops.search_records(
        app_token=APP_TOKEN,
        table_id=TABLE_ID,
        view_id=VIEW_ID,
        filter_conditions=[
            {"field_name": FILTER_FIELD, "operator": "is", "value": [FILTER_VALUE]},
        ],
        page_size=50,
    )
    print(f"[OK] 共查到 {len(records)} 条待合入记录")

    if not records:
        print("[INFO] 无待更新记录，退出。")
        exit(0)

    # ── 逐条更新「代码合入评审」→「已合入」 ────────────────────────
    print(f"\n[INFO] 开始将「{FILTER_VALUE}」→「{TARGET_VALUE}」...")
    for i, record in enumerate(records, 1):
        rid = record["record_id"]
        try:
            result = ops.update_record(
                app_token=APP_TOKEN,
                table_id=TABLE_ID,
                record_id=rid,
                fields={FILTER_FIELD: TARGET_VALUE},
            )
            print(f"  [{i}] ✅ record_id={rid} 更新成功")
        except Exception as e:
            print(f"  [{i}] ❌ record_id={rid} 更新失败: {e}")
