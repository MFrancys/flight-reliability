from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger
from tqdm import tqdm

from settings import CONFIG, DATA_DIR
from utils import monthly_zip_name


def _download(url: str, dest: Path, chunk_bytes: int) -> None:
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
            for chunk in response.iter_bytes(chunk_bytes):
                file.write(chunk)
                bar.update(len(chunk))


def download_month(year: int, month: int, data_dir: Path, bts_config: dict) -> Path:
    zip_path = data_dir / monthly_zip_name(year, month)
    if zip_path.exists():
        logger.info("Using cached {}", zip_path.name)
        return zip_path

    url = f"{bts_config['base_url']}/{zip_path.name}"
    logger.info("Downloading {} ...", zip_path.name)
    tmp = zip_path.with_suffix(".tmp")
    try:
        _download(url, tmp, int(bts_config["download_chunk_bytes"]))
        tmp.rename(zip_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return zip_path


def main(data_dir: Path, dataset_config: dict, bts_config: dict) -> None:
    data_dir.mkdir(exist_ok=True)
    for year in dataset_config["years"]:
        for month in dataset_config["months"]:
            download_month(year, month, data_dir, bts_config)
    logger.info("Raw BTS files ready in {}", data_dir)


if __name__ == "__main__":
    main(DATA_DIR, CONFIG["dataset"], CONFIG["bts"])
