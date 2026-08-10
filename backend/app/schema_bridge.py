"""把 Pydantic 模型轉成 Gemini 的 responseSchema。

存在的理由是「單一事實來源」：Outline 這個結構只在 schemas.py 定義一次，
既拿來驗證 API 回應，也拿來約束 LLM 的輸出。

如果兩邊各寫一份，總有一天會改了 A 忘了 B，然後模型產出的欄位跟後端期待的
對不起來——那種 bug 很難查，因為兩份定義單獨看都是對的。

轉換需要做兩件事：
1. Pydantic 產出的 JSON Schema 會把巢狀模型抽成 $defs 再用 $ref 指過去，
   Gemini 不吃這種寫法，要把它展開成內嵌結構。
2. 型別名稱從小寫（string）改成 Gemini 要的大寫（STRING），
   並丟掉 title、default 這些 Gemini 不認得的欄位。
"""

from typing import Any

from pydantic import BaseModel

_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}

# Gemini responseSchema 認得、且我們用得到的欄位
_PASSTHROUGH_KEYS = ("description", "enum", "minItems", "maxItems", "nullable")


def to_gemini_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    converted = _convert(raw, defs)
    # 最外層的 description 來自類別 docstring，那是寫給開發者看的，
    # 對模型只是雜訊。欄位層級的 description 才是真正在引導模型的說明。
    converted.pop("description", None)
    return converted


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    # $ref 展開。注意 description 可能掛在 $ref 的旁邊而不是被指向的定義裡，
    # 所以要先留著，展開後再補回去。
    sibling_description = node.get("description")
    if "$ref" in node:
        def_name = node["$ref"].rsplit("/", 1)[-1]
        node = defs[def_name]

    converted: dict[str, Any] = {}

    node_type = node.get("type")
    if node_type in _TYPE_MAP:
        converted["type"] = _TYPE_MAP[node_type]

    for key in _PASSTHROUGH_KEYS:
        if key in node:
            converted[key] = node[key]
    if sibling_description:
        converted["description"] = sibling_description

    if "properties" in node:
        converted["properties"] = {
            name: _convert(prop, defs) for name, prop in node["properties"].items()
        }
        # 明確指定欄位順序，讓模型的輸出順序穩定、也比較好讀
        converted["propertyOrdering"] = list(node["properties"].keys())
        if "required" in node:
            converted["required"] = node["required"]

    if "items" in node:
        converted["items"] = _convert(node["items"], defs)

    return converted
