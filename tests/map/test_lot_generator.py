from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_SCRIPTS_DIR = REPO_ROOT / "tools" / "map_gen" / "maps"
GENERATED_DIR = REPO_ROOT / "tools" / "map_gen" / "gen"
EXPECTED_DIR = REPO_ROOT / "src" / "app" / "map" / "map_data"


def _run_generator(script_name: str) -> None:
    script_path = MAP_SCRIPTS_DIR / script_name
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise AssertionError(
            f"Generator failed for {script_name}.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _assert_png_matches_expected(actual_path: Path, expected_path: Path) -> None:
    assert actual_path.exists(), f"Generated image is missing: {actual_path}"
    assert expected_path.exists(), f"Expected baseline image is missing: {expected_path}"

    with Image.open(actual_path) as actual, Image.open(expected_path) as expected:
        assert actual.size == expected.size, (
            f"Image sizes differ for {actual_path.name}: "
            f"generated={actual.size}, expected={expected.size}"
        )

        actual_rgba = actual.convert("RGBA")
        expected_rgba = expected.convert("RGBA")
        diff = ImageChops.difference(actual_rgba, expected_rgba)
        assert diff.getbbox() is None, f"Pixel output differs for {actual_path.name}"


@pytest.fixture(autouse=True)
def clean_generated_outputs() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    for lot_name in ("lot1", "lot2", "lot3"):
        png_path = GENERATED_DIR / f"{lot_name}.png"
        csv_path = GENERATED_DIR / f"{lot_name}.csv"
        if png_path.exists():
            png_path.unlink()
        if csv_path.exists():
            csv_path.unlink()


@pytest.mark.parametrize(
    ("script_name", "lot_name"),
    (
        ("generate_lot_1.py", "lot1"),
        ("generate_lot_2.py", "lot2"),
        ("generate_lot_3.py", "lot3"),
    ),
)
def test_lot_generators_match_expected_png_baselines(script_name: str, lot_name: str) -> None:
    _run_generator(script_name)

    generated_png = GENERATED_DIR / f"{lot_name}.png"
    expected_png = EXPECTED_DIR / f"{lot_name}.png"

    _assert_png_matches_expected(generated_png, expected_png)
