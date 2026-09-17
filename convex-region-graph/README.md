# Graph of Convex Regions (2D)

Công cụ này thực hiện task cuối trong slide:

- Mỗi convex region là một vertex.
- Hai region được nối nếu giao của chúng khác rỗng.
- Quan hệ được phân loại thành `overlap`, `shared_edge`, hoặc `point_contact`.
- Mỗi kết nối hình học sinh ra hai directed edges để robot có thể đi hai chiều.
- Kết quả gồm graph JSON, connected components và hình SVG.

Không cần cài thư viện ngoài.

## Chạy demo

```bash
cd convex-region-graph
python build_graph.py example_regions.json --output graph.json --svg graph.svg
```

Mở `graph.svg` bằng trình duyệt hoặc chèn trực tiếp vào slide.

## Định dạng input

```json
{
  "regions": [
    {
      "id": "Q1",
      "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]
    },
    {
      "id": "Q2",
      "polygon": [[2, 0], [4, 0], [4, 2], [2, 2]]
    }
  ]
}
```

Các điểm của polygon có thể theo chiều kim đồng hồ hoặc ngược chiều kim đồng hồ. Điểm đầu không cần lặp lại ở cuối. Mỗi polygon phải lồi và có ít nhất ba điểm.

## Định dạng output

`graph.json` chứa:

- `vertices`: region id, centroid và polygon.
- `undirected_edges`: một record cho mỗi cặp region giao nhau.
- `directed_edges`: hai chiều cho mỗi kết nối.
- `connected_components`: dùng để kiểm tra graph có bị tách rời hay không.

## Dùng với output ACD/VCC

Phần duy nhất cần adapter là chuyển output của repo thành `example_regions.json` theo schema trên. Sau đó graph builder không phụ thuộc ACD hay VCC.

Pseudo-code tích hợp:

```python
regions = run_acd_or_vcc(environment)
json.dump({
    "regions": [
        {"id": f"Q{i}", "polygon": polygon_vertices}
        for i, polygon_vertices in enumerate(regions)
    ]
}, file)
```

## Test

```bash
python -m unittest -v test_build_graph.py
```

Test bao phủ các trường hợp: chung cạnh, chạm tại một điểm, overlap có diện tích, containment, disjoint và tạo cạnh hai chiều.

---

## Part 3: LLM-weighted region planning

Part 3 consumes the existing Graph of Convex Regions (GCR), asks an LLM API to
assign preference costs to the existing directed edges, validates those costs,
and runs Dijkstra's algorithm to produce a region sequence.

> The LLM does not directly generate the robot's continuous trajectory. It
> assigns preference weights to the existing Graph of Convex Regions. A
> deterministic graph-search algorithm then converts those learned preferences
> into a valid region sequence.

The separation is intentional:

```text
GCR + start/goal
        |
        v
Weight Provider ---- general LLM API now / adapted LLM later
        |
        v
validated edge weights (greater than 0.0, up to 1.0)
        |
        v
Dijkstra ---- deterministic valid path selection
        |
        v
route.json ---- input corridor for RRT/RRT*/bi-RRT later
```

Lower weights mean more preferable transitions. The Python planner does not
invent the final scores and does not let the LLM add topology. Only
`directed_edges` are used; `undirected_edges` are ignored.

Part 3 assumes that the Graph of Convex Regions supplied by Part 1 has already
been constructed according to the team's graph definition. Part 3 does not
modify graph topology or special-case relation types. It consumes the supplied
`directed_edges` and asks the LLM to assign traversal preference weights.
Part 3 consumes `directed_edges` exactly as supplied. The legacy demo graph may
still contain older relation types; the final integrated Part 1 output is
responsible for supplying the team's intended topology.

### Input

The planner expects a GCR JSON object containing:

```json
{
  "vertices": [
    {"id": "C0", "centroid": [1.2, 3.4], "polygon": []}
  ],
  "directed_edges": [
    {"source": "C0", "target": "C1", "relation": "shared_edge"}
  ]
}
```

The command line accepts start and goal region IDs. Point-to-region lookup can
be added later without changing the weight provider or Dijkstra modules.

### API configuration

This prototype uses OpenRouter's free API models by default. No OpenAI API
billing is required. The provider calls OpenRouter's OpenAI-compatible Chat
Completions endpoint through Python's standard library, so no external SDK is
required. The request asks for a JSON object, while the existing Python
validation remains authoritative.

Setup:

1. Create an account at `https://openrouter.ai`.
2. Create an API key at `https://openrouter.ai/keys`.
3. Copy the example configuration:

   ```bash
   cp .env.example .env
   ```

   In PowerShell, the equivalent is `Copy-Item .env.example .env`.

4. Put the key in `.env`:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEMPERATURE=0
```

Never commit `.env`; it is included in `.gitignore`. Existing process
environment variables take precedence over `.env` values. The planner depends
on the abstract `LLMWeightProvider`, so another API or a future adapted or
fine-tuned model can be added without modifying validation or graph search.
The CLI uses only the OpenRouter-specific environment variable names, avoiding
accidental reuse of credentials or billing configuration from another API.

The default is OpenRouter's free-model router:

```dotenv
OPENROUTER_MODEL=openrouter/free
```

`OPENROUTER_TEMPERATURE` is parsed as a floating-point value and defaults to
`0.0`. A temperature of zero reduces sampling randomness, but it does not
guarantee identical results when using `openrouter/free`: that router may
select a different currently available free model on a later request. The CLI
prints both the requested model and, when OpenRouter reports it, the actual
resolved model.

The program never silently switches models and never falls back to a paid
model. Free services have lower rate limits, may have higher latency, and their
model availability can change.

The HTTP request explicitly sets `stream: false`, sends `Accept:
application/json`, and retains `response_format: {"type": "json_object"}`.
HTTP-envelope JSON and the JSON string returned inside
`choices[0].message.content` are parsed as separate stages with distinct error
messages.

Malformed or truncated HTTP envelopes, transient network failures, and HTTP
5xx responses are retried at most once. Authentication, rate-limit, model
weight validation, and conflicting-duplicate errors are not retried. If an
HTTP response is malformed, its complete received body is saved to
`outputs/openrouter_invalid_response.txt` together with an error reporting the
status, content type, byte count, parsing failure, and debug path. If a response
unexpectedly uses SSE despite `stream: false`, it is reported clearly rather
than decoded heuristically. Credentials are never written to error messages;
an exact API-key value echoed by an upstream response is redacted in the debug
file.

### Run with the real LLM API

From this directory:

```bash
python llm_planner.py graph.json \
  --start C0 \
  --goal C6 \
  --provider openrouter \
  --weights-output outputs/llm_weights.json \
  --route-output outputs/route.json \
  --svg-output outputs/route.svg
```

The decoded edge weights are saved to `--weights-output` before validation,
together with provider metadata containing the requested model, OpenRouter's
resolved model (or `null`), and the request temperature. The dedicated prompt is in
`prompts/edge_weight_prompt.txt`. Authentication failures, free-tier rate
limits, unavailable models, malformed model JSON, and network errors produce
specific messages. If a specifically configured free model is unavailable, the
error suggests `openrouter/free`; if the free router itself is unavailable, it
suggests retrying later or manually choosing another `:free` model. No paid
model is selected automatically.

For an exactly reproducible demonstration, make the real API call once and
save `outputs/llm_weights.json`, then reuse that same file without another API
call:

```bash
python llm_planner.py graph.json --start C0 --goal C6 --provider openrouter --weights-output outputs/llm_weights.json --route-output outputs/route.json --svg-output outputs/route.svg
python llm_planner.py graph.json --start C0 --goal C6 --weights outputs/llm_weights.json --route-output outputs/route.json --svg-output outputs/route.svg
```

### Run offline with saved or mock weights

Supplying `--weights` skips the API entirely. This is useful for reproducible
development and testing:

```bash
python llm_planner.py graph.json \
  --start C0 \
  --goal C6 \
  --weights examples/mock_llm_weights.json \
  --route-output outputs/route.json \
  --svg-output outputs/route.svg
```

`examples/mock_llm_weights.json` is explicitly synthetic demo data, not a real
API response or expert training data. Saved real API responses also include
top-level provider metadata, which validation safely ignores:

```json
{
  "provider_metadata": {
    "provider": "openrouter",
    "requested_model": "openrouter/free",
    "resolved_model": "actual/model-id",
    "temperature": 0.0
  },
  "edge_weights": [
    {
      "source": "C0",
      "target": "C1",
      "weight": 0.12,
      "reason": "Shared boundary and useful progress toward C6."
    }
  ]
}
```

The optional `reason` is retained only for debugging and explanation. It never
affects path calculation.

### Validation and missing-weight policy

Before search, the planner checks that the response is JSON, every referenced
region exists, every scored pair is an existing supplied directed edge, and
every weight is numeric in `(0, 1]` (strictly greater than zero and less than
or equal to one). Unknown regions, invented edges, conflicting
duplicate scores, and out-of-range values cause a clear error.

If the LLM repeats an edge with the same numeric weight, the first record is
kept, the identical repetition is ignored, and the CLI prints a warning. If it
repeats an edge with a different weight, validation fails instead of averaging,
minimizing, maximizing, or otherwise inventing a decision.

If an otherwise usable response omits individual edges, each missing edge gets
the neutral weight `0.5` and the CLI reports how many defaults were assigned. A
response with no usable edge weights is rejected rather than producing an
all-default route.

### Output and Part 2 integration

`route.json` is deliberately small and machine-readable:

```json
{
  "start_region": "C0",
  "goal_region": "C6",
  "sequence": ["C0", "C1", "C3", "C6"],
  "edges": [
    {"source": "C0", "target": "C1", "weight": 0.12},
    {"source": "C1", "target": "C3", "weight": 0.14},
    {"source": "C3", "target": "C6", "weight": 0.11}
  ],
  "total_cost": 0.37,
  "valid": true
}
```

Every consecutive pair is guaranteed to be a real directed GCR edge. If no
directed path exists, the output has `valid: false`, an empty `sequence`, and a
human-readable reason; no route is fabricated. Part 2 can later consume
`sequence` as a preferred sampling corridor or priority region list for RRT,
RRT*, or bi-RRT. This repository does not implement those sampling planners.

`route.svg` shows polygons, region IDs, centroids, all valid directed edges,
their validated weights, and the selected sequence highlighted in red.

### LLM-guided region-prior mode (primary guidance architecture)

The region-prior workflow is separate from edge weighting and Dijkstra. It
sends the start/goal IDs, every centroid, and directed topology to OpenRouter
and asks for one importance score in `(0, 1]` per graph region:

```bash
python llm_region_prior.py graph.json \
  --start C0 \
  --goal C6 \
  --provider openrouter \
  --output outputs/region_prior.json
```

Unknown IDs, duplicate IDs, booleans/non-numeric values, non-finite values, and
scores outside `(0, 1]` are rejected. A response with no usable scores is also
rejected. If an otherwise usable response omits individual graph regions, each
omitted region receives the documented positive fallback score `0.1` and a
warning. Reasons are retained for explanation only.

For offline development, reuse a saved response with `--response`:

```bash
python llm_region_prior.py graph.json \
  --start C0 --goal C6 \
  --response examples/mock_region_prior.json \
  --output outputs/region_prior.json
```

Merge the validated scores with every graph polygon:

```bash
python export_sampling_prior.py \
  --graph graph.json \
  --prior outputs/region_prior.json \
  --output outputs/sampling_prior.json
```

`sampling_prior.json` is the direct C++ interface. It contains authoritative
start/goal region IDs and all regions in graph order:

```json
{
  "start_region": "C0",
  "goal_region": "C6",
  "regions": [
    {"id": "C0", "score": 0.7, "polygon": [[0, 4], [3, 4], [4, 7], [0, 7]]}
  ]
}
```

The C++ sampler normalizes scores when selecting a region; the values are not
RRT path costs and do not change planner rewiring or collision checking.

### Export the strict Part 2 sampling corridor

The adapter deliberately reads both `graph.json` and `route.json`: the route
owns only the selected IDs, while the graph remains the source of polygon
geometry. It rejects an empty route or any unknown region ID and writes only
the selected polygons, in sequence order:

```bash
python export_sampling_corridor.py \
  --graph graph.json \
  --route outputs/route.json \
  --output outputs/sampling_corridor.json
```

The result has this stable Python/C++ boundary:

```json
{
  "sequence": ["C0", "C1", "C3", "C6"],
  "regions": [
    {"id": "C0", "polygon": [[0.0, 4.0], [3.0, 4.0], [4.0, 7.0], [0.0, 7.0]]}
  ]
}
```

No polygon coordinates are duplicated into `route.json`, and neither LLM
weighting nor Dijkstra is involved in this export step.

### Tests

Run all existing and new tests offline:

```bash
python -m unittest discover -v
```

Tests cover directed-only graph use, edge and region score validation,
region-score fallback behavior, both sampling exporters, provider metadata,
configurable temperature, minimum-cost Dijkstra routing, no-path output, and
mocked HTTP/provider behavior without a real API call.

### Future adapted/fine-tuned LLM

This prototype uses a general-purpose API model and does not claim to be
fine-tuned. Later, good or near-optimal trajectories from RRT/RRT*/bi-RRT can be
mapped to expert region sequences and stored with the corresponding GCR,
start, and goal. Those records can supervise an adapted model that predicts
edge preferences. Real expert trajectories should be collected and evaluated;
the synthetic mock file in this repository must not be presented as training
data. Swapping provider implementations will not require rewriting Dijkstra.
