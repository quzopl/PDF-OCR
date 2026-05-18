from app.system_info import get_system_info


def test_system_info_shape():
    info = get_system_info()
    assert info["cpu"]["count"] >= 1
    assert isinstance(info["cpu"]["model"], str)
    assert info["ram"]["total_gb"] > 0
    assert info["ram"]["available_gb"] > 0
    assert "cuda_available" in info["gpu"]
    assert "devices" in info["gpu"]
    assert isinstance(info["gpu"]["devices"], list)
    assert "paddle_gpu_installed" in info["gpu"]
