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
        self._modules_to_use = []  # 用于存储需要 using 的模块列表

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

    def use(self, *modules: str) -> 'JuliaBridge':
        """
        添加一个或多个模块名，这些模块将在每次调用 Julia 函数前被 using。
        返回 self，以便链式调用。
        """
        for module in modules:  # 'module' here is correctly inferred as str by Pylance
            if not isinstance(module, str) or not module:
                logger.warning(f"Invalid module name '{module}', must be a non-empty string.")
                continue
            # Pylance 误报：在这一行忽略类型检查错误
            if module not in self._modules_to_use:  # type: ignore
                self._modules_to_use.append(module)  # type: ignore
                logger.info(f"Added module '{module}' to be used in Julia process.")
        return self

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
        """
        准备调用 Julia 函数的 payload 数据，包括函数名、参数、类型、形状，
        以及需要 using 的模块列表和需要 include 的文件列表。
        """
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
                'modules': self._modules_to_use,  # 添加 using 模块
            }

            with open(os.path.join(self._temp_dir, 'payload.json'), 'w') as f:
                json.dump(payload, f)
            return True
        except Exception as e:
            print(e)
            return False

    async def _check_files(self, finished_path: str, error_log_path: str) -> str:
        while True:
            if os.path.exists(finished_path):
                return 'finished'
            if os.path.exists(error_log_path):
                return 'error'
            if self._terminate_flag:
                return 'terminated'
            await asyncio.sleep(0.1)

    async def __wait_for_result(self, timeout: int) -> str:
        """
        同时等待 finished 文件和 error.log 文件的出现。
        返回状态字符串：
        - "finished" 表示成功完成
        - "error" 表示发生错误
        - "timeout" 表示超时
        """
        finished_path = os.path.join(self._temp_dir, 'finished')
        error_log_path = os.path.join(self._temp_dir, 'error.log')

        try:
            # 使用 asyncio.wait_for 设定超时
            return await asyncio.wait_for(self._check_files(finished_path, error_log_path), timeout=timeout)
        except TimeoutError:
            return 'timeout'
        except Exception as e:
            # 捕获其他异常并返回一个默认值
            logger.error(f'Unexpected error in __wait_for_result: {e}')
            return 'error'

    async def __run_julia(self, timeout: int) -> Sequence | None:
        """
        运行 Julia 脚本并处理结果或错误。
        """
        # 构建 bridge.jl 的路径
        bridge_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bridge.jl')
        command = ['julia']
        if self._project_dir is not None:
            command.extend(['--project=' + self._project_dir])
        command.extend(self._options + [bridge_script])

        process = subprocess.Popen(command, stdout=None)
        try:
            # 等待结果或错误
            status = await self.__wait_for_result(timeout)

            if status == 'finished':
                # 读取结果文件
                result_path = os.path.join(self._temp_dir, 'result.json')
                with open(result_path) as f:
                    result = json.load(f).get('result')
                return result

            elif status == 'error':
                # 读取错误日志
                error_log_path = os.path.join(self._temp_dir, 'error.log')
                with open(error_log_path) as f:
                    error_message = f.read()
                raise RuntimeError(f'Julia process encountered an error:\n{error_message}')

            elif status == 'timeout':
                raise TimeoutError('Julia process timed out')

            elif status == 'terminated':
                raise RuntimeError('Julia process was terminated by user')

        finally:
            # 清理临时文件
            for file_name in ['result.json', 'finished', 'error.log']:
                file_path = os.path.join(self._temp_dir, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            # 确保进程被终止
            process.kill()
