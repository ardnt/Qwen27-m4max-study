#include "engine/SemanticPlanner.hpp"
#include <cassert>
#include <iostream>

using namespace splash::engine::semantic;
int main() {
  SemanticPlanner on(Mode::On), off(Mode::Off);
  std::vector<uint32_t> marker{101, 102, 103};
  std::vector<uint32_t> prompt(1160, 7);
  std::copy(marker.begin(), marker.end(), prompt.begin() + 1024);
  on.observePrompt(prompt, marker, 32, 1152);
  Input in; in.replay = 1152; in.required = {1152};
  in.stateBytes = 128 * 1024 * 1024; in.maximumBytes = 512 * 1024 * 1024;
  // Invalid geometry must reach native fallback without division by zero.
  for (int field = 0; field < 3; ++field) {
    Input bad = in;
    if (field == 0) bad.chunk = 0;
    if (field == 1) bad.bulkRows = 0;
    if (field == 2) bad.page = 0;
    assert(on.choose(bad, prompt, marker, 0, 0).reason == Reason::Invalid);
  }
  auto result = on.choose(in, prompt, marker, 0, 0);
  assert(result.reason == Reason::Selected && result.selected == std::vector<uint32_t>{1024});
  assert(result.baselineDraftRows == result.plannedDraftRows);
  in.growthPaused = true;
  assert(on.choose(in, prompt, marker, 0, 0).reason == Reason::Pressure);
  in.growthPaused = false; in.maximumBytes = in.stateBytes - 1;
  assert(on.choose(in, prompt, marker, 0, 0).reason == Reason::MemoryBudget);
  in.maximumBytes = 512 * 1024 * 1024;
  // Observe cold, unrelated requests even without a cache and without choosing.
  for (uint32_t i = 0; i < 100; ++i) {
    prompt[9] = 1000 + i;
    on.observePrompt(prompt, marker, 32, 1152);
  }
  result = on.choose(in, prompt, marker, 0, 0);
  assert(result.reason == Reason::NotWorthwhile);
  assert(on.snapshot().overlapObservations == 100);
  assert(on.snapshot().probabilities[3] > 0.95);
  // A genuine changed-suffix workload adapts to observed branch use.
  for (uint32_t i = 0; i < 100; ++i) {
    prompt[1100] = 2000 + i;
    on.observePrompt(prompt, marker, 32, 1152);
  }
  result = on.choose(in, prompt, marker, 0, 0);
  assert(result.reason == Reason::Selected);
  assert(on.snapshot().probabilities[0] > 0.95);
  // Measurements reject malformed values; finite estimates use actual rows.
  const auto before = on.snapshot().costSamples;
  on.observeCommand(512, 512, -1); on.observeCommand(512, 8192, 50);
  assert(on.snapshot().costSamples == before);
  for (uint32_t i = 0; i < 300; ++i) {
    on.observeCommand(512, 0, 1054); // 2.0 ms/target row, 30 ms dispatch
    on.observeCommand(512, 512, 1310); // .5 ms/draft row
    on.observeCommand(64, 0, 94); // 1 ms/short row
    on.observeCommand(128, 128, 222);
    on.observeCommand(256, 0, 798); // 3 ms/middle row, no ANE-sized dispatch
  }
  const auto c = on.snapshot().costs;
  assert(c.bulkRowMs > 1.7 && c.bulkRowMs < 2.4);
  assert(c.shortRowMs > 0.6 && c.shortRowMs < 1.6);
  assert(c.draftRowMs > 0.3 && c.draftRowMs < 0.7);
  assert(c.middleRowMs > 2.7 && c.middleRowMs < 3.4);
  on.observeCapture(17); on.observeRestore(12);
  assert(on.snapshot().costs.snapshotMs == 17 && on.snapshot().costs.restoreMs == 12);
  off.observePrompt(prompt, marker, 32, 1152); off.observeCommand(512, 512, 50);
  assert(off.snapshot().overlapObservations == 0 && off.snapshot().costSamples == 0);
  // Marker-like user text supplies scheduling hints only. No state is reused here.
  assert(SemanticPlanner::userBoundaries(prompt, {}, 32).empty());
  assert(SemanticPlanner::userBoundaries(prompt, marker, 0).empty());
  SemanticPlanner shapes(Mode::On);
  std::vector<uint32_t> multi(1300, 7), older(750, 7);
  std::copy(marker.begin(), marker.end(), multi.begin() + 512);
  std::copy(marker.begin(), marker.end(), multi.begin() + 1024);
  std::copy(marker.begin(), marker.end(), older.begin() + 512);
  older[520] = 99;
  shapes.observePrompt(multi, marker, 32, 1280);
  shapes.observePrompt(older, marker, 32, 736);
  in.replay = 1280; in.required = {1280};
  shapes.choose(in, multi, marker, 0, 0);
  assert(shapes.snapshot().probabilities[1] > 0.4);
  std::cout << "{\"controller_tests\":\"passed\",\"bounded_history\":64,\"cold_miss_learning\":true,\"drift_adaptation\":true,\"cost_fit\":["
            << c.bulkRowMs << ',' << c.middleRowMs << ',' << c.shortRowMs << ',' << c.draftRowMs << ',' << c.commandMs << "]}\n";
}
