#pragma once
struct Servo {
  int angle = 90;
  bool connected = false;
  void setPeriodHertz(int) {}
  void attach(int, int, int) { connected = true; }
  bool attached() { return connected; }
  void write(int value) { angle = value; }
};
