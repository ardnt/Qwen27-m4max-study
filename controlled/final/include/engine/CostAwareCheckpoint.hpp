#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <span>
#include <vector>

namespace splash::engine::semantic {

// Boundaries are placement hints only. Native token/image identity and complete
// target + draft state still authorize reuse. No approximate semantic reuse.
enum class Kind : uint8_t { LatestUser, EarlierUser, StablePrefix, ToolResult };
struct Hint {
  uint32_t tokens = 0;
  Kind kind = Kind::LatestUser;
};
struct Forecast {
  uint32_t overlap = 0;
  uint32_t suffix = 0;
  double expectedUses = 0.0;
};
struct Costs {
  double bulkRowMs = 3.2;
  double middleRowMs = 3.2;
  double shortRowMs = 3.2;
  double draftRowMs = 0.5;
  double commandMs = 0.0;
  double snapshotMs = 100.0;
  double restoreMs = 100.0;
  double retentionMsPerByte = 0.0;
  double queueInterferenceMs = 0.0;
  // Conservative priors, not measured timings. The engine replaces them with
  // observations; receipts must distinguish initialized and observed values.
};
struct Input {
  uint32_t resume = 0;
  uint32_t replay = 0;
  uint32_t page = 32;
  uint32_t chunk = 2048;
  uint32_t shortRows = 128;
  uint32_t bulkRows = 512;
  uint32_t draftWindow = 2048;
  uint32_t maximumStates = 2;
  uint64_t stateBytes = 0;
  uint64_t maximumBytes = 0;
  double minimumNetGainMs = 1.0;
  bool growthPaused = false;
  // Required rolling recovery/replay captures are preserved. Rolling points
  // affect today's draft work, but are not assumed to survive for a future hit.
  std::vector<uint32_t> required;
  std::vector<Hint> hints;
  std::vector<Forecast> forecast;
  Costs costs;
};
enum class Reason : uint8_t { Selected, NotWorthwhile, MemoryBudget, Pressure, Invalid };
struct Result {
  std::vector<uint32_t> selected;
  Reason reason = Reason::NotWorthwhile;
  double baselineMs = 0.0;
  double plannedMs = 0.0;
  double expectedSavedMs = 0.0;
  double additionalCaptureMs = 0.0;
  uint64_t retainedBytes = 0;
  uint64_t baselineDraftRows = 0;
  uint64_t plannedDraftRows = 0;
  uint32_t candidateCount = 0;
  uint32_t transitions = 0;
};

inline bool finiteNonnegative(double value) noexcept {
  return std::isfinite(value) && value >= 0.0;
}
inline bool valid(const Input &in) noexcept {
  const Costs &c = in.costs;
  if (!in.page || !in.chunk || !in.draftWindow || !in.stateBytes ||
      in.resume > in.replay || in.resume % in.page || in.replay % in.page ||
      in.shortRows >= in.bulkRows || in.bulkRows > in.chunk || in.maximumStates > 8 ||
      in.hints.size() > 64 || in.forecast.size() > 66 || in.required.size() > 256 ||
      !finiteNonnegative(in.minimumNetGainMs)) return false;
  for (double v : {c.bulkRowMs, c.middleRowMs, c.shortRowMs, c.draftRowMs, c.commandMs,
                   c.snapshotMs, c.restoreMs, c.retentionMsPerByte,
                   c.queueInterferenceMs})
    if (!finiteNonnegative(v)) return false;
  if (c.bulkRowMs == 0.0 || c.middleRowMs == 0.0 || c.shortRowMs == 0.0) return false;
  uint32_t previous = in.resume;
  for (uint32_t b : in.required) {
    if (b <= previous || b > in.replay || b % in.page) return false;
    previous = b;
  }
  for (const Forecast &f : in.forecast)
    if (!finiteNonnegative(f.expectedUses) || f.expectedUses > 1000000.0 ||
        uint64_t{f.overlap} + f.suffix > UINT32_MAX) return false;
  return true;
}

// Dispatch lengths, not physical decode lanes. An extra split can push a
// formerly large tail below the ANE threshold or into the register route.
inline double targetCost(const Input &in, uint32_t begin, uint32_t end) noexcept {
  if (end <= begin) return 0.0;
  const uint32_t rows = end - begin;
  const uint32_t full = rows / in.chunk, tail = rows % in.chunk;
  const double tailRate = tail <= in.shortRows ? in.costs.shortRowMs :
                          tail >= in.bulkRows ? in.costs.bulkRowMs : in.costs.middleRowMs;
  return double(full) * (in.costs.commandMs + in.chunk * in.costs.bulkRowMs) +
         (tail ? in.costs.commandMs + tail * tailRate : 0.0);
}
inline uint64_t draftRows(const Input &in, uint32_t begin, uint32_t end) noexcept {
  return std::min(in.draftWindow, end - begin);
}
inline double futureCost(const Input &in, uint32_t resume, const Forecast &f) noexcept {
  if (f.overlap < resume) return 0.0;
  const uint32_t end = f.overlap + f.suffix;
  return targetCost(in, resume, end) +
         in.costs.draftRowMs * draftRows(in, resume, end) +
         (resume ? in.costs.restoreMs : 0.0);
}

// The current prefill includes mandatory recovery snapshots between two
// retained nodes. Its draft windows overlap/continue exactly as planDraftContext
// does: charge min(window, distance), not a fresh full window per checkpoint.
inline double currentSegment(const Input &in, uint32_t begin, uint32_t end,
                             uint64_t *draft = nullptr) noexcept {
  double cost = 0.0;
  uint32_t at = begin;
  uint64_t rows = 0;
  for (uint32_t b : in.required) {
    if (b <= begin || b >= end) continue;
    cost += targetCost(in, at, b);
    rows += draftRows(in, at, b);
    at = b;
  }
  cost += targetCost(in, at, end);
  rows += draftRows(in, at, end);
  if (draft) *draft += rows;
  return cost + in.costs.draftRowMs * rows;
}
inline double captureCost(const Input &in, uint32_t at) noexcept {
  const bool alreadyRequired = std::binary_search(in.required.begin(), in.required.end(), at);
  return (alreadyRequired ? 0.0 : in.costs.snapshotMs + in.costs.queueInterferenceMs) +
         in.stateBytes * in.costs.retentionMsPerByte;
}
inline double futureInterval(const Input &in, uint32_t begin, uint32_t end) noexcept {
  double cost = 0.0;
  for (const Forecast &f : in.forecast)
    if (f.overlap >= begin && f.overlap < end)
      cost += f.expectedUses * futureCost(in, begin, f);
  return cost;
}
inline double evaluate(const Input &in, std::span<const uint32_t> selected,
                       uint64_t *draft = nullptr) noexcept {
  uint32_t at = in.resume;
  double score = 0.0;
  for (uint32_t b : selected) {
    score += currentSegment(in, at, b, draft) + futureInterval(in, at, b) + captureCost(in, b);
    at = b;
  }
  return score + currentSegment(in, at, in.replay, draft) + futureInterval(in, at, in.replay);
}

// A shortest path through ordinary retained checkpoints. Each overlap outcome
// is charged once to its deepest reusable predecessor. State-count and byte
// budgets constrain the path. Required progress captures stay on every edge.
// O(N^2 K + N^2 (M+F)), bounded N <= 64, K <= 8. The selection is optimal only
// under this cost/forecast model; actual cache retention is still a confounder.
inline Result plan(const Input &in) {
  Result out;
  if (!valid(in)) { out.reason = Reason::Invalid; return out; }
  out.baselineMs = evaluate(in, {}, &out.baselineDraftRows);
  if (!std::isfinite(out.baselineMs)) { out = {}; out.reason = Reason::Invalid; return out; }
  out.plannedMs = out.baselineMs;
  out.plannedDraftRows = out.baselineDraftRows;
  if (in.growthPaused) { out.reason = Reason::Pressure; return out; }
  const uint32_t budget = static_cast<uint32_t>(std::min<uint64_t>(
      in.maximumStates, in.maximumBytes / in.stateBytes));
  if (!budget) { out.reason = Reason::MemoryBudget; return out; }
  if (std::none_of(in.forecast.begin(), in.forecast.end(), [&](const Forecast &f) {
        return f.expectedUses > 0.0 && f.overlap >= in.resume && f.overlap < in.replay;
      })) return out;
  std::vector<uint32_t> positions{in.resume};
  for (const Hint &hint : in.hints) {
    const uint32_t b = hint.tokens / in.page * in.page;
    if (b > in.resume && b < in.replay) positions.push_back(b);
  }
  std::sort(positions.begin(), positions.end());
  positions.erase(std::unique(positions.begin(), positions.end()), positions.end());
  out.candidateCount = static_cast<uint32_t>(positions.size() - 1);
  positions.push_back(in.replay);
  const size_t n = positions.size(), terminal = n - 1;
  std::vector<double> edge(n * n, 0.0);
  for (size_t i = 0; i < terminal; ++i)
    for (size_t j = i + 1; j < n; ++j)
      edge[i*n+j] = currentSegment(in, positions[i], positions[j]) +
                    futureInterval(in, positions[i], positions[j]) +
                    (j != terminal ? captureCost(in, positions[j]) : 0.0);
  const double infinity = std::numeric_limits<double>::infinity();
  std::vector<double> score((budget + 1) * n, infinity);
  std::vector<size_t> previous(score.size(), n);
  score[0] = 0.0;
  double best = out.baselineMs;
  size_t last = 0;
  uint32_t bestCount = 0;
  for (uint32_t count = 0; count <= budget; ++count) {
    for (size_t i = 0; i < terminal; ++i) {
      const double prefix = score[count*n+i];
      if (!std::isfinite(prefix)) continue;
      const double total = prefix + edge[i*n+terminal];
      if (total < best - 1e-9) { best = total; last = i; bestCount = count; }
      if (count == budget) continue;
      for (size_t j = i + 1; j < terminal; ++j) {
        ++out.transitions;
        const double candidate = prefix + edge[i*n+j];
        const size_t index = (count+1)*n+j;
        if (candidate < score[index] - 1e-9) {
          score[index] = candidate;
          previous[index] = i;
        }
      }
    }
  }
  if (!std::isfinite(best) || out.baselineMs - best < in.minimumNetGainMs) return out;
  for (uint32_t count = bestCount; count; --count) {
    out.selected.push_back(positions[last]);
    last = previous[count*n+last];
  }
  std::reverse(out.selected.begin(), out.selected.end());
  out.plannedDraftRows = 0;
  out.plannedMs = evaluate(in, out.selected, &out.plannedDraftRows);
  out.expectedSavedMs = out.baselineMs - out.plannedMs;
  const double oldNow = currentSegment(in, in.resume, in.replay);
  uint32_t at = in.resume;
  double newNow = 0.0;
  for (uint32_t b : out.selected) {
    newNow += currentSegment(in, at, b) + captureCost(in, b);
    at = b;
  }
  newNow += currentSegment(in, at, in.replay);
  out.additionalCaptureMs = newNow - oldNow;
  out.retainedBytes = out.selected.size() * in.stateBytes;
  out.reason = out.selected.empty() ? Reason::NotWorthwhile : Reason::Selected;
  return out;
}

} // namespace splash::engine::semantic
