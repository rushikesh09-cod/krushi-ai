"""
standardization.py

Purpose (in simple language):
------------------------------
Government data entry is done by many different people across many years,
so the same crop or market often appears spelled differently:
  "onion", "ONION", "Onion ", "Onions"  -> should all become "Onion"
  "sangli", "SANGLI ", "Sangli(APMC)"   -> should all become "Sangli"

The list of "correct" crop and market names now lives OUTSIDE this Python
file, in two small config files:
  config/crops.json
  config/markets.json

This means adding a 6th, 7th, 13th crop later is just editing crops.json -
nobody needs to touch this Python file or any other pipeline code.
"""

import json
import os
import pandas as pd

BASE_DIR = os.path.dirname(__file__)
CONFIG_DIR = os.path.join(BASE_DIR, "..", "..", "config")
CROPS_CONFIG_PATH = os.path.join(CONFIG_DIR, "crops.json")
MARKETS_CONFIG_PATH = os.path.join(CONFIG_DIR, "markets.json")


def _load_config(path: str, key: str) -> dict:
    """
    Loads a config file like crops.json and returns two things combined
    into lookup structures: the canonical name list, and a variant->
    canonical lookup dictionary.
    """
    with open(path, "r") as f:
        data = json.load(f)

    canonical_names = []
    variant_lookup = {}
    for entry in data[key]:
        canonical = entry["canonical_name"]
        canonical_names.append(canonical)
        for variant in entry.get("variants", []):
            variant_lookup[variant.strip().lower()] = canonical
        # the canonical name itself should also map to itself
        variant_lookup[canonical.strip().lower()] = canonical

    return {"canonical_names": canonical_names, "variant_lookup": variant_lookup}


_crops_data = _load_config(CROPS_CONFIG_PATH, "crops")
_markets_data = _load_config(MARKETS_CONFIG_PATH, "markets")

CANONICAL_CROPS = _crops_data["canonical_names"]
CROP_NAME_VARIANTS = _crops_data["variant_lookup"]

CANONICAL_MARKETS = _markets_data["canonical_names"]
MARKET_NAME_VARIANTS = _markets_data["variant_lookup"]


def _clean_text_key(value: str) -> str:
    """Lowercase, strip spaces, and remove common junk characters for lookup."""
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("(", " (").replace(")", ") ")
    text = " ".join(text.split())
    return text


def standardize_crop_name(raw_value: str) -> str:
    """
    Converts any messy commodity text into its canonical crop name (from
    crops.json). Returns the original (Title Cased) value unchanged if
    it's not a known crop, so the pipeline can set it aside as unsupported.
    """
    key = _clean_text_key(raw_value)
    if key in CROP_NAME_VARIANTS:
        return CROP_NAME_VARIANTS[key]
    simplified = key.replace(" (apmc)", "").strip()
    if simplified in CROP_NAME_VARIANTS:
        return CROP_NAME_VARIANTS[simplified]
    return str(raw_value).strip().title()


def standardize_market_name(raw_value: str) -> str:
    """
    Converts any messy market text into its canonical market name (from
    markets.json). Returns the original (Title Cased) value unchanged if
    it's not a known market for this project.
    """
    key = _clean_text_key(raw_value)
    if key in MARKET_NAME_VARIANTS:
        return MARKET_NAME_VARIANTS[key]
    simplified = key.replace(" (apmc)", "").strip()
    if simplified in MARKET_NAME_VARIANTS:
        return MARKET_NAME_VARIANTS[simplified]
    return str(raw_value).strip().title()


def standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Applies crop and market standardization to an entire dataframe."""
    df = df.copy()
    df["Commodity"] = df["Commodity"].apply(standardize_crop_name)
    df["Market"] = df["Market"].apply(standardize_market_name)
    return df
