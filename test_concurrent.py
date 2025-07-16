#!/usr/bin/env python3
"""
并发测试脚本 - 用于测试MinerU PDF服务的并发处理能力
"""

import asyncio
import aiohttp
import time
import json
import os
from pathlib import Path
import argparse

async def test_single_request(session, api_url, test_file_path, request_id):
    """测试单个请求"""
    start_time = time.time()
    try:
        with open(test_file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=f'test_{request_id}.pdf')
            
            async with session.post(f"{api_url}/convert", data=data, timeout=300) as response:
                end_time = time.time()
                
                if response.status == 200:
                    result = await response.json()
                    return {
                        "request_id": request_id,
                        "success": True,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "processing_time": result.get("data", {}).get("metadata", {}).get("processing_time_seconds", 0),
                        "pages": result.get("data", {}).get("metadata", {}).get("pages", 0)
                    }
                else:
                    error_text = await response.text()
                    return {
                        "request_id": request_id,
                        "success": False,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "error": error_text[:200]  # 限制错误信息长度
                    }
                    
    except Exception as e:
        end_time = time.time()
        return {
            "request_id": request_id,
            "success": False,
            "status_code": 0,
            "response_time": end_time - start_time,
            "error": str(e)[:200]
        }

async def test_concurrent_requests(api_url, test_file_path, concurrent_count, total_requests=None):
    """测试并发请求"""
    if total_requests is None:
        total_requests = concurrent_count
    
    print(f"开始测试: {concurrent_count}个并发请求，总共{total_requests}个请求")
    print(f"API地址: {api_url}")
    print(f"测试文件: {test_file_path}")
    print("-" * 50)
    
    # 检查健康状态
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"服务健康状态: {health_data}")
                else:
                    print(f"警告: 健康检查失败，状态码: {response.status}")
    except Exception as e:
        print(f"错误: 无法连接到服务 - {e}")
        return
    
    # 创建信号量控制并发数
    semaphore = asyncio.Semaphore(concurrent_count)
    
    async def controlled_request(session, request_id):
        async with semaphore:
            return await test_single_request(session, api_url, test_file_path, request_id)
    
    start_time = time.time()
    
    # 执行并发测试
    async with aiohttp.ClientSession() as session:
        tasks = [controlled_request(session, i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 分析结果
    successful_requests = [r for r in results if isinstance(r, dict) and r.get("success")]
    failed_requests = [r for r in results if isinstance(r, dict) and not r.get("success")]
    exceptions = [r for r in results if not isinstance(r, dict)]
    
    print("\n" + "="*50)
    print("测试结果汇总:")
    print(f"总请求数: {total_requests}")
    print(f"成功请求: {len(successful_requests)}")
    print(f"失败请求: {len(failed_requests)}")
    print(f"异常请求: {len(exceptions)}")
    print(f"成功率: {len(successful_requests)/total_requests*100:.1f}%")
    print(f"总耗时: {total_time:.2f}秒")
    
    if successful_requests:
        avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
        avg_processing_time = sum(r.get("processing_time", 0) for r in successful_requests) / len(successful_requests)
        print(f"平均响应时间: {avg_response_time:.2f}秒")
        print(f"平均处理时间: {avg_processing_time:.2f}秒")
        print(f"吞吐量: {len(successful_requests)/total_time:.2f} 请求/秒")
    
    # 显示失败详情
    if failed_requests:
        print("\n失败请求详情:")
        for req in failed_requests[:5]:  # 只显示前5个失败请求
            print(f"  请求{req['request_id']}: 状态码{req['status_code']}, 错误: {req.get('error', 'Unknown')}")
    
    if exceptions:
        print(f"\n异常详情: {exceptions[:3]}")  # 只显示前3个异常
    
    return {
        "concurrent_count": concurrent_count,
        "total_requests": total_requests,
        "successful": len(successful_requests),
        "failed": len(failed_requests),
        "success_rate": len(successful_requests)/total_requests*100,
        "total_time": total_time,
        "avg_response_time": avg_response_time if successful_requests else 0,
        "throughput": len(successful_requests)/total_time if total_time > 0 else 0
    }

async def find_max_concurrent(api_url, test_file_path, start_concurrent=1, max_concurrent=10, step=1):
    """逐步增加并发数，找到最大并发能力"""
    print("开始寻找最大并发能力...")
    results = []
    
    for concurrent in range(start_concurrent, max_concurrent + 1, step):
        print(f"\n测试并发数: {concurrent}")
        result = await test_concurrent_requests(api_url, test_file_path, concurrent, concurrent * 2)
        results.append(result)
        
        # 如果成功率低于80%，停止测试
        if result["success_rate"] < 80:
            print(f"成功率降至{result['success_rate']:.1f}%，停止测试")
            break
        
        # 等待一段时间让服务恢复
        await asyncio.sleep(2)
    
    # 输出最终建议
    print("\n" + "="*60)
    print("并发能力测试总结:")
    for result in results:
        print(f"并发{result['concurrent_count']}: 成功率{result['success_rate']:.1f}%, "
              f"吞吐量{result['throughput']:.2f}req/s")
    
    # 找到最佳并发数
    good_results = [r for r in results if r["success_rate"] >= 95]
    if good_results:
        best_result = max(good_results, key=lambda x: x["throughput"])
        print(f"\n推荐并发数: {best_result['concurrent_count']} (成功率{best_result['success_rate']:.1f}%)")
    else:
        print("\n警告: 没有找到稳定的并发配置")

def main():
    parser = argparse.ArgumentParser(description="MinerU PDF服务并发测试")
    parser.add_argument("--api-url", default="http://localhost:8007", help="API服务地址")
    parser.add_argument("--test-file", required=True, help="测试用的PDF文件路径")
    parser.add_argument("--concurrent", type=int, help="指定并发数进行单次测试")
    parser.add_argument("--find-max", action="store_true", help="自动寻找最大并发能力")
    parser.add_argument("--max-test", type=int, default=8, help="最大测试并发数")
    
    args = parser.parse_args()
    
    # 检查测试文件
    if not os.path.exists(args.test_file):
        print(f"错误: 测试文件不存在: {args.test_file}")
        return
    
    if args.find_max:
        asyncio.run(find_max_concurrent(args.api_url, args.test_file, max_concurrent=args.max_test))
    elif args.concurrent:
        asyncio.run(test_concurrent_requests(args.api_url, args.test_file, args.concurrent))
    else:
        print("请指定 --concurrent N 或 --find-max")

if __name__ == "__main__":
    main()
