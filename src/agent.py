"""
AI-powered apartment analysis agent using PydanticAI + Anthropic Claude.

Usage:
    python src/agent.py                     # uses data/apparts.csv by default
    python src/agent.py --data path/to.csv  # custom data path

Environment:
    ANTHROPIC_API_KEY   Required — your Anthropic API key
    KAJIN_AI_MODEL      Optional — override model (default: claude-sonnet-4-6)
"""

import os
import json
import argparse
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage

# ─── Configuration ────────────────────────────────────────────────────────────

_MODEL = os.environ.get("KAJIN_AI_MODEL", "claude-sonnet-4-6")

_SYSTEM_PROMPT = """\
You are an expert French real estate analyst helping users find and evaluate \
rental apartments from Jinka listings.

Your key responsibilities:
- Analyze apartment data using the available tools
- Compare prices, locations, and value metrics
- Highlight the best deals (lowest price/m² for the given criteria)
- Note rent reductions (rent_evolution < 0 means the landlord lowered the price)

IMPORTANT — Ask for clarification when the user's request is ambiguous:
- If no budget is mentioned for a search, ask for their maximum rent
- If no location preference is given and the dataset has multiple cities, ask which city
- If no apartment size/room count is specified for recommendations, ask what they need
- Keep clarification questions short and specific — one question at a time

When presenting results:
- Lead with the most actionable insight (e.g. "The 5 best value apartments are…")
- Express price/m² in €/m² rounded to one decimal
- Mention metro access when available — it matters a lot in French cities
- If the user asks something you cannot answer with the available tools, say so clearly
"""

# ─── Dependencies ─────────────────────────────────────────────────────────────


@dataclass
class Deps:
    csv_path: str


# ─── Tool input models ────────────────────────────────────────────────────────


class ApartmentFilter(BaseModel):
    """Criteria for filtering apartments. All fields are optional."""

    max_rent: Optional[float] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    max_price_m2: Optional[float] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    city: Optional[str] = None
    metro_line: Optional[str] = None
    metro_station: Optional[str] = None


# ─── Agent ────────────────────────────────────────────────────────────────────

agent = Agent(
    f"anthropic:{_MODEL}",
    system_prompt=_SYSTEM_PROMPT,
    deps_type=Deps,
    retries=2,
)

# ─── Internal helpers ─────────────────────────────────────────────────────────

_DISPLAY_COLS = [
    "rent", "area", "price_m2", "city", "room",
    "metro_stations", "metro_lines", "link", "rent_evolution",
]


def _load(csv_path: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    if not os.path.exists(csv_path):
        return None, (
            f"No apartment data found at '{csv_path}'. "
            "Run the main application first to fetch listings."
        )
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8", index_col="id")
    return df, None


def _pick_cols(df: pd.DataFrame, extras: list[str] = []) -> list[str]:
    wanted = _DISPLAY_COLS + extras
    return [c for c in wanted if c in df.columns]


def _df_to_json(df: pd.DataFrame, **meta) -> str:
    records = df.reset_index()[["id"] + _pick_cols(df)].to_dict(orient="records")
    return json.dumps({**meta, "apartments": records}, ensure_ascii=False, default=str)


# ─── Tools ────────────────────────────────────────────────────────────────────


@agent.tool
def load_apartments_summary(ctx: RunContext[Deps]) -> str:
    """
    Return a high-level overview of the dataset: total count, average rent/area/price_m²,
    breakdown by city, room count, and listing source.
    Call this first to understand what data is available before filtering.
    """
    df, err = _load(ctx.deps.csv_path)
    if err:
        return err

    summary: dict = {"total_listings": len(df)}

    for col in ("rent", "area", "price_m2"):
        if col in df.columns:
            s = df[col].dropna()
            summary[f"avg_{col}"] = round(float(s.mean()), 2)

    if "city" in df.columns:
        summary["cities"] = df["city"].value_counts().to_dict()
    if "room" in df.columns:
        summary["room_distribution"] = df["room"].value_counts().to_dict()
    if "source" in df.columns:
        summary["sources"] = df["source"].value_counts().to_dict()

    return json.dumps(summary, ensure_ascii=False)


@agent.tool
def get_market_stats(
    ctx: RunContext[Deps],
    city: Optional[str] = None,
    rooms: Optional[int] = None,
) -> str:
    """
    Return detailed price statistics (mean, median, min, max) for rent, area, and price/m².
    Optionally filter by city and/or number of rooms to get segment-specific stats.
    """
    df, err = _load(ctx.deps.csv_path)
    if err:
        return err

    if city:
        df = df[df["city"].str.lower().str.contains(city.lower(), na=False)]
    if rooms is not None and "room" in df.columns:
        df = df[df["room"] == rooms]

    if df.empty:
        return json.dumps({"error": "No apartments match those filters.", "city": city, "rooms": rooms})

    result: dict = {"filters": {"city": city, "rooms": rooms}, "count": len(df)}
    for col in ("rent", "area", "price_m2"):
        if col in df.columns:
            s = df[col].dropna()
            result[col] = {
                "mean": round(float(s.mean()), 2),
                "median": round(float(s.median()), 2),
                "min": round(float(s.min()), 2),
                "max": round(float(s.max()), 2),
                "std": round(float(s.std()), 2),
            }
    if "room" in df.columns:
        result["room_distribution"] = df["room"].value_counts().to_dict()

    return json.dumps(result, ensure_ascii=False)


@agent.tool
def filter_apartments(
    ctx: RunContext[Deps],
    filters: ApartmentFilter,
    sort_by: str = "price_m2",
    top_n: int = 10,
) -> str:
    """
    Filter apartments by rent, area, price/m², rooms, city, metro line or metro station.
    Returns up to top_n results sorted by sort_by ('price_m2', 'rent', or 'area').
    Use this when the user specifies concrete search criteria.
    """
    df, err = _load(ctx.deps.csv_path)
    if err:
        return err

    mask = pd.Series(True, index=df.index)

    if filters.max_rent and "rent" in df.columns:
        mask &= df["rent"] <= filters.max_rent
    if filters.min_area and "area" in df.columns:
        mask &= df["area"] >= filters.min_area
    if filters.max_area and "area" in df.columns:
        mask &= df["area"] <= filters.max_area
    if filters.max_price_m2 and "price_m2" in df.columns:
        mask &= df["price_m2"] <= filters.max_price_m2
    if filters.min_rooms and "room" in df.columns:
        mask &= df["room"] >= filters.min_rooms
    if filters.max_rooms and "room" in df.columns:
        mask &= df["room"] <= filters.max_rooms
    if filters.city and "city" in df.columns:
        mask &= df["city"].str.lower().str.contains(filters.city.lower(), na=False)
    if filters.metro_line and "metro_lines" in df.columns:
        mask &= df["metro_lines"].str.contains(filters.metro_line, na=False)
    if filters.metro_station and "metro_stations" in df.columns:
        mask &= df["metro_stations"].str.contains(filters.metro_station, case=False, na=False)

    df = df[mask]
    if df.empty:
        return json.dumps({"matched": 0, "message": "No apartments match your filters."})

    sort_col = sort_by if sort_by in df.columns else "price_m2"
    top = df.sort_values(sort_col).head(top_n)

    return _df_to_json(top, matched=int(len(df)), showing=len(top), sorted_by=sort_col)


@agent.tool
def rank_best_value(
    ctx: RunContext[Deps],
    top_n: int = 10,
    city: Optional[str] = None,
    max_rent: Optional[float] = None,
) -> str:
    """
    Return the top N apartments with the best value — i.e. the lowest price per m².
    Optionally restrict by city and/or a maximum monthly rent.
    Use this when the user asks for 'best deals', 'best value', or 'top picks'.
    """
    df, err = _load(ctx.deps.csv_path)
    if err:
        return err

    if city and "city" in df.columns:
        df = df[df["city"].str.lower().str.contains(city.lower(), na=False)]
    if max_rent and "rent" in df.columns:
        df = df[df["rent"] <= max_rent]

    if df.empty or "price_m2" not in df.columns:
        return json.dumps({"error": "Insufficient data after applying filters."})

    top = df.sort_values("price_m2").head(top_n)
    return _df_to_json(top, ranking="best value (price/m² ascending)", count=len(top))


@agent.tool
def compare_cities(ctx: RunContext[Deps]) -> str:
    """
    Compare average rent and price/m² across all cities in the dataset.
    Useful when the user is deciding between locations.
    """
    df, err = _load(ctx.deps.csv_path)
    if err:
        return err

    if "city" not in df.columns:
        return json.dumps({"error": "No city data available."})

    agg: dict = {}
    for col in ("rent", "area", "price_m2"):
        if col in df.columns:
            agg[col] = ["mean", "median", "count"]

    if not agg:
        return json.dumps({"error": "No numeric columns available for comparison."})

    grouped = df.groupby("city").agg(agg).round(2)
    grouped.columns = ["_".join(c) for c in grouped.columns]
    result = grouped.reset_index().to_dict(orient="records")
    return json.dumps({"city_comparison": result}, ensure_ascii=False, default=str)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def run_interactive(csv_path: str) -> None:
    print("\nKajin AI Apartment Analyst")
    print("=" * 52)
    print(f"Model : {_MODEL}")
    print(f"Data  : {csv_path}")
    print("=" * 52)
    print("Ask me anything about your apartment listings.")
    print("I'll ask for clarification when your request is unclear.")
    print("Type 'exit' to quit.\n")

    history: list[ModelMessage] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        try:
            result = agent.run_sync(
                user_input,
                deps=Deps(csv_path=csv_path),
                message_history=history,
            )
            print(f"\nAgent: {result.output}\n")
            history = result.all_messages()
        except Exception as exc:
            print(f"\n[Error] {exc}\n")


if __name__ == "__main__":
    _root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    _default_csv = os.path.join(_root, "data", "apparts.csv")

    _parser = argparse.ArgumentParser(description="AI-powered apartment analysis")
    _parser.add_argument(
        "--data",
        default=_default_csv,
        help="Path to apartments CSV (default: data/apparts.csv)",
    )
    _args = _parser.parse_args()

    run_interactive(os.path.normpath(_args.data))
