// Continuous USB capture is isolated from client/network backpressure. GPL-3.0-or-later.
#pragma once
#include "sample_queue.hpp"
#include <uhd/usrp/multi_usrp.hpp>
#include <uhd/stream.hpp>
#include <sys/resource.h>
#include <pthread.h>
#include <unistd.h>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

namespace b210 {
struct Radio {
    bool synthetic = false;
    uint32_t maximum_rate = 4000000, frequency = 137900000, gain = 30, decimation = 2;
    uint32_t serial = 0, maximum_gain = 76;
    double rate = 1000000;
    bool streaming = false;
    SampleQueue queue;
    std::atomic<uint64_t> received{0}, usb_overflows{0}, queue_dropped{0}, timeouts{0};
    std::atomic<size_t> peak_blocks{0};
    uint64_t retune_discarded = 0;
    size_t chunk_samples = 16384;
    explicit Radio(bool (*stop)()) : external_stop_(stop), scratch_(16384) { }
    ~Radio() { halt(); }
    void initialize() {
        rate = maximum_rate / double(1u << decimation);
        if (synthetic) { std::puts("SYNTHETIC: 35 kHz carrier; no USB hardware is used"); return; }
        std::puts("Opening B210 and loading FX3/FPGA images...");
        const int old_nice = getpriority(PRIO_PROCESS, 0);
        // The libusb event threads inherit a modest CFS priority. Do not use realtime policy.
        if (geteuid() == 0 && setpriority(PRIO_PROCESS, 0, -4) != 0)
            std::perror("USB event priority");
        usrp_ = uhd::usrp::multi_usrp::make("type=b200,master_clock_rate=16e6,recv_frame_size=16360,num_recv_frames=128");
        if (geteuid() == 0) setpriority(PRIO_PROCESS, 0, old_nice);
        usrp_->set_rx_subdev_spec(uhd::usrp::subdev_spec_t("A:A"));
        usrp_->set_rx_antenna("RX2", 0);
        for (unsigned char c : usrp_->get_usrp_rx_info(0).get("mboard_serial", "")) serial = (serial ^ c) * 16777619u;
        apply();
        std::printf("B210 initialized: %s, antenna RF A/RX2\n", usrp_->get_pp_string().c_str());
        std::puts("USB receive pool: 128 x 16360 bytes; dedicated capture thread enabled");
    }
    void halt() noexcept {
        receiving_.store(false, std::memory_order_release);
        if (worker_.joinable()) worker_.join();
        if (rx_ && streaming) {
            try { rx_->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_STOP_CONTINUOUS); }
            catch (const std::exception& e) { std::fprintf(stderr, "RX stop: %s\n", e.what()); }
        }
        streaming = false;
        rx_.reset();
    }
    void apply() {
        const bool resume = streaming;
        halt();
        rate = maximum_rate / double(1u << decimation);
        if (usrp_) {
            usrp_->set_rx_rate(rate, 0);
            if (std::abs(usrp_->get_rx_rate(0) - rate) > 0.5)
                throw std::runtime_error("UHD refused the protocol's exact sample rate");
            usrp_->set_rx_freq(double(frequency), 0);
            usrp_->set_rx_bandwidth(std::max(200000.0, rate * 0.9), 0);
            update_gain();
        }
        if (resume) start();
        std::printf("RX settings: %u Hz, %.0f S/s, gain %u dB\n", frequency, rate, gain);
    }
    void set_gain(uint32_t value) {
        gain = std::min(value, maximum_gain);
        if (usrp_) usrp_->set_rx_gain(double(gain), 0);
    }
    void set_frequency(uint32_t value) {
        frequency = value;
        if (usrp_) { usrp_->set_rx_freq(double(frequency), 0); update_gain(); }
        retune_discarded += queue.discard_ready();
    }
    void start() {
        if (streaming) return;
        chunk_samples = std::clamp<size_t>(size_t(rate * 0.016), 1024, 16384);
        const size_t capacity = std::clamp<size_t>(size_t(std::ceil(rate * 0.5 / chunk_samples)), 8, 256);
        queue.reset(capacity);
        peak_blocks.store(0, std::memory_order_relaxed);
        receiver_failed_.store(false, std::memory_order_relaxed);
        { std::lock_guard<std::mutex> lock(error_mutex_); receiver_error_.clear(); }
        if (usrp_) {
            uhd::stream_args_t args("sc16", "sc16"); args.channels = {0};
            rx_ = usrp_->get_rx_stream(args);
            rx_->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_START_CONTINUOUS);
        }
        streaming = true;
        receiving_.store(true, std::memory_order_release);
        try { worker_ = std::thread([this] { capture(); }); }
        catch (...) { halt(); throw; }
        std::printf("RX capture started: %.0f S/s, %zu samples/block, %zu blocks (%.0f ms)\n", rate, chunk_samples, capacity, 1000.0 * capacity * chunk_samples / rate);
    }
    void check_receiver() {
        if (receiver_failed_.load(std::memory_order_acquire)) {
            std::lock_guard<std::mutex> lock(error_mutex_);
            throw std::runtime_error(receiver_error_);
        }
    }
private:
    bool (*external_stop_)();
    std::atomic<bool> receiving_{false}, receiver_failed_{false};
    std::thread worker_;
    std::mutex error_mutex_;
    std::string receiver_error_;
    uhd::usrp::multi_usrp::sptr usrp_;
    uhd::rx_streamer::sptr rx_;
    std::vector<Sample> scratch_;
    double phase_ = 0;
    std::chrono::steady_clock::time_point synthetic_due_{};
    void update_gain() {
        maximum_gain = uint32_t(std::floor(std::max(0.0, usrp_->get_rx_gain_range(0).stop())));
        set_gain(gain);
    }
    size_t read_samples(Sample* destination) {
        if (synthetic) {
            constexpr double pi = 3.14159265358979323846;
            const double step_phase = 2 * pi * 35000 / rate;
            const std::complex<double> step(std::cos(step_phase), std::sin(step_phase));
            std::complex<double> oscillator(std::cos(phase_), std::sin(phase_));
            for (size_t k = 0; k < chunk_samples; ++k) {
                destination[k] = {int16_t(6500 * oscillator.real()), int16_t(6500 * oscillator.imag())};
                oscillator *= step;
            }
            phase_ = std::atan2(oscillator.imag(), oscillator.real());
            synthetic_due_ += std::chrono::nanoseconds(uint64_t(chunk_samples * 1e9 / rate));
            std::this_thread::sleep_until(synthetic_due_);
            return chunk_samples;
        }
        uhd::rx_metadata_t md;
        const size_t n = rx_->recv(destination, chunk_samples, md, 0.1, false);
        if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_OVERFLOW) usb_overflows.fetch_add(1, std::memory_order_relaxed);
        else if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_TIMEOUT) timeouts.fetch_add(1, std::memory_order_relaxed);
        else if (md.error_code != uhd::rx_metadata_t::ERROR_CODE_NONE) throw std::runtime_error(md.strerror());
        // recv may return valid partial samples together with timeout/overflow metadata.
        return n;
    }
    void capture() noexcept {
        pthread_setname_np(pthread_self(), "b210-usb-rx");
        if (geteuid() == 0 && setpriority(PRIO_PROCESS, 0, -8) != 0) std::perror("RX thread priority");
        synthetic_due_ = std::chrono::steady_clock::now();
        try {
            while (receiving_.load(std::memory_order_acquire) && !external_stop_()) {
                auto* block = queue.writable();
                const size_t n = read_samples(block ? block->data.data() : scratch_.data());
                if (!n) continue;
                received.fetch_add(n, std::memory_order_relaxed);
                if (!block) {
                    // Never wait for TCP. Drain USB even if the app's queue is full.
                    block = queue.writable();
                    if (block) std::memcpy(block->data.data(), scratch_.data(), n * sizeof(Sample));
                }
                if (block) {
                    queue.publish(n);
                    size_t peak = peak_blocks.load(std::memory_order_relaxed), depth = queue.depth();
                    while (depth > peak && !peak_blocks.compare_exchange_weak(peak, depth, std::memory_order_relaxed)) { }
                } else queue_dropped.fetch_add(n, std::memory_order_relaxed);
            }
        } catch (const std::exception& e) {
            { std::lock_guard<std::mutex> lock(error_mutex_); receiver_error_ = e.what(); }
            receiver_failed_.store(true, std::memory_order_release);
        } catch (...) {
            { std::lock_guard<std::mutex> lock(error_mutex_); receiver_error_ = "Unknown receive-thread error"; }
            receiver_failed_.store(true, std::memory_order_release);
        }
        receiving_.store(false, std::memory_order_release);
    }
};
}
