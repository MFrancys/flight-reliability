from __future__ import annotations

from pathlib import Path

import httpx
from tqdm import tqdm

from utils import monthly_zip_name

_BTS_BASE = "https://transtats.bts.gov/PREZIP"
_CHUNK_BYTES = 1 << 17  # 128 KB


def _download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0)) or None
        with dest.open("wb") as file, tqdm(
            desc=dest.name,
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
        ) as bar:
            for chunk in response.iter_bytes(_CHUNK_BYTES):
                file.write(chunk)
                bar.update(len(chunk))


def download_month(year: int, month: int, data_dir: Path) -> Path:
    zip_path = data_dir / monthly_zip_name(year, month)
    if zip_path.exists():
        print(f"Using cached {zip_path.name}")
        return zip_path

    url = f"{_BTS_BASE}/{zip_path.name}"
    print(f"Downloading {zip_path.name} ...")
    tmp = zip_path.with_suffix(".tmp")
    try:
        _download(url, tmp)
        tmp.rename(zip_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return zip_path


def main(data_dir: Path, years: list[int], months: list[int]) -> None:
    data_dir.mkdir(exist_ok=True)
    for year in years:
        for month in months:
            download_month(year, month, data_dir)
    print(f"Raw BTS files ready in {data_dir}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    main(project_root.parent / "data", [2019], [1, 2, 3])
