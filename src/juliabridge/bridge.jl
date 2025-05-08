using JSON

# 获取 .temp 文件夹的绝对路径
# 假设 bridge.jl 位于 juliabridge 包的根目录，.temp 目录也在那里
temp_dir = joinpath(@__DIR__, ".temp")

# 定义错误日志文件路径
error_log_path = joinpath(temp_dir, "error.log")
# 定义完成标志文件路径
finished_flag_path = joinpath(temp_dir, "finished")
# 定义结果文件路径
result_path = joinpath(temp_dir, "result.json")
# 定义 payload 文件路径
payload_path = joinpath(temp_dir, "payload.json")


# --- 错误处理函数 ---
# 捕获错误，写入错误日志文件，并创建错误标志文件
function handle_error(e, stacktrace_info)
    open(error_log_path, "w") do io
        println(io, "Julia Error:")
        println(io, e)
        println(io, "\nStacktrace:")
        println(io, stacktrace_info)
    end
    # 创建一个错误标志文件，或者直接让 Python 端检查 error.log 的存在
    # 为了简化，这里直接写入 error.log 并让 Python 端检查它的存在
end

# --- 主执行逻辑 (使用 try...catch 捕获错误) ---
try
    # 解析 payload.json 的内容
    # 确保文件存在再读取，虽然 Python 端应该保证这一点
    if !isfile(payload_path)
         throw(FileNotFoundnError("Payload file not found at $payload_path"))
    end
    payload = JSON.parse(read(payload_path, String))

    # --- 新增：处理 using 模块列表 ---
    # 获取 'modules' 键的值，如果不存在则为 nothing
    modules_to_use = get(payload, "modules", nothing)
    # 检查获取到的值是否非空且是列表类型
    if modules_to_use !== nothing && isa(modules_to_use, AbstractVector)
        # 遍历模块名列表
        for module_name in modules_to_use
            # 确保模块名是字符串类型
            if isa(module_name, String)
                try
                    # 动态执行 using 语句
                    eval(Meta.parse("using $(module_name)"))
                    # println("Successfully used module: $(module_name)") # 调试信息
                catch e
                    # 如果 using 失败 (例如模块不存在)，捕获错误并发出警告
                    # 在实际应用中，可能需要更严格的错误处理，比如中断执行
                    @warn "Failed to use module $(module_name): $(e)"
                    # 或者将错误记录到单独的日志文件
                end
            else
                 # 如果列表中包含非字符串元素，发出警告
                 @warn "Invalid module name found in 'modules' list: $(module_name) (type: $(typeof(module_name)))"
            end
        end
    end
    # --- 结束：处理 using 模块列表 ---


    # 提取 payload 中的其他信息
    func = Symbol(payload["func"])  # 将函数名转为符号
    args = payload["args"]
    kwargs = payload["kwargs"]
    # 假设 payload 中传递的是形状 tuple，键名是 argsdim 和 kwargsdim
    args_shape = get(payload, "argsdim", nothing) # 使用 get 获取，如果不存在则为 nothing
    kwargs_shape = get(payload, "kwargsdim", nothing) # 使用 get 获取

    # 假设 included_files 键总是存在，即使列表为空
    included_files = get(payload, "included_files", [])


    # 将 include 的 Julia 文件包含进来
    if included_files !== nothing && isa(included_files, AbstractVector)
        for file in included_files
            if isa(file, String)
                # 假设包含的文件路径是相对于 bridge.jl 所在的目录的相对路径
                # 或者 Python 端已经提供了绝对路径
                # 如果 Python 端提供的是相对于 project_dir 的路径，这里需要调整
                # 这里的 joinpath("..", file) 假设 .temp 在 bridge.jl 同级，而 include 文件在 bridge.jl 的父目录
                # 需要根据实际文件结构调整 include 路径
                full_include_path = abspath(joinpath(@__DIR__, "..", file)) # 尝试构建绝对路径
                if isfile(full_include_path)
                    try
                         include(full_include_path)
                         # println("Successfully included file: $(full_include_path)") # 调试信息
                    catch e
                         @error "Failed to include file $(full_include_path): $(e)"
                         # 实际应用中，include 失败可能是严重错误，可能需要中断
                         # throw(e) # 如果 include 失败应中断
                    end
                else
                    @warn "Include file not found: $(full_include_path)"
                end
            else
                 @warn "Invalid include file path found in 'included_files' list: $(file) (type: $(typeof(file)))"
            end
        end
    end


    # 转换 args 和 kwargs 中的 numpy 数组（ndarray）为 Julia 数组
    # 这个函数现在期望接收形状 tuple
    function convert_ndarray(arg, shape_tuple)
        if shape_tuple !== nothing && isa(shape_tuple, AbstractVector) # 检查是否是列表/元组表示的形状
            # 将嵌套列表转换为多维数组
            julia_shape = tuple(shape_tuple...) # 转换为 Julia 的 tuple

            # 将数据展平为一维数组
            # collect(Iterators.flatten(arg)) 适用于任意嵌套深度的列表
            flat_data = collect(Iterators.flatten(arg))

            # 按照 NumPy 的行优先顺序重新排列数据
            # reshape 默认按列优先，因此需要显式指定顺序
            # NumPy 形状 (r1, r2, ..., rn) 对应 Julia 形状 (rn, ..., r2, r1)
            # reshape(flat_data, reverse(julia_shape)) 会得到一个形状为 (rn, ..., r2, r1) 的 Julia 数组
            # 然后 permutedims(..., reverse(1:length(julia_shape))) 将其转置回形状 (r1, r2, ..., rn)
            # 这样就模拟了 NumPy 的内存布局
            if isempty(julia_shape) # 处理标量情况 (shape is empty tuple)
                 if isempty(flat_data)
                      return nothing # 或者根据需要返回其他默认值
                 else
                      return flat_data[1] # 假设只有一个元素
                 end
            else
                 array = reshape(flat_data, reverse(julia_shape))
                 array = permutedims(array, reverse(1:length(julia_shape)))
                 return array
            end
        else
            # 如果 shape_tuple 是 nothing 或无效，直接返回原始参数
            return arg
        end
    end

    # 转换所有 args
    # 确保 args_shape 也是一个列表或元组，且长度与 args 匹配
    if args_shape === nothing || length(args) != length(args_shape)
         # 如果形状信息缺失或不匹配，可能无法正确转换数组
         @warn "Shape information missing or mismatched for positional arguments. NumPy array conversion might fail."
         # 创建一个与 args 长度相同的 None 列表作为占位符，避免 zip 错误
         args_shape_padded = fill(nothing, length(args))
         args = [convert_ndarray(arg, shape) for (arg, shape) in zip(args, args_shape_padded)]
    else
        args = [convert_ndarray(arg, shape) for (arg, shape) in zip(args, args_shape)]
    end


    # 转换所有 kwargs
    # 确保 kwargs_shape 是一个字典，且包含 kwargs 中所有 ndarray 的键
    if kwargs_shape === nothing
         @warn "Shape information missing for keyword arguments. NumPy array conversion might fail."
         # 尝试转换 kwargs，对于 ndarray 但没有形状信息的，convert_ndarray 会返回原始数据
         kwargs = Dict(k => convert_ndarray(v, nothing) for (k, v) in kwargs)
    else
        kwargs = Dict(k => convert_ndarray(v, get(kwargs_shape, k, nothing)) for (k, v) in kwargs)
    end


    # --- 动态调用函数 ---
    # 构建函数调用表达式字符串
    # 注意：这里需要确保参数能被正确地表示为 Julia 代码字符串
    # 对于字符串参数，需要加上引号
    # 对于其他类型（数字、布尔、None/nothing），直接转换为字符串即可
    # 对于已经转换好的 Julia 数组，直接使用其变量名（在 eval 作用域中）或将其表示为代码
    # 最简单的方式是直接在 eval 作用域中创建变量并调用
    # 但更灵活的是构建表达式树或字符串
    # 考虑到参数可能是复杂类型，直接构建字符串表达式并解析是常用的方法

    # 辅助函数：格式化参数为 Julia 代码字符串
    # 这个函数在当前使用临时变量的方法中可能不再直接用于构建最终调用字符串
    # 但如果需要将 Julia 对象转换为其代码表示，可以修改此函数
    function format_arg_for_eval(arg)
        if isa(arg, String)
            # 转义字符串中的引号和反斜杠
            return repr(arg) # repr() 通常能生成一个字符串的 Julia 代码表示
        elseif arg === nothing # Python 的 None 对应 Julia 的 nothing
             return nothing # 返回 Julia 的 nothing
        else
             # 对于数字、布尔等基本类型，直接返回
             return arg
        end
    end

    # 如果函数是 eval，直接 eval 参数字符串
    if func == :eval
        # 假设 eval 的参数是 args 列表的第一个元素，且是字符串
        if !isempty(args) && isa(args[1], String)
             result = eval(Meta.parse(args[1]))
        else
             throw(ArgumentError("eval function requires a single string argument"))
        end
    else
        # 简化方法：直接在 eval 作用域中定义临时变量，然后调用函数
        # 这种方法依赖于 eval 在当前全局作用域执行
        temp_vars = []
        for i in 1:length(args)
             temp_var_name = Symbol("_arg$(i)")
             # 在当前作用域定义临时变量，将转换后的 Julia 对象赋值给它
             @eval $(temp_var_name) = $(args[i])
             push!(temp_vars, temp_var_name)
        end
        temp_kw_vars = Dict()
        for (k, v) in kwargs
             temp_var_name = Symbol("_kwarg$(k)")
             # 在当前作用域定义临时变量，将转换后的 Julia 对象赋值给它
             @eval $(temp_var_name) = $(v)
             temp_kw_vars[k] = temp_var_name
        end

        # 构建函数调用字符串
        # 引用临时变量来构建函数调用表达式字符串
        arg_call_str = join([string(var) for var in temp_vars], ", ")
        kwarg_call_str = join(["$(k)=$(temp_kw_vars[k])" for k in keys(kwargs)], ", ")

        call_str = string(func, "(", arg_call_str)
        if !isempty(kwargs)
             call_str = string(call_str, "; ", kwarg_call_str)
        end
        call_str = string(call_str, ")")

        # 执行函数调用
        result = eval(Meta.parse(call_str))

    end


    # 如果函数没有返回值，result 可能是 nothing 或其他表示空值的东西
    # Python 端期望一个可序列化的结果，nothing 是可以的
    # 确保 result 是一个可以被 JSON 序列化的类型
    # 如果 Julia 函数返回了不可序列化的类型，这里会出错
    # 可以考虑在这里进行结果的序列化处理，例如转换为字符串或特定的表示

    # 删除 payload.json
    # 确保在成功执行后才删除 payload 文件
    rm(payload_path)

    # 将结果写入 result.json
    # 确保结果是 JSON 可序列化的
    # 对于复杂的 Julia 对象，可能需要自定义序列化逻辑
    # 简单起见，假设返回的结果是基本类型、数组或它们的组合
    open(result_path, "w") do io
        JSON.print(io, Dict("result" => result))
    end

    # 写一个 flag 文件到 .temp 文件夹，表示已经完成
    # 确保在成功写入 result.json 后才创建完成标志
    open(finished_flag_path, "w") do io
        write(io, "")
    end

catch e
    # 捕获执行过程中的任何错误
    stacktrace_info = stacktrace(catch_backtrace())
    handle_error(e, stacktrace_info)
    # 在发生错误时，不创建 finished 文件，Python 端会检测到超时或 error.log
end

