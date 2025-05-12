FROM vllm/vllm-openai:latest

# Copy the entire vllm-workspace directory from the base image
COPY --from=vllm/vllm-openai:latest /vllm-workspace /vllm-workspace

# Copy our benchmark script
COPY run_benchmark.sh /vllm-workspace/benchmarks/
RUN chmod +x /vllm-workspace/benchmarks/run_benchmark.sh

# Set the working directory
WORKDIR /vllm-workspace/benchmarks

# Set the default command to run the benchmark script
CMD ["./run_benchmark.sh"] 