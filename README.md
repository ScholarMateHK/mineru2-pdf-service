# MinerU VLM PDF转Markdown微服务

基于先进VLM技术的高性能PDF文档转Markdown服务，支持复杂表格、公式、图像的智能解析。

## 🚀 快速开始

### 部署服务

```bash
# 1. 准备文件
git clone <repository> 
cd mineru-pdf-service/

# 2. 构建镜像
docker build -t mineru-pdf-service:latest .

# 3. 启动服务
docker run --gpus '"device=0"' \
  -p 8007:8080 \
  --shm-size 100g \
  --ipc=host \
  -d \
  --name mineru-pdf-service \
  mineru-pdf-service:latest

# 4. 验证服务
curl http://localhost:8007/health
```

### 系统要求

- **GPU**: NVIDIA GPU (16GB+ 显存推荐)
- **内存**: 32GB+ RAM推荐  
- **存储**: 50GB+ 可用空间
- **软件**: Docker + nvidia-docker支持

## 📚 API文档

### 基础信息

- **服务地址**: `http://localhost:8007`
- **请求限制**: 200MB文件大小，支持8个并发请求
- **响应格式**: JSON
- **支持格式**: PDF

### 接口列表

#### 1. 健康检查

```http
GET /health
```

**响应示例**:
```json
{
  "status": "healthy",
  "vlm_service": "available", 
  "service": "MinerU PDF to Markdown Converter"
}
```

#### 2. 服务信息

```http
GET /
```

**响应示例**:
```json
{
  "service": "MinerU VLM PDF to Markdown Service",
  "version": "1.0.0",
  "description": "Convert PDF documents to Markdown format using advanced VLM technology",
  "endpoints": {
    "POST /convert": "Convert PDF file to Markdown",
    "GET /health": "Service health check", 
    "GET /": "Service information"
  },
  "usage": {
    "max_file_size": "200MB",
    "supported_formats": ["PDF"]
  }
}
```

#### 3. PDF转Markdown (核心接口)

```http
POST /convert
```

**请求参数**:
- `file`: PDF文件 (multipart/form-data)

**请求示例**:
```bash
curl -X POST http://localhost:8007/convert \
  -F "file=@document.pdf"
```

**成功响应** (HTTP 200):
```json
{
  "status": "success",
  "data": {
    "markdown": "# 标题\n\n这是转换后的markdown内容...",
    "metadata": {
      "filename": "document.pdf",
      "pages": 5,
      "processing_time_seconds": 12.34
    }
  }
}
```

**错误响应**:
```json
{
  "detail": "Only PDF files are supported. Please upload a .pdf file."
}
```

**错误码说明**:
- `400`: 文件格式错误、文件为空
- `413`: 文件过大 (>200MB)
- `500`: 服务内部错误

## 💻 集成示例

### Python集成

```python
import requests

def convert_pdf_to_markdown(pdf_file_path, service_url="http://localhost:8007"):
    """
    将PDF文件转换为Markdown
    
    Args:
        pdf_file_path: PDF文件路径
        service_url: 服务地址
        
    Returns:
        dict: 包含markdown内容和元数据的字典
    """
    try:
        with open(pdf_file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{service_url}/convert", files=files)
            
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'markdown': result['data']['markdown'],
                'metadata': result['data']['metadata']
            }
        else:
            return {
                'success': False,
                'error': response.json().get('detail', 'Unknown error')
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# 使用示例
result = convert_pdf_to_markdown('document.pdf')
if result['success']:
    print(f"转换成功！页数: {result['metadata']['pages']}")
    print(f"处理时间: {result['metadata']['processing_time_seconds']}秒")
    # 保存markdown
    with open('output.md', 'w', encoding='utf-8') as f:
        f.write(result['markdown'])
else:
    print(f"转换失败: {result['error']}")
```





## 🔧 运维指南

### 监控检查

```bash
# 健康检查
curl -f http://localhost:8007/health || echo "Service unhealthy"

# 性能测试
time curl -X POST http://localhost:8007/convert -F "file=@test.pdf" > /dev/null
```

### 日志查看

```bash
# 查看容器日志
docker logs mineru-pdf-service

# 实时日志
docker logs -f mineru-pdf-service
```

### 重启服务

```bash
# 重启容器
docker restart mineru-pdf-service

# 或重新部署
docker stop mineru-pdf-service
docker rm mineru-pdf-service
docker run --gpus '"device=0"' -p 8007:8080 --shm-size 100g --ipc=host -d --name mineru-pdf-service mineru-pdf-service:latest
```


---

*最后更新: 2025-07-10* 