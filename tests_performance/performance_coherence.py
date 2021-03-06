# -*- Encoding: UTF-8 -*-

import timeit
import numpy as np

from scipy.signal import get_window
import json

import more_itertools

import sys
sys.path.append("/global/homes/r/rkube/repos/delta")
from analysis.channels import channel, channel_pair, channel_range

from analysis.kernels_spectral_cy import kernel_coherence_64_cy, kernel_coherence_64_v2
#from analysis.kernels_spectral_cy import kernel_coherence_32_cy, kernel_coherence_32_v2

from analysis.kernels_spectral_cy import kernel_crossphase_64_cy, kernel_crossphase_64_v2
#from analysis.kernels_spectral_cy import kernel_crossphase_32_cy, kernel_crossphase_32_v2

from analysis.kernels_spectral_cy import kernel_crosspower_64_cy, kernel_crosspower_64_v2
#from analysis.kernels_spectral_cy import kernel_crosspower_32_cy, kernel_crosspower_32_v2

from analysis.kernels_spectral import kernel_coherence, kernel_crossphase, kernel_crosspower

from analysis.task_fft import task_fft_scipy



"""
Compare the performance of the coherence kernel to an implementation in cython
"""


# # Define fft_params and instantiate task_fft object
# with np.load("/global/homes/r/rkube/repos/delta/test_data/io_array_tr_s0001.npz") as df:
#     # Load transformed data, as generated by datareader
#     io_array_tr = df["io_array"]

with open("/global/homes/r/rkube/repos/delta/tests_analysis/config_fft.json", "r") as df:
    config_fft = json.load(df)

config_fft["fft_params"]["fsample"] = config_fft["ECEI_cfg"]["SampleRate"] * 1e3

win = get_window(config_fft["fft_params"]["window"], config_fft["fft_params"]["nfft"])
win_factor = (win**2).mean()

config_fft["fft_params"]["win_factor"] = win_factor

#my_fft = task_fft_scipy(10_000, config_fft["fft_params"], normalize=True, detrend=True)
#fft_data = my_fft.do_fft_local(io_array_tr)


with np.load("/global/homes/r/rkube/repos/delta/test_data/fft_array_s0001.npz") as df:
    fft_data = df["fft_data"]

fft_data_64 = np.ascontiguousarray(fft_data)
fft_data_32 = np.require(fft_data_64, dtype=np.complex64, requirements=['A', 'C'])


###################################################
# Generate channels to iterate over

ref_chrg = channel_range.from_str("L0101-2408")
cmp_chrg = channel_range.from_str("L0101-2408")
channel_pairs = [channel_pair(cr, cx) for cr in ref_chrg for cx in cmp_chrg]
unique_channels = [i[0] for i in more_itertools.distinct_combinations(channel_pairs, 1)]

#ch_it = [channel_pair(channel("L", i, 1), channel("L", i, 2)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 3)) for i in range(1, 25)]
#h_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 4)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 4)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 5)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 6)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 7)) for i in range(1, 25)]
#ch_it = ch_it + [channel_pair(channel("L", i, 1), channel("L", i, 8)) for i in range(1, 25)]


ch1_idx_arr = np.array([int(ch_pair.ch1.idx()) for ch_pair in unique_channels], dtype=np.uint64)
ch2_idx_arr = np.array([int(ch_pair.ch2.idx()) for ch_pair in unique_channels], dtype=np.uint64)


print("++++++++++++++++++++++++++++++ Testing coherence +++++++++++++++++++++++++++++++++++++")

res_coherence_no = kernel_coherence(fft_data, channel_pairs, None)
res_coherence_cy = kernel_coherence_64_cy(fft_data, channel_pairs, config_fft)
print(f"Distance: {np.linalg.norm(res_coherence_no.flatten() - res_coherence_cy.flatten()) / np.linalg.norm(res_coherence_no.flatten())}")


n_loop = 1

tic_no = timeit.default_timer()
for _ in range(n_loop):
    _ = kernel_coherence(fft_data, unique_channels, None)
toc_no = timeit.default_timer()
print(f"Python implementation: {((toc_no - tic_no) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_coherence(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Python implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_coherence_64_cy(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_coherence_64_v2(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_coherence_32_cy(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 32bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_coherence_32_v2(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 32bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")

print("++++++++++++++++++++++++++++++ Testing cross-power +++++++++++++++++++++++++++++++++++++")
res_crosspower_no = kernel_crosspower(fft_data, channel_pairs, None)
res_crosspower_cy = kernel_crosspower_64_cy(fft_data, channel_pairs, config_fft)
print(f"Distance: {np.linalg.norm(res_crosspower_no.flatten() - res_crosspower_cy.flatten()) / np.linalg.norm(res_crosspower_no.flatten())}")



tic_cy = timeit.default_timer()
for _ in range(n_loop):
    _ = kernel_crosspower(fft_data_64, channel_pairs, config_fft)
toc_cy = timeit.default_timer()
print(f"Python implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crosspower_64_cy(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crosspower_64_v2(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crosspower_32_cy(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 32byte:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crosspower_32_v2(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 32byte:{((toc_cy - tic_cy) / n_loop):6.4f}s")

print("++++++++++++++++++++++++++++++ Testing cross-phase +++++++++++++++++++++++++++++++++++++")
res_crossphase_no = kernel_crossphase(fft_data, channel_pairs, None)
res_crossphase_cy = kernel_crossphase_64_cy(fft_data, channel_pairs, config_fft)
print(f"Distance: {np.linalg.norm(res_crossphase_no.flatten() - res_crossphase_cy.flatten()) / np.linalg.norm(res_crossphase_no.flatten())}")


tic_cy = timeit.default_timer()
for _ in range(n_loop):
    _ = kernel_crossphase(fft_data_64, channel_pairs, config_fft)
toc_cy = timeit.default_timer()
print(f"Python implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crossphase_64_cy(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crossphase_64_v2(fft_data_64, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 64bit:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crossphase_32_cy(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation 32byte:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crossphase_32_v2(fft_data_32, channel_pairs, config_fft)
# toc_cy = timeit.default_timer()
# print(f"C      implementation 32byte:{((toc_cy - tic_cy) / n_loop):6.4f}s")



# res_cross_power_no = kernel_crosspower(fft_data, unique_channels, config_fft["fft_params"])
# res_cross_power_cy = crosspower_cy(fft_data, ch1_idx_arr, ch2_idx_arr) / config_fft["fft_params"]["win_factor"]
# print(f"Distance: {np.linalg.norm(res_cross_power_no - res_cross_power_cy)}")


# n_loop = 10

# tic_no = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crosspower(fft_data, unique_channels, config_fft["fft_params"])
# toc_no = timeit.default_timer()
# print(f"Default implementation: {((toc_no - tic_no) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = crosspower_cy(fft_data, ch1_idx_arr, ch2_idx_arr)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation:{((toc_cy - tic_cy) / n_loop):6.4f}s")


# res_cross_phase_no = kernel_crossphase(fft_data, unique_channels, config_fft["fft_params"])
# res_cross_phase_cy = crossphase_cy(fft_data, ch1_idx_arr, ch2_idx_arr)
# print(f"Distance: {np.linalg.norm(res_cross_phase_no - res_cross_phase_cy)}")


# n_loop = 10

# tic_no = timeit.default_timer()
# for _ in range(n_loop):
#     _ = kernel_crossphase(fft_data, unique_channels, config_fft["fft_params"])
# toc_no = timeit.default_timer()
# print(f"Default implementation: {((toc_no - tic_no) / n_loop):6.4f}s")

# tic_cy = timeit.default_timer()
# for _ in range(n_loop):
#     _ = crossphase_cy(fft_data, ch1_idx_arr, ch2_idx_arr)
# toc_cy = timeit.default_timer()
# print(f"Cython implementation:{((toc_cy - tic_cy) / n_loop):6.4f}s")



# End of file performance_coherence.py
