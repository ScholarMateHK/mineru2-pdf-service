import asyncio
import aiohttp
import time
import tempfile
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.data.data_reader_writer import FileBasedDataWriter

async def test_vlm_concurrent(concurrent_num):
    """测试VLM服务的并发处理能力"""
    
    async def single_vlm_test(test_id):
        try:
            start_time = time.time()
            
            # 创建一个简单的测试PDF字节（你需要提供一个小的测试PDF）
            # 这里用空字节模拟，实际需要真实PDF
            test_pdf_bytes = b"test_pdf_content"  # 替换为真实PDF
            
            temp_dir = tempfile.mkdtemp()
            image_writer = FileBasedDataWriter(temp_dir)
            
            # 调用VLM分析
            middle_json, infer_result = vlm_doc_analyze(
                test_pdf_bytes,
                image_writer=image_writer,
                backend='sglang-client',
                server_url='http://localhost:80'
            )
            
            duration = time.time() - start_time
            print(f"VLM请求{test_id}: 成功, 耗时{duration:.2f}s")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"VLM请求{test_id}: 失败 - {e}, 耗时{duration:.2f}s")
            return False
    
    # 并发执行
    tasks = [single_vlm_test(i) for i in range(concurrent_num)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    print(f"并发{concurrent_num}: 成功{success_count}/{concurrent_num}")
    return success_count

async def main():
    print("测试sglang VLM服务并发能力...")
    
    for concurrent in [1, 2, 3, 4, 5, 6, 7, 8]:
        print(f"\n=== 测试并发数: {concurrent} ===")
        await test_vlm_concurrent(concurrent)
        await asyncio.sleep(2)  # 间隔2秒

if __name__ == "__main__":
    asyncio.run(main())