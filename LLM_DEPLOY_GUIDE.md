# Deploy LLM Guide

Deploy a fully self-hosted AI inference server on your own Proxmox infrastructure — no cloud accounts, no usage fees, no data leaving your network.

---

## What Is It?

**Deploy LLM** provisions a complete VM running one of four open-source inference engines:

| Engine | Best For | API | GPU |
|--------|----------|-----|-----|
| **Ollama** | Easy setup, wide model library | `/api/generate` (port 11434) | Optional |
| **llama.cpp** | High-performance C++ inference | Standalone server | Optional |
| **vLLM** | OpenAI-compatible production API | OpenAI format (port 8000) | Required (NVIDIA) |
| **LocalAI** | Drop-in OpenAI API replacement | OpenAI format (port 8080) | Optional |
| **Stable Diffusion (ComfyUI)** | AI image generation | ComfyUI web UI (port 8188) | Optional (strongly recommended) |

---

## Prerequisites

- Proxmox VE host configured in Depl0y
- Cloud images enabled (Settings → Cloud Image Setup) — LLM VMs use Ubuntu 24.04 cloud image
- Recommended: 16 GB+ RAM, 40+ GB disk, SSD storage pool
- For GPU: IOMMU enabled in BIOS and Proxmox; GPU in a separate IOMMU group

---

## Simple Mode (Recommended)

Answer 4 questions — Depl0y handles everything else.

**Step 1 — Use case:**
| Choice | What it does |
|--------|-------------|
| Chat & Q&A | Conversational assistant (Ollama) |
| Coding Helper | Code generation, review, debugging (Ollama) |
| Document Analysis | Summarise and query documents (Ollama) |
| Research & Reasoning | Multi-step analysis and reasoning (Ollama) |
| Humor & Memes | **AI image generation** — deploys Stable Diffusion via ComfyUI on port 8188 |

**Step 2 — Response/image quality:**

For text use cases (Chat, Coding, Docs, Reasoning):
| Tier | Models | RAM | Disk |
|------|--------|-----|------|
| Fast & Light | 1–3B parameter | 4–8 GB | 15–25 GB |
| Balanced | 7–8B parameter | 12–16 GB | 25–40 GB |
| High Quality | 14B+ parameter | 24+ GB | 50+ GB |

For Humor & Memes (Stable Diffusion):
| Tier | Model | RAM | Disk |
|------|-------|-----|------|
| Fast & Light | SD v1.5 | 8 GB | 30 GB |
| Balanced | DreamShaper 8 | 12 GB | 40 GB |
| High Quality | SDXL 1.0 | 24 GB | 60 GB |

**Step 3 — GPU:** Select None (CPU-only), NVIDIA, or AMD. A GPU is strongly recommended for Stable Diffusion (CPU generation is very slow).

**Step 4 — Web UI:** For text use cases, choose Open WebUI (ChatGPT-like interface on port 3000) or API-only. For Humor & Memes, ComfyUI is automatically deployed on port 8188.

Depl0y then walks you through node/storage selection and credentials before deploying.

---

## Advanced Mode

Full control across 8 steps:

1. **Engine** — Ollama / llama.cpp / vLLM / LocalAI
2. **Model** — browse the catalog with per-model RAM, VRAM, and disk requirements
3. **Hardware profile** — CPU-only or GPU accelerated (5–20× faster inference)
4. **GPU device** — select the specific PCI device from your Proxmox node (requires IOMMU)
5. **UI** — Open WebUI or API-only
6. **Infrastructure** — host, node, storage pool, network bridge
7. **Credentials & sizing** — VM name, IP, username, password, CPU/RAM/disk overrides
8. **Review & deploy**

---

## What Happens During Deployment

The VM is provisioned using cloud-init. After first boot, a background script (`/opt/setup-llm.sh`) automatically:

1. Installs GPU drivers (NVIDIA `ubuntu-drivers` or AMD ROCm) if enabled
2. Installs the selected inference engine
3. Pulls the selected model
4. **Auto-tunes thread count** — benchmarks 4–6 thread-count candidates via the Ollama API and bakes the winner into the model's Modelfile (`PARAMETER num_thread N`)
5. Optionally deploys Open WebUI via Docker
6. Logs all output to `/var/log/llm-setup.log`
7. Saves the tuning report to `/var/log/llm-tuning.log`

Setup takes **5–30 minutes** depending on model size and internet speed. The Depl0y progress tracker shows live stage updates.

---

## Access URLs

After deployment:

| Engine | URL |
|--------|-----|
| Ollama | `http://<vm-ip>:11434` |
| vLLM | `http://<vm-ip>:8000` (OpenAI-compatible) |
| LocalAI | `http://<vm-ip>:8080` (OpenAI-compatible) |
| Open WebUI | `http://<vm-ip>:3000` |
| ComfyUI (Stable Diffusion) | `http://<vm-ip>:8188` |

---

## Using Open WebUI

Open WebUI provides a full ChatGPT-like interface connected directly to your local Ollama instance.

1. Navigate to `http://<vm-ip>:3000`
2. Create an account (stored locally on the VM)
3. Select a model from the dropdown
4. Start chatting

---

## Using the Ollama API

```bash
# Basic completion
curl http://<vm-ip>:11434/api/generate \
  -d '{"model":"llama3.1:8b","prompt":"Hello!","stream":false}'

# Chat completion
curl http://<vm-ip>:11434/api/chat \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"Hello!"}]}'
```

---

## Using vLLM / LocalAI (OpenAI-compatible)

```python
from openai import OpenAI

client = OpenAI(base_url="http://<vm-ip>:8000/v1", api_key="none")
response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

---

## Performance Notes

- **CPU inference**: Ollama auto-selects the best GGML CPU backend (AVX2, AVX-512, etc.) for your processor
- **Thread count**: Depl0y benchmarks and sets the optimal `num_thread` for your specific VM — more threads is not always better (56 threads on an 8B model is 3× slower than 12)
- **Flash attention**: enabled by default (`OLLAMA_FLASH_ATTENTION=1`) — reduces memory usage and improves throughput
- **Model keep-alive**: models stay loaded in RAM for 60 minutes between requests (no cold-start penalty on repeated use)
- **GPU acceleration**: NVIDIA/AMD passthrough gives 5–20× faster inference; requires IOMMU groups and a dedicated GPU

### Approximate throughput (CPU, llama3.1:8b, E5-2690 v4):
| Threads | tok/s |
|---------|-------|
| 56 (default, broken) | 1.4 |
| 14 | 4.1 |
| **12 (auto-tuned)** | **4.3** |
| 8 | 3.9 |

---

## Troubleshooting

**Setup still running after 30 minutes**
```bash
ssh <username>@<vm-ip>
tail -f /var/log/llm-setup.log
```

**Model not loaded / slow first response**
- First request after idle triggers model load from disk (~30–60 s for 8B models)
- `OLLAMA_KEEP_ALIVE=60m` keeps it in RAM for 60 min after last use

**Check tuning results**
```bash
cat /var/log/llm-tuning.log
```

**Ollama service not starting**
```bash
sudo systemctl status ollama
sudo journalctl -u ollama -n 50
```

**GPU not detected**
- Verify IOMMU is enabled: `dmesg | grep -i iommu`
- Check the GPU is in its own IOMMU group in Proxmox
- NVIDIA: `nvidia-smi` inside the VM

---

## Humor & Memes — Image Generation

The **Humor & Memes** use case deploys a Stable Diffusion image generation stack rather than a text LLM.

- **Engine:** ComfyUI on port 8188 — a powerful node-based image generation interface
- **Models:** SD v1.5, DreamShaper 8 (fine-tuned for creative images), or SDXL 1.0 (1024×1024 high-res)
- **Input:** Text prompts → generated images (JPEG/PNG)
- **GPU strongly recommended:** CPU inference works but is extremely slow (5–30 minutes per image). A GPU delivers images in seconds.
- **Model files** are downloaded from HuggingFace during first boot. If the download fails (network issues or model access), ComfyUI still starts — add model checkpoints manually to `/opt/comfyui/models/checkpoints/`

### Using ComfyUI

1. Navigate to `http://<vm-ip>:8188`
2. Load a workflow (File → Load Default or drag a JSON workflow)
3. Set your text prompt in the `CLIPTextEncode` node
4. Click **Queue Prompt** to generate an image

For meme generation, try prompts like:
```
funny meme image, surprised cat face, white text overlay, high contrast
```
