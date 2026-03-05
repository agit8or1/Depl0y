"""LLM cloud-init configuration generator"""
import base64
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LLMCloudInitService:
    """Generates cloud-init extras for LLM VM deployments."""

    @staticmethod
    def generate_setup_script(
        engine: str,
        model: str,
        ui_type: str,
        gpu_enabled: bool,
        gpu_type: str,
    ) -> str:
        """Return a bash script that installs the LLM engine, pulls the model,
        and optionally deploys a web UI.  The script is designed to run in the
        background after cloud-init so it never blocks VM startup."""

        lines: List[str] = [
            "#!/bin/bash",
            "set -e",
            "exec > /var/log/llm-setup.log 2>&1",
            "",
            "# Ensure HOME is set — cloud-init runs without a login shell",
            "export HOME=/root",
            "export USER=root",
            "",
            'echo "=== LLM Auto-Setup Starting: $(date) ==="',
            "",
        ]

        # GPU driver installation
        if gpu_enabled:
            if gpu_type == "nvidia":
                lines += [
                    "# Install NVIDIA drivers",
                    "echo 'Installing NVIDIA drivers...'",
                    "apt-get update -qq",
                    "DEBIAN_FRONTEND=noninteractive ubuntu-drivers autoinstall || true",
                    "# Reload kernel modules",
                    "modprobe nvidia || true",
                    'echo "NVIDIA drivers installed"',
                    "",
                ]
            elif gpu_type == "amd":
                lines += [
                    "# Install ROCm support for AMD GPU",
                    "echo 'Installing AMD ROCm...'",
                    "apt-get update -qq",
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y rocm-hip-sdk || true",
                    "usermod -aG render,video ubuntu || true",
                    'echo "AMD ROCm installed"',
                    "",
                ]

        # Engine installation
        if engine == "ollama":
            lines += [
                "# Install Ollama",
                "echo 'Installing Ollama...'",
                "curl -fsSL https://ollama.ai/install.sh | sh",
                "",
                "# Configure Ollama service with performance settings",
                "mkdir -p /etc/systemd/system/ollama.service.d",
                "cat > /etc/systemd/system/ollama.service.d/override.conf << 'OLLAMA_CONF_EOF'",
                "[Service]",
                "Environment=\"OLLAMA_MODELS=/usr/share/ollama/.ollama/models\"",
                "Environment=\"OLLAMA_KEEP_ALIVE=60m\"",
                "Environment=\"OLLAMA_FLASH_ATTENTION=1\"",
                "Environment=\"OLLAMA_MAX_LOADED_MODELS=1\"",
                "OLLAMA_CONF_EOF",
                "systemctl daemon-reload",
                "systemctl enable ollama",
                "systemctl start ollama",
                "# Wait for Ollama daemon to be ready",
                "for i in $(seq 1 30); do",
                "  ollama list >/dev/null 2>&1 && break",
                "  sleep 2",
                "done",
                f'echo "Pulling model: {model} ..."',
                f"OLLAMA_MODELS=/usr/share/ollama/.ollama/models ollama pull {model}",
                "",
                "# ── Thread-count tuning ─────────────────────────────────────────────",
                "# Benchmark a range of num_thread values and pick the fastest.",
                "# Ollama 0.17+ ignores OLLAMA_NUM_THREAD; the only reliable way",
                "# to set it is via a Modelfile PARAMETER.",
                f'echo "=== Tuning thread count for {model} ==="',
                "TOTAL_CPUS=$(nproc --all)",
                'echo "Available vCPUs: $TOTAL_CPUS"',
                "",
                "# Write a small benchmark helper so the loop stays clean",
                "cat > /tmp/bench_ollama.py << 'BENCH_EOF'",
                "import sys, json",
                "try:",
                "    import urllib.request",
                "    model   = sys.argv[1]",
                "    threads = int(sys.argv[2])",
                "    payload = json.dumps({",
                '        "model":   model,',
                '        "prompt":  "Count from 1 to 20 in words.",',
                '        "stream":  False,',
                '        "options": {"num_thread": threads, "num_predict": 40}',
                "    }).encode()",
                '    resp = urllib.request.urlopen("http://localhost:11434/api/generate", data=payload, timeout=120)',
                "    d    = json.loads(resp.read())",
                "    rate = d.get('eval_count', 0) / max(d.get('eval_duration', 1), 1) * 1e9",
                '    print(f"{rate:.2f}")',
                "except Exception as e:",
                '    sys.stderr.write(f"bench error: {e}\\n")',
                '    print("0.0")',
                "BENCH_EOF",
                "",
                "# Candidate thread counts scaled to available vCPUs",
                "if   [ \"$TOTAL_CPUS\" -le 4 ];  then CANDIDATES=\"2 4\"",
                "elif [ \"$TOTAL_CPUS\" -le 8 ];  then CANDIDATES=\"4 6 8\"",
                "elif [ \"$TOTAL_CPUS\" -le 16 ]; then CANDIDATES=\"6 8 10 12\"",
                "else                                  CANDIDATES=\"8 10 12 14 16\"",
                "fi",
                "",
                "BEST_THREADS=8",
                "BEST_RATE=0",
                "",
                "for T in $CANDIDATES; do",
                f'  RATE=$(python3 /tmp/bench_ollama.py "{model}" "$T" 2>/dev/null || echo 0)',
                '  echo "  num_thread=$T: ${RATE} tok/s"',
                "  IS_BETTER=$(python3 -c \"print('yes' if float('$RATE') > float('$BEST_RATE') else 'no')\" 2>/dev/null || echo no)",
                '  if [ "$IS_BETTER" = "yes" ]; then',
                "    BEST_RATE=$RATE",
                "    BEST_THREADS=$T",
                "  fi",
                "done",
                "",
                'echo "Tuning result: $BEST_THREADS threads @ ${BEST_RATE} tok/s"',
                'echo "Applying to Modelfile..."',
                f'echo "FROM {model}"                          > /tmp/Modelfile',
                'echo "PARAMETER num_thread $BEST_THREADS"    >> /tmp/Modelfile',
                'echo "PARAMETER num_ctx 4096"                >> /tmp/Modelfile',
                f"OLLAMA_MODELS=/usr/share/ollama/.ollama/models ollama create {model} -f /tmp/Modelfile",
                "",
                "# Save tuning report",
                "{"  ,
                f'echo "model        : {model}"',
                'echo "vcpus        : $TOTAL_CPUS"',
                'echo "num_thread   : $BEST_THREADS"',
                'echo "rate_tok_s   : $BEST_RATE"',
                'echo "tuned_at     : $(date -u +%Y-%m-%dT%H:%M:%SZ)"',
                "} > /var/log/llm-tuning.log",
                'echo "Tuning report: /var/log/llm-tuning.log"',
                'echo "Model ready!"',
                "",
            ]
        elif engine == "llama.cpp":
            cuda_flag = "-DGGML_CUDA=ON" if gpu_enabled and gpu_type == "nvidia" else ""
            lines += [
                "# Install llama.cpp",
                "echo 'Installing llama.cpp...'",
                "apt-get update -qq",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential cmake git",
                "git clone --depth 1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp",
                f"cmake -S /opt/llama.cpp -B /opt/llama.cpp/build {cuda_flag}",
                "cmake --build /opt/llama.cpp/build --config Release -j $(nproc)",
                "ln -sf /opt/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server || true",
                'echo "llama.cpp built successfully!"',
                "",
            ]
        elif engine == "vllm":
            # Map catalog model IDs to HuggingFace model IDs
            hf_model_map = {
                "llama3.1:8b": "meta-llama/Llama-3.1-8B-Instruct",
                "llama3.1:70b": "meta-llama/Llama-3.1-70B-Instruct",
                "mistral:7b": "mistralai/Mistral-7B-Instruct-v0.3",
                "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
            }
            hf_model = hf_model_map.get(model, model)
            lines += [
                "# Install vLLM",
                "echo 'Installing vLLM and dependencies...'",
                "apt-get update -qq",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip python3-venv",
                "python3 -m venv /opt/vllm-env",
                "/opt/vllm-env/bin/pip install --upgrade pip",
                "/opt/vllm-env/bin/pip install vllm",
                "",
                "# Create vLLM systemd service",
                "cat > /etc/systemd/system/vllm.service << 'VLLM_SERVICE_EOF'",
                "[Unit]",
                "Description=vLLM OpenAI-compatible API server",
                "After=network.target",
                "",
                "[Service]",
                "Type=simple",
                "User=root",
                "Restart=on-failure",
                "RestartSec=10",
                f"Environment=VLLM_MODEL={hf_model}",
                "ExecStart=/opt/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \\",
                f"    --model {hf_model} \\",
                "    --host 0.0.0.0 \\",
                "    --port 8000",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "VLLM_SERVICE_EOF",
                "",
                "systemctl daemon-reload",
                "systemctl enable vllm",
                "systemctl start vllm",
                f'echo "vLLM service started – model: {hf_model}"',
                'echo "API available on port 8000 (OpenAI-compatible)"',
                "",
            ]
        elif engine == "localai":
            # LocalAI is Docker-based
            if gpu_enabled and gpu_type == "nvidia":
                docker_image = "localai/localai:latest-aio-gpu-nvidia-cuda-12"
                gpu_flag = "--gpus all"
            else:
                docker_image = "localai/localai:latest-aio-cpu"
                gpu_flag = ""
            lines += [
                "# Install Docker for LocalAI",
                "echo 'Installing Docker...'",
                "curl -fsSL https://get.docker.com | sh",
                "systemctl enable docker",
                "systemctl start docker",
                "# Wait for Docker daemon",
                "for i in $(seq 1 20); do",
                "  docker info >/dev/null 2>&1 && break",
                "  sleep 3",
                "done",
                "",
                "# Deploy LocalAI",
                "echo 'Starting LocalAI on port 8080...'",
                f"docker run -d {gpu_flag} \\",
                "  -p 8080:8080 \\",
                "  --name local-ai \\",
                "  -v local-ai-data:/build/models \\",
                "  --restart always \\",
                f"  {docker_image}",
                'echo "LocalAI container started – OpenAI-compatible API on port 8080"',
                "",
            ]

        # Web UI installation
        if ui_type == "open-webui":
            lines += [
                "# Install Docker",
                "echo 'Installing Docker...'",
                "curl -fsSL https://get.docker.com | sh",
                "systemctl enable docker",
                "systemctl start docker",
                "# Wait for Docker daemon",
                "for i in $(seq 1 20); do",
                "  docker info >/dev/null 2>&1 && break",
                "  sleep 3",
                "done",
                "",
                "# Deploy Open WebUI",
                "echo 'Starting Open WebUI on port 3000...'",
                "docker run -d \\",
                "  --name open-webui \\",
                "  --network=host \\",
                "  -v open-webui:/app/backend/data \\",
                "  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \\",
                "  -e PORT=3000 \\",
                "  --restart always \\",
                "  ghcr.io/open-webui/open-webui:main",
                'echo "Open WebUI deployed!"',
                "",
            ]

        lines += [
            'echo "=== LLM Setup Complete: $(date) ==="',
            'echo "--- Access URLs ---"',
        ]

        if ui_type == "open-webui":
            lines.append(
                "echo \"  Web UI  : http://$(hostname -I | awk '{print $1}'):3000\""
            )
        if engine == "ollama":
            lines.append(
                "echo \"  API     : http://$(hostname -I | awk '{print $1}'):11434\""
            )
        elif engine == "vllm":
            lines.append(
                "echo \"  API     : http://$(hostname -I | awk '{print $1}'):8000  (OpenAI-compatible)\""
            )
        elif engine == "localai":
            lines.append(
                "echo \"  API     : http://$(hostname -I | awk '{print $1}'):8080  (OpenAI-compatible)\""
            )

        return "\n".join(lines) + "\n"

    @staticmethod
    def generate_cloud_init_config(
        engine: str,
        model: str,
        ui_type: str,
        gpu_enabled: bool,
        gpu_type: str,
    ) -> Dict[str, Any]:
        """Return a dict that is stored in VirtualMachine.cloud_init_config.

        The deployment service merges extra_packages, write_files, and
        extra_runcmd into the cloud-init user-data snippet.
        """
        extra_packages: List[str] = ["curl", "ca-certificates"]

        if gpu_enabled and gpu_type == "nvidia":
            extra_packages.append("ubuntu-drivers-common")

        if engine == "vllm":
            extra_packages += ["python3-pip", "python3-venv"]
        elif engine == "localai":
            # Docker is installed by the setup script via get.docker.com
            extra_packages += ["ca-certificates", "gnupg"]

        script_content = LLMCloudInitService.generate_setup_script(
            engine=engine,
            model=model,
            ui_type=ui_type,
            gpu_enabled=gpu_enabled,
            gpu_type=gpu_type,
        )

        # Base64-encode the script to avoid YAML escaping issues
        encoded = base64.b64encode(script_content.encode()).decode()

        write_files = [
            {
                "path": "/opt/setup-llm.sh",
                "permissions": "0755",
                "encoding": "b64",
                "content": encoded,
            }
        ]

        # Run setup in background so cloud-init finishes quickly
        extra_runcmd = [
            "nohup bash /opt/setup-llm.sh > /var/log/llm-setup.log 2>&1 &"
        ]

        return {
            "extra_packages": extra_packages,
            "write_files": write_files,
            "extra_runcmd": extra_runcmd,
        }
