function plus(a::Int, b::Int)::Int
    return a + b
end

function seconds_loop(seconds::Int)
    start_time = time()
    while time() - start_time < seconds
        println("Running...", time() - start_time, "s has passed.")
        sleep(1)
    end
end

function show_threads_num()
    println(Threads.nthreads())
end