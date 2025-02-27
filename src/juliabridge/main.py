import asyncio
from collections.abc import Sequence
import inspect
import json
import logging
import os
import subprocess
from typing import Any

import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JuliaBridge:
    def __init__(self, timeout: int = 15, project_dir: str | None = None):
        self._included_files = []
        self._options = []
        self._timeout = timeout
        self._result = None  # 用于存储 Julia 函数的返回值
        self._index = 0  # 用于跟踪当前迭代的位置
        self._terminate_flag = False  # 用于标记是否终止 Julia 进程
        self._terminated_by_user = False  # 用于标记是否被用户终止
        self._sync_mode = True  # 默认使用同步模式
        self._temp_dir = os.path.join(os.path.dirname(__file__), '.temp')
        os.makedirs(self._temp_dir, exist_ok=True)

        if project_dir is not None:
            self._project_dir = self.__get_full_path_from_caller(project_dir)
            self.__setup_env()
        else:
            self._project_dir = None

    def set_sync_mode(self, sync_mode: bool) -> None:
        """设置调用模式：True 为同步，False 为异步"""
        self._sync_mode = sync_mode

    def __setup_env(self) -> None:
        """设置虚拟环境，或者说安装相关的依赖包。因为 project_dir 下的 Project.toml 和 Manifest.toml
        文件本身就代表了一种虚拟环境，我们现在做的只是安装其中的依赖包到 ~/.julia/packages 目录下。
        """
        try:
            # 构建创建虚拟环境的 Julia 命令
            if self._project_dir is not None:
                command = ['julia', '--project=' + self._project_dir, '-e', 'using Pkg; Pkg.instantiate()']
            else:
                raise ValueError('project_dir is not set')

            # 运行命令
            subprocess.run(command, check=True)
            logger.info(f'Dependencies of {self._project_dir} have been installed')
        except subprocess.CalledProcessError as e:
            logger.error(f'Error setting up environment: {e}')
            raise RuntimeError(f'Failed to set up environment: {e}')

    def __iter__(self):
        # 重置迭代器状态
        self._index = 0
        return self

    def __next__(self):
        if self._result is None:
            raise StopIteration('No result available to iterate over')

        if self._index >= len(self._result):
            raise StopIteration  # 停止迭代

        # 返回当前值并更新索引
        value = self._result[self._index]
        self._index += 1
        return value

    def __getattr__(self, name):
        def method(*args, **kwargs) -> Any:
            if self._sync_mode:
                # 同步调用：使用 asyncio.run 执行异步方法
                return asyncio.run(self.__call_julia(name, *args, **kwargs))
            else:
                # 异步调用：直接返回 Coroutine 对象
                return self.__call_julia(name, *args, **kwargs)

        return method

    async def __call_julia(self, func: str, *args, **kwargs):
        """调用 Julia 函数的通用方法"""
        if self.__init_julia(
            func,
            *args,
            included_files=self._included_files,
            **kwargs,
        ):
            try:
                result = await self.__run_julia(self._timeout)
                if result is not None:
                    return result  # 返回可迭代的结果（列表或元组）
                else:
                    print('\033[93mNo result returned from Julia\033[0m')
            except Exception as e:
                if not self._terminated_by_user:
                    print(f'Error running Julia: {e}')
        else:
            raise ValueError('Failed to initialize Julia function')

    def add_option(self, *options: str) -> None:
        self._options.extend(options)

    def remove_option(self, *options: str) -> None:
        for option in options:
            if option in self._options:
                self._options.remove(option)

    def include(self, *modules: str) -> 'JuliaBridge':
        # 添加 include 模块
        for module in modules:
            full_path = self.__get_full_path_from_caller(module)
            self._included_files.append(full_path)
        return self

    def add_pkg(self, *pkgs) -> None:
        # 添加包
        try:
            for pkg in pkgs:
                if self._project_dir is None:
                    command = ['julia', '-e', f'using Pkg; Pkg.add("{pkg}")']
                else:
                    command = ['julia', '--project=' + self._project_dir, '-e', f'using Pkg; Pkg.add("{pkg}")']
                subprocess.run(command, check=True)
                logger.info(f'{pkg} has been added')
        except subprocess.CalledProcessError as e:
            logger.error(f'Error adding package: {e}')
            raise RuntimeError(f'Failed to add package: {e}')

    def remove_pkg(self, *pkgs) -> None:
        # 移除包
        try:
            for pkg in pkgs:
                if self._project_dir is None:
                    command = ['julia', '-e', f'using Pkg; Pkg.rm("{pkg}")']
                else:
                    command = ['julia', '--project=' + self._project_dir, '-e', f'using Pkg; Pkg.rm("{pkg}")']
                subprocess.run(command, check=True)
                logger.info(f'{pkg} has been removed')
        except subprocess.CalledProcessError as e:
            logger.error(f'Error removing package: {e}')
            raise RuntimeError(f'Failed to remove package: {e}')

    def terminate(self) -> None:
        # 设置终止标志
        self._terminate_flag = True
        self._terminated_by_user = True
        print('\033[1;35mJulia process terminated by user\033[0m')

    def __get_full_path_from_caller(self, subpath: str) -> str:
        """根据调用者的路径获取文件的绝对路径"""
        if os.path.isabs(subpath):
            return subpath
        # 获取调用栈
        stack = inspect.stack()
        # 获取调用者的帧
        caller_frame = stack[2]
        # 获取调用者的文件名
        caller_filename = caller_frame.filename
        # 获取调用者的绝对路径
        caller_dir = os.path.dirname(os.path.abspath(caller_filename))
        # 拼接路径
        return os.path.join(caller_dir, subpath)

    def __init_julia(self, func: str, *args, included_files=None, **kwargs) -> bool:
        try:
            # 将 numpy 数组转换为列表，并记录参数类型和维度数
            args_list = []
            args_type = []
            args_dim = []  # 用于记录每个 ndarray 的维数

            for arg in args:
                if isinstance(arg, np.ndarray):
                    args_list.append(arg.tolist())
                    args_type.append('ndarray')
                    args_dim.append(arg.shape)  # 保存 ndarray 的形状
                else:
                    args_list.append(arg)
                    args_type.append(type(arg).__name__)
                    args_dim.append(None)  # 对于非 ndarray，设置为 None

            kwargs_list = {}
            kwargs_type = {}
            kwargs_dim = {}  # 用于记录 kwargs 中 ndarray 的维数
            for k, v in kwargs.items():
                # 跳过 include 模块
                if k in ['included_files']:
                    continue
                if isinstance(v, np.ndarray):
                    kwargs_list[k] = v.tolist()
                    kwargs_type[k] = 'ndarray'
                    kwargs_dim[k] = v.shape  # 保存 ndarray 的形状
                else:
                    kwargs_list[k] = v
                    kwargs_type[k] = type(v).__name__
                    kwargs_dim[k] = None  # 对于非 ndarray，设置为 None

            # 创建 payload，并将维度数信息一起存储
            payload = {
                'func': func,
                'args': args_list,
                'argstype': args_type,
                'argsdim': args_dim,  # 添加 ndarray 的形状
                'kwargs': kwargs_list,
                'kwargstype': kwargs_type,
                'kwargsdim': kwargs_dim,  # 添加 kwargs 中 ndarray 的形状
                'included_files': included_files,  # 添加 include 模块
            }

            with open(os.path.join(self._temp_dir, 'payload.json'), 'w') as f:
                json.dump(payload, f)
            return True
        except Exception as e:
            print(e)
            return False

    async def __wait_for_result(self, timeout: int) -> bool:
        try:
            if timeout == 0:
                return await self.__wait_for_file()  # 不设置超时
            else:
                # 使用 asyncio.wait_for 设定超时
                result = await asyncio.wait_for(self.__wait_for_file(), timeout)
            if result:
                print('\033[1;32mJulia process finished\033[0m')
            return result
        except TimeoutError:
            if not self._terminated_by_user:
                print('\033[1;31mTimeout reached\033[0m')
            return False

    async def __wait_for_file(self):
        # 检查文件是否存在
        while not os.path.exists(os.path.join(self._temp_dir, 'finished')):
            if self._terminate_flag:
                return False
            await asyncio.sleep(0.1)
        return True

    async def __run_julia(self, timeout: int) -> Sequence | None:
        # 构建 bridge.jl 的路径
        bridge_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bridge.jl')
        command = ['julia']
        # 构建使用指定环境运行的命令
        if self._project_dir is not None:
            command.extend(['--project=' + self._project_dir])
        command.extend(self._options + [bridge_script])

        process = subprocess.Popen(command, stdout=None)
        try:
            if timeout == 0:
                await self.__wait_for_file()
            else:
                await asyncio.wait_for(self.__wait_for_file(), timeout)  # 等待进程结束，设置超时时间
        except TimeoutError:
            process.kill()
            if not self._terminated_by_user:
                print('\033[1;35mJulia process killed due to timeout\033[0m')
            raise TimeoutError('result.json not found')

        if await self.__wait_for_result(timeout):
            try:
                with open(os.path.join(self._temp_dir, 'result.json')) as f:
                    result = json.load(f).get('result')
                    return result
            except Exception as e:
                if not self._terminated_by_user:
                    print(f'Error reading or processing result.json: {e}')
            finally:
                # 删除 result.json, finished
                if os.path.exists(os.path.join(self._temp_dir, 'result.json')):
                    os.remove(os.path.join(self._temp_dir, 'result.json'))
                if os.path.exists(os.path.join(self._temp_dir, 'finished')):
                    os.remove(os.path.join(self._temp_dir, 'finished'))
        else:
            process.kill()
            if not self._terminated_by_user:
                print('\033[1;35mJulia process killed due to timeout\033[0m')
            raise TimeoutError('result.json not found')
