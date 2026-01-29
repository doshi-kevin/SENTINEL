"""
GPU Check Script for SENTINEL-Z Phase 2
Verifies CUDA availability and GPU specifications
"""

import sys

print("=" * 50)
print("SENTINEL-Z GPU Verification")
print("=" * 50)

# Check PyTorch
try:
    import torch
    print(f"\n[OK] PyTorch Version: {torch.__version__}")
except ImportError:
    print("[FAIL] PyTorch not installed!")
    sys.exit(1)

# Check CUDA
print(f"\n--- CUDA Status ---")
print(f"CUDA Available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"cuDNN Version: {torch.backends.cudnn.version()}")
    print(f"GPU Count: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"\n--- GPU {i}: {props.name} ---")
        print(f"  Compute Capability: {props.major}.{props.minor}")
        print(f"  Total Memory: {props.total_memory / 1024**3:.2f} GB")
        print(f"  Multi-Processor Count: {props.multi_processor_count}")
    
    # Quick tensor test
    print("\n--- Quick GPU Test ---")
    x = torch.randn(1000, 1000).cuda()
    y = torch.randn(1000, 1000).cuda()
    z = torch.matmul(x, y)
    print(f"[OK] GPU computation test passed! (1000x1000 matrix multiply)")
    print(f"  Result tensor device: {z.device}")
    
    # Memory check
    print(f"\n--- GPU Memory ---")
    print(f"  Allocated: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
    print(f"  Cached: {torch.cuda.memory_reserved() / 1024**2:.2f} MB")
    
    print("\n" + "=" * 50)
    print("[SUCCESS] GPU is READY for Phase 2 training!")
    print("=" * 50)
else:
    print("\n[FAIL] CUDA is NOT available.")
    print("  PyTorch may be CPU-only version.")
    print("  To install CUDA version, run:")
    print("  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")

# Check PyTorch Geometric
print("\n--- PyTorch Geometric Status ---")
try:
    import torch_geometric
    print(f"[OK] PyTorch Geometric Version: {torch_geometric.__version__}")
except ImportError:
    print("[MISSING] PyTorch Geometric not installed (needed for GNN training)")
    print("  Will install: pip install torch-geometric")
