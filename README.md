# MinerU PDF转Markdown服务

基于Sglang-VLM的高性能PDF转Markdown服务，支持复杂表格、公式、图像的智能解析。

## 🚀 快速开始

```bash
# 构建并启动服务
docker build -t mineru-pdf-service:latest .
docker run --gpus '"device=0"' -p 8007:8080 --shm-size 100g --ipc=host -d mineru-pdf-service:latest

# 验证服务
curl http://localhost:8007/health
```

**系统要求**: NVIDIA GPU (16GB+显存) + 32GB RAM + Docker

## 📋 API接口

### PDF转换接口

**POST /convert** - 上传PDF文件转换为Markdown
```bash
curl -X POST http://localhost:8007/convert -F "file=@document.pdf"
```

响应格式：
```json
{
  "status": "success",
  "data": {
    "markdown": "转换后的markdown内容...",
    "metadata": {
      "filename": "document.pdf",
      "pages": 5,
      "processing_time_seconds": 12.34
    }
  }
}
```

**限制**: 单文件最大200MB，支持8个并发请求

### 其他接口

**GET /health** - 健康检查 | **GET /** - 服务信息

### 🔄 从mineru1微服务迁移

如果你的微服务之前使用 `response.get("text")`，现在需要改为：

```python
# 适配新版本响应格式
response_data = response.json()
if response_data.get("status") == "success" and "data" in response_data:
    markdown_content = response_data["data"]["markdown"]
    metadata = response_data["data"]["metadata"]
else:
    # 兼容旧版本格式
    markdown_content = response_data.get("text")
```

## 💻 集成示例

### 单文件处理

```python
import requests

def convert_pdf(pdf_path, api_url="http://localhost:8007"):
    """单个PDF文件转换"""
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{api_url}/convert", files=files)

    if response.status_code == 200:
        result = response.json()
        return result['data']['markdown']
    else:
        raise Exception(f"转换失败: {response.json().get('detail')}")

# 使用示例
markdown = convert_pdf('document.pdf')
with open('output.md', 'w', encoding='utf-8') as f:
    f.write(markdown)
```

### 批量处理

```python
import asyncio
import aiohttp
import os
from pathlib import Path

async def process_single_pdf(session, pdf_path, api_url):
    """处理单个PDF文件"""
    try:
        with open(pdf_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=os.path.basename(pdf_path))

            async with session.post(f"{api_url}/convert", data=data) as response:
                result = await response.json()
                return {"file": pdf_path, "success": True, "result": result}
    except Exception as e:
        return {"file": pdf_path, "success": False, "error": str(e)}

async def batch_process_pdfs(pdf_files, api_url="http://localhost:8007", max_concurrent=3):
    """批量处理PDF文件"""
    semaphore = asyncio.Semaphore(max_concurrent)  # 控制并发数

    async def process_with_semaphore(session, pdf_path):
        async with semaphore:
            return await process_single_pdf(session, pdf_path, api_url)

    async with aiohttp.ClientSession() as session:
        tasks = [process_with_semaphore(session, pdf) for pdf in pdf_files]
        results = await asyncio.gather(*tasks)

    return results

# 使用示例
async def main():
    pdf_dir = Path("./pdfs")
    pdf_files = list(pdf_dir.glob("*.pdf"))

    results = await batch_process_pdfs(pdf_files, max_concurrent=3)

    # 处理结果
    for result in results:
        if result["success"]:
            output_path = Path(result["file"]).with_suffix(".md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result["result"]["data"]["markdown"])
            print(f"✅ 已转换: {result['file']} → {output_path}")
        else:
            print(f"❌ 转换失败: {result['file']} - {result['error']}")

# 运行批处理
if __name__ == "__main__":
    asyncio.run(main())
```




## 🔧 运维参考

```bash
# 健康检查
curl -f http://localhost:8007/health

# 查看日志
docker logs -f mineru-pdf-service

# 重启服务
docker restart mineru-pdf-service

# 设置自动重启
docker update --restart=always mineru-pdf-service
```

---

*最后更新: 2025-07-11*