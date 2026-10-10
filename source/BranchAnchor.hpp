#pragma once

#include <algorithm>
#include <cstdint>
#include <optional>
#include <span>

namespace splash::engine {

// A stable history ends immediately before the final user turn. KV pages
// alone cannot resume a hybrid model: its recurrent state and the complete
// draft window must be captured at the same, fully verified token boundary.
// A marker is a scheduling hint only. Prefix hashes still authorize reuse.
[[nodiscard]] inline std::optional<uint32_t>
branchAnchor(std::span<const uint32_t> prompt,
             std::span<const uint32_t> marker, uint32_t pageTokens,
             uint32_t resumeBoundary, uint32_t replayBoundary,
             uint32_t minimumGain) {
  if (marker.empty() || !pageTokens || prompt.size() < marker.size())
    return std::nullopt;
  for (size_t end = prompt.size() - marker.size() + 1; end; --end) {
    const size_t position = end - 1;
    if (!std::equal(marker.begin(), marker.end(), prompt.begin() + position))
      continue;
    const uint32_t boundary = static_cast<uint32_t>(position / pageTokens * pageTokens);
    if (boundary <= resumeBoundary || boundary > replayBoundary ||
        uint64_t{boundary} < uint64_t{resumeBoundary} + minimumGain)
      return std::nullopt;
    return boundary;
  }
  return std::nullopt;
}

} // namespace splash::engine
