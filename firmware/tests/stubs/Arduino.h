#pragma once
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

constexpr int LOW = 0, HIGH = 1, INPUT = 1, OUTPUT = 2;
extern uint32_t fakeNow;
extern unsigned long fakeEcho;
extern int levels[40];
extern std::vector<std::string> hardwareEvents;
inline uint32_t millis() { return fakeNow; }
inline void delay(unsigned long ms) { fakeNow += ms; }
inline void delayMicroseconds(unsigned int) {}
inline void digitalWrite(int pin, int value) { levels[pin] = value; }
inline void pinMode(int pin, int) {
  hardwareEvents.push_back("mode:" + std::to_string(pin));
}
inline unsigned long pulseIn(int, int, unsigned long timeout) {
  fakeNow += (fakeEcho ? fakeEcho : timeout) / 1000;
  return fakeEcho;
}
struct FakeSerial {
  std::deque<uint8_t> input;
  std::string output;
  int txRoom = 64;
  void begin(int) { hardwareEvents.push_back("serial"); }
  int available() { return static_cast<int>(input.size()); }
  int availableForWrite() { return txRoom; }
  int read() {
    if (input.empty()) return -1;
    int c = input.front(); input.pop_front(); return c;
  }
  size_t write(const uint8_t *data, size_t length) {
    output.append(reinterpret_cast<const char *>(data), length); return length;
  }
  void receive(const std::string &line) {
    for (unsigned char c : line) input.push_back(c);
  }
};
extern FakeSerial Serial;
