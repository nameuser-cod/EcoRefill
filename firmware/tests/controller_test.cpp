// Compile the actual sketch against fake GPIO, time, ultrasonic and serial I/O.
#include <Arduino.h>
#include <cassert>
#include <iostream>
uint32_t fakeNow = 0;
unsigned long fakeEcho = 292; // approximately 5 cm
int levels[40] = {};
std::vector<std::string> hardwareEvents;
FakeSerial Serial;
#include "../ecorefill_controller/ecorefill_controller.ino"

void runFor(uint32_t duration) {
  uint32_t start = fakeNow;
  while (elapsed(fakeNow, start) < duration) loop();
}
void receive(const std::string &text) {
  Serial.receive(text);
  do { loop(); } while (!Serial.input.empty());
}
void fresh(uint32_t start = 0) {
  fakeNow = start;
  fakeEcho = 292;
  Serial = FakeSerial{};
  hardwareEvents.clear();
  state = State::RESETTING;
  activeCommand = nullptr;
  stateStarted = lastSensorAt = lastPresentAt = 0;
  waterDuration = absenceStarted = 0;
  bottleReadings = 0;
  waterNeedsRemoval = trackingAbsence = sensorMissing = false;
  commandLength = 0;
  discardingCommand = false;
  txHead = txCount = txOffset = 0;
  setup();
  assert(levels[RELAY1] == RELAY_OFF && levels[RELAY2] == RELAY_OFF);
  assert(hardwareEvents[0] == "preload:5");
  assert(hardwareEvents[1] == "preload:23");
  assert(hardwareEvents[2] == "mode:5");
  runFor(1100);
  assert(state == State::IDLE);
  Serial.output.clear();
}
void startWater(const char *command = "WATER_250\n") {
  receive(command);
  runFor(150);
  assert(state == State::DISPENSING && levels[RELAY1] == RELAY_ON);
}
bool reported(const std::string &text) {
  runFor(50);
  return Serial.output.find(text) != std::string::npos;
}

int main() {
  fresh();
  startWater();
  uint32_t lostAt = fakeNow;
  for (int i = 0; i < 10 && state == State::DISPENSING; ++i) {
    fakeEcho = i % 2 ? 0 : 1166; // Alternate no echo and 20 cm.
    runFor(100);
  }
  assert(state == State::IDLE && levels[RELAY1] == RELAY_OFF);
  assert(elapsed(fakeNow, lostAt) <= 700);

  fresh(); startWater();
  fakeEcho = 0;
  runFor(650);
  assert(levels[RELAY1] == RELAY_OFF);
  assert(reported("ERROR WATER_250 SENSOR_LOST\n"));

  fresh(); startWater();
  fakeEcho = 1166;
  runFor(650);
  assert(reported("ERROR WATER_250 CONTAINER_REMOVED\n"));

  fresh(); startWater();
  fakeEcho = 0; runFor(200); fakeEcho = 292; runFor(500);
  assert(state == State::DISPENSING); // Brief noise recovers within grace time.
  receive("RESET\n");
  assert(levels[RELAY1] == RELAY_OFF && levels[RELAY2] == RELAY_OFF);
  assert(state == State::RESETTING);
  assert(reported("ERROR WATER_250 CANCELLED\n"));
  runFor(1100);
  assert(reported("OK RESET\n"));
  receive("WATER_250\n");
  assert(reported("ERROR WATER_250 REMOVE_CONTAINER\n"));

  fresh();
  receive("WATER_500\n"); // One good sample.
  assert(state == State::WAIT_BOTTLE);
  fakeEcho = 0; runFor(250);
  fakeEcho = 292; runFor(75); // One new good sample must not start the pump.
  assert(state == State::WAIT_BOTTLE && levels[RELAY1] == RELAY_OFF);
  runFor(150);
  assert(state == State::DISPENSING);

  fresh(); fakeEcho = 0;
  receive("WATER_250\n");
  receive("RESET\n");
  assert(state == State::RESETTING && levels[RELAY1] == RELAY_OFF);
  assert(reported("ERROR WATER_250 CANCELLED\n"));

  fresh(); fakeEcho = 0;
  receive("WATER_250\n"); runFor(30100);
  assert(state == State::IDLE && levels[RELAY1] == RELAY_OFF);
  assert(reported("ERROR WATER_250 NO_BOTTLE\n"));

  fresh(); startWater();
  uint32_t originalStart = stateStarted;
  receive("WATER_250\nWATER_500\nBOTTLE\n");
  assert(stateStarted == originalStart);
  assert(reported("ERROR WATER_500 BUSY\n"));
  assert(reported("ERROR BOTTLE BUSY\n"));
  runFor(WATER_250_TIME);
  assert(state == State::IDLE && levels[RELAY1] == RELAY_OFF);
  assert(reported("OK WATER_250\n"));
  receive("WATER_250\n");
  assert(state == State::IDLE);
  assert(reported("ERROR WATER_250 REMOVE_CONTAINER\n"));
  fakeEcho = 0; runFor(1200); // Empty backdrop re-arms only while pump is off.
  assert(!waterNeedsRemoval);
  fakeEcho = 292; startWater("WATER_500\n");

  fresh();
  receive(std::string(80, 'X') + "WATER_250\n");
  assert(state == State::IDLE);
  assert(reported("ERROR SERIAL LINE_TOO_LONG\n"));
  receive("WATER_"); runFor(1100); receive("250\n");
  assert(state == State::IDLE);
  assert(reported("ERROR SERIAL LINE_TIMEOUT\n"));
  receive(std::string("WATER_250\0junk\n", 15));
  assert(state == State::IDLE);
  receive("  water_250\r\n"); runFor(150);
  assert(state == State::DISPENSING);

  fresh(); startWater();
  Serial.txRoom = 0; // Unread/full serial output must not stall the pump cutoff.
  fakeEcho = 0;
  Serial.receive(std::string(30000, 'X'));
  runFor(650);
  assert(levels[RELAY1] == RELAY_OFF);
  assert(commandLength < sizeof(commandBuffer) && txCount <= TX_SLOTS);

  fresh(); startWater(); Serial.txRoom = 0;
  for (int i = 0; i < 100; ++i) receive("CAN\n");
  assert(txCount <= TX_SLOTS - 4);
  receive("RESET\n");
  assert(levels[RELAY1] == RELAY_OFF);
  Serial.txRoom = 1; // Resume even with partial-line transmission.
  runFor(2000);
  assert(Serial.output.find("ERROR WATER_250 CANCELLED\n") != std::string::npos);
  assert(Serial.output.find("OK RESET\n") != std::string::npos);

  fresh(); fakeNow = UINT32_MAX - 500;
  receive("WATER_"); runFor(COMMAND_TIMEOUT + 50); receive("250\n");
  assert(state == State::IDLE && levels[RELAY1] == RELAY_OFF);
  assert(reported("ERROR SERIAL LINE_TIMEOUT\n"));

  fresh();
  receive("BOTTLE\n");
  assert(sortServo.angle == SORT_BOTTLE && gateServo.angle == GATE_CENTER);
  runFor(MOVE_DELAY);
  assert(gateServo.angle == GATE_ACCEPT);
  runFor(DROP_DELAY);
  assert(gateServo.angle == GATE_CENTER);
  runFor(MOVE_DELAY);
  assert(sortServo.angle == SORT_CENTER && state != State::IDLE);
  runFor(MOVE_DELAY + 50);
  assert(state == State::IDLE && reported("OK BOTTLE\n"));
  receive("CAN\n"); assert(sortServo.angle == SORT_CAN);
  receive("RESET\n");
  assert(gateServo.angle == GATE_CENTER && sortServo.angle == SORT_CENTER);
  assert(state == State::RESETTING);

  fresh(); receive("REJECT\n");
  assert(gateServo.angle == GATE_REJECT);
  runFor(DROP_DELAY + 2 * MOVE_DELAY + 100);
  assert(state == State::IDLE && reported("OK REJECT\n"));

  fresh(); fakeNow = UINT32_MAX - 500; startWater();
  runFor(WATER_250_TIME + 100);
  assert(fakeNow < WATER_250_TIME + 1000);
  assert(state == State::IDLE && levels[RELAY1] == RELAY_OFF);
  assert(reported("OK WATER_250\n"));

  fresh(); fakeNow = UINT32_MAX - 500; fakeEcho = 0;
  receive("WATER_1000\n"); runFor(BOTTLE_WAIT_TIMEOUT + 100);
  assert(reported("ERROR WATER_1000 NO_BOTTLE\n"));

  fresh(); fakeNow = UINT32_MAX - 500; startWater();
  fakeEcho = 0; runFor(650);
  assert(levels[RELAY1] == RELAY_OFF && reported("ERROR WATER_250 SENSOR_LOST\n"));
  std::cout << "All controller regression scenarios passed.\n";
}
