import asyncio
from typing import Any

from juliabridge import JuliaBridge

# --------------------普通测试--------------------
# 创建 JuliaBridge 实例，设置超时时间为 15 秒
jb: Any = JuliaBridge(timeout=15)

# 测试 include Julia 文件
jb.include('test.jl')

# 测试调用 Julia 函数
result = jb.eval('1 + 1')
print(result)  # 2

jb.println('Hello, World!')  # Hello, World!

a = jb.plus(2, 332)
print(a)  # 334

# 测试超时自动关闭
jb.seconds_loop(5)  # 未超时
jb.seconds_loop(20)  # 超时

# 测试添加 Pkg
jb.add_pkg('Plots')

# 测试添加命令行参数
jb.add_option('--threads', '12')
threads = jb.show_threads_num()  # We are now using 12 threads for Julia!


# 测试异步模式和终止任务
async def main() -> None:
    jb.set_sync_mode(False)  # 设置为异步模式
    try:
        # 启动异步任务
        task = asyncio.create_task(jb.seconds_loop(30))  # 假设这个任务需要运行 30 秒

        # 等待 10 秒后终止任务
        await asyncio.sleep(10)
        jb.terminate()

        # 等待任务完成（如果任务被终止，这里会抛出异常）
        await task
    except TimeoutError:
        print('Task timed out')
    except asyncio.CancelledError:
        print('Task was cancelled by terminate()')
    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        jb.set_sync_mode(True)  # 恢复为同步模式


# 运行主函数
asyncio.run(main())

# --------------------测试虚拟环境--------------------
jb2: Any = JuliaBridge(project_dir='./julia_venv_test')

jb2.add_pkg('Plots')  # 此时应该出现 ./julia_venv_test/Project.toml 文件, 里面有 Plots 包
jb2.add_pkg('MAT')
jb2.remove_pkg('Plots')

# --------------------测试不限时--------------------
jb3: Any = JuliaBridge(timeout=0)
jb3.include('test.jl')
jb.seconds_loop(30)
