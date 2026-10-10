// Splash contributors, Apache-2.0. Test-only extracted upstream reference.
// See PROVENANCE.md; the function body is unchanged except its named constant.
#pragma once
#include <algorithm>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <vector>
namespace splash {
enum class DraftBoundaryPurpose : uint8_t { Active, Materialization };

struct DraftCaptureSpan final {
  uint32_t begin = 0;
  uint32_t end = 0;
  bool resetDraftState = false;
};

struct DraftBoundaryPlan final {
  uint32_t boundary = 0;
  DraftBoundaryPurpose purpose = DraftBoundaryPurpose::Active;
  uint32_t captureBegin = 0;
};

struct DraftContextPlan final {
  uint32_t replayBegin = 0;
  uint32_t replayEnd = 0;
  std::vector<DraftCaptureSpan> captureSpans;
  std::vector<DraftBoundaryPlan> boundaries;
  // The first capture continues the restored draft ring: a non-zero replay
  // whose first boundary is within one draft window of it. Otherwise the
  // restore skips the ring.
  bool restoresDraftState = false;
};

DraftContextPlan
planDraftContext(uint32_t replayBegin, uint32_t replayEnd,
                 std::span<const uint32_t> materializationBoundaries) {
  if (replayEnd < replayBegin) {
    throw std::invalid_argument("draft replay range is reversed");
  }

  uint32_t previousMaterialization = 0;
  bool havePreviousMaterialization = false;
  for (uint32_t boundary : materializationBoundaries) {
    if (boundary <= replayBegin || boundary > replayEnd) {
      throw std::invalid_argument(
          "draft materialization boundary is outside replay range");
    }
    if (havePreviousMaterialization && boundary <= previousMaterialization) {
      throw std::invalid_argument(
          "draft materialization boundaries are not sorted and unique");
    }
    previousMaterialization = boundary;
    havePreviousMaterialization = true;
  }

  DraftContextPlan result;
  result.replayBegin = replayBegin;
  result.replayEnd = replayEnd;

  constexpr uint32_t window = 2048;
  uint32_t stateBoundary = replayBegin;
  bool haveState = replayBegin != 0;

  const auto addBoundary = [&](uint32_t boundary,
                               DraftBoundaryPurpose purpose) {
    const uint32_t distance = boundary - stateBoundary;
    const bool useRestored = haveState && distance == 0;
    uint32_t captureBegin = boundary;

    if (!useRestored) {
      const bool continueState = haveState && distance < window;
      captureBegin =
          continueState ? stateBoundary : boundary - std::min(boundary, window);
      const uint32_t rows = boundary - captureBegin;

      if (rows != 0 && !result.captureSpans.empty() && continueState &&
          result.captureSpans.back().end ==
              captureBegin) {
        result.captureSpans.back().end = boundary;
      } else if (rows != 0) {
        result.captureSpans.push_back({captureBegin, boundary, !continueState});
      }
    }

    result.boundaries.push_back({boundary, purpose, captureBegin});
    stateBoundary = boundary;
    haveState = true;
  };

  // A cache state at prompt end is the active state itself; do not describe or
  // build the same physical state twice.
  for (uint32_t boundary : materializationBoundaries) {
    if (boundary < replayEnd)
      addBoundary(boundary, DraftBoundaryPurpose::Materialization);
  }
  addBoundary(replayEnd, DraftBoundaryPurpose::Active);

  const uint32_t firstBoundary =
      !materializationBoundaries.empty() &&
              materializationBoundaries.front() < replayEnd
          ? materializationBoundaries.front()
          : replayEnd;
  result.restoresDraftState =
      replayBegin != 0 && firstBoundary - replayBegin < window;
  return result;
}

}
