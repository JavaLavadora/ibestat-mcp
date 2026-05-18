"""MCP prompt definitions for guided IBESTAT data exploration.

Each prompt provides lightweight context to help an LLM navigate IBESTAT's
statistical data catalogue.  Prompts set the scene (what IBESTAT is, what
tools are available, what the user wants) and let the LLM decide the
exact tool sequence.
"""

from __future__ import annotations


def explore_topic(topic: str, language: str = "ca") -> str:
    """Seed a full exploration of an IBESTAT statistical topic."""
    return (
        f"The user wants to explore '{topic}' data from IBESTAT, "
        f"the official statistics office of the Balearic Islands "
        f"(Mallorca, Menorca, Ibiza, Formentera). IBESTAT publishes "
        f"~3,700 datasets across 52 thematic categories covering "
        f"demographics, economy, tourism, labour, and more. "
        f"Use language='{language}' for all tool calls. "
        f"Available tools: browse_topics (thematic catalogue), "
        f"list_datasets_by_topic (datasets under a category), "
        f"search_datasets (keyword search), get_dataset_info "
        f"(dimensions and codelist references), get_codelist "
        f"(hierarchical code values), and get_data "
        f"(fetch observations with filters)."
    )


def query_dataset(dataset_id: str, language: str = "ca") -> str:
    """Seed a conversation for querying a known dataset."""
    return (
        f"The user wants to query IBESTAT dataset '{dataset_id}'. "
        f"Use language='{language}' for all tool calls. "
        f"Start by inspecting the dataset with get_dataset_info to see its "
        f"dimensions and available codelist references. Use get_codelist to "
        f"explore hierarchical filter values (e.g., geographic or temporal "
        f"codes). Then use get_data with appropriate filters to fetch the "
        f"observations the user needs."
    )


def compare_municipalities(
    topic: str,
    municipalities: str | None = None,
    language: str = "ca",
) -> str:
    """Seed a comparison of data across Balearic municipalities."""
    municipalities_note = (
        f"The user is interested in comparing: {municipalities}. "
        if municipalities
        else (
            "The user hasn't specified which municipalities "
            "yet -- help them choose. "
        )
    )
    return (
        f"The user wants to compare '{topic}' data across municipalities in "
        f"the Balearic Islands. {municipalities_note}"
        f"IBESTAT geographic codelists follow a hierarchy: "
        f"autonomous community > island > municipality. Use get_codelist with "
        f"the TERRITORIO dimension's codelist_id (typically CL_AREA_ES53) to "
        f"resolve municipality names to numeric codes. "
        f"Use language='{language}' for all tool calls."
    )


def time_series(
    topic: str,
    years: str | None = None,
    language: str = "ca",
) -> str:
    """Seed a trend analysis over time for an IBESTAT topic."""
    years_note = (
        f"The user wants data for the period {years}. "
        if years
        else (
            "The user hasn't specified a time range "
            "-- help them discover what's available. "
        )
    )
    return (
        f"The user wants to see trends over time for '{topic}' data from "
        f"IBESTAT, the Balearic Islands statistics office. {years_note}"
        f"Most IBESTAT datasets include a TIME_PERIOD dimension with yearly "
        f"codes (e.g., '2020', '2024'). Use get_dataset_info to see available "
        f"time periods, then filter get_data by TIME_PERIOD to fetch the "
        f"relevant observations. Use language='{language}' for all tool calls."
    )


def discover_available_data(language: str = "ca") -> str:
    """Onboarding prompt for first-time users of IBESTAT data."""
    return (
        f"The user wants to discover what data is available from IBESTAT, "
        f"the official statistics office of the Balearic Islands (Mallorca, "
        f"Menorca, Ibiza, Formentera). IBESTAT publishes approximately 3,700 "
        f"datasets organised into 52 thematic categories including "
        f"demographics, economy, tourism, labour market, education, health, "
        f"environment, and more. "
        f"Start with browse_topics to show the full thematic catalogue, then "
        f"help the user narrow down to a topic of interest. "
        f"Use language='{language}' for all tool calls."
    )
