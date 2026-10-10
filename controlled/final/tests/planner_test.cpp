#include "engine/CostAwareCheckpoint.hpp"
#include "vendor/DraftContextPlan.hpp"

#include <cassert>
#include <chrono>
#include <iostream>
#include <random>

using namespace splash::engine::semantic;

// Brute force is an independent subset oracle. It evaluates all future
// overlap outcomes directly and delegates draft capture to upstream's planner.
double oracle(const Input &in, const std::vector<uint32_t> &kept) {
  std::vector<uint32_t> captures = in.required;
  captures.insert(captures.end(), kept.begin(), kept.end());
  captures.push_back(in.replay);
  std::sort(captures.begin(), captures.end());
  captures.erase(std::unique(captures.begin(), captures.end()), captures.end());
  const auto draft = splash::planDraftContext(in.resume, in.replay, captures);
  uint64_t rows = 0;
  for (const auto &span : draft.captureSpans) rows += span.end - span.begin;
  double cost = rows * in.costs.draftRowMs;
  uint32_t start = in.resume;
  for (uint32_t stop : captures) {
    uint32_t distance = stop - start;
    while (distance) {
      const uint32_t chunk = std::min(distance, in.chunk);
      cost += in.costs.commandMs + chunk *
        (chunk >= in.bulkRows ? in.costs.bulkRowMs : chunk <= in.shortRows ? in.costs.shortRowMs : in.costs.middleRowMs);
      distance -= chunk;
    }
    start = stop;
  }
  for (uint32_t b : kept) {
    if (std::find(in.required.begin(), in.required.end(), b) == in.required.end())
      cost += in.costs.snapshotMs + in.costs.queueInterferenceMs;
    cost += in.stateBytes * in.costs.retentionMsPerByte;
  }
  for (const auto &f : in.forecast) {
    if (f.overlap < in.resume || f.overlap >= in.replay) continue;
    uint32_t best = in.resume;
    for (uint32_t b : kept) if (b <= f.overlap) best = std::max(best, b);
    const uint32_t end = f.overlap + f.suffix;
    const auto future = splash::planDraftContext(best, end, {});
    uint64_t draftCount = 0;
    for (const auto &span : future.captureSpans) draftCount += span.end - span.begin;
    double futureTime = draftCount * in.costs.draftRowMs +
      (best ? in.costs.restoreMs : 0.0);
    uint32_t distance = end - best;
    while (distance) {
      const uint32_t chunk = std::min(distance, in.chunk);
      futureTime += in.costs.commandMs + chunk *
        (chunk >= in.bulkRows ? in.costs.bulkRowMs : chunk <= in.shortRows ? in.costs.shortRowMs : in.costs.middleRowMs);
      distance -= chunk;
    }
    cost += f.expectedUses * futureTime;
  }
  return cost;
}

Input fixture() {
  Input in;
  in.replay = 1056;
  in.required = {1056};
  in.stateBytes = 128 * 1024 * 1024;
  in.maximumBytes = 2 * in.stateBytes;
  in.hints = {{1024, Kind::LatestUser}};
  in.forecast = {{1024, 32, 0.7}};
  in.costs.snapshotMs = 20;
  in.costs.restoreMs = 20;
  in.costs.commandMs = 1;
  return in;
}

int main() {
  Input in = fixture();
  auto result = plan(in);
  assert(result.selected == std::vector<uint32_t>{1024});
  assert(result.plannedDraftRows == result.baselineDraftRows);
  assert(result.expectedSavedMs > 2000);
  in.growthPaused = true;
  assert(plan(in).reason == Reason::Pressure);
  in = fixture(); in.maximumBytes = in.stateBytes - 1;
  assert(plan(in).reason == Reason::MemoryBudget);
  in = fixture(); in.forecast.clear(); assert(plan(in).selected.empty());
  in = fixture(); in.costs.snapshotMs = 1e6; assert(plan(in).selected.empty());
  in = fixture(); in.hints.push_back({512, Kind::EarlierUser});
  assert(plan(in).selected.size() == 1); // no double counting one overlap
  in.forecast = {{512, 32, 0.5}, {1024, 32, 0.5}};
  assert(plan(in).selected.size() == 2);
  in.maximumBytes = in.stateBytes; assert(plan(in).selected.size() == 1);
  in = fixture(); in.hints.push_back({1030, Kind::LatestUser});
  assert(plan(in).candidateCount == 1); // page-equivalent hints deduplicate
  in = fixture(); in.costs.bulkRowMs = NAN; assert(plan(in).reason == Reason::Invalid);
  in = fixture(); in.forecast[0].expectedUses = -1; assert(plan(in).reason == Reason::Invalid);
  in = fixture(); in.required = {1024, 512}; assert(plan(in).reason == Reason::Invalid);
  in = fixture(); in.forecast[0].overlap = UINT32_MAX; assert(plan(in).reason == Reason::Invalid);

  // An expensive medium tail makes the command-aligned earlier alternative
  // better than a checkpoint closer to the actual overlap boundary.
  in = fixture(); in.chunk = 512; in.replay = 1664; in.required = {1664};
  in.hints = {{1024, Kind::EarlierUser}, {1472, Kind::LatestUser}};
  in.forecast = {{1472, 32, 0.7}};
  in.costs.bulkRowMs = 1; in.costs.shortRowMs = 1; in.costs.middleRowMs = 100;
  assert(plan(in).selected == std::vector<uint32_t>{1024});

  std::mt19937 rng(20261010);
  unsigned instances = 0, subsets = 0;
  for (unsigned trial = 0; trial < 3000; ++trial) {
    Input q;
    q.resume = trial % 3 ? 0 : 1024;
    q.replay = q.resume + 4096;
    q.required = {q.resume + 2048, q.replay};
    q.stateBytes = 1024;
    q.maximumStates = 1 + rng() % 4;
    q.maximumBytes = q.stateBytes * (rng() % 5);
    q.minimumNetGainMs = 1e-7;
    q.costs.bulkRowMs = 0.1 + double(rng()%100)/20;
    q.costs.middleRowMs = 0.1 + double(rng()%100)/20;
    q.costs.shortRowMs = 0.1 + double(rng()%100)/20;
    q.costs.draftRowMs = double(rng()%50)/20;
    q.costs.commandMs = double(rng()%100)/10;
    q.costs.snapshotMs = double(rng()%500);
    q.costs.restoreMs = double(rng()%300);
    q.costs.retentionMsPerByte = double(rng()%20)/1000;
    q.costs.queueInterferenceMs = double(rng()%200);
    std::vector<uint32_t> candidates;
    for (unsigned j = 1; j <= 7; ++j) {
      const uint32_t at = q.resume + j * 512;
      q.hints.push_back({at, Kind::EarlierUser});
      candidates.push_back(at);
      q.forecast.push_back({at + uint32_t(rng()%32), uint32_t(rng()%180),
                            0.01 + double(rng()%200)/100});
    }
    double best = oracle(q, {});
    const unsigned limit = std::min<uint64_t>(q.maximumStates, q.maximumBytes/q.stateBytes);
    for (unsigned mask = 0; mask < (1u<<candidates.size()); ++mask) {
      if (static_cast<unsigned>(__builtin_popcount(mask)) > limit) continue;
      std::vector<uint32_t> kept;
      for (size_t j = 0; j < candidates.size(); ++j)
        if (mask & (1u<<j)) kept.push_back(candidates[j]);
      best = std::min(best, oracle(q, kept));
      ++subsets;
    }
    const auto chosen = plan(q);
    assert(std::abs(chosen.baselineMs - oracle(q, {})) < 1e-6);
    assert(std::abs(chosen.plannedMs - best) < 1e-5);
    assert(chosen.retainedBytes <= q.maximumBytes);
    std::vector<uint32_t> captures = q.required;
    captures.insert(captures.end(), chosen.selected.begin(), chosen.selected.end());
    std::sort(captures.begin(), captures.end());
    captures.erase(std::unique(captures.begin(), captures.end()), captures.end());
    const auto real = splash::planDraftContext(q.resume, q.replay, captures);
    uint64_t draftCount = 0;
    for (const auto &span : real.captureSpans) draftCount += span.end - span.begin;
    assert(draftCount == chosen.plannedDraftRows);
    ++instances;
  }
  Input worst = fixture(); worst.replay = 65504; worst.required.clear();
  for (uint32_t b = 4096; b < worst.replay; b += 4096) worst.required.push_back(b);
  worst.required.push_back(worst.replay); worst.hints.clear(); worst.forecast.clear();
  for (uint32_t i = 1; i <= 32; ++i) {
    worst.hints.push_back({i*1952, Kind::EarlierUser});
    worst.forecast.push_back({i*1952, 64, 1.0/32});
  }
  std::vector<double> times;
  for (unsigned i = 0; i < 2000; ++i) {
    const auto start = std::chrono::steady_clock::now();
    const auto value = plan(worst);
    assert(value.candidateCount == 32);
    times.push_back(std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count());
  }
  std::sort(times.begin(), times.end());
  std::cout << "{\"instances\":" << instances << ",\"brute_force_subsets\":" << subsets
            << ",\"upstream_draft_plans\":\"matched\",\"edge_cases\":\"passed\",\"maximum_32_candidate_us_p50\":"
            << times[times.size()/2] << ",\"maximum_32_candidate_us_p95\":" << times[times.size()*95/100] << "}\n";
}
