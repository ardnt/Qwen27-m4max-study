#pragma once

#include "engine/CostAwareCheckpoint.hpp"

#include <array>
#include <chrono>
#include <cstdlib>
#include <deque>
#include <string_view>

namespace splash::engine::semantic {

enum class Mode : uint8_t { Off, Shadow, On };
struct PlannerSnapshot {
  Mode mode = Mode::Off;
  uint64_t decisions = 0, selectedStates = 0, abstentions = 0, invalid = 0;
  uint64_t costSamples = 0, captureSamples = 0, restoreSamples = 0;
  uint64_t overlapObservations = 0, unrelated = 0;
  double lastPlanUs = 0.0, maximumPlanUs = 0.0;
  double expectedNetSavedMs = 0.0, additionalCaptureMs = 0.0;
  uint64_t stateBytes = 0, retainedBytes = 0;
  uint64_t baselineDraftRows = 0, plannedDraftRows = 0;
  Costs costs;
  std::vector<uint32_t> selected;
  Reason reason = Reason::NotWorthwhile;
  uint32_t candidates = 0;
  std::array<double, 4> probabilities{0.55, 0.15, 0.20, 0.10};
  uint32_t resume = 0, replay = 0;
  Costs decisionCosts;
  std::vector<Forecast> forecast;
};

// Per-engine, bounded, CPU-only learner. Observations are exact token overlaps,
// including misses; existing cache placements cannot censor its observations.
// Role markers guide *where to capture*, never authorize a cache hit.
class SemanticPlanner final {
public:
  explicit SemanticPlanner(Mode mode = environmentMode()) { stats_.mode = mode; }
  [[nodiscard]] static Mode environmentMode() noexcept {
    const char *value = std::getenv("SPLASH_SEMANTIC_PLANNER");
    if (!value) return Mode::Off;
    if (std::string_view(value) == "on") return Mode::On;
    if (std::string_view(value) == "shadow") return Mode::Shadow;
    return Mode::Off;
  }
  [[nodiscard]] bool enabled() const noexcept { return stats_.mode != Mode::Off; }
  [[nodiscard]] bool applies() const noexcept { return stats_.mode == Mode::On; }
  [[nodiscard]] PlannerSnapshot snapshot() const { return stats_; }

  // Counts use the model's *actual* committed target/draft rows. Coefficients
  // are regularized nonnegative regression estimates of complete command wall
  // time, not invented measurements of separate kernels. Five weak priors
  // keep underidentified routes conservative until diverse commands arrive.
  void observeCommand(uint32_t rows, uint64_t draftRows, double wallMs) noexcept {
    if (!enabled() || !rows || rows > 2048 || draftRows > 4096 ||
        !std::isfinite(wallMs) || wallMs <= 0.0 || wallMs > 30000.0) return;
    const std::array<double, 5> x{
        rows >= 512 ? rows / 512.0 : 0.0,
        rows > 128 && rows < 512 ? rows / 512.0 : 0.0,
        rows <= 128 ? rows / 512.0 : 0.0, draftRows / 512.0, 1.0};
    // Exponential decay bounds old data's influence after thermal/load drift.
    for (size_t i = 0; i < 5; ++i) {
      rhs_[i] = 0.985 * rhs_[i] + x[i] * wallMs;
      for (size_t j = 0; j < 5; ++j)
        gram_[i][j] = 0.985 * gram_[i][j] + x[i] * x[j];
    }
    ++stats_.costSamples;
    fit();
  }
  void observeCapture(double ms) noexcept {
    if (!enabled() || !std::isfinite(ms) || ms <= 0.0 || ms > 30000.0) return;
    stats_.costs.snapshotMs = stats_.captureSamples ?
        0.8 * stats_.costs.snapshotMs + 0.2 * ms : ms;
    ++stats_.captureSamples;
  }
  void observeRestore(double ms) noexcept {
    if (!enabled() || !std::isfinite(ms) || ms < 0.0 || ms > 30000.0) return;
    stats_.costs.restoreMs = stats_.restoreSamples ?
        0.8 * stats_.costs.restoreMs + 0.2 * ms : ms;
    ++stats_.restoreSamples;
  }

  [[nodiscard]] static std::vector<uint32_t>
  userBoundaries(std::span<const uint32_t> prompt, std::span<const uint32_t> marker,
                 uint32_t page) {
    std::vector<uint32_t> result;
    if (marker.empty() || !page || prompt.size() < marker.size()) return result;
    for (size_t i = 0; i + marker.size() <= prompt.size(); ++i) {
      if (prompt[i] != marker[0] ||
          !std::equal(marker.begin(), marker.end(), prompt.begin() + i)) continue;
      const auto at = static_cast<uint32_t>(i / page * page);
      if (result.empty() || result.back() != at) result.push_back(at);
      // Only recent conversation turns enter the planner, at most 24.
      if (result.size() > 24) result.erase(result.begin());
      i += marker.size() - 1;
    }
    return result;
  }

  void observePrompt(std::span<const uint32_t> prompt,
                     std::span<const uint32_t> marker, uint32_t page,
                     uint32_t replay) {
    if (!enabled() || prompt.size() > 65536) return;
    const auto cuts = userBoundaries(prompt, marker, page);
    if (cuts.empty()) return;
    if (!previousTokens_.empty()) {
      History &history = histories_[previousShape_];
      const auto mismatch = std::mismatch(previousTokens_.begin(), previousTokens_.end(),
                                           prompt.begin(), prompt.end());
      const auto overlap = static_cast<uint32_t>(mismatch.first - previousTokens_.begin());
      // Exact repeat/continuation, latest turn edit, earlier edit, unrelated.
      const uint8_t outcome = overlap >= previousReplay_ ? 2 :
          overlap >= previousCuts_.back() ? 0 :
          previousCuts_.size() > 1 && overlap >= std::max(32U, previousCuts_.front()) ? 1 : 3;
      if (history.outcomes.size() == 64) {
        --history.counts[history.outcomes.front()]; history.outcomes.pop_front();
      }
      history.outcomes.push_back(outcome); ++history.counts[outcome];
      ++stats_.overlapObservations;
      if (outcome == 3) ++stats_.unrelated;
    }
    // Attribute the outcome to the *previous* shape, even when an earlier edit
    // changes a multi-turn request into a single-turn request.
    previousTokens_.assign(prompt.begin(), prompt.end());
    previousCuts_ = cuts; previousReplay_ = replay;
    previousShape_ = shape(prompt.size(), cuts);
  }

  Result choose(Input input, std::span<const uint32_t> prompt,
                std::span<const uint32_t> marker, uint32_t observedJunction,
                uint32_t competingDecoders) {
    const auto begin = std::chrono::steady_clock::now();
    const auto cuts = userBoundaries(prompt, marker, input.page);
    input.costs = stats_.costs;
    input.costs.queueInterferenceMs = input.costs.snapshotMs * competingDecoders;
    input.forecast.clear(); input.hints.clear();
    // Validate geometry before division when constructing aligned candidates.
    // plan() below still records Invalid and leaves placement to native fallback.
    if (valid(input) && !cuts.empty()) {
      const History &history = histories_[shape(prompt.size(), cuts)];
      // Two documented pseudo-observations, then a rolling 64 transition window.
      constexpr std::array<double, 4> prior{0.55, 0.15, 0.20, 0.10};
      for (size_t i = 0; i < 4; ++i)
        stats_.probabilities[i] = (history.counts[i] + 2.0 * prior[i]) /
                                 (history.outcomes.size() + 2.0);
      const uint32_t suffix = static_cast<uint32_t>(std::clamp<size_t>(
          prompt.size() - cuts.back(), 32, 256));
      const uint32_t latest = cuts.back();
      input.hints.push_back({latest, Kind::LatestUser});
      // The command-aligned alternative can trade 0..480 future rows for fewer
      // split/tail commands. Page identity remains exact for either choice.
      input.hints.push_back({latest / input.chunk * input.chunk, Kind::LatestUser});
      input.hints.push_back({latest / input.bulkRows * input.bulkRows, Kind::LatestUser});
      input.forecast.push_back({latest, suffix, stats_.probabilities[0]});
      std::vector<uint32_t> earlier;
      for (uint32_t at : cuts) if (at < latest) earlier.push_back(at);
      if (observedJunction > input.resume && observedJunction < latest)
        earlier.push_back(observedJunction);
      std::sort(earlier.begin(), earlier.end());
      earlier.erase(std::unique(earlier.begin(), earlier.end()), earlier.end());
      for (uint32_t at : earlier) {
        input.hints.push_back({at, Kind::EarlierUser});
        input.hints.push_back({at / input.chunk * input.chunk, Kind::EarlierUser});
        input.forecast.push_back({at, suffix,
                                 stats_.probabilities[1] / earlier.size()});
      }
    }
    Result result = plan(input);
    ++stats_.decisions;
    stats_.selectedStates += result.selected.size();
    if (result.selected.empty()) ++stats_.abstentions;
    if (result.reason == Reason::Invalid) ++stats_.invalid;
    stats_.selected = result.selected; stats_.reason = result.reason;
    stats_.candidates = result.candidateCount;
    stats_.expectedNetSavedMs = result.expectedSavedMs;
    stats_.additionalCaptureMs = result.additionalCaptureMs;
    stats_.stateBytes = input.stateBytes; stats_.retainedBytes = result.retainedBytes;
    stats_.resume = input.resume; stats_.replay = input.replay;
    stats_.decisionCosts = input.costs; stats_.forecast = input.forecast;
    stats_.baselineDraftRows = result.baselineDraftRows;
    stats_.plannedDraftRows = result.plannedDraftRows;
    stats_.lastPlanUs = std::chrono::duration<double, std::micro>(
        std::chrono::steady_clock::now() - begin).count();
    stats_.maximumPlanUs = std::max(stats_.maximumPlanUs, stats_.lastPlanUs);
    return result;
  }

private:
  struct History {
    std::array<uint32_t, 4> counts{};
    std::deque<uint8_t> outcomes;
  };
  static size_t shape(size_t tokens, const std::vector<uint32_t> &cuts) noexcept {
    return cuts.size() > 1 ? 2 : cuts.back() > tokens / 2 ? 0 : 1;
  }
  void fit() noexcept {
    constexpr std::array<double, 5> prior{3.2 * 512, 3.2 * 512, 3.2 * 512, 0.5 * 512, 0.0};
    constexpr std::array<double, 5> ridge{1.0, 0.2, 0.05, 1.0, 0.1};
    std::array<double, 5> theta{stats_.costs.bulkRowMs * 512,
        stats_.costs.middleRowMs * 512, stats_.costs.shortRowMs * 512, stats_.costs.draftRowMs * 512,
        stats_.costs.commandMs};
    for (uint32_t iteration = 0; iteration < 32; ++iteration)
      for (size_t i = 0; i < 5; ++i) {
        double residual = rhs_[i] + ridge[i] * prior[i];
        for (size_t j = 0; j < 5; ++j)
          if (i != j) residual -= gram_[i][j] * theta[j];
        theta[i] = std::max(i < 3 ? 0.0512 : 0.0,
                           residual / (gram_[i][i] + ridge[i]));
      }
    stats_.costs.bulkRowMs = theta[0] / 512;
    stats_.costs.middleRowMs = theta[1] / 512;
    stats_.costs.shortRowMs = theta[2] / 512;
    stats_.costs.draftRowMs = theta[3] / 512;
    stats_.costs.commandMs = theta[4];
  }
  PlannerSnapshot stats_;
  std::array<History, 3> histories_;
  std::vector<uint32_t> previousTokens_, previousCuts_;
  uint32_t previousReplay_ = 0;
  size_t previousShape_ = 0;
  std::array<std::array<double, 5>, 5> gram_{};
  std::array<double, 5> rhs_{};
};

} // namespace splash::engine::semantic
