#pragma once
#include <Arduino.h>
using gpio_num_t = int;
inline int gpio_set_level(gpio_num_t pin, int value) {
  hardwareEvents.push_back("preload:" + std::to_string(pin));
  levels[pin] = value;
  return 0;
}
