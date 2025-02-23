from bridge import JuliaBridge

# 创建 JuliaBridge 实例
julia = JuliaBridge()

result = julia.eval("1 + 1")

print(result)  # 2

