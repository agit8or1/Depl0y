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
    cpu_cores: int
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
        cpu_sockets=1,
        cpu_cores=deploy_data.cpu_cores,
        cpu_type="host",
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


async def _deploy_llm_background(
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
        "description": "Adds --lowvram to ComfyUI's ExecStart in systemd and restarts the service",
        "commands": [
            # Match any ExecStart= line (not just ones containing 'comfyui')
            "grep -q -- '--lowvram' /etc/systemd/system/comfyui.service || "
            "sed -i '/^ExecStart=/ s/$/ --lowvram/' /etc/systemd/system/comfyui.service",
            "systemctl daemon-reload",
            "systemctl restart comfyui",
        ],
    },
    "install_xformers": {
        "label": "Install xformers",
        "description": "Installs xformers for faster attention operations and restarts ComfyUI",
        "commands": [
            # Use the ComfyUI venv pip if it exists, otherwise fall back to pip3
            "/opt/comfyui/venv/bin/pip install xformers --quiet 2>/dev/null || pip3 install xformers --quiet",
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


@router.post("/ai-tune/{vm_id}/apply")
async def apply_ai_tune_action(
    vm_id: int,
    body: dict = Body(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Execute a pre-approved tuning action on an LLM VM via SSH"""
    import paramiko

    action_id = body.get("action_id")
    if action_id not in _TUNE_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action_id}'")

    action = _TUNE_ACTIONS[action_id]

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

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm.ip_address, username=vm.username, password=password, timeout=30)

        import shlex
        outputs = []
        for cmd in action["commands"]:
            # Wrap in bash -c so compound commands (||, &&) all run under sudo
            stdin, stdout, stderr = client.exec_command(f"sudo -S bash -c {shlex.quote(cmd)}")
            if password:
                stdin.write((password + "\n").encode())
                stdin.flush()
                stdin.channel.shutdown_write()
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
            # Filter sudo password prompt from stderr
            real_err = "\n".join(
                l for l in err.splitlines()
                if l.strip() and not l.startswith("[sudo]") and "password for" not in l.lower()
            )
            if exit_code != 0 and real_err:
                client.close()
                raise HTTPException(
                    status_code=500,
                    detail=f"Command failed (exit {exit_code}): {real_err}",
                )
            if out:
                outputs.append(out)

        client.close()
        return {
            "status": "applied",
            "action": action["label"],
            "output": "\n".join(outputs) if outputs else "Done",
        }

    except HTTPException:
        raise
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="SSH authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply failed: {str(e)}")


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
        recs += [
            "",
            "Ollama tuning:",
            "  OLLAMA_NUM_PARALLEL=2      # allow 2 concurrent requests",
            "  OLLAMA_MAX_LOADED_MODELS=1 # prevent VRAM fragmentation",
            "  Apply via: systemctl daemon-reload && systemctl restart ollama",
        ]
        actions.append({**_TUNE_ACTIONS["ollama_perf_env"], "id": "ollama_perf_env"})

    if has_comfyui:
        recs += [
            "",
            "ComfyUI tuning:",
            "• Low VRAM mode: add --lowvram to ExecStart in /etc/systemd/system/comfyui.service",
            "• Install xformers for faster attention: pip install xformers",
        ]
        actions.append({**_TUNE_ACTIONS["comfyui_lowvram"], "id": "comfyui_lowvram"})
        actions.append({**_TUNE_ACTIONS["install_xformers"], "id": "install_xformers"})

    if not recs:
        recs.append("No running LLM services detected. Ensure Ollama/llama.cpp/ComfyUI is running.")

    return {"text": "\n".join(recs), "actions": actions}
