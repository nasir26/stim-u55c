// stim-u55c: FPGA-accelerated stabilizer circuit sampling for Alveo U55C
// Author: Nasir Ali, C-DAC Noida
#pragma once

#include "config.hpp"
#include "frame_store.hpp"
#include "instruction.hpp"

namespace stim_u55c {

void stim_frame_sampler(const Instruction *instructions, int num_instructions, uint32_t seed_lo, uint32_t seed_hi,
                         ap_uint<SHOTS> detector_out[NUM_DETECTORS_MAX],
                         ap_uint<SHOTS> observable_out[NUM_OBSERVABLES_MAX]);

}  // namespace stim_u55c
