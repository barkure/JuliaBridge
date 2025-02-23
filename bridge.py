import asyncio
import json
import os
import subprocess
from typing import Optional, Sequence

import numpy as np


class JuliaBridge:
    def __init__(self):
        self._included_files = []
        self._result = None  # 用于存储 Julia 函数的返回值
        self._index = 0  # 用于跟踪当前迭代的位置

    def __iter__(self):
        # 重置迭代器状态
        self._index = 0
        return self

    def __next__(self):
        if self._result is None:
            raise StopIteration("No result available to iterate over")

        if self._index >= len(self._result):
            raise StopIteration  # 停止迭代

        # 返回当前值并更新索引
        value = self._result[self._index]
        self._index += 1
        return value

    def __getattr__(self, name):
        def method(*args, **kwargs):
            # 调用 Julia 函数
            if init_julia(name, *args, included_files=self._included_files, **kwargs):
                result = asyncio.run(run_julia())
                if result is not None:
                    return result  # 返回可迭代的结果（列表或元组）
                else:
                    raise ValueError("Julia function returned None")
            else:
                raise ValueError("Failed to initialize Julia function")

        return method

    def include(self, *modules):
        # 添加 include 模块
        self._included_files.extend(modules)
        return self


def init_julia(func: str, *args, included_files=None, **kwargs) -> bool:
    try:
        # 将 numpy 数组转换为列表，并记录参数类型和维度数
        args_list = []
        args_type = []
        args_dim = []  # 用于记录每个 ndarray 的维数

        for arg in args:
            if isinstance(arg, np.ndarray):
                args_list.append(arg.tolist())
                args_type.append("ndarray")
                args_dim.append(arg.shape)  # 保存 ndarray 的形状
            else:
                args_list.append(arg)
                args_type.append(type(arg).__name__)
                args_dim.append(None)  # 对于非 ndarray，设置为 None

        kwargs_list = {}
        kwargs_type = {}
        kwargs_dim = {}  # 用于记录 kwargs 中 ndarray 的维数
        for k, v in kwargs.items():
            if k == "included_files":
                continue  # 跳过 include 参数
            if isinstance(v, np.ndarray):
                kwargs_list[k] = v.tolist()
                kwargs_type[k] = "ndarray"
                kwargs_dim[k] = v.shape  # 保存 ndarray 的形状
            else:
                kwargs_list[k] = v
                kwargs_type[k] = type(v).__name__
                kwargs_dim[k] = None  # 对于非 ndarray，设置为 None

        # 创建 payload，并将维度数信息一起存储
        payload = {
            "func": func,
            "args": args_list,
            "argstype": args_type,
            "argsdim": args_dim,  # 添加 ndarray 的形状
            "kwargs": kwargs_list,
            "kwargstype": kwargs_type,
            "kwargsdim": kwargs_dim,  # 添加 kwargs 中 ndarray 的形状
            "included_files": included_files,  # 添加 include 模块
        }

        os.makedirs(".temp", exist_ok=True)
        with open(".temp/payload.json", "w") as f:
            json.dump(payload, f)
        return True
    except Exception as e:
        print(e)
        return False


# 异步等待 result.json 文件生成
async def wait_for_result(timeout: int) -> bool:
    for _ in range(timeout * 10):  # 每 0.1 秒检查一次，最多等待 timeout 秒
        if os.path.exists(".temp/finished"):
            return True
        await asyncio.sleep(0.1)
    return False


async def run_julia() -> Optional[Sequence]:
    process = subprocess.Popen(["julia", "bridge.jl"], stdout=subprocess.PIPE)

    # 等待 result.json 文件生成，超时时间为 10 秒
    if await wait_for_result(600):
        try:
            with open(".temp/result.json", "r") as f:
                result = json.load(f).get("result")
                if result is not None:
                    return result
                else:
                    raise ValueError(
                        "The 'result' key is missing or None in result.json"
                    )
        except Exception as e:
            print(f"Error reading or processing result.json: {e}")
            return None
        finally:
            # 删除 result.json, finished
            if os.path.exists(".temp/result.json"):
                os.remove(".temp/result.json")
            if os.path.exists(".temp/finished"):
                os.remove(".temp/finished")
    else:
        process.kill()
        raise TimeoutError("Timed out waiting for result.json")
