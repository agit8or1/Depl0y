"""LLM Deployment API routes"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_operator
from app.core.database import get_db
from app.core.security import encrypt_data
from app.models import (
    CloudImage,
    LLMDeployment,
    OSType,
    ProxmoxHost,
    ProxmoxNode,
    User,
    VMStatus,
    VirtualMachine,
)
from app.services.llm_cloudinit import LLMCloudInitService

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

LLM_CATALOG: Dict[str, Any] = {
    "engines": [
        {
            "id": "ollama",
            "name": "Ollama",
            "description": "Easy setup with a wide model library. Runs on CPU and GPU. Recommended for most users.",
            "recommended": True,
        },
        {
            "id": "llama.cpp",
            "name": "llama.cpp",
            "description": "High-performance C++ inference. Ideal for power users who want maximum throughput.",
            "recommended": False,
        },
        {
            "id": "vllm",
            "name": "vLLM",
            "description": "GPU-optimized production serving with OpenAI-compatible API. Requires NVIDIA GPU. Best throughput for concurrent users.",
            "recommended": False,
            "gpu_required": True,
        },
        {
            "id": "localai",
            "name": "LocalAI",
            "description": "Drop-in OpenAI API replacement. Runs on CPU or GPU. Great for apps already using the OpenAI SDK.",
            "recommended": False,
        },
        {
            "id": "stable-diffusion",
            "name": "Stable Diffusion (ComfyUI)",
            "description": "AI image generation engine. Deploys ComfyUI on port 8188. Generates images from text prompts. GPU strongly recommended.",
            "recommended": False,
        },
        {
            "id": "meme-maker",
            "name": "Meme Maker",
            "description": "AI-powered meme generator. Enter a topic or upload an image; the AI suggests formats and captions, then generates the image. Runs ComfyUI + Ollama on the VM.",
            "recommended": False,
        },
    ],
    "models": {
        "ollama": [
            {
                "id": "llama3.2:1b",
                "name": "Llama 3.2 1B",
                "category": "general",
                "description": "Meta's smallest Llama 3.2. Fast, minimal resource use – great for testing.",
                "size_gb": 0.8,
                "min_ram_gb": 4,
                "recommended_ram_gb": 6,
                "min_vram_gb": 1,
                "min_cpu_cores": 2,
                "min_disk_gb": 20,
                "gpu_optional": True,
            },
            {
                "id": "llama3.2:3b",
                "name": "Llama 3.2 3B",
                "category": "general",
                "description": "Balanced performance and size. Good for CPU-only setups.",
                "size_gb": 2.0,
                "min_ram_gb": 8,
                "recommended_ram_gb": 12,
                "min_vram_gb": 2,
                "min_cpu_cores": 4,
                "min_disk_gb": 25,
                "gpu_optional": True,
            },
            {
                "id": "llama3.1:8b",
                "name": "Llama 3.1 8B",
                "category": "general",
                "description": "Meta's highly capable 8B model. Best balance of quality and resource cost.",
                "size_gb": 4.7,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 6,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "llama3.3:70b",
                "name": "Llama 3.3 70B",
                "category": "general",
                "description": "Top-tier large model. Requires substantial resources – GPU strongly recommended.",
                "size_gb": 43,
                "min_ram_gb": 64,
                "recommended_ram_gb": 128,
                "min_vram_gb": 48,
                "min_cpu_cores": 16,
                "min_disk_gb": 100,
                "gpu_optional": False,
            },
            {
                "id": "mistral:7b",
                "name": "Mistral 7B",
                "category": "general",
                "description": "Highly capable 7B model with strong reasoning. One of the most popular choices.",
                "size_gb": 4.1,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "phi4:14b",
                "name": "Phi-4 14B",
                "category": "general",
                "description": "Microsoft Phi-4 – exceptional reasoning for its size.",
                "size_gb": 9.1,
                "min_ram_gb": 16,
                "recommended_ram_gb": 24,
                "min_vram_gb": 10,
                "min_cpu_cores": 8,
                "min_disk_gb": 45,
                "gpu_optional": True,
            },
            {
                "id": "gemma2:2b",
                "name": "Gemma 2 2B",
                "category": "general",
                "description": "Google's compact Gemma 2. Very efficient for basic tasks.",
                "size_gb": 1.6,
                "min_ram_gb": 6,
                "recommended_ram_gb": 8,
                "min_vram_gb": 2,
                "min_cpu_cores": 2,
                "min_disk_gb": 20,
                "gpu_optional": True,
            },
            {
                "id": "gemma2:9b",
                "name": "Gemma 2 9B",
                "category": "general",
                "description": "Google's Gemma 2 9B. Strong quality with manageable resource needs.",
                "size_gb": 5.4,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 8,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "qwen2.5:7b",
                "name": "Qwen 2.5 7B",
                "category": "general",
                "description": "Alibaba Qwen 2.5 – excellent multilingual support.",
                "size_gb": 4.4,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "deepseek-r1:7b",
                "name": "DeepSeek R1 7B",
                "category": "reasoning",
                "description": "Reasoning-focused with chain-of-thought. Great for complex problems.",
                "size_gb": 4.7,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "codellama:7b",
                "name": "Code Llama 7B",
                "category": "code",
                "description": "Meta's Code Llama. Specialized for code generation and debugging.",
                "size_gb": 3.8,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "qwen2.5-coder:7b",
                "name": "Qwen 2.5 Coder 7B",
                "category": "code",
                "description": "Excellent coding assistant supporting 92+ programming languages.",
                "size_gb": 4.4,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "nomic-embed-text",
                "name": "Nomic Embed Text",
                "category": "embedding",
                "description": "High-quality text embeddings for RAG pipelines and semantic search.",
                "size_gb": 0.3,
                "min_ram_gb": 4,
                "recommended_ram_gb": 4,
                "min_vram_gb": 1,
                "min_cpu_cores": 2,
                "min_disk_gb": 20,
                "gpu_optional": True,
            },
        ],
        "llama.cpp": [
            {
                "id": "llama-3.1-8b-instruct",
                "name": "Llama 3.1 8B Instruct (GGUF)",
                "category": "general",
                "description": "Llama 3.1 8B in GGUF format for llama.cpp.",
                "size_gb": 4.7,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 6,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "mistral-7b-instruct",
                "name": "Mistral 7B Instruct (GGUF)",
                "category": "general",
                "description": "Mistral 7B in GGUF format for llama.cpp.",
                "size_gb": 4.1,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
        ],
        "vllm": [
            {
                "id": "llama3.1:8b",
                "name": "Llama 3.1 8B (HuggingFace)",
                "category": "general",
                "description": "Meta Llama 3.1 8B pulled from HuggingFace via vLLM. High-throughput GPU serving.",
                "size_gb": 16.0,
                "min_ram_gb": 20,
                "recommended_ram_gb": 24,
                "min_vram_gb": 16,
                "min_cpu_cores": 8,
                "min_disk_gb": 50,
                "gpu_optional": False,
            },
            {
                "id": "llama3.1:70b",
                "name": "Llama 3.1 70B (HuggingFace)",
                "category": "general",
                "description": "Meta Llama 3.1 70B for high-quality production serving. Requires multi-GPU or large VRAM.",
                "size_gb": 140.0,
                "min_ram_gb": 80,
                "recommended_ram_gb": 128,
                "min_vram_gb": 80,
                "min_cpu_cores": 16,
                "min_disk_gb": 200,
                "gpu_optional": False,
            },
            {
                "id": "mistral:7b",
                "name": "Mistral 7B (HuggingFace)",
                "category": "general",
                "description": "Mistral 7B pulled from HuggingFace via vLLM. Strong reasoning with OpenAI-compatible API.",
                "size_gb": 14.0,
                "min_ram_gb": 20,
                "recommended_ram_gb": 24,
                "min_vram_gb": 14,
                "min_cpu_cores": 8,
                "min_disk_gb": 45,
                "gpu_optional": False,
            },
            {
                "id": "qwen2.5:7b",
                "name": "Qwen 2.5 7B (HuggingFace)",
                "category": "general",
                "description": "Alibaba Qwen 2.5 7B via vLLM. Excellent multilingual support with OpenAI-compatible API.",
                "size_gb": 14.0,
                "min_ram_gb": 20,
                "recommended_ram_gb": 24,
                "min_vram_gb": 14,
                "min_cpu_cores": 8,
                "min_disk_gb": 45,
                "gpu_optional": False,
            },
        ],
        "stable-diffusion": [
            {
                "id": "sd-v1.5",
                "name": "Stable Diffusion v1.5",
                "category": "image",
                "description": "Classic SD 1.5. CPU-capable but slow. Fast with GPU. Good starting point for meme generation.",
                "size_gb": 2.0,
                "min_ram_gb": 8,
                "recommended_ram_gb": 12,
                "min_vram_gb": 4,
                "min_cpu_cores": 4,
                "min_disk_gb": 30,
                "gpu_optional": True,
            },
            {
                "id": "dreamshaper-8",
                "name": "DreamShaper 8",
                "category": "image",
                "description": "Highly capable fine-tuned SD model. Excellent for creative, stylized, and meme images.",
                "size_gb": 2.0,
                "min_ram_gb": 12,
                "recommended_ram_gb": 16,
                "min_vram_gb": 4,
                "min_cpu_cores": 4,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "sdxl",
                "name": "Stable Diffusion XL 1.0",
                "category": "image",
                "description": "High-resolution image generation (1024×1024). Best quality but needs significant VRAM. GPU recommended.",
                "size_gb": 6.6,
                "min_ram_gb": 16,
                "recommended_ram_gb": 24,
                "min_vram_gb": 8,
                "min_cpu_cores": 8,
                "min_disk_gb": 60,
                "gpu_optional": True,
            },
        ],
        "meme-maker": [
            {
                "id": "meme-maker-v1",
                "name": "Meme Maker v1",
                "category": "image",
                "description": "DreamShaper 8 for generation + Llama 3.2 1B for caption suggestions. GPU optional.",
                "size_gb": 3.0,
                "min_ram_gb": 12,
                "recommended_ram_gb": 16,
                "min_vram_gb": 4,
                "min_cpu_cores": 4,
                "min_disk_gb": 40,
                "gpu_optional": True,
            }
        ],
        "localai": [
            {
                "id": "llama3.2:1b",
                "name": "Llama 3.2 1B (GGUF)",
                "category": "general",
                "description": "Meta's smallest Llama 3.2 in GGUF format. Fast, minimal resource use.",
                "size_gb": 0.8,
                "min_ram_gb": 4,
                "recommended_ram_gb": 6,
                "min_vram_gb": 1,
                "min_cpu_cores": 2,
                "min_disk_gb": 20,
                "gpu_optional": True,
            },
            {
                "id": "llama3.2:3b",
                "name": "Llama 3.2 3B (GGUF)",
                "category": "general",
                "description": "Balanced performance in GGUF format. Good for CPU-only setups via LocalAI.",
                "size_gb": 2.0,
                "min_ram_gb": 8,
                "recommended_ram_gb": 12,
                "min_vram_gb": 2,
                "min_cpu_cores": 4,
                "min_disk_gb": 25,
                "gpu_optional": True,
            },
            {
                "id": "llama3.1:8b",
                "name": "Llama 3.1 8B (GGUF)",
                "category": "general",
                "description": "Meta Llama 3.1 8B in GGUF format via LocalAI OpenAI-compatible API.",
                "size_gb": 4.7,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 6,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
            {
                "id": "mistral:7b",
                "name": "Mistral 7B (GGUF)",
                "category": "general",
                "description": "Mistral 7B in GGUF format. Drop-in replacement for OpenAI API calls.",
                "size_gb": 4.1,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "codellama:7b",
                "name": "Code Llama 7B (GGUF)",
                "category": "code",
                "description": "Meta Code Llama 7B in GGUF format. Specialized for code generation via LocalAI.",
                "size_gb": 3.8,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 35,
                "gpu_optional": True,
            },
            {
                "id": "deepseek-r1:7b",
                "name": "DeepSeek R1 7B (GGUF)",
                "category": "reasoning",
                "description": "Reasoning-focused model in GGUF format. Chain-of-thought via LocalAI API.",
                "size_gb": 4.7,
                "min_ram_gb": 16,
                "recommended_ram_gb": 16,
                "min_vram_gb": 5,
                "min_cpu_cores": 8,
                "min_disk_gb": 40,
                "gpu_optional": True,
            },
        ],
    },
    "os_options": [
        {
            "id": "ubuntu2404",
            "name": "Ubuntu 24.04 LTS",
            "description": "Latest LTS – best NVIDIA/AMD driver support. Recommended.",
            "recommended": True,
            "search_terms": ["ubuntu 24", "ubuntu-24", "noble"],
        },
        {
            "id": "ubuntu2204",
            "name": "Ubuntu 22.04 LTS",
            "description": "Previous LTS – very stable and widely tested.",
            "recommended": False,
            "search_terms": ["ubuntu 22", "ubuntu-22", "jammy"],
        },
    ],
    "ui_options": [
        {
            "id": "open-webui",
            "name": "Open WebUI",
            "description": "Full-featured ChatGPT-like interface. Runs on port 3000 via Docker.",
            "recommended": True,
            "port": 3000,
        },
        {
            "id": "api-only",
            "name": "API Only",
            "description": "Just the inference API (Ollama REST on port 11434). For developers and custom frontends.",
            "recommended": False,
            "port": 11434,
        },
        {
            "id": "comfyui",
            "name": "ComfyUI",
            "description": "Node-based image generation interface for Stable Diffusion. Runs on port 8188. Automatically deployed with image generation engines.",
            "recommended": False,
            "port": 8188,
        },
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _access_port(engine: str, ui_type: str) -> int:
    """Return the primary access port for a given engine/UI combination."""
    if ui_type == "open-webui":
        return 3000
    if ui_type == "comfyui" or engine == "stable-diffusion":
        return 8188
    if engine == "meme-maker":
        return 8189
    if engine == "vllm":
        return 8000
    if engine == "localai":
        return 8080
    return 11434  # ollama default


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LLMDeployRequest(BaseModel):
    # LLM configuration
    engine: str = "ollama"
    model: str
    ui_type: str = "open-webui"

    # Hardware
    gpu_enabled: bool = False
    gpu_type: Optional[str] = None       # nvidia, amd
    gpu_device_id: Optional[str] = None  # Proxmox PCI device ID

    # OS
    os_variant: str = "ubuntu2404"
    cloud_image_id: Optional[int] = None  # auto-selected if None

    # Infrastructure
    proxmox_host_id: int
    node_id: int
    storage: Optional[str] = None
    network_bridge: Optional[str] = None

    # VM identity & resources
    vm_name: str
    hostname: str
    cpu_sockets: int = 1
    cpu_cores: int
    cpu_type: str = "host"
    memory: int    # MB
    disk_size: int  # GB

    # Network
    ip_address: Optional[str] = None
    gateway: Optional[str] = None
    netmask: Optional[str] = None
    dns_servers: Optional[str] = None

    # Credentials
    username: str
    password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/catalog")
def get_llm_catalog():
    """Return the full LLM engine / model / OS / UI catalog."""
    return LLM_CATALOG


@router.get("/gpu-devices")
def get_gpu_devices(
    host_id: int,
    node_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return GPU PCI devices available for passthrough on a given Proxmox node."""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")

    node = (
        db.query(ProxmoxNode)
        .filter(ProxmoxNode.id == node_id, ProxmoxNode.host_id == host_id)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="Proxmox node not found")

    try:
        from app.services.proxmox import ProxmoxService

        service = ProxmoxService(host)
        try:
            pci_devices = service.proxmox.nodes(node.node_name).hardware.pci.get()
        except Exception as e:
            logger.warning(f"Could not query PCI devices on {node.node_name}: {e}")
            return {"devices": []}

        gpu_devices = []
        for device in pci_devices:
            device_class = str(device.get("class", ""))
            device_name = (device.get("device_name") or device.get("subsystem_device_name") or "")
            vendor_name = device.get("vendor_name") or ""

            is_gpu = (
                device_class.startswith("0x030")
                or "GeForce" in device_name
                or "Radeon" in device_name
                or "NVIDIA" in vendor_name
                or "AMD" in vendor_name
                or "GPU" in device_name.upper()
            )

            if not is_gpu:
                continue

            if "NVIDIA" in vendor_name.upper() or "NVIDIA" in device_name.upper():
                gpu_type = "nvidia"
            elif "AMD" in vendor_name.upper() or "Radeon" in device_name:
                gpu_type = "amd"
            else:
                gpu_type = "other"

            gpu_devices.append(
                {
                    "id": device.get("id"),
                    "name": f"{vendor_name} {device_name}".strip(),
                    "vendor": vendor_name,
                    "type": gpu_type,
                    "iommugroup": device.get("iommugroup"),
                }
            )

        return {"devices": gpu_devices}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GPU device query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query GPU devices: {e}")


@router.post("/deploy", status_code=status.HTTP_201_CREATED)
async def deploy_llm(
    deploy_data: LLMDeployRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Deploy a new LLM inference VM using the wizard configuration."""

    # --- Validate selections against catalog ---
    valid_engines = [e["id"] for e in LLM_CATALOG["engines"]]
    if deploy_data.engine not in valid_engines:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid engine. Choose one of: {valid_engines}",
        )

    valid_models = [m["id"] for m in LLM_CATALOG["models"].get(deploy_data.engine, [])]
    if deploy_data.model not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{deploy_data.model}' for engine '{deploy_data.engine}'.",
        )

    valid_ui = [u["id"] for u in LLM_CATALOG["ui_options"]]
    if deploy_data.ui_type not in valid_ui:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UI type. Choose one of: {valid_ui}",
        )

    # --- Resolve cloud image ---
    cloud_image_id = deploy_data.cloud_image_id
    if not cloud_image_id:
        os_opt = next(
            (o for o in LLM_CATALOG["os_options"] if o["id"] == deploy_data.os_variant),
            None,
        )
        search_terms = os_opt["search_terms"] if os_opt else ["ubuntu"]
        for term in search_terms:
            img = (
                db.query(CloudImage)
                .filter(
                    CloudImage.is_downloaded == True,
                    CloudImage.name.ilike(f"%{term}%"),
                )
                .first()
            )
            if img:
                cloud_image_id = img.id
                break

        if not cloud_image_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No downloaded cloud image found for OS variant '{deploy_data.os_variant}'. "
                    "Please download an appropriate Ubuntu cloud image first."
                ),
            )

    # --- Build LLM cloud-init extras ---
    llm_cloud_init = LLMCloudInitService.generate_cloud_init_config(
        engine=deploy_data.engine,
        model=deploy_data.model,
        ui_type=deploy_data.ui_type,
        gpu_enabled=deploy_data.gpu_enabled,
        gpu_type=deploy_data.gpu_type or "none",
    )

    # --- Machine type: q35 + UEFI for GPU passthrough ---
    machine_type = "q35" if deploy_data.gpu_enabled else "pc"
    bios_type = "ovmf" if deploy_data.gpu_enabled else "seabios"

    description = (
        f"LLM: {deploy_data.model} | Engine: {deploy_data.engine} | UI: {deploy_data.ui_type}"
    )
    if deploy_data.gpu_enabled:
        description += f" | GPU: {deploy_data.gpu_type or 'passthrough'}"
    tags = f"llm;{deploy_data.engine};ai"

    # --- Create VirtualMachine record ---
    new_vm = VirtualMachine(
        name=deploy_data.vm_name,
        hostname=deploy_data.hostname,
        proxmox_host_id=deploy_data.proxmox_host_id,
        node_id=deploy_data.node_id,
        cloud_image_id=cloud_image_id,
        os_type=OSType.UBUNTU,
        cpu_sockets=deploy_data.cpu_sockets,
        cpu_cores=deploy_data.cpu_cores,
        cpu_type=deploy_data.cpu_type,
        memory=deploy_data.memory,
        disk_size=deploy_data.disk_size,
        storage=deploy_data.storage,
        bios_type=bios_type,
        machine_type=machine_type,
        vga_type="std",
        boot_order="cdn",
        onboot=True,
        kvm=True,
        acpi=True,
        agent_enabled=True,
        description=description,
        tags=tags,
        network_bridge=deploy_data.network_bridge,
        ip_address=deploy_data.ip_address,
        gateway=deploy_data.gateway,
        netmask=deploy_data.netmask,
        dns_servers=deploy_data.dns_servers,
        username=deploy_data.username,
        password=encrypt_data(deploy_data.password),
        status=VMStatus.CREATING,
        cloud_init_config=llm_cloud_init,
        created_by=current_user.id,
    )
    db.add(new_vm)
    db.flush()

    # --- Create LLMDeployment record ---
    llm_dep = LLMDeployment(
        vm_id=new_vm.id,
        engine=deploy_data.engine,
        model=deploy_data.model,
        ui_type=deploy_data.ui_type,
        gpu_enabled=deploy_data.gpu_enabled,
        gpu_type=deploy_data.gpu_type,
        gpu_device_id=deploy_data.gpu_device_id,
        os_variant=deploy_data.os_variant,
        created_by=current_user.id,
    )
    db.add(llm_dep)
    db.commit()
    db.refresh(new_vm)
    db.refresh(llm_dep)

    # --- Queue background deployment ---
    background_tasks.add_task(
        _deploy_llm_background,
        vm_id=new_vm.id,
        llm_dep_id=llm_dep.id,
        gpu_enabled=deploy_data.gpu_enabled,
        gpu_device_id=deploy_data.gpu_device_id,
    )

    # Build access URL for response
    ip = deploy_data.ip_address or "YOUR_VM_IP"
    port = _access_port(deploy_data.engine, deploy_data.ui_type)
    access_url = f"http://{ip}:{port}"

    return {
        "id": llm_dep.id,
        "vm_id": new_vm.id,
        "engine": deploy_data.engine,
        "model": deploy_data.model,
        "ui_type": deploy_data.ui_type,
        "gpu_enabled": deploy_data.gpu_enabled,
        "status": "creating",
        "access_url": access_url,
        "created_at": llm_dep.created_at.isoformat(),
        "message": (
            f"LLM deployment started. The VM will automatically install "
            f"{deploy_data.model} on first boot. Check /var/log/llm-setup.log "
            f"inside the VM for progress."
        ),
    }


def _deploy_llm_background(
    vm_id: int,
    llm_dep_id: int,
    gpu_enabled: bool,
    gpu_device_id: Optional[str],
):
    """Background task: run the standard Linux deployment, then attach GPU if requested."""
    from app.core.database import SessionLocal
    from app.services.deployment import DeploymentService

    task_db = SessionLocal()
    try:
        vm = task_db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
        if not vm:
            logger.error(f"LLM VM {vm_id} not found in background task")
            return

        svc = DeploymentService(task_db)
        svc.deploy_linux_vm(vm_id)

        # Attach GPU passthrough device after VM is created (before or after start)
        if gpu_enabled and gpu_device_id:
            try:
                vm = task_db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
                if vm and vm.vmid:
                    host = (
                        task_db.query(ProxmoxHost)
                        .filter(ProxmoxHost.id == vm.proxmox_host_id)
                        .first()
                    )
                    node = (
                        task_db.query(ProxmoxNode)
                        .filter(ProxmoxNode.id == vm.node_id)
                        .first()
                    )
                    if host and node:
                        from app.services.proxmox import ProxmoxService

                        px = ProxmoxService(host)
                        px.proxmox.nodes(node.node_name).qemu(vm.vmid).config.put(
                            hostpci0=f"{gpu_device_id},pcie=1,x-vga=1"
                        )
                        logger.info(
                            f"GPU passthrough device {gpu_device_id} attached to VM {vm.vmid}"
                        )
            except Exception as gpu_err:
                logger.error(f"GPU passthrough setup failed for VM {vm_id}: {gpu_err}")

    except Exception as e:
        logger.error(f"LLM VM deployment background task failed: {e}")
        vm = task_db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
        if vm:
            vm.status = VMStatus.ERROR
            vm.error_message = str(e)
            task_db.commit()
    finally:
        task_db.close()


@router.get("/deployments")
def list_llm_deployments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all LLM deployments."""
    deps = (
        db.query(LLMDeployment)
        .order_by(LLMDeployment.created_at.desc())
        .all()
    )
    result = []
    for dep in deps:
        vm = db.query(VirtualMachine).filter(VirtualMachine.id == dep.vm_id).first()
        ip = vm.ip_address if vm else None
        port = _access_port(dep.engine, dep.ui_type)
        access_url = f"http://{ip}:{port}" if ip else None

        result.append(
            {
                "id": dep.id,
                "vm_id": dep.vm_id,
                "vm_name": vm.name if vm else "Unknown",
                "engine": dep.engine,
                "model": dep.model,
                "ui_type": dep.ui_type,
                "gpu_enabled": dep.gpu_enabled,
                "gpu_type": dep.gpu_type,
                "status": vm.status.value if vm else "unknown",
                "ip_address": ip,
                "access_url": access_url,
                "created_at": dep.created_at.isoformat(),
            }
        )
    return result


@router.get("/deployments/{dep_id}")
def get_llm_deployment(
    dep_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single LLM deployment."""
    dep = db.query(LLMDeployment).filter(LLMDeployment.id == dep_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="LLM deployment not found")

    vm = db.query(VirtualMachine).filter(VirtualMachine.id == dep.vm_id).first()
    ip = vm.ip_address if vm else None
    port = _access_port(dep.engine, dep.ui_type)
    access_url = f"http://{ip}:{port}" if ip else None

    return {
        "id": dep.id,
        "vm_id": dep.vm_id,
        "vm_name": vm.name if vm else "Unknown",
        "engine": dep.engine,
        "model": dep.model,
        "ui_type": dep.ui_type,
        "gpu_enabled": dep.gpu_enabled,
        "gpu_type": dep.gpu_type,
        "gpu_device_id": dep.gpu_device_id,
        "os_variant": dep.os_variant,
        "status": vm.status.value if vm else "unknown",
        "status_message": vm.status_message if vm else None,
        "ip_address": ip,
        "access_url": access_url,
        "created_at": dep.created_at.isoformat(),
    }


@router.post("/ai-tune/{vm_id}")
async def ai_tune_vm(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Run AI performance tuning diagnostics on an LLM VM"""
    import paramiko
    from app.models import VirtualMachine

    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    if not vm.ip_address:
        raise HTTPException(
            status_code=400,
            detail="VM has no IP address — open SSH credentials and set the IP first",
        )

    # Decrypt password
    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm.ip_address, username=vm.username, password=password, timeout=30)

        def run(cmd):
            try:
                _, stdout, _ = client.exec_command(cmd, timeout=20)
                out = stdout.read().decode("utf-8", errors="replace").strip()
                stdout.channel.recv_exit_status()
                return out or "N/A"
            except Exception:
                return "N/A"

        diag = {
            "gpu": run("nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>/dev/null || echo 'no_gpu'"),
            "ram": run("free -h 2>/dev/null | grep Mem || echo 'N/A'"),
            "cpu": run("nproc 2>/dev/null; grep 'model name' /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2"),
            "model_service": run("systemctl list-units 2>/dev/null | grep -E 'ollama|llama|vllm|localai|comfyui' | head -5 || echo 'none'"),
            "ollama_models": run("ollama list 2>/dev/null | tail -n +2 || echo 'N/A'"),
            "comfyui_installed": run("[ -d /opt/comfyui ] && echo yes || echo no"),
            "ollama_installed": run("which ollama 2>/dev/null && echo yes || echo no"),
            # State checks — skip actions already applied / not applicable
            "comfyui_lowvram_set": run(
                "grep -q -- '--lowvram' /etc/systemd/system/comfyui.service 2>/dev/null && echo yes || echo no"
            ),
            # --lowvram is mutually exclusive with --cpu in ComfyUI's arg parser;
            # never offer it on CPU-only deployments
            "comfyui_cpu_mode": run(
                "grep -q -- '--cpu' /etc/systemd/system/comfyui.service 2>/dev/null && echo yes || echo no"
            ),
            "xformers_installed": run(
                "(/opt/comfyui/venv/bin/pip show xformers 2>/dev/null || pip3 show xformers 2>/dev/null) | grep -q 'Name: xformers' && echo yes || echo no"
            ),
            "ollama_perf_set": run(
                "grep -q 'OLLAMA_NUM_PARALLEL' /etc/systemd/system/ollama.service 2>/dev/null && echo yes || echo no"
            ),
        }
        client.close()

        rec_data = _generate_ai_tune_recommendations(diag)
        return {
            "diagnostics": diag,
            "recommendations": rec_data["text"],
            "actions": rec_data["actions"],
            "status": "complete",
        }

    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="SSH authentication failed — check credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI tune failed: {str(e)}")


# Pre-approved tuning actions (SSH commands run server-side)
_TUNE_ACTIONS = {
    "ollama_perf_env": {
        "label": "Apply Ollama performance settings",
        "description": "Adds OLLAMA_NUM_PARALLEL=2 and OLLAMA_MAX_LOADED_MODELS=1 to the Ollama systemd service, then restarts Ollama",
        "commands": [
            "grep -q 'OLLAMA_NUM_PARALLEL' /etc/systemd/system/ollama.service || "
            "sed -i '/^\\[Service\\]/a Environment=\"OLLAMA_NUM_PARALLEL=2\"' /etc/systemd/system/ollama.service",
            "grep -q 'OLLAMA_MAX_LOADED_MODELS' /etc/systemd/system/ollama.service || "
            "sed -i '/^\\[Service\\]/a Environment=\"OLLAMA_MAX_LOADED_MODELS=1\"' /etc/systemd/system/ollama.service",
            "systemctl daemon-reload",
            "systemctl restart ollama",
        ],
    },
    "comfyui_lowvram": {
        "label": "Enable ComfyUI low VRAM mode",
        "description": "Adds --lowvram to ComfyUI's ExecStart in systemd and restarts the service (GPU deployments only)",
        "commands": [
            # Guard: --lowvram is mutually exclusive with --cpu in ComfyUI's arg parser.
            # Abort with a clear error if --cpu is present rather than corrupting the service file.
            "grep -q -- '--cpu' /etc/systemd/system/comfyui.service && "
            "{ echo 'ERROR: --lowvram conflicts with --cpu (CPU-only deployment). Skipping.'; exit 1; } || true",
            # Only add if not already present
            "grep -q -- '--lowvram' /etc/systemd/system/comfyui.service || "
            "sed -i '/^ExecStart=/ s/$/ --lowvram/' /etc/systemd/system/comfyui.service",
            "systemctl daemon-reload",
            "systemctl restart comfyui",
        ],
    },
    "install_xformers": {
        "label": "Install xformers (GPU only)",
        "description": "Installs xformers for faster GPU attention operations and restarts ComfyUI. Requires CUDA.",
        "commands": [
            # Prefer ComfyUI venv; fall back to system pip3 with --break-system-packages
            # (required on Ubuntu 24.04+ due to PEP 668 externally-managed-environment)
            "if [ -f /opt/comfyui/venv/bin/pip ]; then"
            " /opt/comfyui/venv/bin/pip install xformers --quiet --timeout 120;"
            " else pip3 install xformers --quiet --break-system-packages --timeout 120; fi",
            "systemctl restart comfyui",
        ],
    },
    "update_nvidia_drivers": {
        "label": "Update NVIDIA drivers",
        "description": "Runs apt-get to upgrade NVIDIA driver packages to the latest available version",
        "commands": [
            "apt-get update -qq",
            "apt-get install --only-upgrade -y 'nvidia-driver-*' 2>/dev/null || "
            "apt-get install --only-upgrade -y 'nvidia-*' 2>/dev/null || "
            "echo 'No NVIDIA packages found to upgrade'",
        ],
    },
}


# ── Apply job store (in-memory, keyed by uuid) ─────────────────────────────
import uuid as _uuid_mod
import threading as _threading
import time as _time

_apply_jobs: dict = {}  # job_id → {status, output, error, created_at}


def _run_apply_job(job_id: str, commands: list, ip: str, username: str, password):
    """Execute tuning commands via SSH, streaming output to the job store."""
    import paramiko, shlex, time as _t
    job = _apply_jobs[job_id]
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=username, password=password, timeout=30)
        # Send SSH keepalives every 30 s so NAT/firewalls don't drop long-running
        # transfers (e.g. ollama pull of a several-GB model).
        client.get_transport().set_keepalive(30)

        for cmd in commands:
            job["output"] += f"$ {cmd}\n"
            stdin, stdout, stderr = client.exec_command(
                f"sudo -S bash -c {shlex.quote(cmd)}"
            )
            if password:
                stdin.write((password + "\n").encode())
                stdin.flush()
                stdin.channel.shutdown_write()
            # Stream raw bytes so we capture \r-terminated progress bars from
            # commands like `ollama pull` without blocking on \n line endings.
            chan = stdout.channel
            while True:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode("utf-8", errors="replace")
                    job["output"] += chunk
                elif chan.exit_status_ready():
                    # Drain any remaining buffered output
                    while chan.recv_ready():
                        chunk = chan.recv(8192).decode("utf-8", errors="replace")
                        job["output"] += chunk
                    break
                else:
                    _t.sleep(0.3)
            # Read stderr (safe after stdout channel is fully drained)
            err_bytes = b""
            while stderr.channel.recv_stderr_ready():
                err_bytes += stderr.channel.recv_stderr(4096)
            err = err_bytes.decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
            # -1 means the channel closed without a status (connection dropped);
            # treat as a transient failure rather than a hard error
            if exit_code == -1:
                job["output"] += "\n[connection lost or command timed out]\n"
                job["status"] = "failed"
                job["error"] = "SSH channel closed before command finished (connection lost or timeout)"
                client.close()
                return
            # Filter noise from stderr: sudo prompts, pip WARNING lines, blank lines
            real_err = "\n".join(
                l for l in err.splitlines()
                if l.strip()
                and not l.startswith("[sudo]")
                and "password for" not in l.lower()
                and not l.startswith("WARNING:")
                and not l.startswith("DEPRECATION:")
            )
            if exit_code != 0 and real_err:
                job["status"] = "failed"
                job["error"] = f"Command failed (exit {exit_code}): {real_err}"
                client.close()
                return

        client.close()
        job["status"] = "completed"

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


def _cleanup_apply_jobs():
    """Drop completed/failed jobs older than 10 minutes."""
    cutoff = _time.time() - 600
    stale = [jid for jid, j in list(_apply_jobs.items())
             if j.get("created_at", 0) < cutoff and j["status"] != "running"]
    for jid in stale:
        _apply_jobs.pop(jid, None)


@router.post("/ai-tune/{vm_id}/apply")
async def apply_ai_tune_action(
    vm_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Start a tuning action in a background thread; returns job_id for polling."""
    action_id = body.get("action_id")
    if action_id not in _TUNE_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action_id}'")

    from app.models import VirtualMachine
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if not vm.ip_address:
        raise HTTPException(status_code=400, detail="VM has no IP address — set SSH credentials first")

    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password

    _cleanup_apply_jobs()
    job_id = str(_uuid_mod.uuid4())
    _apply_jobs[job_id] = {
        "status": "running",
        "output": "",
        "error": None,
        "action": _TUNE_ACTIONS[action_id]["label"],
        "created_at": _time.time(),
    }
    t = _threading.Thread(
        target=_run_apply_job,
        args=(job_id, _TUNE_ACTIONS[action_id]["commands"], vm.ip_address, vm.username, password),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "started"}


@router.get("/ai-tune/{vm_id}/apply/{job_id}")
async def get_apply_job_status(
    vm_id: int,
    job_id: str,
    current_user: User = Depends(require_operator),
):
    """Poll for apply-action progress."""
    job = _apply_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return job


# ---------------------------------------------------------------------------
# Ollama Model Manager
# ---------------------------------------------------------------------------

OLLAMA_CATALOG = [
    # CPU-friendly (Q4_K_M / Q5_K_S — runs on 8-16 GB RAM, no GPU needed)
    {"id": "llama3.2:1b", "name": "Llama 3.2 1B  (CPU, ~0.8 GB)", "size": "~0.8 GB", "tier": "CPU"},
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B  (CPU, ~2.0 GB)", "size": "~2.0 GB", "tier": "CPU"},
    {"id": "phi3:mini", "name": "Phi-3 Mini 3.8B  (CPU, ~2.2 GB)", "size": "~2.2 GB", "tier": "CPU"},
    {"id": "deepseek-r1:7b", "name": "DeepSeek R1 7B  (CPU, ~4.7 GB)", "size": "~4.7 GB", "tier": "CPU"},
    {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B  (CPU, ~4.7 GB)", "size": "~4.7 GB", "tier": "CPU"},
    {"id": "mistral:7b-instruct-q4_K_M", "name": "Mistral 7B Instruct Q4  (CPU, ~4.1 GB)", "size": "~4.1 GB", "tier": "CPU"},
    {"id": "nous-hermes2", "name": "Nous Hermes 2 10.7B  (CPU*, ~6.1 GB)", "size": "~6.1 GB", "tier": "CPU"},
    # GPU 8-12 GB VRAM
    {"id": "llama3.1:8b", "name": "Llama 3.1 8B  (GPU 8-12 GB, ~4.7 GB)", "size": "~4.7 GB", "tier": "GPU 8-12 GB"},
    {"id": "mistral:7b", "name": "Mistral 7B  (GPU 8-12 GB, ~4.1 GB)", "size": "~4.1 GB", "tier": "GPU 8-12 GB"},
    {"id": "deepseek-r1:8b", "name": "DeepSeek R1 8B  (GPU 8-12 GB, ~4.9 GB)", "size": "~4.9 GB", "tier": "GPU 8-12 GB"},
    # GPU 16 GB VRAM
    {"id": "qwen2.5:14b", "name": "Qwen 2.5 14B  (GPU 16 GB, ~9.0 GB)", "size": "~9.0 GB", "tier": "GPU 16 GB"},
    {"id": "llama3.1:8b-q8_0", "name": "Llama 3.1 8B Q8  (GPU 16 GB, ~8.5 GB)", "size": "~8.5 GB", "tier": "GPU 16 GB"},
    # GPU 24 GB VRAM
    {"id": "llama3.1:70b-q4_K_M", "name": "Llama 3.1 70B Q4  (GPU 24 GB, ~40 GB)", "size": "~40 GB", "tier": "GPU 24 GB"},
    {"id": "qwen2.5:32b-q4_K_M", "name": "Qwen 2.5 32B Q4  (GPU 24 GB, ~20 GB)", "size": "~20 GB", "tier": "GPU 24 GB"},
    {"id": "mixtral:8x7b-q4_K_M", "name": "Mixtral 8x7B Q4  (GPU 24 GB, ~26 GB)", "size": "~26 GB", "tier": "GPU 24 GB"},
    # GPU 48 GB+ VRAM
    {"id": "llama3.1:70b", "name": "Llama 3.1 70B  (GPU 48 GB+, ~47 GB)", "size": "~47 GB", "tier": "GPU 48 GB+"},
    {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B  (GPU 48 GB+, ~47 GB)", "size": "~47 GB", "tier": "GPU 48 GB+"},
    {"id": "mixtral:8x22b", "name": "Mixtral 8x22B  (GPU 48 GB+, ~80 GB)", "size": "~80 GB", "tier": "GPU 48 GB+"},
]


@router.get("/ai-tune/{vm_id}/models")
async def get_vm_models(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """List installed Ollama models on a VM."""
    import paramiko
    import re as _re

    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if not vm.ip_address:
        raise HTTPException(status_code=400, detail="VM has no IP address")

    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm.ip_address, username=vm.username, password=password, timeout=30)
        _, stdout, _ = client.exec_command("ollama list 2>/dev/null", timeout=20)
        raw = stdout.read().decode("utf-8", errors="replace")
        stdout.channel.recv_exit_status()
        client.close()

        raw = _re.sub(r'\x1b\[[0-9;]*m', '', raw)
        models = []
        for line in raw.splitlines()[1:]:  # Skip header row
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            # Detect if second column is a hex hash (ID column present)
            if len(parts) >= 2 and _re.match(r'^[0-9a-f]{8,}$', parts[1]):
                size = f"{parts[2]} {parts[3]}" if len(parts) > 3 else (parts[2] if len(parts) > 2 else "")
                modified = " ".join(parts[4:]) if len(parts) > 4 else ""
            elif len(parts) >= 2:
                size = f"{parts[1]} {parts[2]}" if len(parts) > 2 else parts[1]
                modified = " ".join(parts[3:]) if len(parts) > 3 else ""
            else:
                size, modified = "", ""
            models.append({"name": name, "size": size, "modified": modified})

        return {"models": models, "catalog": OLLAMA_CATALOG}

    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="SSH authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {e}")


def _run_pull_job(job_id: str, model: str, ip: str, username: str, password):
    """Launch `ollama pull` as a background process on the VM, then poll the log file.

    Uses short, independent SSH sessions for each poll so NAT timeouts and
    SSH keepalive issues can never stall a large model download.
    """
    import paramiko as _pm, shlex, time as _t, re as _re

    job = _apply_jobs[job_id]
    log_file = f"/tmp/depl0y-pull-{job_id}.log"

    def _ssh_run(cmd, timeout=20):
        c = _pm.SSHClient()
        c.set_missing_host_key_policy(_pm.AutoAddPolicy())
        c.connect(ip, username=username, password=password, timeout=20)
        stdin, stdout, _ = c.exec_command(
            f"sudo -S bash -c {shlex.quote(cmd)}", timeout=timeout
        )
        if password:
            stdin.write((password + "\n").encode())
            stdin.flush()
            stdin.channel.shutdown_write()
        out = stdout.read().decode("utf-8", errors="replace")
        stdout.channel.recv_exit_status()
        c.close()
        return out

    try:
        # Launch the pull as a fire-and-forget background process.
        # We append EXIT:<code> as the last line so polling can detect completion.
        launch_cmd = (
            f"nohup bash -c 'ollama pull {shlex.quote(model)} 2>&1; "
            f"echo \"EXIT:$?\"' > {log_file} 2>&1 &"
        )
        _ssh_run(launch_cmd)
        job["output"] = f"$ ollama pull {model}\n[Pulling in background — reading log...]\n"

        # Poll the log file until the EXIT: marker appears (max 30 minutes)
        for _ in range(600):
            _t.sleep(3)
            try:
                raw = _ssh_run(f"cat {log_file} 2>/dev/null || echo ''")
                # Strip ANSI escape codes
                clean = _re.sub(r'\x1b\[[0-9;]*[mGKHFJA]', '', raw)
                # Collapse \r progress bars — keep the last segment per \r group
                lines = []
                for segment in clean.split('\r'):
                    stripped = segment.strip()
                    if stripped:
                        lines.append(stripped)
                # Deduplicate consecutive identical lines (repeated progress bars)
                deduped = []
                for ln in lines:
                    if not deduped or ln != deduped[-1]:
                        deduped.append(ln)
                job["output"] = f"$ ollama pull {model}\n" + "\n".join(deduped)

                if "EXIT:" in raw:
                    m = _re.search(r'EXIT:(\d+)', raw)
                    exit_code = int(m.group(1)) if m else 0
                    if exit_code == 0:
                        job["status"] = "completed"
                    else:
                        job["status"] = "failed"
                        job["error"] = f"ollama pull exited with code {exit_code}"
                    # Best-effort cleanup
                    try:
                        _ssh_run(f"rm -f {log_file}")
                    except Exception:
                        pass
                    return

            except Exception as poll_err:
                job["output"] += f"\n[poll: {poll_err}]\n"

        # Timed out
        job["status"] = "failed"
        job["error"] = "Timed out waiting for model pull (30 minutes)"

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


@router.post("/ai-tune/{vm_id}/models/pull")
async def pull_ollama_model(
    vm_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Start an ollama pull job in background; returns job_id for polling."""
    model = (body.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if not vm.ip_address:
        raise HTTPException(status_code=400, detail="VM has no IP address")

    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password

    _cleanup_apply_jobs()
    job_id = str(_uuid_mod.uuid4())
    _apply_jobs[job_id] = {
        "status": "running",
        "output": "",
        "error": None,
        "action": f"ollama pull {model}",
        "created_at": _time.time(),
    }
    t = _threading.Thread(
        target=_run_pull_job,
        args=(job_id, model, vm.ip_address, vm.username, password),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "started"}


@router.get("/ai-tune/{vm_id}/models/pull/{job_id}")
async def get_pull_job_status(
    vm_id: int,
    job_id: str,
    current_user: User = Depends(require_operator),
):
    """Poll for model pull progress."""
    job = _apply_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return job


@router.delete("/ai-tune/{vm_id}/models/{model_name:path}")
async def delete_ollama_model(
    vm_id: int,
    model_name: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Delete an Ollama model from the VM."""
    import paramiko
    import shlex as _shlex

    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if not vm.ip_address:
        raise HTTPException(status_code=400, detail="VM has no IP address")

    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm.ip_address, username=vm.username, password=password, timeout=30)
        cmd = f"ollama rm {_shlex.quote(model_name)}"
        stdin, stdout, stderr = client.exec_command(
            f"sudo -S bash -c {_shlex.quote(cmd)}", timeout=30
        )
        if password:
            stdin.write((password + "\n").encode())
            stdin.flush()
            stdin.channel.shutdown_write()
        stdout.channel.recv_exit_status()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        client.close()
        # Filter sudo prompt noise
        real_err = "\n".join(
            l for l in err.splitlines()
            if l.strip() and not l.startswith("[sudo]") and "password for" not in l.lower()
        )
        if real_err and "deleted" not in real_err.lower() and "not found" not in real_err.lower():
            raise HTTPException(status_code=500, detail=f"Delete failed: {real_err}")
        return {"success": True, "model": model_name}

    except HTTPException:
        raise
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="SSH authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {e}")


# ---------------------------------------------------------------------------
# Conversation Logging
# ---------------------------------------------------------------------------
# The VM runs a lightweight proxy on port 11500 that intercepts Ollama API
# calls and logs them to /var/log/depl0y/conversations.jsonl


def _ssh_run_quick(ip: str, username: str, password: str, cmd: str, timeout: int = 15) -> str:
    """Open a short SSH session, run one command, return stdout."""
    import paramiko as _pm, shlex
    c = _pm.SSHClient()
    c.set_missing_host_key_policy(_pm.AutoAddPolicy())
    c.connect(ip, username=username, password=password, timeout=15)
    stdin, stdout, _ = c.exec_command(
        f"sudo -S bash -c {shlex.quote(cmd)}", timeout=timeout
    )
    if password:
        stdin.write((password + "\n").encode())
        stdin.flush()
        stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    stdout.channel.recv_exit_status()
    c.close()
    return out


def _get_vm_creds(vm_id: int, db) -> tuple:
    """Return (vm, ip, username, password) or raise HTTPException."""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if not vm.ip_address:
        raise HTTPException(status_code=400, detail="VM has no IP address")
    password = None
    if vm.password:
        try:
            from app.core.security import decrypt_data
            password = decrypt_data(vm.password)
        except Exception:
            password = vm.password
    return vm, vm.ip_address, vm.username, password


@router.get("/ai-tune/{vm_id}/conv-logs")
async def get_conv_logs(
    vm_id: int,
    limit: int = 50,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Return recent conversation log entries from the VM."""
    import json as _json
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        raw = _ssh_run_quick(
            ip, username, password,
            f"tail -n {limit} /var/log/depl0y/conversations.jsonl 2>/dev/null || echo ''"
        )
        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(_json.loads(line))
                except Exception:
                    pass
        return {"entries": entries}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


@router.get("/ai-tune/{vm_id}/conv-logs/status")
async def get_conv_logger_status(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Check whether the conversation logger proxy is installed and running."""
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        status = _ssh_run_quick(
            ip, username, password,
            "systemctl is-active depl0y-logger 2>/dev/null || echo inactive"
        ).strip()
        installed = _ssh_run_quick(
            ip, username, password,
            "[ -f /opt/depl0y-logger/logger.py ] && echo yes || echo no"
        ).strip()
        log_size = _ssh_run_quick(
            ip, username, password,
            "wc -l /var/log/depl0y/conversations.jsonl 2>/dev/null | awk '{print $1}' || echo 0"
        ).strip()
        return {
            "installed": installed == "yes",
            "active": status == "active",
            "status": status,
            "log_entries": int(log_size) if log_size.isdigit() else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check logger status: {e}")


@router.post("/ai-tune/{vm_id}/conv-logs/install")
async def install_conv_logger(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Install/update the conversation logger proxy on the VM via background job."""
    import json as _json
    vm, ip, username, password = _get_vm_creds(vm_id, db)

    # The logger is a simple Python proxy: listens on 11500, forwards to Ollama
    # on 11434, logs every /api/chat and /api/generate call to JSONL
    logger_src = r'''#!/usr/bin/env python3
"""depl0y Conversation Logger
Transparent proxy: port 11500 -> Ollama port 11434.
Logs every /api/chat and /api/generate request+response pair to JSONL.
"""
import http.server, urllib.request, urllib.error, json, time, os, threading

LOG_FILE  = "/var/log/depl0y/conversations.jsonl"
OLLAMA    = "http://127.0.0.1:11434"
LISTEN    = 11500
_log_lock = threading.Lock()

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def _log(entry: dict):
    with _log_lock:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence access log

    def _forward(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        target = OLLAMA + self.path
        req = urllib.request.Request(
            target, data=body or None, method=self.command,
            headers={k: v for k, v in self.headers.items()
                     if k.lower() not in ("host", "content-length")},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
                return body, resp_body, resp.status
        except urllib.error.HTTPError as e:
            rb = e.read()
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(rb)
            return body, rb, e.code
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            msg = str(e).encode()
            self.wfile.write(msg)
            return body, msg, 502

    def do_GET(self):
        self._forward()

    def do_POST(self):
        req_body, resp_body, status = self._forward()
        if self.path.startswith(("/api/chat", "/api/generate")):
            try:
                req_json  = json.loads(req_body)  if req_body  else {}
                resp_json = json.loads(resp_body) if resp_body else {}
                model     = req_json.get("model", "")
                messages  = req_json.get("messages") or []
                prompt    = req_json.get("prompt", "")
                if messages:
                    user_text = next(
                        (m.get("content","") for m in reversed(messages) if m.get("role") == "user"), ""
                    )
                    assistant_text = resp_json.get("message", {}).get("content", "")
                else:
                    user_text      = prompt
                    assistant_text = resp_json.get("response", "")
                _log({
                    "ts":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "model":     model,
                    "endpoint":  self.path,
                    "user":      user_text[:4000],
                    "assistant": assistant_text[:4000],
                    "status":    status,
                })
            except Exception:
                pass

    def do_DELETE(self): self._forward()
    def do_PUT(self):    self._forward()


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", LISTEN), Handler)
    print(f"depl0y-logger listening on :{LISTEN} -> {OLLAMA}", flush=True)
    server.serve_forever()
'''

    install_cmds = [
        "mkdir -p /opt/depl0y-logger /var/log/depl0y",
        # Write logger.py
        f"cat > /opt/depl0y-logger/logger.py << 'LOGGER_EOF'\n{logger_src}\nLOGGER_EOF",
        "chmod +x /opt/depl0y-logger/logger.py",
        # Systemd service
        """cat > /etc/systemd/system/depl0y-logger.service << 'SVC_EOF'
[Unit]
Description=depl0y Conversation Logger Proxy
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/depl0y-logger/logger.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVC_EOF""",
        "systemctl daemon-reload",
        "systemctl enable depl0y-logger",
        "systemctl restart depl0y-logger",
    ]

    _cleanup_apply_jobs()
    job_id = str(_uuid_mod.uuid4())
    _apply_jobs[job_id] = {
        "status": "running",
        "output": "",
        "error": None,
        "action": "Install conversation logger",
        "created_at": _time.time(),
    }
    t = _threading.Thread(
        target=_run_apply_job,
        args=(job_id, install_cmds, ip, username, password),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "started"}


@router.delete("/ai-tune/{vm_id}/conv-logs")
async def clear_conv_logs(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Clear the conversation log file on the VM."""
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        _ssh_run_quick(
            ip, username, password,
            "truncate -s 0 /var/log/depl0y/conversations.jsonl 2>/dev/null || true"
        )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {e}")


# ---------------------------------------------------------------------------
# RAG (Retrieval-Augmented Generation)
# ---------------------------------------------------------------------------

RAG_CATALOG = [
    {"id": "nomic-embed-text", "name": "Nomic Embed Text (recommended)", "size": "~274 MB"},
    {"id": "mxbai-embed-large", "name": "mxbai-embed-large", "size": "~669 MB"},
    {"id": "all-minilm", "name": "all-minilm (small/fast)", "size": "~46 MB"},
]


@router.get("/ai-tune/{vm_id}/rag/status")
async def get_rag_status(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Check whether the RAG service is installed and return document count."""
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        installed = _ssh_run_quick(
            ip, username, password,
            "[ -f /opt/depl0y-rag/rag.py ] && echo yes || echo no"
        ).strip()
        active = _ssh_run_quick(
            ip, username, password,
            "systemctl is-active depl0y-rag 2>/dev/null || echo inactive"
        ).strip()
        doc_count = _ssh_run_quick(
            ip, username, password,
            "[ -d /var/lib/depl0y/rag-docs ] && ls /var/lib/depl0y/rag-docs | wc -l || echo 0"
        ).strip()
        return {
            "installed": installed == "yes",
            "active": active == "active",
            "status": active,
            "doc_count": int(doc_count) if doc_count.isdigit() else 0,
            "catalog": RAG_CATALOG,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check RAG status: {e}")


@router.post("/ai-tune/{vm_id}/rag/install")
async def install_rag(
    vm_id: int,
    body: dict = Body(default={}),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Install ChromaDB + embedding model for RAG on the VM."""
    import base64 as _b64
    embed_model = (body.get("embed_model") or "nomic-embed-text").strip()
    vm, ip, username, password = _get_vm_creds(vm_id, db)

    # RAG service script — use base64 encoding to avoid heredoc quoting issues
    rag_py = (
        "#!/usr/bin/env python3\n"
        "# depl0y RAG Service — REST API on port 11501\n"
        "import sys, json, os, hashlib\n"
        "sys.path.insert(0, '/opt/depl0y-rag-env/lib/python3.12/site-packages')\n"
        "import chromadb, urllib.request\n"
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        "\n"
        "DB_PATH = '/var/lib/depl0y/rag-chroma'\n"
        "OLLAMA  = 'http://127.0.0.1:11434'\n"
        "PORT    = 11501\n"
        "EMBED_MODEL = os.environ.get('EMBED_MODEL', 'nomic-embed-text')\n"
        "_client     = chromadb.PersistentClient(path=DB_PATH)\n"
        "_collection = _client.get_or_create_collection('depl0y-rag')\n"
        "\n"
        "def _embed(text):\n"
        "    payload = json.dumps({'model': EMBED_MODEL, 'prompt': text}).encode()\n"
        "    req = urllib.request.Request(OLLAMA + '/api/embeddings', data=payload,\n"
        "                                 headers={'Content-Type': 'application/json'})\n"
        "    with urllib.request.urlopen(req, timeout=60) as r:\n"
        "        return json.loads(r.read())['embedding']\n"
        "\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def log_message(self, *a): pass\n"
        "    def _body(self):\n"
        "        n = int(self.headers.get('Content-Length', 0))\n"
        "        return json.loads(self.rfile.read(n)) if n else {}\n"
        "    def _reply(self, data, code=200):\n"
        "        body = json.dumps(data).encode()\n"
        "        self.send_response(code)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        "        self.send_header('Content-Length', str(len(body)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(body)\n"
        "    def do_GET(self):\n"
        "        if self.path == '/docs':\n"
        "            res = _collection.get()\n"
        "            docs = [{'id': i, 'source': m.get('source',''), 'preview': d[:120]}\n"
        "                    for i, d, m in zip(res['ids'], res['documents'], res['metadatas'])]\n"
        "            self._reply({'docs': docs, 'count': len(docs)})\n"
        "        else:\n"
        "            self._reply({'error': 'not found'}, 404)\n"
        "    def do_POST(self):\n"
        "        b = self._body()\n"
        "        if self.path == '/ingest':\n"
        "            text = b.get('text', ''); source = b.get('source', 'unknown')\n"
        "            if not text: return self._reply({'error': 'text required'}, 400)\n"
        "            doc_id = hashlib.md5((source + text[:64]).encode()).hexdigest()\n"
        "            emb = _embed(text)\n"
        "            _collection.upsert(ids=[doc_id], documents=[text], embeddings=[emb],\n"
        "                               metadatas=[{'source': source, **b.get('metadata', {})}])\n"
        "            self._reply({'id': doc_id, 'source': source})\n"
        "        elif self.path == '/query':\n"
        "            query = b.get('query', ''); n = int(b.get('n_results', 5))\n"
        "            if not query: return self._reply({'error': 'query required'}, 400)\n"
        "            emb = _embed(query)\n"
        "            res = _collection.query(query_embeddings=[emb], n_results=n)\n"
        "            results = [{'id': i, 'text': d, 'source': m.get('source',''), 'distance': dist}\n"
        "                       for i, d, m, dist in zip(res['ids'][0], res['documents'][0],\n"
        "                                               res['metadatas'][0], res['distances'][0])]\n"
        "            self._reply({'results': results})\n"
        "        else:\n"
        "            self._reply({'error': 'not found'}, 404)\n"
        "    def do_DELETE(self):\n"
        "        if self.path.startswith('/docs/'):\n"
        "            _collection.delete(ids=[self.path[6:]])\n"
        "            self._reply({'deleted': self.path[6:]})\n"
        "        else:\n"
        "            self._reply({'error': 'not found'}, 404)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(f'depl0y-rag listening :{PORT}', flush=True)\n"
        "    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()\n"
    )
    rag_b64 = _b64.b64encode(rag_py.encode()).decode()

    svc_content = (
        "[Unit]\n"
        "Description=depl0y RAG Service\n"
        "After=network.target ollama.service\n\n"
        "[Service]\n"
        "Type=simple\nUser=root\n"
        f"Environment=EMBED_MODEL={embed_model}\n"
        "ExecStart=/usr/bin/python3 /opt/depl0y-rag/rag.py\n"
        "Restart=on-failure\nRestartSec=5\n"
        "StandardOutput=journal\nStandardError=journal\n\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )
    svc_b64 = _b64.b64encode(svc_content.encode()).decode()

    install_cmds = [
        "mkdir -p /opt/depl0y-rag /var/lib/depl0y/rag-docs /var/lib/depl0y/rag-chroma",
        "python3 -m venv /opt/depl0y-rag-env 2>/dev/null || true",
        "/opt/depl0y-rag-env/bin/pip install --upgrade pip --quiet",
        "/opt/depl0y-rag-env/bin/pip install chromadb --quiet",
        f"OLLAMA_MODELS=/usr/share/ollama/.ollama/models ollama pull {embed_model}",
        f"echo '{rag_b64}' | base64 -d > /opt/depl0y-rag/rag.py",
        "chmod +x /opt/depl0y-rag/rag.py",
        f"echo '{svc_b64}' | base64 -d > /etc/systemd/system/depl0y-rag.service",
        "systemctl daemon-reload",
        "systemctl enable depl0y-rag",
        "systemctl restart depl0y-rag",
    ]

    _cleanup_apply_jobs()
    job_id = str(_uuid_mod.uuid4())
    _apply_jobs[job_id] = {
        "status": "running",
        "output": "",
        "error": None,
        "action": f"Install RAG service (embed model: {embed_model})",
        "created_at": _time.time(),
    }
    t = _threading.Thread(
        target=_run_apply_job,
        args=(job_id, install_cmds, ip, username, password),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "started"}


@router.post("/ai-tune/{vm_id}/rag/ingest")
async def rag_ingest(
    vm_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Ingest a text document into the VM's RAG knowledge base."""
    import urllib.request as _ur, urllib.error as _ue
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    payload = {
        "text": body.get("text", ""),
        "source": body.get("source", "manual"),
        "metadata": body.get("metadata", {}),
    }
    if not payload["text"]:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        req = _ur.Request(
            f"http://{ip}:11501/ingest",
            data=__import__("json").dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with _ur.urlopen(req, timeout=60) as r:
            return __import__("json").loads(r.read())
    except _ue.URLError as e:
        raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-tune/{vm_id}/rag/query")
async def rag_query(
    vm_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Query the VM's RAG knowledge base."""
    import urllib.request as _ur, urllib.error as _ue
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    payload = {"query": body.get("query", ""), "n_results": body.get("n_results", 5)}
    if not payload["query"]:
        raise HTTPException(status_code=400, detail="query is required")
    try:
        req = _ur.Request(
            f"http://{ip}:11501/query",
            data=__import__("json").dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with _ur.urlopen(req, timeout=60) as r:
            return __import__("json").loads(r.read())
    except _ue.URLError as e:
        raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-tune/{vm_id}/rag/docs")
async def rag_list_docs(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """List documents in the VM's RAG knowledge base."""
    import urllib.request as _ur, urllib.error as _ue
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        with _ur.urlopen(f"http://{ip}:11501/docs", timeout=10) as r:
            return __import__("json").loads(r.read())
    except _ue.URLError as e:
        raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/ai-tune/{vm_id}/rag/docs/{doc_id}")
async def rag_delete_doc(
    vm_id: int,
    doc_id: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Delete a document from the VM's RAG knowledge base."""
    import urllib.request as _ur, urllib.error as _ue
    vm, ip, username, password = _get_vm_creds(vm_id, db)
    try:
        req = _ur.Request(f"http://{ip}:11501/docs/{doc_id}", method="DELETE")
        with _ur.urlopen(req, timeout=10) as r:
            return __import__("json").loads(r.read())
    except _ue.URLError as e:
        raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_ai_tune_recommendations(diag: dict) -> dict:
    """Return both a human-readable text summary and structured applicable actions."""
    recs = []
    actions = []
    gpu = diag.get("gpu", "")
    model_service = diag.get("model_service", "")
    ollama_models = diag.get("ollama_models", "")

    has_gpu = not ("no_gpu" in gpu or gpu in ("N/A", ""))
    # Detect via running service OR installed binary/directory
    has_ollama = (
        "ollama" in model_service.lower()
        or "ollama" in ollama_models.lower()
        or diag.get("ollama_installed") == "yes"
    )
    has_comfyui = (
        "comfyui" in model_service.lower()
        or diag.get("comfyui_installed") == "yes"
    )

    if not has_gpu:
        recs += [
            "CPU-only inference detected.",
            "• Use quantized GGUF models (Q4_K_M or Q5_K_S) to reduce RAM and maximise CPU throughput.",
            "• Set num_thread in Ollama to match your vCPU count for best single-request performance.",
        ]
    else:
        recs += [
            f"GPU detected: {gpu}",
            "• Verify VRAM offloading: run `ollama ps` and confirm layers are on GPU.",
        ]
        actions.append({**_TUNE_ACTIONS["update_nvidia_drivers"], "id": "update_nvidia_drivers"})

    if has_ollama:
        ollama_perf_set = diag.get("ollama_perf_set") == "yes"
        if not ollama_perf_set:
            recs += [
                "",
                "Ollama tuning:",
                "  OLLAMA_NUM_PARALLEL=2      # allow 2 concurrent requests",
                "  OLLAMA_MAX_LOADED_MODELS=1 # prevent VRAM fragmentation",
                "  Apply via: systemctl daemon-reload && systemctl restart ollama",
            ]
            actions.append({**_TUNE_ACTIONS["ollama_perf_env"], "id": "ollama_perf_env"})
        else:
            recs += ["", "Ollama: performance env vars already applied. ✓"]

    if has_comfyui:
        cpu_mode = diag.get("comfyui_cpu_mode") == "yes"
        lowvram_set = diag.get("comfyui_lowvram_set") == "yes"
        xformers_ok = diag.get("xformers_installed") == "yes"
        comfyui_recs = []
        # --lowvram is mutually exclusive with --cpu; only suggest it for GPU deployments
        if cpu_mode:
            comfyui_recs.append("• Running in CPU mode (--cpu) — --lowvram is not applicable here.")
        elif not lowvram_set:
            comfyui_recs.append("• Low VRAM mode: add --lowvram to ExecStart in /etc/systemd/system/comfyui.service")
            actions.append({**_TUNE_ACTIONS["comfyui_lowvram"], "id": "comfyui_lowvram"})
        else:
            comfyui_recs.append("• Low VRAM mode: already enabled. ✓")
        # xformers requires CUDA — pointless (and hangs) on CPU-only deployments
        if cpu_mode:
            comfyui_recs.append("• xformers: not applicable in CPU mode (requires CUDA).")
        elif not xformers_ok:
            comfyui_recs.append("• Install xformers for faster attention (GPU only)")
            actions.append({**_TUNE_ACTIONS["install_xformers"], "id": "install_xformers"})
        else:
            comfyui_recs.append("• xformers: already installed. ✓")
        recs += ["", "ComfyUI tuning:"] + comfyui_recs

    if not recs:
        recs.append("No running LLM services detected. Ensure Ollama/llama.cpp/ComfyUI is running.")

    return {"text": "\n".join(recs), "actions": actions}
