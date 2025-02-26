function plus(a::Int, b::Int)::Int
    return a + b
end

function seconds_loop(seconds::Int)
    start_time = time()
    println("Start running...")
    while time() - start_time < seconds
        sleep(1)
        println("Running...", time() - start_time, "s has passed.")
    end
end

function show_threads_num()
    println("We are now using $(Threads.nthreads()) threads for Julia!")
end
