load("@rules_cc//cc:defs.bzl", "cc_binary", "objc_library")

objc_library(
    name = "projection_probe_lib",
    srcs = ["projection_probe.mm"],
    deps = [
        "//ml_drift/common:gpu_model_builder",
        "//ml_drift/common:operations",
        "//ml_drift/common:precision",
        "//ml_drift/common:tensor",
        "//ml_drift/metal:environment",
        "//ml_drift/metal:inference_context",
        "//third_party/apple_frameworks:Metal",
        "@com_google_absl//absl/status",
        "@com_google_absl//absl/status:status_macros",
    ],
    alwayslink = 1,
)

cc_binary(name = "projection_probe", deps = [":projection_probe_lib"])
