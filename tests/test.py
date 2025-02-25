from typing import Any

from juliabridge import JuliaBridge

# 创建 JuliaBridge 实例
julia: Any = JuliaBridge(timeout=10,threads = 24)

# 测试 include
julia.include("test.jl")

# # # 测试调用 Julia 函数
result = julia.eval("1 + 1")
print(result)  # 2

# # 测试调用 Julia 函数
julia.println("Hello, World!")
julia.show_threads_num()

a = julia.plus(2, 332)
print(a)  # 334

# 测试超时自动关闭
julia.seconds_loop(5)  # 未超时
julia.seconds_loop(15)  # 超时

# 测试添加 Pkg
julia.add_pkg("Plots")
