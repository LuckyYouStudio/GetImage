# img.the5288.com 图片生成 HTTP 协议（自动化对接用）

本文档的每条结论都标注了来源：**[实测]** = 2026-09-09 真实请求验证过；**[未验证]** = 按 OpenAI 官方协议推断，接入前请自行确认。

---

## 1. 端点

| 项 | 值 |
|---|---|
| 生成图片 | `POST https://img.the5288.com/v1/images/generations` **[实测]** |
| 模型列表 | `GET https://img.the5288.com/v1/models` **[实测]** |
| 图片编辑 | `POST https://img.the5288.com/v1/images/edits` **[实测]** 可用，multipart/form-data，见第 3.1 节 |
| 图片变体 | `POST /v1/images/variations` **[实测]** 404，不支持 |

协议为 OpenAI Images API 兼容格式。

---

## 2. 请求头

```http
POST /v1/images/generations HTTP/1.1
Host: img.the5288.com
Content-Type: application/json
Authorization: Bearer sk-xxxxxxxx
User-Agent: curl/8.4.0
```

| 头 | 必需 | 说明 |
|---|---|---|
| `Authorization: Bearer <key>` | 是 | **[实测]** 服务端提示也接受 `x-api-key` 或 `x-goog-api-key`，但未实测 |
| `Content-Type: application/json` | 是 | **[实测]** |
| `User-Agent` | **是（见下）** | **[实测]** |

### ⚠️ User-Agent 陷阱 —— 自动化最容易踩的坑

**服务端会拦截 `User-Agent: Python-urllib/x.y`**，返回：

```json
HTTP 502
{"error":{"message":"Upstream access forbidden, please contact administrator","type":"upstream_error"}}
```

而 **Python 的 `urllib` 在请求头缺 UA 时会自动补上这个值**，所以下面这段看似正常的代码 100% 失败：

```python
# ❌ 必然 502
req = urllib.request.Request(url, data=body, headers={
    "Content-Type": "application/json",
    "Authorization": "Bearer " + key,
})
```

**[实测] 已验证可用的 UA：** `curl/8.4.0`、完全不发 UA。
**[实测] 已验证被拦的 UA：** `Python-urllib/3.12`。
其他 UA 字符串未逐一验证 —— 保险起见显式设成 `curl/8.4.0`。

`requests` 库自带 `python-requests/x.y` 的 UA，未实测是否被拦，建议同样显式覆盖。

---

## 3. 请求体

```json
{
  "model": "gpt-image-2",
  "prompt": "a blue ceramic mug on a windowsill, soft morning light",
  "n": 1,
  "size": "1024x1024"
}
```

| 字段 | 类型 | 状态 |
|---|---|---|
| `model` | string | **必需。[实测]** 只有 `gpt-image-2` 能出图，详见第 5 节 |
| `prompt` | string | **必需。[实测]** |
| `n` | int | **[实测] 传 `99` 不报错，但仍只返回 1 张。**是否支持 2–4 未验证 |
| `size` | string | **[实测] 传 `"1x1"` 不报错，返回的仍是 1024×1024。**见下方警告 |
| `quality` | string | **[未验证]** `low` / `medium` / `high` |
| `background` | string | **[未验证]** `transparent` / `opaque` / `auto` |
| `output_format` | string | **[未验证]** `png` / `jpeg` / `webp` |
| `response_format` | string | **[未验证]** gpt-image 系列通常不支持此字段，恒返回 base64 |

### 3.1 图生图 `POST /v1/images/edits` **[实测]**

`multipart/form-data`，不是 JSON：

| 字段 | 说明 |
|---|---|
| `model` | `gpt-image-2` |
| `prompt` | 对参考图要做什么 |
| `image` | 参考图文件（PNG / JPEG / WebP）。多张时用 `image[]` 重复字段 **[多张未验证]** |
| `n` / `size` / `quality` / `background` / `output_format` | 同 generations |

```bash
curl -X POST "https://img.the5288.com/v1/images/edits" \
  -H "Authorization: Bearer $API_KEY" -H "User-Agent: curl/8.4.0" --max-time 180 \
  -F "model=gpt-image-2" -F "prompt=把背景换成黄昏的海边" \
  -F "image=@photo.png;type=image/png" -o resp.json
```

**[实测]** 1×1 像素的输入图 + `prompt=make it red`，19.6 秒返回 `HTTP 200`，输出 1254×1254 PNG。响应结构与 generations 相同（见第 4 节）。

### ⚠️ 服务端不校验参数

**[实测]** 传入非法的 `size`（`"1x1"`）和 `n`（`99`），服务端**既不报错也不遵守**，直接按默认值生成并返回 `HTTP 200`。

对自动化的直接影响：

- **不能用 HTTP 状态码判断参数是否生效。** 想要特定尺寸，必须解析返回 PNG 的 IHDR 块自行校验（宽高在文件第 16–24 字节，大端 uint32）。
- **不能假设 `n` 生效。** 要多张就发多次请求。

唯一实测会被校验的字段是 `model`：

```json
HTTP 400
{"error":{"message":"images endpoint requires an image model, got \"__no_such_model__\"","type":"invalid_request_error"}}
```

---

## 4. 响应

### 成功 **[实测]**

```json
HTTP 200
{
  "created": 1788936242,
  "background": "auto",
  "output_format": "png",
  "quality": "...",
  "size": "...",
  "data": [
    { "b64_json": "iVBORw0KGgoAAAANSUhEUgAABAAAAAQA..." }
  ],
  "usage": {
    "input_tokens": 19,
    "input_tokens_details": { "image_tokens": 0, "text_tokens": 19 },
    "output_tokens": 343,
    "output_tokens_details": { "image_tokens": 343, "text_tokens": 0 },
    "total_tokens": 362
  }
}
```

顶层字段 **[实测]**：`created` `background` `output_format` `quality` `size` `data` `usage`。`usage` 结构如上 **[实测 2026-09-29]**：`quality: low` 的一张图 `output_tokens` 343、合计 362。**注意 `size` 字段回显的是服务端实际采用的值，不一定等于你传的**——见第 3 节的参数校验警告。

| 特征 | 实测值 |
|---|---|
| 图片载体 | `data[0].b64_json`，**未出现过 `url` 形式** |
| 图片格式 | PNG，1024×1024，8bit truecolor（colortype 2） |
| base64 长度 | 约 1.87–2.28 MB |
| 解码后大小 | 约 1.4 MB |
| **耗时** | **约 50–56 秒** |

图片内嵌 C2PA 出处元数据（base64 头部可见 `c2pa` / `jumb` 标记）。

### 超时设置

**[实测]** 单张稳定在 50–56 秒。客户端超时**至少设 180 秒**，别用默认的 30 秒。本项目 `proxy.py` 设的是 300 秒。

---

## 5. 模型可用性 **[实测]**

`/v1/models` 返回 22 个模型，图像类 3 个，但**只有一个真能用**：

| 模型 | 结果 |
|---|---|
| `gpt-image-2` | ✅ 正常出图 |
| `gpt-image-1.5` | ❌ `HTTP 502` `{"error":{"message":"Upstream request failed","type":"upstream_error"}}` |
| `gpt-image-1` | ❌ 同上 |

**模型出现在 `/v1/models` 列表里 ≠ 可用。** 自动化里不要靠列表做模型发现，硬编码 `gpt-image-2`，并对 502 做告警。

**2026-09-28 补充**：列表里新增了 `gpt-image-2.5`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`，**均未实测**。同日用 `gpt-image-2` + `size=1024x1024` + 不传 `quality` 生成，服务端返回的是 **1370×1148、`quality: "low"`**（9 月 9 日同样参数返回 1024×1024）——再次印证参数由上游决定、随时可能变，以返回的 `size` / `quality` 字段和实际图片为准。

图生图 `/v1/images/edits` 同日实测：2 张参考图（`image[]`）+ 不传 `quality`，38 秒返回 1370×1148、`quality: "medium"`、3813 tokens。文生图 2 张并发各 27 秒、522 tokens。

其余 19 个是 `gpt-5.2` ~ `gpt-6` 系列文本模型。

---

## 6. 错误格式

**服务端混用两种错误结构**，解析时必须都兼容：

```json
{"error": {"message": "...", "type": "..."}}     // 网关层
{"code": "INVALID_API_KEY", "message": "..."}    // 鉴权层
```

| HTTP | 响应 | 含义 |
|---|---|---|
| 400 | `{"error":{"type":"invalid_request_error"}}` | 模型名不是图像模型 **[实测]** |
| 401 | `{"code":"API_KEY_REQUIRED"}` | 没带 Authorization 头 **[实测]** |
| 401 | `{"code":"INVALID_API_KEY"}` | Key 无效 **[实测]** |
| 502 | `{"error":{"message":"Upstream access forbidden, please contact administrator"}}` | **UA 被拦**，见第 2 节 **[实测]** |
| 502 | `{"error":{"message":"Upstream request failed"}}` | 上游通道故障，换模型或稍后重试 **[实测]** |

推荐的解析顺序：`json.error.message` → `json.message`（有 `code` 就拼在前面）→ 原始响应体截断。

### CORS **[实测]**

`OPTIONS` 预检返回 **403 且不下发任何 `Access-Control-Allow-*` 头**。浏览器端无法直连，必须经服务端中转（本项目的 `proxy.py` 就是干这个的）。命令行和服务端程序不受影响。

---

## 7. 可运行示例

### curl

```bash
curl -X POST "https://img.the5288.com/v1/images/generations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "User-Agent: curl/8.4.0" \
  --max-time 180 \
  -d '{"model":"gpt-image-2","prompt":"a blue ceramic mug","n":1,"size":"1024x1024"}' \
  -o resp.json
```

### Python（标准库，无依赖）

```python
import base64, json, struct, urllib.request

API_KEY = "sk-..."
URL = "https://img.the5288.com/v1/images/generations"

def generate(prompt, out_path, model="gpt-image-2", size="1024x1024"):
    body = json.dumps({
        "model": model, "prompt": prompt, "n": 1, "size": size,
    }).encode("utf-8")

    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
        "User-Agent": "curl/8.4.0",   # 关键：不设会变成 Python-urllib 而被 502 拦掉
    })

    with urllib.request.urlopen(req, timeout=180) as r:   # 单张约 50 秒
        payload = json.load(r)

    raw = base64.b64decode(payload["data"][0]["b64_json"])
    with open(out_path, "wb") as f:
        f.write(raw)

    # 服务端不保证遵守 size，自己从 PNG IHDR 读真实尺寸
    w, h = struct.unpack(">II", raw[16:24])
    return w, h

print(generate("a blue ceramic mug on a windowsill", "out.png"))
```

错误处理（`HTTPError` 的响应体带着真正的原因，务必读出来）：

```python
import urllib.error

try:
    ...
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace")
    raise RuntimeError("HTTP %d: %s" % (e.code, detail))
```

### Node.js（18+，无依赖）

```javascript
import { writeFile } from "node:fs/promises";

const API_KEY = process.env.API_KEY;

async function generate(prompt, outPath) {
  const res = await fetch("https://img.the5288.com/v1/images/generations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${API_KEY}`,
      "User-Agent": "curl/8.4.0",
    },
    body: JSON.stringify({
      model: "gpt-image-2", prompt, n: 1, size: "1024x1024",
    }),
    signal: AbortSignal.timeout(180_000),
  });

  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`);

  const json = JSON.parse(text);
  await writeFile(outPath, Buffer.from(json.data[0].b64_json, "base64"));
}
```

### PowerShell

```powershell
$body = @{ model = "gpt-image-2"; prompt = "a blue ceramic mug"; n = 1; size = "1024x1024" } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "https://img.the5288.com/v1/images/generations" -Method Post `
  -Headers @{ Authorization = "Bearer $env:API_KEY"; "User-Agent" = "curl/8.4.0" } `
  -ContentType "application/json" -Body $body -TimeoutSec 180
[IO.File]::WriteAllBytes("out.png", [Convert]::FromBase64String($resp.data[0].b64_json))
```

---

## 8. 自动化对接检查清单

- [ ] 显式设置 `User-Agent`（**别让 urllib 用默认值**）
- [ ] 超时 ≥ 180 秒
- [ ] 模型硬编码 `gpt-image-2`，不做列表发现
- [ ] 两种错误结构都要解析
- [ ] 502 单独告警：区分 UA 被拦（代码问题）和上游故障（可重试）
- [ ] 需要特定尺寸就解析 PNG IHDR 校验，别信请求参数
- [ ] 需要多张就发多次请求，别依赖 `n`
- [ ] 串行调用，并发上限未测试
- [ ] 响应体约 2MB，注意内存和日志（**别把 base64 打进日志**）

---

## 9. 尚未验证的部分

以下都需要真实调用才能确认，每次约 50 秒并消耗额度：

- `quality` / `background` / `output_format` 是否真正生效
- `n = 2..4` 能否返回多张
- `1536x1024`、`1024x1536` 等非方形尺寸是否被遵守
- `/v1/images/edits` 传多张参考图（`image[]`）是否支持
- 并发限制、速率限制、单 Key 配额
- 是否有内容审核拦截及其错误形态

单条验证命令模板：

```bash
curl -X POST "https://img.the5288.com/v1/images/generations" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $API_KEY" \
  -H "User-Agent: curl/8.4.0" --max-time 180 \
  -d '{"model":"gpt-image-2","prompt":"test","size":"1536x1024"}' \
  -o r.json -w "%{http_code} %{time_total}s\n"
python -c "import json,base64,struct;d=base64.b64decode(json.load(open('r.json'))['data'][0]['b64_json']);print(struct.unpack('>II',d[16:24]))"
```
