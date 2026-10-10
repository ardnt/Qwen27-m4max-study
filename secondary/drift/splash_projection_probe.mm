#include "metal/MetalBackend.hpp"
#include "metal/CommandGraph.hpp"
#include "ops/Linear.hpp"
#include "tuning/LinearNumerics.hpp"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>

using namespace splash::metal;
using namespace splash::ops;

uint32_t code(uint32_t index, uint32_t seed) {
  uint32_t h = index + seed * 1009u;
  h ^= h >> 16; h *= 0x7feb352du;
  h ^= h >> 15; h *= 0x846ca68bu;
  h ^= h >> 16; return h & 15u;
}
double median(std::vector<double> x) {
  std::sort(x.begin(),x.end()); return x[x.size()/2];
}

int main(int argc, char** argv) {
  if (argc != 4) return 2;
  try {
    const uint32_t rows = std::stoi(argv[1]);
    MetalBackend backend(argv[2]);
    Linear linear(backend.capabilities());
    auto zeros = [&](uint64_t bytes) {
      if (!bytes) return MetalBuffer{};
      auto b = backend.allocateBuffer(bytes,BufferStorage::Shared,"drift comparison");
      std::memset(b.contents(),0,bytes); return b;
    };
    uint32_t stored = rows == 8 ? rows : ((rows+31)/32)*32;
    MetalBuffer input = zeros(uint64_t(stored)*5120*2);
    auto* input_bits = static_cast<uint16_t*>(input.contents());
    for (uint32_t r=0;r<rows;++r) for(uint32_t i=0;i<5120;++i)
      input_bits[uint64_t(r)*5120+i] = tuning::floatToBf16((int((i*13+r*11)%97)-48)/64.f);
    std::vector<Projection> projections;
    std::vector<MetalBuffer> outputs, sums;
    std::vector<LinearPlan> plans;
    std::vector<LinearScratch> workspaces;
    for (uint32_t seed=0;seed<4;++seed) {
      uint32_t k=seed%2?17408:5120, n=seed%2?5120:17408;
      uint64_t count=uint64_t(n)*k/64;
      AffineWeights w{zeros(count*32),zeros(count*2),zeros(count*2)};
      auto* packed=static_cast<uint8_t*>(w.weights.contents());
      auto* scale=static_cast<uint16_t*>(w.scales.contents());
      auto* bias=static_cast<uint16_t*>(w.biases.contents());
      for (uint32_t o=0;o<n;++o) for (uint32_t g=0;g<k/64;++g) {
        uint64_t parameter=(uint64_t(o/256)*(k/64)+g)*256+o%256;
        scale[parameter]=tuning::floatToBf16(1.f/128);
        bias[parameter]=tuning::floatToBf16(-8.f/128);
        for (uint32_t i=0;i<64;i+=2) {
          uint32_t index=o*k+g*64+i;
          packed[parameter*32+i/2]=code(index,seed)|(code(index+1,seed)<<4);
        }
      }
      projections.emplace_back(n,k,std::move(w));
      const auto phase = rows==8 ? LinearPhase::Decode : LinearPhase::Prefill;
      plans.push_back(linear.plan({{n,k},rows,phase,LinearEpilogue::None},projections.back()));
      outputs.push_back(zeros(uint64_t(stored)*n*2));
      sums.push_back(zeros(plans.back().sumsBytes()));
      auto sz=plans.back().scratchSize();
      workspaces.push_back({zeros(sz.input),zeros(sz.sums),zeros(sz.partials),zeros(sz.counters)});
    }
    CommandGraph graph;
    auto current=input;
    for (uint32_t i=0;i<4;++i) {
      if (rows!=8) linear.addPrefillSums(graph,current,sums[i],projections[i],rows);
      auto prepared=linear.add(graph,{.input=current,.output=outputs[i],.sums=sums[i],.scratch=workspaces[i]},
                               projections[i],plans[i]);
      (void)prepared; current=outputs[i];
    }
    std::vector<double> gpu_ms,wall_ms;
    for (int sample=0;sample<25;++sample) {
      auto start=std::chrono::steady_clock::now();
      auto done=backend.submitCommandAsync(graph.dispatches()).wait();
      auto stop=std::chrono::steady_clock::now();
      if (sample>=4) {
        gpu_ms.push_back(done.gpuSeconds*1000);
        wall_ms.push_back(std::chrono::duration<double,std::milli>(stop-start).count());
      }
    }
    std::vector<float> result(uint64_t(rows)*5120);
    auto* raw=static_cast<uint16_t*>(current.contents());
    for (size_t i=0;i<result.size();++i) result[i]=tuning::bf16ToFloat(raw[i]);
    std::ofstream binary(argv[3],std::ios::binary);
    binary.write(reinterpret_cast<const char*>(result.data()),result.size()*4);
    double max_error=0,es=0,rs=0;
    auto* first=static_cast<uint16_t*>(outputs.front().contents());
    for(uint32_t r:{0u,rows-1}) for(uint32_t o:{0u,1u,17u,5119u,8191u,17407u}) {
      double ref=0;
      for(uint32_t i=0;i<5120;++i)
        ref+=tuning::bf16ToFloat(input_bits[uint64_t(r)*5120+i])*(int(code(o*5120+i,0))-8)/128.0;
      double e=tuning::bf16ToFloat(first[uint64_t(r)*17408+o])-ref;
      max_error=std::max(max_error,std::abs(e)); es+=e*e; rs+=ref*ref;
    }
    std::cout << std::setprecision(8) << "{\"runtime\":\"Splash 1.3 production policy and metallib\",\"rows\":" << rows
      << ",\"activation_dtype\":\"bf16\",\"chain_length\":4,\"samples\":21,\"gpu_ms\":" << median(gpu_ms)
      << ",\"sync_wall_ms\":" << median(wall_ms) << ",\"sampled_cpu_max_abs_error\":" << max_error
      << ",\"sampled_cpu_relative_l2_error\":" << std::sqrt(es/rs) << ",\"kernels\":[";
    for(size_t i=0;i<plans.size();++i) std::cout << (i?",":"") << '"' << plans[i].pipeline() << '"';
    std::cout << "]}" << std::endl;
  } catch(const std::exception& e) { std::cerr << e.what() << std::endl; return 1; }
}
