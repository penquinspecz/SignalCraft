from __future__ import annotations

from pathlib import Path


def test_wrapper_overlays_exist_with_common_labels() -> None:
    wrappers = {
        "ops/k8s/overlays/eks/kustomization.yaml": "jobintel.io/overlay: eks",
        "ops/k8s/overlays/onprem/kustomization.yaml": "jobintel.io/overlay: onprem",
    }

    for rel_path, label in wrappers.items():
        path = Path(rel_path)
        assert path.exists(), f"missing wrapper overlay: {rel_path}"
        text = path.read_text(encoding="utf-8")
        assert "kind: Kustomization" in text
        assert "resources:" in text
        assert "commonLabels:" in text
        assert label in text
