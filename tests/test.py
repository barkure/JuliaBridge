from typing import Any

from juliabridge import JuliaBridge

# 创建 JuliaBridge 实例，设置超时时间为 10 秒
julia: Any = JuliaBridge(timeout=10)

# 测试 include Julia 文件
julia.include("test.jl")

# 测试调用 Julia 函数
result = julia.eval("1 + 1")
print(result)  # 2

julia.println("Hello, World!")  # Hello, World!

a = julia.plus(2, 332)
print(a)  # 334

# 测试超时自动关闭
julia.seconds_loop(5)  # 未超时
julia.seconds_loop(15)  # 超时

# 测试添加 Pkg
julia.add_pkg("Plots")

# 测试添加命令行参数
julia.add_option("--threads", "12")
threads = julia.show_threads_num() # 12