#include "ops/Linear.hpp"
#include <cassert>
#include <cstdlib>
#include <iostream>

int main() {
  using namespace splash;
  using namespace splash::ops;
  setenv("SPLASH_REGISTER_PREFILL","128",1);
  DeviceCapabilities device;
  device.appleGpuFamily=9;device.gpuCoreCount=32;
  Linear linear(device);
  unsigned checks=0;
  for (const auto matrix : {LinearMatrix{5120,5120},LinearMatrix{17408,5120},
                           LinearMatrix{5120,17408},LinearMatrix{5120,25600}}) {
    Projection projection(matrix.outputSize,matrix.inputSize,AffineWeights{});
    const auto bound=linear.prefillScratchSize(projection.shape());
    for (uint32_t rows=1;rows<=128;++rows) {
      for (auto epilogue : {LinearEpilogue::None,LinearEpilogue::Residual,LinearEpilogue::GateUp}) {
        const auto plan=linear.prefillPlan(projection,rows,epilogue);
        assert(plan.workload().phase==LinearPhase::RegisterPrefill);
        assert(plan.storageRows()==(rows+7)/8*8);
        assert(plan.usesQ4Register());
        const auto needed=plan.scratchSize();
        assert(bound.input>=needed.input && bound.sums>=needed.sums &&
               bound.partials>=needed.partials && bound.counters>=needed.counters);
        ++checks;
      }
    }
    assert(linear.prefillPlan(projection,129,LinearEpilogue::None).workload().phase==LinearPhase::Prefill);
    // Real decode still refuses more than four physical model lanes.
    bool refused=false;
    try { static_cast<void>(linear.decodePlan(projection,5)); }
    catch(const std::invalid_argument &) {refused=true;}
    assert(refused);
  }
  std::cout << checks << " register prefill plans fit their scratch bounds; physical lane guard retained\n";
}
