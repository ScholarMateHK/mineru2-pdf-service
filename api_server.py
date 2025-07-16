import os
import time
import tempfile
import shutil
import requests
import threading
from typing import Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode

app = FastAPI(
    title="MinerU VLM PDF to Markdown Service", 
    version="1.0.0",
    description="High-performance PDF to Markdown conversion service"
)

# 线程池用于CPU密集型任务 - 最保守的稳定配置
executor = ThreadPoolExecutor(max_workers=2)

# PDF预处理互斥锁 - 防止并发时的资源竞争
pdf_processing_lock = threading.Lock()

# VLM服务并发限制 - 防止VLM服务过载
vlm_semaphore = threading.Semaphore(2)  # 最多2个并发VLM请求

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_vlm_service():
    """检查VLM服务是否健康"""
    try:
        response = requests.get("http://localhost:80/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def wait_for_vlm_service(max_wait=60):
    """等待VLM服务恢复"""
    logger.info("Waiting for VLM service to recover...")
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if check_vlm_service():
            logger.info("VLM service is healthy again")
            return True
        time.sleep(2)
    logger.error("VLM service did not recover within timeout")
    return False

def process_pdf_to_markdown(pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    核心PDF处理函数 - 只返回markdown内容，不保存文件，带重试机制
    """
    import threading
    thread_id = threading.current_thread().ident
    logger.info(f"[Thread {thread_id}] Starting processing {filename}")

    start_time = time.time()
    temp_dir = None
    max_retries = 2

    try:
        for attempt in range(max_retries + 1):
            try:
                # 检查VLM服务状态
                if not check_vlm_service():
                    logger.warning(f"VLM service unhealthy on attempt {attempt + 1}")
                    if attempt < max_retries:
                        wait_for_vlm_service()
                        continue
                    else:
                        raise Exception("VLM service is unavailable after retries")

                # 创建临时目录
                if temp_dir is None:
                    temp_dir = tempfile.mkdtemp()

                # PDF预处理 - 使用互斥锁防止并发竞争
                logger.info(f"[Thread {thread_id}] Acquiring PDF processing lock for {filename}")
                with pdf_processing_lock:
                    logger.info(f"[Thread {thread_id}] PDF processing lock acquired for {filename}")
                    pdf_file_name = filename.replace('.pdf', '').replace(' ', '_')
                    processed_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
                    logger.info(f"[Thread {thread_id}] PDF preprocessing completed for {filename}")

                # 准备临时环境（不保存到永久位置）
                local_image_dir, _ = prepare_env(temp_dir, pdf_file_name, 'auto')
                image_writer = FileBasedDataWriter(local_image_dir)

                # VLM分析 - 使用信号量限制并发数
                logger.info(f"[Thread {thread_id}] Acquiring VLM semaphore for {filename}")
                with vlm_semaphore:
                    logger.info(f"[Thread {thread_id}] VLM semaphore acquired, calling VLM service for {filename}")
                    middle_json, _ = vlm_doc_analyze(
                        processed_pdf_bytes,
                        image_writer=image_writer,
                        backend='sglang-client',
                        server_url='http://localhost:80'
                    )
                    logger.info(f"[Thread {thread_id}] VLM analysis completed for {filename}")

                # 生成markdown（内存中处理，不写文件）
                pdf_info = middle_json["pdf_info"]
                image_dir = str(os.path.basename(local_image_dir))
                markdown_content = vlm_union_make(pdf_info, MakeMode.MM_MD, image_dir)

                processing_time = time.time() - start_time

                return {
                    "success": True,
                    "markdown": markdown_content,
                    "pages": len(pdf_info),
                    "processing_time_seconds": round(processing_time, 2),
                    "filename": filename
                }

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries:
                    logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2)  # 等待2秒再重试
                    continue
                else:
                    # 最后一次尝试失败
                    raise e

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time_seconds": round(time.time() - start_time, 2),
            "filename": filename
        }

    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass  # 静默处理清理失败

@app.post("/convert")
async def convert_pdf_to_markdown(file: UploadFile = File(...)):
    """
    PDF转Markdown API
    
    Parameters:
    - file: PDF文件
    
    Returns:
    - markdown: 转换后的markdown内容
    - metadata: 处理信息
    """
    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDF files are supported. Please upload a .pdf file."
        )
    
    # 检查文件大小（限制200MB）
    if file.size and file.size > 200 * 1024 * 1024:
        raise HTTPException(
            status_code=413, 
            detail="File too large. Maximum size is 200MB."
        )
    
    try:
        # 读取PDF内容
        pdf_content = await file.read()
        
        if len(pdf_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
        
        # 异步处理（避免阻塞其他请求）
        logger.info(f"Submitting {file.filename} to thread pool (active threads: {executor._threads})")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            process_pdf_to_markdown,
            pdf_content,
            file.filename
        )
        logger.info(f"Completed processing {file.filename}")
        
        if result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "data": {
                        "markdown": result["markdown"],
                        "metadata": {
                            "filename": result["filename"],
                            "pages": result["pages"],
                            "processing_time_seconds": result["processing_time_seconds"]
                        }
                    }
                }
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Processing failed: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 简单检查VLM服务是否可用
        import requests
        response = requests.get("http://localhost:80/health", timeout=5)
        vlm_healthy = response.status_code == 200
        vlm_response_time = response.elapsed.total_seconds() if vlm_healthy else None
    except Exception as e:
        vlm_healthy = False
        vlm_response_time = None

    return {
        "status": "healthy" if vlm_healthy else "degraded",
        "vlm_service": "available" if vlm_healthy else "unavailable",
        "vlm_response_time_seconds": vlm_response_time,
        "max_concurrent_workers": 2,
        "service": "MinerU PDF to Markdown Converter"
    }

@app.get("/")
async def root():
    """服务信息"""
    return {
        "service": "MinerU VLM PDF to Markdown Service",
        "version": "1.0.0",
        "description": "Convert PDF documents to Markdown format using advanced VLM technology",
        "endpoints": {
            "POST /convert": "Convert PDF file to Markdown (upload file)",
            "GET /health": "Service health check",
            "GET /": "Service information"
        },
                 "usage": {
             "curl_example": "curl -X POST http://localhost:8080/convert -F 'file=@document.pdf'",
             "max_file_size": "200MB",
             "supported_formats": ["PDF"]
         }
    }

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080,
        workers=1,  # 单worker避免GPU冲突
        loop="asyncio"
    ) 