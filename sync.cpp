// sync.cpp
// C++ optimized two-pointer sync between RR intervals and FIT timestamps.
// Written as C++ code but using C headers for broad compatibility.

#include <stddef.h>  // size_t
#include <math.h>    // fabs()

#ifdef _WIN32
  #define EXPORT __declspec(dllexport)
#else
  #define EXPORT
#endif

extern "C" {

/**
 * Sync RR intervals to FIT timestamps using O(n+m) two-pointer approach.
 * rr_times and fit_times are sorted arrays of timestamps (seconds since epoch).
 * out_idx[i] = index of best matching fit_times for rr_times[i].
 */
EXPORT void sync_rr_to_fit(const double* rr_times,
                           size_t rr_count,
                           const double* fit_times,
                           size_t fit_count,
                           size_t* out_idx)
{
    if (!rr_times || !fit_times || !out_idx) return;
    if (rr_count == 0 || fit_count == 0) return;

    size_t j = 0;
    for (size_t i = 0; i < rr_count; ++i) {
        double t = rr_times[i];
        // Advance j while the next FIT timestamp is closer to t
        while (j + 1 < fit_count &&
               fabs(fit_times[j + 1] - t) <= fabs(fit_times[j] - t)) {
            ++j;
        }
        out_idx[i] = j;
    }
}

} // extern "C"
