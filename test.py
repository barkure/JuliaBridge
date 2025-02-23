from bridge import JuliaBridge
from typing import Any

# 创建 JuliaBridge 实例
julia: Any = JuliaBridge()

# 调用 Julia 函数
result = julia.eval("1 + 1")
print(result)  # 2

# include 模块
julia.include("test.jl")
a, b, c = julia.add(2, 332)
print(a, b, c)  # 334, 2, 332
