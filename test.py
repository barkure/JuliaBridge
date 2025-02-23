from typing import Any

from bridge import JuliaBridge

# 创建 JuliaBridge 实例
julia: Any = JuliaBridge()

# 测试 add Pkg
julia.add_pkg('Plots')

# 测试调用 Julia 函数
result = julia.eval('1 + 1')
print(result)  # 2

# 测试 include
julia.include('test.jl')
a = julia.plus(2, 332)
print(a)  # 334
