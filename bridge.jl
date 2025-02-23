import Pkg
Pkg.add("JSON")
using JSON

# 解析 payload.json 的内容，获取 func, args, kwargs
payload = JSON.parse(read(".temp/payload.json", String))

func = Symbol(payload["func"])  # 将函数名转为符号
args = payload["args"]
kwargs = payload["kwargs"]
args_dim = payload["argsdim"]
kwargs_dim = payload["kwargsdim"]
included_files = payload["included_files"]

# 将 include 的 Julia 文件包含进来
if included_files !== nothing
    for file in included_files
        include(file)
    end
end

# 转换 args 和 kwargs 中的 numpy 数组（ndarray）为 Julia 数组
function convert_ndarray(arg, dim)
    if dim !== nothing
        # 将嵌套列表转换为多维数组
        dim_tuple = tuple(dim...)

        # 将数据展平为一维数组
        flat_data = collect(Iterators.flatten(arg))

        # 按照 NumPy 的行优先顺序重新排列数据
        # 注意：reshape 默认按列优先，因此需要显式指定顺序
        array = reshape(flat_data, reverse(dim_tuple))  # 反转维度以适应 Julia 的列优先
        array = permutedims(array, reverse(1:length(dim_tuple)))  # 转置以恢复原始形状

        return array
    else
        return arg
    end
end

# 转换所有 args
args = [convert_ndarray(arg, dim) for (arg, dim) in zip(args, args_dim)]

# 转换所有 kwargs
kwargs = Dict(k => convert_ndarray(v, kwargs_dim[k]) for (k, v) in kwargs)

# 动态调用解析出的函数
if isempty(kwargs)
    result = eval(Meta.parse("$func($(join(map(string, args), ", ")))"))
else
    kwargs_str = join(["$k=$v" for (k, v) in kwargs], ", ")
    result = eval(Meta.parse("$func($(join(map(string, args), ", ")); $kwargs_str)"))
end

# 删除 payload.json
rm(".temp/payload.json")

# 将结果写入 result.json
open(".temp/result.json", "w") do io
    JSON.print(io, Dict("result" => result))
end

# 写一个 flag 文件到 .temp 文件夹，表示已经完成
open(".temp/finished", "w") do io
    write(io, "")
end