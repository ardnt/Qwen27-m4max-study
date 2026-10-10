#include "../source/BranchAnchor.hpp"

#include <array>
#include <cassert>
#include <iostream>
#include <vector>

using splash::engine::branchAnchor;

// Forward scan oracle, independently selecting the last marker before applying
// placement constraints. It tests boundary selection, not GPU state contents.
std::optional<uint32_t> reference(std::span<const uint32_t> prompt,
                                  std::span<const uint32_t> marker,
                                  uint32_t page, uint32_t resume,
                                  uint32_t replay, uint32_t minimum) {
  if (!page || marker.empty() || marker.size() > prompt.size())
    return std::nullopt;
  std::optional<size_t> last;
  for (size_t i = 0; i + marker.size() <= prompt.size(); ++i) {
    bool equal = true;
    for (size_t j = 0; j < marker.size(); ++j)
      if (prompt[i + j] != marker[j]) equal = false;
    if (equal) last = i;
  }
  if (!last) return std::nullopt;
  const uint32_t at = static_cast<uint32_t>(*last / page * page);
  if (at <= resume || at > replay || uint64_t{at} < uint64_t{resume} + minimum)
    return std::nullopt;
  return at;
}

int main() {
  const std::array<uint32_t, 3> marker{248045, 846, 198};
  unsigned checked = 0;
  for (uint32_t page : {8u, 32u, 64u}) {
    for (uint32_t position = 2048; position < 8384; ++position) {
      std::vector<uint32_t> p(position + 52, 17);
      std::copy(marker.begin(), marker.end(), p.begin() + 12);
      std::copy(marker.begin(), marker.end(), p.begin() + position);
      for (uint32_t resume : {0u, 2048u, position / page * page}) {
        assert(branchAnchor(p, marker, page, resume, position + 32, 2048) ==
               reference(p, marker, page, resume, position + 32, 2048));
        ++checked;
      }
    }
  }
  std::vector<uint32_t> p(8440, 17);
  std::copy(marker.begin(), marker.end(), p.begin() + 8301);
  assert(branchAnchor(p, marker, 32, 0, 8416, 2048) == 8288);
  assert(!branchAnchor(p, marker, 32, 8192, 8416, 2048));
  assert(!branchAnchor(p, marker, 32, 0, 8192, 2048));
  assert(!branchAnchor(p, std::span<const uint32_t>{}, 32, 0, 8416, 2048));
  assert(!branchAnchor(p, marker, 0, 0, 8416, 2048));
  assert(!branchAnchor({}, marker, 32, 0, 8416, 2048));
  assert(!branchAnchor(p, marker, 32, UINT32_MAX - 15, UINT32_MAX, 2048));
  std::vector<uint32_t> truncated{248045, 846};
  assert(!branchAnchor(truncated, marker, 32, 0, 32, 0));
  auto sibling = p;
  sibling[8304] = 55;
  const uint32_t at = *branchAnchor(p, marker, 32, 0, 8416, 2048);
  assert(std::equal(p.begin(), p.begin() + at, sibling.begin()));
  assert(p != sibling);
  sibling[at - 1] = 99;
  assert(!std::equal(p.begin(), p.begin() + at, sibling.begin()));
  // A matching marker does not make the changed prefix equal: the native
  // cache must still check prefix and image identity before restoration.
  assert(branchAnchor(p, marker, 32, 0, 8416, 2048) ==
         branchAnchor(sibling, marker, 32, 0, 8416, 2048));
  std::cout << checked << " independent boundary comparisons and edge checks passed\n";
}
