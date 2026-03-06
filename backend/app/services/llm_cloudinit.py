"""LLM cloud-init configuration generator"""
import base64
import json
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
            "# Create swap file early to prevent OOM during PyTorch/model installation.",
            "# pip installing PyTorch + loading a model can easily exhaust 8-16 GB RAM.",
            "if [ ! -f /swapfile ]; then",
            "  SWAP_GB=4",
            "  FREE_GB=$(df -BG / | awk 'NR==2{gsub(\"G\",\"\",$4); print $4}')",
            "  if [ \"${FREE_GB:-0}\" -gt 6 ]; then",
            "    echo \"Creating ${SWAP_GB}G swap file (${FREE_GB}G disk free)...\"",
            "    fallocate -l ${SWAP_GB}G /swapfile 2>/dev/null \\",
            "      || dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB*1024)) status=none",
            "    chmod 600 /swapfile",
            "    mkswap /swapfile",
            "    swapon /swapfile",
            "    echo '/swapfile none swap sw 0 0' >> /etc/fstab",
            "    echo \"Swap enabled: $(free -h | grep Swap)\"",
            "  else",
            "    echo \"Low disk space (${FREE_GB}G free), skipping swap\"",
            "  fi",
            "fi",
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

        elif engine == "stable-diffusion":
            # Map model IDs to HuggingFace download URLs
            sd_model_urls = {
                "sd-v1.5": (
                    "https://huggingface.co/runwayml/stable-diffusion-v1-5"
                    "/resolve/main/v1-5-pruned-emaonly.safetensors"
                ),
                "dreamshaper-8": (
                    "https://huggingface.co/Lykon/DreamShaper"
                    "/resolve/main/DreamShaper_8_pruned.safetensors"
                ),
                "sdxl": (
                    "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0"
                    "/resolve/main/sd_xl_base_1.0.safetensors"
                ),
            }
            model_url = sd_model_urls.get(model, sd_model_urls["sd-v1.5"])
            model_filename = model_url.split("/")[-1]
            image_size = 1024 if model == "sdxl" else 512

            # Build SD-compatible ComfyUI default workflow
            sd_workflow = {
                "last_node_id": 9,
                "last_link_id": 9,
                "nodes": [
                    {
                        "id": 4,
                        "type": "CheckpointLoaderSimple",
                        "pos": [26, 474],
                        "size": [315, 98],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "outputs": [
                            {"name": "MODEL", "type": "MODEL", "links": [1], "slot_index": 0},
                            {"name": "CLIP", "type": "CLIP", "links": [3, 5], "slot_index": 1},
                            {"name": "VAE", "type": "VAE", "links": [8], "slot_index": 2},
                        ],
                        "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
                        "widgets_values": [model_filename],
                    },
                    {
                        "id": 6,
                        "type": "CLIPTextEncode",
                        "pos": [415, 186],
                        "size": [422, 164],
                        "flags": {},
                        "order": 2,
                        "mode": 0,
                        "inputs": [{"name": "clip", "type": "CLIP", "link": 3}],
                        "outputs": [
                            {"name": "CONDITIONING", "type": "CONDITIONING", "links": [4], "slot_index": 0}
                        ],
                        "properties": {"Node name for S&R": "CLIPTextEncode"},
                        "widgets_values": ["masterpiece, best quality, beautiful scenery"],
                    },
                    {
                        "id": 7,
                        "type": "CLIPTextEncode",
                        "pos": [415, 378],
                        "size": [422, 164],
                        "flags": {},
                        "order": 3,
                        "mode": 0,
                        "inputs": [{"name": "clip", "type": "CLIP", "link": 5}],
                        "outputs": [
                            {"name": "CONDITIONING", "type": "CONDITIONING", "links": [6], "slot_index": 0}
                        ],
                        "properties": {"Node name for S&R": "CLIPTextEncode"},
                        "widgets_values": ["text, watermark, blurry, low quality"],
                    },
                    {
                        "id": 5,
                        "type": "EmptyLatentImage",
                        "pos": [473, 609],
                        "size": [315, 106],
                        "flags": {},
                        "order": 1,
                        "mode": 0,
                        "outputs": [
                            {"name": "LATENT", "type": "LATENT", "links": [2], "slot_index": 0}
                        ],
                        "properties": {"Node name for S&R": "EmptyLatentImage"},
                        "widgets_values": [image_size, image_size, 1],
                    },
                    {
                        "id": 3,
                        "type": "KSampler",
                        "pos": [863, 186],
                        "size": [315, 262],
                        "flags": {},
                        "order": 4,
                        "mode": 0,
                        "inputs": [
                            {"name": "model", "type": "MODEL", "link": 1},
                            {"name": "positive", "type": "CONDITIONING", "link": 4},
                            {"name": "negative", "type": "CONDITIONING", "link": 6},
                            {"name": "latent_image", "type": "LATENT", "link": 2},
                        ],
                        "outputs": [
                            {"name": "LATENT", "type": "LATENT", "links": [7], "slot_index": 0}
                        ],
                        "properties": {"Node name for S&R": "KSampler"},
                        "widgets_values": [42, "fixed", 20, 7, "euler", "normal", 1.0],
                    },
                    {
                        "id": 8,
                        "type": "VAEDecode",
                        "pos": [1209, 188],
                        "size": [210, 46],
                        "flags": {},
                        "order": 5,
                        "mode": 0,
                        "inputs": [
                            {"name": "samples", "type": "LATENT", "link": 7},
                            {"name": "vae", "type": "VAE", "link": 8},
                        ],
                        "outputs": [
                            {"name": "IMAGE", "type": "IMAGE", "links": [9], "slot_index": 0}
                        ],
                        "properties": {"Node name for S&R": "VAEDecode"},
                    },
                    {
                        "id": 9,
                        "type": "SaveImage",
                        "pos": [1451, 189],
                        "size": [210, 58],
                        "flags": {},
                        "order": 6,
                        "mode": 0,
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 9}],
                        "properties": {"Node name for S&R": "SaveImage"},
                        "widgets_values": ["ComfyUI"],
                    },
                ],
                "links": [
                    [1, 4, 0, 3, 0, "MODEL"],
                    [2, 5, 0, 3, 3, "LATENT"],
                    [3, 4, 1, 6, 0, "CLIP"],
                    [4, 6, 0, 3, 1, "CONDITIONING"],
                    [5, 4, 1, 7, 0, "CLIP"],
                    [6, 7, 0, 3, 2, "CONDITIONING"],
                    [7, 3, 0, 8, 0, "LATENT"],
                    [8, 4, 2, 8, 1, "VAE"],
                    [9, 8, 0, 9, 0, "IMAGE"],
                ],
                "groups": [],
                "config": {},
                "extra": {},
                "version": 0.4,
            }
            workflow_json = json.dumps(sd_workflow)

            # Select PyTorch index URL based on GPU type
            if gpu_enabled and gpu_type == "nvidia":
                torch_index = "https://download.pytorch.org/whl/cu121"
                comfyui_args = "--listen 0.0.0.0 --port 8188 --default-workflow /opt/comfyui/default_workflow.json"
            elif gpu_enabled and gpu_type == "amd":
                torch_index = "https://download.pytorch.org/whl/rocm5.6"
                comfyui_args = "--listen 0.0.0.0 --port 8188 --default-workflow /opt/comfyui/default_workflow.json"
            else:
                torch_index = "https://download.pytorch.org/whl/cpu"
                comfyui_args = "--listen 0.0.0.0 --port 8188 --cpu --force-fp32 --default-workflow /opt/comfyui/default_workflow.json"

            lines += [
                "# Install ComfyUI (Stable Diffusion image generation)",
                "echo 'Installing ComfyUI and dependencies...'",
                "apt-get update -qq",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip python3-venv git wget",
                "",
                "# Clone ComfyUI",
                "git clone --depth 1 https://github.com/comfyanonymous/ComfyUI /opt/comfyui",
                "",
                "# Create venv",
                "python3 -m venv /opt/comfyui-env",
                "/opt/comfyui-env/bin/pip install --upgrade pip",
                "",
                "# Install PyTorch (hardware-specific)",
                f"echo 'Installing PyTorch from {torch_index}...'",
                f"/opt/comfyui-env/bin/pip install torch torchvision torchaudio --index-url {torch_index}",
                "",
                "# Install ComfyUI requirements",
                "/opt/comfyui-env/bin/pip install -r /opt/comfyui/requirements.txt",
                "",
                "# Download SD model checkpoint",
                f'echo "Downloading model: {model} ({model_filename}) ..."',
                "mkdir -p /opt/comfyui/models/checkpoints",
                f'wget -q --show-progress -O "/opt/comfyui/models/checkpoints/{model_filename}" \\',
                f'  "{model_url}" || echo "WARNING: Model download failed. Add model manually to /opt/comfyui/models/checkpoints/"',
                "",
                "# Write SD-compatible default workflow (avoids FLUX 'Missing Models' dialog)",
                "cat > /opt/comfyui/default_workflow.json << 'WORKFLOW_EOF'",
                workflow_json,
                "WORKFLOW_EOF",
                "",
                "# Write comfy.settings.json to suppress 'Missing Models' dialog",
                "mkdir -p /opt/comfyui/user/default",
                'echo \'{"Comfy.InstalledVersion": "0.0.0", "Comfy.TutorialCompleted": true, "Comfy.Workflow.ShowMissingModelsWarning": false}\' > /opt/comfyui/user/default/comfy.settings.json',
                "",
                "# Create ComfyUI systemd service",
                "cat > /etc/systemd/system/comfyui.service << 'COMFY_SERVICE_EOF'",
                "[Unit]",
                "Description=ComfyUI Stable Diffusion Web Interface",
                "After=network.target",
                "",
                "[Service]",
                "Type=simple",
                "User=root",
                "WorkingDirectory=/opt/comfyui",
                f"ExecStart=/opt/comfyui-env/bin/python main.py {comfyui_args}",
                "Restart=on-failure",
                "RestartSec=10",
                "StandardOutput=journal",
                "StandardError=journal",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "COMFY_SERVICE_EOF",
                "",
                "systemctl daemon-reload",
                "systemctl enable comfyui",
                "systemctl start comfyui",
                f'echo "ComfyUI started on port 8188 with model: {model}"',
                'echo "Web UI: http://$(hostname -I | awk \'{print $1}\'):8188"',
                "",
            ]

        elif engine == "meme-maker":
            dreamshaper_url = (
                "https://huggingface.co/Lykon/DreamShaper"
                "/resolve/main/DreamShaper_8_pruned.safetensors"
            )
            if gpu_enabled and gpu_type == "nvidia":
                torch_index = "https://download.pytorch.org/whl/cu121"
                comfyui_args = "--listen 0.0.0.0 --port 8188"
            elif gpu_enabled and gpu_type == "amd":
                torch_index = "https://download.pytorch.org/whl/rocm5.6"
                comfyui_args = "--listen 0.0.0.0 --port 8188"
            else:
                torch_index = "https://download.pytorch.org/whl/cpu"
                comfyui_args = "--listen 0.0.0.0 --port 8188 --cpu --force-fp32"

            meme_app_src = r'''#!/usr/bin/env python3
"""Meme Maker — split-pipeline: LLM captions + textless image + Pillow overlay.

Why we overlay text (avoid garbled AI text)
-------------------------------------------
Diffusion models (DreamShaper, SDXL, etc.) cannot reliably render legible text.
Asking the image model to draw captions produces corrupted, blurry, or hallucinated
lettering. Instead we split responsibilities:
  1. LLM generates ONLY structured caption JSON (top_text / bottom_text).
  2. Image model generates a TEXTLESS scene (negative prompt suppresses all text).
  3. Pillow overlays Impact-style captions on the final image server-side.
"""
import json, io, os, base64, re, random, uuid, threading, time, urllib.request, urllib.error
from flask import Flask, request, jsonify

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

app = Flask(__name__)
COMFY_URL  = "http://localhost:8188"
OLLAMA_URL = "http://localhost:11434"

# Strong negative prompt — every text-rendering token suppressed
NEGATIVE_PROMPT = (
    "text, letters, words, captions, subtitles, watermark, logo, brand, "
    "signature, ui, screenshot, title, label, annotation, font, typography, "
    "blurry, low quality, nsfw, deformed, bad anatomy, ugly, duplicate"
)

# ComfyUI workflow dict — __POSITIVE__ / __NEGATIVE__ replaced at runtime
_WF = {
    "4": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "DreamShaper_8_pruned.safetensors"}},
    "6": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "__POSITIVE__", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "__NEGATIVE__", "clip": ["4", 1]}},
    "5": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "3": {"class_type": "KSampler",
          "inputs": {"seed": 0, "steps": 20, "cfg": 6.0,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras",
                     "denoise": 1.0, "model": ["4", 0],
                     "positive": ["6", 0], "negative": ["7", 0],
                     "latent_image": ["5", 0]}},
    "8": {"class_type": "VAEDecode",
          "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage",
          "inputs": {"images": ["8", 0], "filename_prefix": "meme_raw"}},
}

# In-memory stores (cleared on service restart)
_job_captions = {}   # pid -> (top_text, bottom_text)
_job_progress = {}   # pid -> {step, total, status}
_raw_images   = {}   # pid -> bytes  (textless base image for caption regen)

FONT_PATHS = [
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


# ── TEXT OVERLAY (Pillow) ─────────────────────────────────────────

def _best_font(size):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap_text(text, max_words=8):
    text = re.sub(r'\s+', ' ', text.upper().strip())
    words = text.split()
    return ' '.join(words[:max_words]) if len(words) > max_words else text


def _draw_meme_line(draw, text, img_w, img_h, position):
    text = _wrap_text(text)
    if not text:
        return
    margin   = max(int(img_h * 0.03), 8)
    max_w    = int(img_w * 0.92)
    start_sz = max(int(img_h * 0.10), 28)
    size = start_sz
    font = _best_font(size)
    while size > 12:
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            break
        size -= 2
        font  = _best_font(size)
    bbox   = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x      = (img_w - tw) // 2
    y      = margin if position == "top" else img_h - th - margin
    stroke = max(int(th * 0.14), 2)
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")


def apply_meme_text(img_bytes, top_text, bottom_text):
    """Overlay Impact-style captions on image bytes. Returns PNG bytes."""
    if not PIL_OK or (not top_text and not bottom_text):
        return img_bytes
    try:
        img  = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        if top_text:
            _draw_meme_line(draw, top_text,    w, h, "top")
        if bottom_text:
            _draw_meme_line(draw, bottom_text, w, h, "bottom")
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return img_bytes


# ── IMAGE PROMPT BUILDER (no text, no captions) ───────────────────

_SCENES = {
    "programmer": "a developer staring at monitors covered in error messages, coffee cups everywhere",
    "developer":  "a developer staring at monitors covered in error messages, coffee cups everywhere",
    "coding":     "a developer staring at monitors covered in error messages, coffee cups everywhere",
    "monday":     "a person looking exhausted at a coffee machine before sunrise",
    "meeting":    "office workers sitting around a conference table looking completely bored",
    "cat":        "a judgy cat staring down from a high shelf with contempt",
    "dog":        "a very excited golden retriever causing cheerful chaos",
    "coffee":     "someone desperately clutching a giant coffee mug with both hands",
    "deadline":   "a developer frantically typing at 3am surrounded by energy drink cans",
    "gym":        "a person doing an intense workout with an expression of absolute agony",
    "food":       "a person reacting dramatically and joyfully to a plate of delicious food",
    "sleep":      "someone refusing to get out of bed despite a blaring alarm clock",
}


def _build_image_prompt(topic, style):
    """Return a descriptive, fully textless scene prompt for the image model."""
    topic_lower = topic.lower()
    scene = None
    for kw, s in _SCENES.items():
        if kw in topic_lower:
            scene = s
            break
    if not scene:
        scene = "a funny expressive reaction scene involving " + topic
    prompt = (
        "high quality humorous photo of " + scene +
        ", meme reaction image, expressive face, sharp focus, "
        "natural lighting, no text, no words, no letters, photorealistic, detailed"
    )
    style_lower = (style or "").lower()
    if style_lower == "surreal":
        prompt += ", surreal dreamlike bizarre"
    elif style_lower == "wholesome":
        prompt += ", warm cheerful heartwarming"
    elif style_lower == "dark humor":
        prompt += ", dramatic dark cinematic"
    elif "programmer" in style_lower or "technical" in style_lower:
        prompt += ", office tech environment, computer screens"
    return prompt


# ── LLM CAPTION GENERATION ───────────────────────────────────────

_CAPTION_SYSTEM = (
    "You are a meme caption writer. You output ONLY valid JSON. "
    "No markdown. No explanation. No extra text."
)

_CAPTION_USER = (
    'Topic: "{topic}"\n'
    'Style: "{style}"\n\n'
    'Output this exact JSON (no other text):\n'
    '{{\n'
    '  "top_text": "ALL CAPS MAX 8 WORDS",\n'
    '  "bottom_text": "ALL CAPS MAX 8 WORDS",\n'
    '  "alternatives": [\n'
    '    {{"top_text": "...", "bottom_text": "..."}},\n'
    '    {{"top_text": "...", "bottom_text": "..."}},\n'
    '    {{"top_text": "...", "bottom_text": "..."}}\n'
    '  ]\n'
    '}}\n\n'
    'Rules:\n'
    '- ALL CAPS\n'
    '- No emojis unless style asks\n'
    '- No punctuation at end of lines\n'
    '- Punchy, funny, relatable\n'
    '- Do NOT describe an image -- captions only\n'
    '- Hard limit: 8 words per line; trim if needed'
)


def _parse_caption_json(text):
    s, e = text.find("{"), text.rfind("}") + 1
    if s < 0 or e <= s:
        return None
    try:
        data = json.loads(text[s:e])
    except Exception:
        return None
    top    = _wrap_text(str(data.get("top_text",    "")))
    bottom = _wrap_text(str(data.get("bottom_text", "")))
    if not top or not bottom:
        return None
    _PLACEHOLDER = {"...", "…", "...", "..."}
    alts = []
    for a in data.get("alternatives", []):
        if not isinstance(a, dict):
            continue
        at = _wrap_text(str(a.get("top_text",    "")))
        ab = _wrap_text(str(a.get("bottom_text", "")))
        # Skip unfilled placeholder alternatives left by truncated output
        if at and ab and at not in _PLACEHOLDER and ab not in _PLACEHOLDER:
            alts.append({"top_text": at, "bottom_text": ab})
    return {"top_text": top, "bottom_text": bottom, "alternatives": alts}


def _call_llm_captions(topic, style, model, extra=""):
    user_msg = _CAPTION_USER.format(topic=topic, style=style)
    if extra:
        user_msg += "\n\n" + extra
    # Use stream=True so each token arrives individually — the socket stays active
    # and never triggers a timeout, even on slow CPU-only inference.
    # We accumulate the full text then parse JSON at the end.
    # Cap at 150 tokens; the full caption JSON is ~80-120 tokens.
    # num_ctx=2048: caps KV-cache at ~200 MB instead of the default 32k-128k
    # context window which can consume 4-8 GB and crash a 16 GB VM when loaded
    # alongside ComfyUI. Caption generation needs <400 tokens total, so 2048 is safe.
    NUM_PREDICT = 150
    NUM_CTX = 2048
    for api in ("/api/chat", "/api/generate"):
        try:
            if api == "/api/chat":
                payload = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _CAPTION_SYSTEM},
                        {"role": "user",   "content": user_msg},
                    ],
                    "stream": True,
                    "options": {"temperature": 0.75, "top_p": 0.9, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
                }).encode()
            else:
                payload = json.dumps({
                    "model": model,
                    "prompt": _CAPTION_SYSTEM + "\n\n" + user_msg,
                    "stream": True,
                    "options": {"temperature": 0.75, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
                }).encode()
            req = urllib.request.Request(
                OLLAMA_URL + api, data=payload,
                headers={"Content-Type": "application/json"}
            )
            text = ""
            # timeout=180: large models (e.g. qwen2.5:7b) take 60-120s to load
            # from disk on a CPU-only VM before the first token arrives.
            # Per-token latency once streaming starts is well under 180s.
            with urllib.request.urlopen(req, timeout=180) as r:
                for raw_line in r:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    token = (chunk.get("message", {}).get("content")
                             or chunk.get("response", ""))
                    text += token
                    if chunk.get("done"):
                        break
            parsed = _parse_caption_json(text.strip())
            if parsed:
                return parsed
        except Exception:
            continue
    return None


def _unload_model(model):
    """Evict large models from Ollama RAM so ComfyUI has headroom.
    Small models (<=2GB) are kept loaded — they barely affect memory
    and reloading them is expensive relative to their size."""
    _SMALL = {"llama3.2:1b", "llama3.2:1b-instruct-q8_0", "llama3.2:3b"}
    if model in _SMALL:
        return
    try:
        payload = json.dumps(
            {"model": model, "prompt": "", "stream": False, "keep_alive": 0}
        ).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                OLLAMA_URL + "/api/generate", data=payload,
                headers={"Content-Type": "application/json"}
            ), timeout=5
        )
    except Exception:
        pass


def _free_comfy():
    """Tell ComfyUI to release its loaded model weights from RAM.
    Called before LLM inference so the two large models don't coexist.
    Skipped if ComfyUI has an active or queued job (would abort it).
    Waits up to 8s for memory to actually be released after the call."""
    try:
        with urllib.request.urlopen(COMFY_URL + "/queue", timeout=3) as r:
            q = json.loads(r.read())
        if q.get("queue_running") or q.get("queue_pending"):
            return  # generation in progress — don't free
    except Exception:
        return
    try:
        payload = json.dumps({"unload_models": True, "free_memory": True}).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                COMFY_URL + "/free", data=payload,
                headers={"Content-Type": "application/json"}
            ), timeout=10
        )
        time.sleep(3)  # give ComfyUI time to actually release pages
    except Exception:
        pass


HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meme Maker</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;padding:20px;max-width:860px;margin:0 auto}
h1{color:#58a6ff;margin-bottom:20px;font-size:1.6rem}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;margin-bottom:16px}
label{display:block;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin-bottom:6px;margin-top:14px}
label:first-child{margin-top:0}
input[type=text],select{width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;color:#e6edf3;border-radius:6px;font-size:14px}
.hint{font-size:11px;color:#8b949e;margin-top:4px}
.btn-row{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
button{padding:9px 18px;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500}
.btn-primary{background:#238636;color:#fff}.btn-primary:hover{background:#2ea043}
.btn-secondary{background:#21262d;color:#e6edf3;border:1px solid #30363d}.btn-secondary:hover{background:#30363d}
.btn-regen{background:#1f6feb;color:#fff}.btn-regen:hover{background:#388bfd}
.btn-sm{padding:6px 14px;font-size:13px}
.status{padding:10px 14px;border-radius:6px;font-size:14px;margin-top:12px}
.status-info{background:#0c2d6b;color:#58a6ff;border:1px solid #1f4a9b}
.status-error{background:#3b0a0a;color:#f85149;border:1px solid #6e1a1a}
.suggestion{display:flex;align-items:center;gap:12px;padding:12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;margin-bottom:8px}
.suggestion-text{flex:1;font-size:13px}
.sugg-caps{font-weight:700;font-size:14px;margin-bottom:4px}
.sugg-sub{color:#8b949e;font-size:12px}
.use-btn{padding:6px 14px;background:#1f6feb;color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:13px;white-space:nowrap}
.use-btn:hover{background:#388bfd}
.result-img{max-width:100%;border-radius:8px;display:block;margin-bottom:12px}
.dl-btn{padding:8px 16px;background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;cursor:pointer;text-decoration:none;font-size:13px;display:inline-block}
.dl-btn:hover{background:#30363d}
h2{font-size:1rem;color:#8b949e;font-weight:600;margin-bottom:12px}
.caption-bar{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:13px}
.caption-bar strong{color:#58a6ff}
</style>
</head>
<body>
<h1>Meme Maker</h1>
<div class="card">
  <label>Topic</label>
  <input type="text" id="topic" placeholder="e.g. Monday morning, programmer life, cats..." />
  <label>Style</label>
  <select id="style">
    <option>Any</option><option>Classic</option><option>Surreal</option>
    <option>Dark Humor</option><option>Wholesome</option><option>Technical / Programmer</option>
  </select>
  <label>AI Model</label>
  <select id="llm"><option value="">Loading...</option></select>
  <div class="hint" id="llmHint"></div>
  <div class="btn-row">
    <button class="btn-primary" onclick="getSuggestions()">Get Suggestions</button>
    <button class="btn-secondary" onclick="generateRandom()">Generate Random</button>
  </div>
</div>
<div id="status" style="display:none" class="status"></div>
<div id="progWrap" style="display:none;background:#21262d;border-radius:4px;height:10px;margin-top:8px;overflow:hidden">
  <div id="progBar" style="height:100%;background:linear-gradient(90deg,#1f6feb,#58a6ff);border-radius:4px;transition:width 0.5s ease;width:0%"></div>
</div>
<div id="suggestions" class="card" style="display:none">
  <h2 id="suggHeader">Suggestions</h2>
  <div id="suggList"></div>
</div>
<div id="resultCard" class="card" style="display:none">
  <h2>Generated Meme</h2>
  <div id="captionBar" class="caption-bar" style="display:none"></div>
  <img id="resultImg" class="result-img" />
  <div class="btn-row">
    <button class="btn-regen btn-sm" onclick="regenCaptions()">Regenerate Captions</button>
    <button class="btn-secondary btn-sm" onclick="regenImage()">Regenerate Image</button>
    <a id="dlLink" download="meme.png" class="dl-btn">Download</a>
  </div>
</div>
<script>
var _suggs=[];
var _genPoller=null;
var _genStart=0;
var _currentPid='';
var _currentTop='';
var _currentBottom='';
var _currentImagePrompt='';
var _currentModel='';

function showStatus(msg,isErr){var el=document.getElementById('status');el.textContent=msg;el.className='status '+(isErr?'status-error':'status-info');el.style.display='block';}
function hideStatus(){document.getElementById('status').style.display='none';document.getElementById('progWrap').style.display='none';document.getElementById('progBar').style.width='0%';}
function showProgress(msg,pct){showStatus(msg,false);if(pct!==undefined){document.getElementById('progWrap').style.display='block';document.getElementById('progBar').style.width=pct+'%';}}

function loadModels(){
  fetch('/models').then(function(r){return r.json();}).then(function(d){
    var sel=document.getElementById('llm');sel.innerHTML='';
    var models=d.models||[];
    if(!models.length){sel.innerHTML='<option value="">No models installed</option>';document.getElementById('llmHint').textContent='No Ollama models -- AI captions disabled';return;}
    models.forEach(function(m){var o=document.createElement('option');o.value=m.id;o.textContent=m.name;sel.appendChild(o);});
    document.getElementById('llmHint').textContent='Captions generated by selected model; image model is always textless';
  }).catch(function(){
    document.getElementById('llm').innerHTML='<option value="">Ollama unavailable</option>';
    document.getElementById('llmHint').textContent='Ollama not running -- AI captions disabled';
  });
}
window.addEventListener('DOMContentLoaded',loadModels);

function displaySuggestions(items,label){
  _suggs=items;
  var h=document.getElementById('suggHeader');if(h&&label)h.textContent=label;
  var list=document.getElementById('suggList');list.innerHTML='';
  items.forEach(function(s,i){
    var el=document.createElement('div');el.className='suggestion';
    var btn=document.createElement('button');btn.className='use-btn';btn.textContent='Use';
    btn.onclick=(function(idx){return function(){useSugg(idx);};})(i);
    var top=s.top_text||s.caption_top||'';
    var bot=s.bottom_text||s.caption_bottom||'';
    var alts=s.alternatives&&s.alternatives.length?' (+'+s.alternatives.length+' alternatives)':'';
    var txt=document.createElement('div');txt.className='suggestion-text';
    txt.innerHTML='<div class="sugg-caps">'+top+' / '+bot+'</div><div class="sugg-sub">'+alts+'</div>';
    el.appendChild(txt);el.appendChild(btn);list.appendChild(el);
  });
  document.getElementById('suggestions').style.display='block';
}

async function getSuggestions(){
  var topic=document.getElementById('topic').value.trim();
  var style=document.getElementById('style').value;
  var model=document.getElementById('llm').value;
  if(!topic){showStatus('Please enter a topic.',true);return;}
  showProgress('Getting template suggestions...');
  try{
    var r=await fetch('/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,style:style})});
    var d=await r.json();
    displaySuggestions(d.suggestions,'Template Suggestions');
    hideStatus();
    if(model){
      showProgress('Getting AI captions...');
      var _aiStart=Date.now();
      var _aiTimer=setInterval(function(){
        var elapsed=Math.round((Date.now()-_aiStart)/1000);
        if(elapsed>15)showProgress('Getting AI captions... (loading model, '+elapsed+'s)');
      },3000);
      fetch('/suggest/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,style:style,model:model})})
        .then(function(r){return r.json();})
        .then(function(d){
          clearInterval(_aiTimer);
          if(d.top_text){
            var items=[{top_text:d.top_text,bottom_text:d.bottom_text,image_prompt:d.image_prompt,alternatives:d.alternatives||[]}];
            (d.alternatives||[]).forEach(function(a){items.push({top_text:a.top_text,bottom_text:a.bottom_text,image_prompt:d.image_prompt,alternatives:[]});});
            displaySuggestions(items,'AI Suggestions');
          }
          hideStatus();
        })
        .catch(function(){clearInterval(_aiTimer);hideStatus();});
    }
  }catch(e){showStatus('Error: '+e.message,true);}
}

function useSugg(i){
  var s=_suggs[i];
  var top=s.top_text||s.caption_top||'';
  var bot=s.bottom_text||s.caption_bottom||'';
  var imgPrompt=s.image_prompt||('funny meme scene about '+document.getElementById('topic').value);
  var model=document.getElementById('llm').value;
  doGenerate(imgPrompt,top,bot,model);
}

async function generateRandom(){
  var topic=document.getElementById('topic').value.trim()||'internet humor';
  var style=document.getElementById('style').value;
  var model=document.getElementById('llm').value;
  var top='',bot='',imgPrompt='';
  showProgress('Getting AI captions...');
  if(model){
    var _rndStart=Date.now();
    var _rndTimer=setInterval(function(){
      var elapsed=Math.round((Date.now()-_rndStart)/1000);
      if(elapsed>15)showProgress('Getting AI captions... (loading model, '+elapsed+'s)');
    },3000);
    try{
      var r=await fetch('/suggest/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,style:style,model:model})});
      var d=await r.json();
      if(d.top_text){top=d.top_text;bot=d.bottom_text;imgPrompt=d.image_prompt||'';}
    }catch(e){}
    clearInterval(_rndTimer);
  }
  if(!imgPrompt){
    var r2=await fetch('/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,style:style})});
    var d2=await r2.json();
    if(d2.image_prompt)imgPrompt=d2.image_prompt;
  }
  doGenerate(imgPrompt||('high quality humorous photo of a funny scene about '+topic+', no text, no words'),top,bot,model);
}

async function doGenerate(imagePrompt,topText,bottomText,model){
  if(_genPoller){clearInterval(_genPoller);_genPoller=null;}
  _currentImagePrompt=imagePrompt;_currentTop=topText;_currentBottom=bottomText;
  if(model)_currentModel=model;
  showProgress('Submitting to image generator...',1);
  try{
    var r=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({image_prompt:imagePrompt,top_text:topText,bottom_text:bottomText,model:_currentModel||'llama3.2:1b'})});
    var d=await r.json();if(!r.ok)throw new Error(d.error||'Failed');
    _currentPid=d.prompt_id;
    _genStart=Date.now();
    showProgress('In queue...',2);
    _genPoller=setInterval(function(){pollProgress(_currentPid);},2000);
  }catch(e){showStatus('Error: '+e.message,true);}
}

async function regenCaptions(){
  if(!_currentPid){showStatus('Generate an image first.',true);return;}
  var model=document.getElementById('llm').value;
  var topic=document.getElementById('topic').value.trim()||'internet humor';
  var style=document.getElementById('style').value;
  showStatus('Regenerating captions...',false);
  try{
    var r=await fetch('/captions/regen',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt_id:_currentPid,topic:topic,style:style,model:model||'llama3.2:1b'})});
    var d=await r.json();if(!r.ok)throw new Error(d.error||'Failed');
    _currentTop=d.caption.top_text;_currentBottom=d.caption.bottom_text;
    setResult(d.meme_b64,d.caption);hideStatus();
  }catch(e){showStatus('Error: '+e.message,true);}
}

function regenImage(){
  if(!_currentImagePrompt){showStatus('Generate an image first.',true);return;}
  doGenerate(_currentImagePrompt,_currentTop,_currentBottom);
}

function setResult(b64,caption){
  var img=document.getElementById('resultImg');
  img.src='data:image/png;base64,'+b64;
  var bar=document.getElementById('captionBar');
  if(caption&&(caption.top_text||caption.bottom_text)){
    bar.innerHTML='<strong>TOP:</strong> '+(caption.top_text||'(none)')+'&nbsp;&nbsp;<strong>BOTTOM:</strong> '+(caption.bottom_text||'(none)');
    bar.style.display='block';
  }else{bar.style.display='none';}
  var bytes=atob(b64),arr=new Uint8Array(bytes.length);
  for(var i=0;i<bytes.length;i++)arr[i]=bytes.charCodeAt(i);
  var blob=new Blob([arr],{type:'image/png'});
  var dl=document.getElementById('dlLink');
  if(dl._blobUrl)URL.revokeObjectURL(dl._blobUrl);
  dl._blobUrl=URL.createObjectURL(blob);dl.href=dl._blobUrl;
  document.getElementById('resultCard').style.display='block';
  img.scrollIntoView({behavior:'smooth'});
}

var _pollFailCount=0;
function pollProgress(pid){
  var elapsed=Math.floor((Date.now()-_genStart)/1000);
  fetch('/progress/'+pid).then(function(r){return r.json();}).then(function(d){
    _pollFailCount=0;
    if(d.status==='done'){
      clearInterval(_genPoller);_genPoller=null;hideStatus();
      if(d.prompt_id)_currentPid=d.prompt_id;
      setResult(d.image_b64,d.caption);
    }else if(d.status==='error'){
      clearInterval(_genPoller);_genPoller=null;
      showStatus('Generation failed: '+(d.error||'unknown'),true);
    }else if(d.status==='running'){
      var step=d.step||0,total=d.total||20,pct=d.pct||0;
      if(step>0){showProgress('Generating... Step '+step+'/'+total+' ('+pct+'%)',pct);}
      else{showProgress('Generating... '+elapsed+'s elapsed -- loading model',5);}
    }else{
      showProgress('In queue... '+elapsed+'s',2);
    }
  }).catch(function(){
    _pollFailCount++;
    if(_pollFailCount>=5){clearInterval(_genPoller);_genPoller=null;showStatus('Lost connection after '+elapsed+'s -- refresh and retry.',true);}
  });
}
</script>
</body>
</html>"""


# ── COMFYUI HELPERS ───────────────────────────────────────────────

def _submit_comfy(image_prompt):
    """Submit a textless-image job to ComfyUI. Returns (pid, client_id)."""
    wf = json.loads(json.dumps(_WF))  # deep copy
    wf["6"]["inputs"]["text"] = image_prompt
    wf["7"]["inputs"]["text"] = NEGATIVE_PROMPT
    wf["3"]["inputs"]["seed"] = random.randint(0, 2 ** 32 - 1)
    client_id = uuid.uuid4().hex
    payload   = json.dumps({"prompt": wf, "client_id": client_id}).encode()
    req = urllib.request.Request(
        COMFY_URL + "/prompt", data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())
    pid = result.get("prompt_id")
    if not pid:
        raise RuntimeError("No prompt_id from ComfyUI")
    return pid, client_id


def _track_ws_progress(pid, client_id):
    import websocket as _ws
    prog = _job_progress.setdefault(pid, {"step": 0, "total": 20, "status": "queued"})
    def on_msg(ws, msg):
        try:
            d = json.loads(msg)
            t = d.get("type", "")
            v = d.get("data", {})
            if v.get("prompt_id") not in (pid, None):
                return
            if t == "progress":
                prog["step"]   = v.get("value", prog["step"])
                prog["total"]  = v.get("max",   prog["total"])
                prog["status"] = "running"
            elif t == "execution_start":
                prog["status"] = "running"
            elif t in ("execution_success", "execution_error", "execution_interrupted"):
                prog["status"] = "done"
                ws.close()
        except Exception:
            pass
    _ws.WebSocketApp(
        "ws://localhost:8188/ws?clientId=" + client_id,
        on_message=on_msg,
        on_error=lambda ws, e: None,
        on_close=lambda ws, *a: None,
    ).run_forever(ping_timeout=300)


def _fetch_raw_from_history(pid):
    """Fetch the textless raw image bytes from ComfyUI history."""
    try:
        with urllib.request.urlopen(COMFY_URL + "/history/" + pid, timeout=5) as r:
            history = json.loads(r.read())
        if pid not in history:
            return None
        for _, nout in history[pid].get("outputs", {}).items():
            for img in nout.get("images", []):
                url = (COMFY_URL + "/view?filename=" + img["filename"]
                       + "&subfolder=" + img.get("subfolder", "") + "&type=output")
                with urllib.request.urlopen(url, timeout=10) as r:
                    return r.read()
    except Exception:
        pass
    return None


# ── FLASK ROUTES ─────────────────────────────────────────────────

@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/models")
def models():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
            data = json.loads(r.read())
        result = [{"id": m["name"], "name": m["name"]} for m in data.get("models", [])]
    except Exception:
        result = []
    return jsonify({"models": result})


@app.route("/suggest", methods=["POST"])
def suggest():
    """Instant template suggestions — no AI wait."""
    data  = request.get_json() or {}
    topic = data.get("topic", "funny meme")
    style = data.get("style", "Any")
    image_prompt = _build_image_prompt(topic, style)
    suggestions = [
        {"top_text": "EXPECTATION",
         "bottom_text": _wrap_text("REALITY WITH " + topic, 8),
         "image_prompt": image_prompt},
        {"top_text": _wrap_text("ME THINKING ABOUT " + topic, 8),
         "bottom_text": "ALSO ME DOING NOTHING",
         "image_prompt": image_prompt},
        {"top_text": _wrap_text(topic, 6),
         "bottom_text": "EVERY SINGLE TIME",
         "image_prompt": image_prompt},
    ]
    return jsonify({"suggestions": suggestions, "image_prompt": image_prompt})


@app.route("/suggest/ai", methods=["POST"])
def suggest_ai():
    """AI-powered caption generation. Image prompt is always textless."""
    data  = request.get_json() or {}
    topic = data.get("topic", "funny meme")
    style = data.get("style", "Any")
    model = data.get("model", "") or "llama3.2:1b"
    _free_comfy()   # release ComfyUI model weights before loading LLM
    image_prompt = _build_image_prompt(topic, style)
    caption_data = _call_llm_captions(topic, style, model)
    if not caption_data:
        return jsonify({"error": "LLM did not return valid captions"}), 500
    return jsonify({
        "top_text":     caption_data["top_text"],
        "bottom_text":  caption_data["bottom_text"],
        "alternatives": caption_data["alternatives"],
        "image_prompt": image_prompt,
    })


@app.route("/generate", methods=["POST"])
def generate():
    """
    Submit a textless image job + store captions for overlay.
    Body: {image_prompt, top_text, bottom_text}
    Returns: {prompt_id}
    """
    data         = request.get_json() or {}
    model        = data.get("model", "") or "llama3.2:1b"
    image_prompt = (data.get("image_prompt") or
                    _build_image_prompt(data.get("topic", "internet humor"),
                                        data.get("style", "Any")))
    top_text     = _wrap_text(data.get("top_text",    ""), 8)
    bottom_text  = _wrap_text(data.get("bottom_text", ""), 8)
    _unload_model(model)
    try:
        pid, client_id = _submit_comfy(image_prompt)
    except urllib.error.URLError as e:
        return jsonify({"error": "ComfyUI unavailable: " + str(e)}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    _job_captions[pid] = (top_text, bottom_text)
    _job_progress[pid] = {"step": 0, "total": 20, "status": "queued"}
    threading.Thread(target=_track_ws_progress, args=(pid, client_id), daemon=True).start()
    return jsonify({"prompt_id": pid})


@app.route("/captions/regen", methods=["POST"])
def captions_regen():
    """
    Regenerate captions for an already-generated image (no new ComfyUI job).
    Body: {prompt_id, topic, style, model}  OR  {prompt_id, top_text, bottom_text}
    Returns: {meme_b64, caption: {top_text, bottom_text}}
    """
    data = request.get_json() or {}
    pid  = data.get("prompt_id", "")
    raw  = _raw_images.get(pid)
    if not raw:
        return jsonify({"error": "Image not found -- generate an image first"}), 404
    if data.get("top_text") and data.get("bottom_text"):
        top    = _wrap_text(data["top_text"])
        bottom = _wrap_text(data["bottom_text"])
    else:
        topic  = data.get("topic", "funny meme")
        style  = data.get("style", "Any")
        model  = data.get("model") or "llama3.2:1b"
        _free_comfy()
        result = _call_llm_captions(topic, style, model)
        if not result:
            return jsonify({"error": "LLM caption generation failed"}), 500
        top    = result["top_text"]
        bottom = result["bottom_text"]
    meme_bytes = apply_meme_text(raw, top, bottom)
    _job_captions[pid] = (top, bottom)
    return jsonify({
        "meme_b64": base64.b64encode(meme_bytes).decode(),
        "caption":  {"top_text": top, "bottom_text": bottom},
    })


@app.route("/progress/<pid>")
def progress(pid):
    """Poll job status. On completion stores raw image and returns overlaid meme."""
    # Already have the raw image cached
    if pid in _raw_images:
        raw   = _raw_images[pid]
        caps  = _job_captions.get(pid, ("", ""))
        final = apply_meme_text(raw, caps[0], caps[1])
        return jsonify({
            "status":    "done",
            "image_b64": base64.b64encode(final).decode(),
            "caption":   {"top_text": caps[0], "bottom_text": caps[1]},
            "prompt_id": pid,
        })
    try:
        with urllib.request.urlopen(COMFY_URL + "/history/" + pid, timeout=5) as r:
            history = json.loads(r.read())
        if pid in history:
            raw = _fetch_raw_from_history(pid)
            if raw:
                _raw_images[pid] = raw
                caps  = _job_captions.get(pid, ("", ""))
                final = apply_meme_text(raw, caps[0], caps[1])
                return jsonify({
                    "status":    "done",
                    "image_b64": base64.b64encode(final).decode(),
                    "caption":   {"top_text": caps[0], "bottom_text": caps[1]},
                    "prompt_id": pid,
                })
            return jsonify({"status": "error", "error": "No image in ComfyUI output"})
        with urllib.request.urlopen(COMFY_URL + "/queue", timeout=5) as r:
            queue = json.loads(r.read())
        running = [item[1] for item in queue.get("queue_running", [])]
        pending = [item[1] for item in queue.get("queue_pending", [])]
        prog    = _job_progress.get(pid, {})
        step    = prog.get("step", 0)
        total   = prog.get("total", 20)
        pct     = int(step / total * 100) if total else 0
        if pid in running:
            return jsonify({"status": "running", "step": step, "total": total, "pct": pct})
        if pid in pending:
            return jsonify({"status": "queued", "position": pending.index(pid) + 1, "pct": 0})
        return jsonify({"status": "queued"})
    except Exception as e:
        return jsonify({"status": "queued", "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8189, debug=False)'''

            lines += [
                "# Install ComfyUI (Stable Diffusion image generation)",
                "echo 'Installing ComfyUI and dependencies for Meme Maker...'",
                "apt-get update -qq",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip python3-venv git wget",
                "",
                "# Clone ComfyUI",
                "git clone --depth 1 https://github.com/comfyanonymous/ComfyUI /opt/comfyui",
                "",
                "# Create venv",
                "python3 -m venv /opt/comfyui-env",
                "/opt/comfyui-env/bin/pip install --upgrade pip",
                "",
                f"echo 'Installing PyTorch from {torch_index}...'",
                f"/opt/comfyui-env/bin/pip install torch torchvision torchaudio --index-url {torch_index}",
                "",
                "/opt/comfyui-env/bin/pip install -r /opt/comfyui/requirements.txt",
                "",
                "# Download DreamShaper 8 checkpoint",
                "echo 'Downloading DreamShaper 8...'",
                "mkdir -p /opt/comfyui/models/checkpoints",
                f'wget -q --show-progress -O "/opt/comfyui/models/checkpoints/DreamShaper_8_pruned.safetensors" \\',
                f'  "{dreamshaper_url}" || echo "WARNING: Model download failed"',
                "",
                "# Write comfy.settings.json to suppress Missing Models dialog",
                "mkdir -p /opt/comfyui/user/default",
                'echo \'{"Comfy.InstalledVersion": "0.0.0", "Comfy.TutorialCompleted": true, "Comfy.Workflow.ShowMissingModelsWarning": false}\' > /opt/comfyui/user/default/comfy.settings.json',
                "",
                "# Write CPU wrapper (disables MKL/oneDNN — needed on KVM CPUs without AVX)",
                "cat > /opt/comfyui/run_cpu.py << 'RUN_CPU_EOF'",
                "import torch",
                "torch.backends.mkldnn.enabled = False",
                "import runpy, sys",
                'sys.argv[0] = "/opt/comfyui/main.py"',
                'runpy.run_path("/opt/comfyui/main.py", run_name="__main__")',
                "RUN_CPU_EOF",
                "",
                "# Create ComfyUI systemd service",
                "cat > /etc/systemd/system/comfyui.service << 'COMFY_MEME_SERVICE_EOF'",
                "[Unit]",
                "Description=ComfyUI for Meme Maker",
                "After=network.target",
                "",
                "[Service]",
                "Type=simple",
                "User=root",
                "WorkingDirectory=/opt/comfyui",
                "Environment=PYTHONUNBUFFERED=1",
                f"ExecStart=/opt/comfyui-env/bin/python /opt/comfyui/run_cpu.py {comfyui_args} --disable-smart-memory",
                "Restart=on-failure",
                "RestartSec=10",
                "StandardOutput=journal",
                "StandardError=journal",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "COMFY_MEME_SERVICE_EOF",
                "",
                "systemctl daemon-reload",
                "systemctl enable comfyui",
                "systemctl start comfyui",
                "",
                "# Install Ollama and pull qwen2.5:7b (structured JSON output for captions)",
                "echo 'Installing Ollama for meme caption suggestions...'",
                "curl -fsSL https://ollama.ai/install.sh | sh",
                "systemctl enable ollama",
                "systemctl start ollama",
                "# Wait for Ollama daemon",
                "for i in $(seq 1 30); do",
                "  ollama list >/dev/null 2>&1 && break",
                "  sleep 2",
                "done",
                "OLLAMA_MODELS=/usr/share/ollama/.ollama/models ollama pull qwen2.5:7b",
                "",
                "# Install Flask + Pillow in own venv (avoids Ubuntu 24.04 externally-managed-environment error)",
                "python3 -m venv /opt/meme-app-env",
                "/opt/meme-app-env/bin/pip install flask Pillow --quiet",
                "",
                "# Write meme Flask app",
                "mkdir -p /opt/meme-app",
                "cat > /opt/meme-app/app.py << 'MEME_APP_EOF'",
            ] + meme_app_src.splitlines() + [
                "MEME_APP_EOF",
                "",
                "# Create meme-app systemd service",
                "cat > /etc/systemd/system/meme-app.service << 'MEME_SVC_EOF'",
                "[Unit]",
                "Description=Meme Maker Web App",
                "After=network.target comfyui.service ollama.service",
                "Wants=comfyui.service ollama.service",
                "",
                "[Service]",
                "Type=simple",
                "User=root",
                "WorkingDirectory=/opt/meme-app",
                "ExecStart=/opt/meme-app-env/bin/python /opt/meme-app/app.py",
                "Restart=on-failure",
                "RestartSec=10",
                "StandardOutput=journal",
                "StandardError=journal",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "MEME_SVC_EOF",
                "",
                "systemctl daemon-reload",
                "systemctl enable meme-app",
                "systemctl start meme-app",
                'echo "Meme Maker services started"',
                'echo "  Meme UI  : http://$(hostname -I | awk \'{print $1}\'):8189"',
                'echo "  ComfyUI  : http://$(hostname -I | awk \'{print $1}\'):8188"',
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
        elif engine == "stable-diffusion":
            lines.append(
                "echo \"  ComfyUI : http://$(hostname -I | awk '{print $1}'):8188\""
            )
        elif engine == "meme-maker":
            lines.append(
                "echo \"  Meme UI : http://$(hostname -I | awk '{print $1}'):8189\""
            )
            lines.append(
                "echo \"  ComfyUI : http://$(hostname -I | awk '{print $1}'):8188\""
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
        elif engine == "stable-diffusion":
            extra_packages += ["python3-pip", "python3-venv", "git", "wget"]
        elif engine == "meme-maker":
            extra_packages += ["python3-pip", "python3-venv", "git", "wget"]

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
