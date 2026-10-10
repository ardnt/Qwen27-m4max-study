// Isolated comparison of four dependent Qwen 27B-size projections.
// Synthetic weights, group 64, signed INT4, exactly representable FP16 scale.
// This is an operation benchmark, not a working Qwen 27B model.
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>
#include "absl/status/status_macros.h"
#include "ml_drift/common/gpu_model_builder.h"
#include "ml_drift/common/operations.h"
#include "ml_drift/metal/environment.h"
#include "ml_drift/metal/inference_context.h"

using namespace ml_drift;

uint32_t code(uint32_t index, uint32_t seed) {
  uint32_t h = index + seed * 1009u;
  h ^= h >> 16;
  h *= 0x7feb352du;
  h ^= h >> 15;
  h *= 0x846ca68bu;
  h ^= h >> 16;
  return h & 15u;
}

double median(std::vector<double> x) {
  std::sort(x.begin(), x.end());
  return x[x.size()/2];
}

absl::Status run(int rows, const std::string& output_path, bool f32_accum) {
  metal::Environment env;
  GpuModelBuilderOptions options;
  options.use_f32_accum_for_f16_convolutions = f32_accum;
  GpuModelBuilder builder(env.GetInfo(), options);
  auto input = builder.AddTensor(BHWC(1, 1, rows, 5120), DataType::kFloat16);
  auto current = input;
  std::vector<uint32_t> outputs;
  for (uint32_t seed = 0; seed < 4; ++seed) {
    int k = seed % 2 ? 17408 : 5120;
    int n = seed % 2 ? 5120 : 17408;
    Tensor<OHWI, DataType::kInt8> weights;
    weights.shape = OHWI(n, 1, 1, k);
    weights.data.resize(size_t(n)*k);
    for (size_t i = 0; i < weights.data.size(); ++i)
      weights.data[i] = static_cast<int8_t>(code(i, seed)) - 8;
    FullyConnectedInt4Attributes attr;
    attr.weights = std::move(weights);
    attr.scale.shape = OHWI(n, 1, 1, k/64);
    attr.scale.data.resize(size_t(n)*k/64, 1.f/128);
    current = builder.FullyConnected(current, attr);
    outputs.push_back(current.id);
  }
  GpuModel model;
  ABSL_RETURN_IF_ERROR(builder.GetGpuModel({input.id}, outputs, &model));
  std::ofstream shader(output_path + ".source");
  shader << model.nodes.front().gpu_operation->code_;
  std::vector<std::string> kernels;
  for (const auto& node : model.nodes) kernels.push_back(node.name);
  std::vector<uint32_t> scale_ids;
  for (const auto& [id, td] : model.const_tensors)
    if (td.GetDataType() == DataType::kFloat16) scale_ids.push_back(id);
  CreateGpuModelInfo info;
  info.precision = f32_accum ? CalculationsPrecision::kF32F16 : CalculationsPrecision::kF16;
  info.storage_type = TensorStorageType::kBuffer;
  info.external_mutable_tensors[input.id] = input.tensor_desc;
  metal::InferenceContext context;
  ABSL_RETURN_IF_ERROR(context.InitFromGpuModel(info, &model, &env));
  for (auto id : scale_ids) {
    TensorFloat32 value;
    ABSL_RETURN_IF_ERROR(context.GetOutputTensor(id, &value));
    std::cerr << "scale id=" << id << " first=" << value.data[0] << " last=" << value.data.back() << '\n';
  }
  TensorFloat32 x;
  x.shape = BHWC(1, 1, rows, 5120);
  x.data.resize(size_t(rows)*5120);
  for (int r = 0; r < rows; ++r)
    for (int i = 0; i < 5120; ++i)
      x.data[size_t(r)*5120+i] = ((i*13+r*11)%97-48)/64.f;
  auto input_descriptor = input.tensor_desc;
  input_descriptor.UploadData(x);
  metal::MetalSpatialTensor persistent_input;
  ABSL_RETURN_IF_ERROR(persistent_input.CreateFromDescriptor(input_descriptor, env.device()));
  ABSL_RETURN_IF_ERROR(context.SetTensor(input.id, &persistent_input));
  ABSL_RETURN_IF_ERROR(context.SetInputTensor(input.id, x));
  TensorFloat32 echo;
  ABSL_RETURN_IF_ERROR(context.GetOutputTensor(input.id, &echo));
  std::cerr << "input CPU/GPU=" << x.data[0] << '/' << echo.data[0]
            << ", last=" << x.data.back() << '/' << echo.data.back() << '\n';
  id<MTLCommandQueue> queue = [env.device() newCommandQueue];
  std::vector<double> gpu_ms, wall_ms;
  for (int sample = 0; sample < 25; ++sample) {
    @autoreleasepool {
      auto start = std::chrono::steady_clock::now();
      id<MTLCommandBuffer> cb = [queue commandBuffer];
      id<MTLComputeCommandEncoder> encoder = [cb computeCommandEncoder];
      context.EncodeWithEncoder(encoder);
      [encoder endEncoding];
      [cb commit];
      [cb waitUntilCompleted];
      if (cb.status != MTLCommandBufferStatusCompleted)
        return absl::InternalError("Metal command failed");
      auto stop = std::chrono::steady_clock::now();
      if (sample >= 4) {
        wall_ms.push_back(std::chrono::duration<double,std::milli>(stop-start).count());
        gpu_ms.push_back((cb.GPUEndTime-cb.GPUStartTime)*1000.0);
      }
    }
  }
  TensorFloat32 result;
  ABSL_RETURN_IF_ERROR(context.GetOutputTensor(outputs.back(), &result));
  std::ofstream binary(output_path, std::ios::binary);
  binary.write(reinterpret_cast<const char*>(result.data.data()), result.data.size()*sizeof(float));
  TensorFloat32 first;
  ABSL_RETURN_IF_ERROR(context.GetOutputTensor(outputs.front(), &first));
  std::cerr << "first output=" << first.data[0] << ',' << first.data[1]
            << ", final=" << result.data[0] << '\n';
  if (!std::all_of(first.data.begin(), first.data.end(), [](float f) {return std::isfinite(f);}) ||
      !std::all_of(result.data.begin(), result.data.end(), [](float f) {return std::isfinite(f);}))
    return absl::InternalError("Non-finite projection output; reject performance measurement");
  double max_error = 0, squared_error = 0, squared_ref = 0;
  // Independent FP32 CPU reference for sampled output columns on first/last row.
  for (int r : {0, rows-1}) for (int o : {0, 1, 17, 5119, 8191, 17407}) {
    double ref = 0;
    for (int i = 0; i < 5120; ++i)
      ref += x.data[size_t(r)*5120+i] * (int(code(uint32_t(o)*5120+i, 0))-8)/128.0;
    double error = first.data[size_t(r)*17408+o]-ref;
    max_error = std::max(max_error, std::abs(error));
    squared_error += error*error;
    squared_ref += ref*ref;
  }
  std::cout << std::setprecision(8) << "{\"runtime\":\"ML Drift Metal\",\"rows\":" << rows
      << ",\"fp32_accumulation\":" << (f32_accum ? "true" : "false")
      << ",\"group_size\":64,\"chain_length\":4,\"gpu_ms\":" << median(gpu_ms)
      << ",\"sync_wall_ms\":" << median(wall_ms)
      << ",\"allocated_bytes\":" << [env.device() currentAllocatedSize]
      << ",\"constant_bytes\":" << context.GetConstantTensorsSize()
      << ",\"intermediate_bytes\":" << context.GetIntermediateTensorsSize()
      << ",\"sampled_cpu_max_abs_error\":" << max_error
      << ",\"sampled_cpu_relative_l2_error\":" << std::sqrt(squared_error/squared_ref)
      << ",\"samples\":21,\"kernels\":[";
  for (size_t i = 0; i < kernels.size(); ++i)
    std::cout << (i ? "," : "") << '"' << kernels[i] << '"';
  std::cout << "]}" << std::endl;
  return absl::OkStatus();
}

int main(int argc, char** argv) {
  if (argc != 3 && argc != 4) return 2;
  @autoreleasepool {
    auto status = run(std::stoi(argv[1]), argv[2], argc == 3 || std::string(argv[3]) != "f16");
    if (!status.ok()) { std::cerr << status << std::endl; return 1; }
  }
}
