[简体中文](./README_zh_cn.md) [English](./README.md)

# JuliaBridge
A Python package for seamless communication with Julia.

To enhance your two-step operation for using the `JuliaBridge` package, we can add more details and best practices to ensure a smooth experience. Here's an improved version of your instructions:

## Installation
1. **Install the package**:
   ```bash
   pip install juliabridge
   ```

2. **Install Julia** (if not already installed):
   - Download and install Julia from [https://julialang.org/downloads/](https://julialang.org/downloads/).
   - Ensure Julia is added to your system's PATH so it can be accessed from the command line.

3. **Install required Julia packages** (optional):
   If your Julia code relies on specific packages, you can install them using the Julia package manager:
   ```bash
   julia -e 'using Pkg; Pkg.add("PackageName")'
   ```

---

## Example Usage
1. **Basic usage**:
   ```python
   from juliabridge import JuliaBridge

   # Initialize the JuliaBridge instance
   jb = JuliaBridge()

   # Evaluate a simple Julia command
   jb.eval('println("Hello from Julia")')
   ```

2. **Passing data between Python and Julia**:
   ```python
   # Send data from Python to Julia
   jb.eval('x = 10')  # Assign a value in Julia
   jb.eval('println(x)')  # Print the value in Julia

   # Retrieve data from Julia to Python
   result = jb.eval('x + 5')  # Evaluate an expression in Julia
   print(result)  # Output: 15
   ```

3. **Include Julia Scripts and Call Functions**:
   Save your Julia code in a file (e.g., `script.jl`) and run it from Python:
   ```python
   jb.include('script.jl')  # Include the .jl file and execute it

   # Suppose the script.jl file contains a function say_hello
   jb.eval('say_hello("Julia")')  # Call the say_hello function
   ```
   
---

## Best Practices
- **Keep Julia sessions alive**: If you plan to execute multiple commands, reuse the same `JuliaBridge` instance to avoid the overhead of starting a new Julia session each time.
- **Use `jb.include` for large scripts**: For larger Julia scripts, save them in a `.jl` file and use `jb.include` to execute them.
- **Optimize data transfer**: When passing large datasets between Python and Julia, consider using efficient formats like JSON or binary files.

---

## Troubleshooting
1. **Julia not found**:
   - Ensure Julia is installed and added to your system's PATH.
   - Verify by running `julia` in your terminal.

2. **Package installation issues**:
   - If `pip install juliabridge` fails, ensure you have the latest version of `pip`:
     ```bash
     pip install --upgrade pip
     ```

3. **Performance issues**:
   - For computationally intensive tasks, consider running them directly in Julia instead of passing data back and forth.

---

By following these steps and best practices, you can effectively use `JuliaBridge` to integrate Julia's capabilities into your Python workflow. Let me know if you need further assistance!