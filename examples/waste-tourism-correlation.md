# Worked Example: Does Tourism Drive Waste in the Balearic Islands?

A step-by-step walkthrough showing how an LLM uses ibestat-mcp to answer a real analytical question — from discovery to insight — without the user knowing a single dataset ID or API endpoint.

## The question

> "Is there a correlation between tourist arrivals and waste generation in the Balearic Islands?"

This is the kind of question a journalist, policy analyst, or researcher might ask. It requires finding two unrelated datasets, extracting comparable time series, and cross-referencing them. With the raw API, this means navigating IBESTAT's catalog, understanding JSON-stat responses, and manually aligning dimensions. With ibestat-mcp, the LLM does all of that through a guided conversation.

## Step 1: Discover the right topic

The LLM starts by browsing IBESTAT's thematic catalog.

**Tool call:** `browse_topics`

This returns 52 statistical categories. The LLM identifies "Territori i medi ambient" (Territory and Environment) as the most relevant domain for waste data.

## Step 2: Find the waste dataset

**Tool call:** `list_datasets_by_topic` with topic "Territori i medi ambient"

The LLM scans the results and finds a subcategory "Residus" (Waste), which contains:

- **`000238A_000078`** — *Residus urbans recollits per capita (kg/hab)* (Urban waste collected per capita)

This is exactly what we need: per-capita waste figures that are already normalized for population.

## Step 3: Find the tourism dataset

The LLM already knows tourism is a major IBESTAT domain. A quick search surfaces the key dataset:

**Tool call:** `search_datasets` with query "turistes Illes Balears"

Result:

- **`000058A_000001`** — *Turistes amb destinacio principal les Illes Balears* (Tourists whose main destination is the Balearic Islands)

Monthly and annual data, broken down by country of origin.

## Step 4: Inspect both datasets

**Tool calls:** `get_dataset_info` for each dataset

The LLM discovers:
- The waste dataset has dimensions for territory and time period (annual, 2010-2021)
- The tourism dataset has dimensions for time period, origin, and frequency (monthly and annual)

Both share a time dimension with overlapping years — they can be cross-referenced.

## Step 5: Retrieve the data

**Tool calls:** `get_data` for each dataset, filtered to the overlapping period

The waste dataset returns per-capita kg for the Balearic Islands. The tourism dataset returns total arrivals (annual aggregates).

## Step 6: Cross-reference and analyze

The LLM aligns the two time series for 2016-2021:

| Year | Waste (kg/capita) | Tourists (millions) |
|------|-------------------|---------------------|
| 2016 | 753.5 | 15.32 |
| 2017 | 766.0 | 16.28 |
| 2018 | 828.8 | 16.55 |
| 2019 | 757.9 | 16.48 |
| 2020 | 568.3 | 3.11 |
| 2021 | 605.0 | 8.68 |

## The insight

The correlation is striking:

- **2018**: Peak tourism (16.55M visitors) coincides with peak waste generation (828.8 kg/capita) — the highest in the series.
- **2020**: The COVID-19 pandemic collapses tourism by 81% (16.48M to 3.11M). Waste drops 25% in the same year.
- **2021**: Partial tourism recovery (8.68M, +179% vs 2020) tracks a partial waste recovery (605.0 kg/capita, +6.5%).

The pattern is clear: tourist arrivals are a significant driver of per-capita waste in the Balearic Islands. The pandemic created a natural experiment — when tourists stopped coming, waste generation fell sharply, even though the resident population stayed roughly constant.

## What made this possible

This analysis required **zero knowledge of IBESTAT's API**. The user asked a question in plain language. The LLM:

1. **Discovered** relevant datasets through the semantic topic tree (not keyword guessing)
2. **Inspected** dataset structures to understand dimensions and available filters
3. **Retrieved** data with precise filters derived from the metadata
4. **Cross-referenced** two independent datasets by aligning their time dimensions
5. **Synthesized** the findings into a narrative with a clear conclusion

The entire workflow — from question to insight — happened in a single conversation. No API documentation was consulted. No dataset IDs were memorized. No JSON-stat responses were manually parsed.

That is the difference between an API wrapper and an analytical tool.
